# Incident Response Playbook — Omnichannel Bridge

Quick reference for common production incidents and remediation steps.

---

## Incident 1: Webhook Not Processing (Messages Not Appearing)

**Symptoms:**
- Customer sends message → no Discuss thread appears
- Log shows: `integration.omni.webhook_ingest: "ok": False`

**Root Causes (in order of likelihood):**
1. Webhook signature validation failure (secret mismatch)
2. Rate limiting active (too many requests/min)
3. Webhook event dedup blocking valid message (corrupt constraint)
4. Network/firewall blocking provider callback

**Diagnosis:**

```bash
# Check webhook controller logs
docker exec campscout_web grep -i "bad_signature\|rate_limit\|payload_too_large" logs/odoo.log | tail -20

# Check webhook events table
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT provider, external_event_id, state, error FROM omni.webhook_event ORDER BY created_at DESC LIMIT 10;"

# Check integration settings
echo "SELECT provider, verify_token FROM omni_integration WHERE provider IN ('meta','telegram','viber','whatsapp');" | \
  docker exec -i campscout_db psql -U odoo -d campscout_prod
```

**Remediation:**

**Case 1a: Signature mismatch (Meta)**
```bash
# Update Meta webhook secret in Odoo Settings
# Odoo: Settings > Omnichannel > Meta > Verify Token

# OR via Python shell:
docker exec campscout_web odoo shell -d campscout_prod
>>> env['res.config.settings'].set_param('omnichannel_bridge.meta_app_secret', 'correct_secret')
>>> exit()

# Test webhook:
curl -X POST http://localhost:8069/omni/webhook/meta \
  -H "X-Hub-Signature-256: sha256=$(echo -n '{"test":1}' | openssl dgst -sha256 -hmac 'correct_secret' | cut -d' ' -f2)" \
  -H "Content-Type: application/json" \
  -d '{"test":1}'
```

**Case 1b: Rate limiting**
```bash
# Check rate limit config
docker exec campscout_web odoo shell -d campscout_prod
>>> settings = env['res.config.settings'].get_param('omnichannel_bridge.webhook_rate_limit_per_minute', '120')
>>> print(f"Rate limit: {settings} msg/min")
>>> exit()

# Increase limit temporarily (if legitimate spike)
docker exec campscout_web odoo shell -d campscout_prod
>>> env['res.config.settings'].set_param('omnichannel_bridge.webhook_rate_limit_per_minute', '300')
>>> exit()

# Check metrics from last hour
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT DATE_TRUNC('minute', created_at), COUNT(*) \
   FROM omni_webhook_event \
   WHERE created_at > NOW() - INTERVAL '1 hour' \
   GROUP BY DATE_TRUNC('minute', created_at) \
   ORDER BY DATE_TRUNC('minute', created_at) DESC;"
```

**Case 1c: Idempotency constraint corruption**
```bash
# Check for orphaned webhook events
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT provider, COUNT(*) AS count FROM omni_webhook_event WHERE external_event_id IS NULL GROUP BY provider;"

# If many records with NULL external_event_id:
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "DELETE FROM omni_webhook_event WHERE external_event_id IS NULL AND state = 'processed';"

# Restart webhook ingest
docker compose restart web
```

**Case 1d: Provider callback blocked**
- Verify firewall allows webhooks from provider IPs
- Check IP whitelist (if configured in provider console)
- Test egress from provider: `curl -v https://your-webhook-domain/omni/webhook/meta`

---

## Incident 2: Bot Not Replying (AI Job Stuck)

**Symptoms:**
- Message appears in Discuss
- Status stuck on "awaiting_bot_reply" for >30 seconds
- No AI reply sent to customer

**Root Causes:**
1. Ollama/LLM backend unavailable or overloaded
2. AI job processing queue stalled (worker not running)
3. LLM request timeout (>30s)
4. Fallback message disabled

**Diagnosis:**

```bash
# Check AI job status
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT channel_id, state, attempt_count, next_attempt_at, error \
   FROM omni_ai_job WHERE state IN ('queued', 'running', 'failed') \
   ORDER BY created_at DESC LIMIT 10;"

# Check Ollama availability
curl -s http://localhost:11434/api/version || echo "Ollama unreachable"

# Check LLM timeouts in log
docker exec campscout_web tail -100 logs/odoo.log | grep -i "timeout\|connection_refused\|unavailable"

# Check fallback message config
docker exec campscout_web odoo shell -d campscout_prod
>>> msg = env['res.config.settings'].get_param('omnichannel_bridge.fallback_message')
>>> print(f"Fallback enabled: {bool(msg)}")
>>> exit()
```

**Remediation:**

**Case 2a: Ollama unavailable**
```bash
# Check if Docker service is running
docker ps | grep ollama || docker run -d ollama/ollama:latest

# Or enable fallback-only mode:
docker exec campscout_web odoo shell -d campscout_prod
>>> env['res.config.settings'].set_param('omnichannel_bridge.llm_enabled', False)
>>> print("Bot now in fallback-only mode (no AI replies)")
>>> exit()

# Customers will receive configured fallback message
```

**Case 2b: Queue stalled**
```bash
# Restart AI job worker
docker exec campscout_web python3 -c \
  "from odoo import api, SUPERUSER_ID; \
   env = api.Environment(pool.db, SUPERUSER_ID, {}); \
   print('Queue reprocessing...'); \
   env['omni.ai.job'].action_process_queued_jobs()"

# Or restart Odoo worker
docker compose restart web
```

**Case 2c: LLM timeout**
```bash
# Increase timeout threshold
docker exec campscout_web odoo shell -d campscout_prod
>>> env['res.config.settings'].set_param('omnichannel_bridge.llm_request_timeout', 60)  # 60 sec
>>> exit()

# Check resource usage on AI host
# (Ollama may need GPU/memory upgrade)
```

---

## Incident 3: Duplicate Messages to Customer (Race Condition)

**Symptoms:**
- Customer receives message twice from bot
- Two copies in customer's chat window
- Both sent within seconds of each other

**Root Causes:**
1. Bot paused guard not active (`omni_bot_paused` field missing)
2. Manager reply detected too late (race between bot/human)
3. Webhook replayed after bot already replied (dedup failure)

**Diagnosis:**

```bash
# Check bot paused state for channel
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT id, omni_bot_paused, omni_last_human_reply_at \
   FROM discuss_channel WHERE omni_channel_id = '<channel_id>' LIMIT 1;"

# Check outbound delivery log
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT channel_id, created_at, state FROM omni_outbound_log \
   WHERE channel_id = '<channel_id>' \
   ORDER BY created_at DESC LIMIT 10;"

# Check AI job history
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT channel_id, state, created_at FROM omni_ai_job \
   WHERE channel_id = '<channel_id>' \
   ORDER BY created_at DESC LIMIT 10;"
```

**Remediation:**

**Case 3a: Bot paused guard missing**
- This is a code issue; should not happen if contract tests pass
- Verify field exists: `ALTER TABLE discuss_channel ADD COLUMN IF NOT EXISTS omni_bot_paused BOOLEAN DEFAULT FALSE;`

**Case 3b: Manager race condition**
```bash
# Manually pause bot for affected channel
docker exec campscout_web odoo shell -d campscout_prod
>>> ch = env['discuss.channel'].browse(<channel_id>)
>>> ch.omni_bot_paused = True
>>> env.cr.commit()
>>> print("Bot paused for channel")
>>> exit()

# Operator sends "bot paused" message to customer
# Once resolved, unpause:
>>> ch.omni_bot_paused = False
```

**Case 3c: Webhook replay (old outgoing)**
```bash
# Check webhook event idempotency
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT COUNT(*) as duplicates FROM omni_webhook_event \
   WHERE provider = 'meta' AND external_event_id = '<msg_id>' AND state = 'processed';"

# If multiple rows: unique constraint is broken
# Investigate DB logs for INSERT conflicts
```

---

## Incident 4: Chat Integrity Lost (Partner/Messages Mismapped)

**Symptoms:**
- Messages appear under wrong customer
- Partner identity links shuffled
- Customer history incomplete

**Root Causes:**
1. Partner deduplication incorrectly merged accounts
2. Webhook identity extraction broken (phone/email parse failed)
3. Direct DB corruption (rare)

**Diagnosis:**

```bash
# Find affected messages
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT dc.id, dc.omni_customer_partner_id, COUNT(cm.id) as msg_count \
   FROM discuss_channel dc \
   LEFT JOIN mail_message cm ON dc.id = cm.res_id \
   WHERE dc.omni_customer_partner_id IS NOT NULL \
   AND dc.created_at > NOW() - INTERVAL '1 hour' \
   GROUP BY dc.id, dc.omni_customer_partner_id \
   HAVING COUNT(cm.id) = 0;"

# Check partner identity linking
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "SELECT p.id, p.email, p.phone, p.omni_identity_source \
   FROM res_partner p \
   WHERE p.omni_external_id = '<external_id>';"
```

**Remediation:**

**Case 4a: Wrong partner merged**
```bash
# Restore from backup if critical
# OR manual correction:
docker exec campscout_web odoo shell -d campscout_prod
>>> ch = env['discuss.channel'].browse(<channel_id>)
>>> correct_partner = env['res.partner'].search([('email', '=', 'correct@example.com')])[0]
>>> ch.omni_customer_partner_id = correct_partner.id
>>> env.cr.commit()
>>> print("Partner corrected for channel")
>>> exit()

# Investigate dedup rule that caused wrong merge
# (See OPERATIONS_RUNBOOK.md for dedup policy)
```

**Case 4b: Identity extraction broken**
```bash
# Check phone parser
docker exec campscout_web odoo shell -d campscout_prod
>>> from odoo.addons.omnichannel_bridge.models.res_partner import _normalize_phone
>>> test_num = "+380671234567"
>>> result = _normalize_phone(test_num)
>>> print(f"Parsed: {result}")
>>> exit()

# If parser wrong: fix in model code, redeploy
```

---

## Incident 5: PII Exposure in Logs (Security)

**Symptoms:**
- Audit finds email/phone number in error logs
- Customer complains of data leak
- GDPR/RODO concern raised

**Root Causes:**
1. PII masking not enabled (feature not deployed)
2. Error message contains unmasked sensitive data
3. Debug mode left ON in production

**Diagnosis:**

```bash
# Scan logs for PII patterns
docker exec campscout_web grep -E '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' logs/odoo.log | head

# Check masking enabled
docker exec campscout_web odoo shell -d campscout_prod
>>> settings = env['res.config.settings']
>>> pii_enabled = settings.get_param('omnichannel_bridge.pii_mask_enabled', False)
>>> debug = settings.get_param('omnichannel_bridge.llm_debug_data_sources', False)
>>> print(f"PII masking: {pii_enabled}, Debug mode: {debug}")
>>> exit()
```

**Remediation:**

**Case 5a: PII masking not enabled**
```bash
docker exec campscout_web odoo shell -d campscout_prod
>>> env['res.config.settings'].set_param('omnichannel_bridge.pii_mask_enabled', True)
>>> env.cr.commit()
>>> print("PII masking enabled")
>>> exit()

# Restart Odoo to apply
docker compose restart web

# Clean existing logs containing PII
docker exec campscout_web bash -c \
  "tail -n 10000 logs/odoo.log | grep -v '@' > logs/odoo.log.cleaned && \
   mv logs/odoo.log.cleaned logs/odoo.log"
```

**Case 5b: Debug mode ON**
```bash
docker exec campscout_web odoo shell -d campscout_prod
>>> env['res.config.settings'].set_param('omnichannel_bridge.llm_debug_data_sources', False)
>>> env.cr.commit()
>>> print("Debug mode disabled")
>>> exit()
```

---

## General Recovery Procedures

### Restore from Snapshot
```bash
# Full DB restore from backup
docker compose stop web
docker volume rm campscout_prod_pg_data
docker compose up -d db
cat backup_2026-04-09.sql | docker compose exec -T db psql -U odoo -d campscout_prod
docker compose up -d web
```

### Reset Specific Channel
```bash
# Clear message history for debugging (irreversible)
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "DELETE FROM mail_message WHERE res_id = <channel_id>;"

# Or mark all as read
docker exec campscout_db psql -U odoo -d campscout_prod -c \
  "UPDATE mail_notification SET is_read = TRUE WHERE channel_id = <channel_id>;"
```

### Escalate to Engineering
**When to escalate (do NOT delay):**
- Recurring crash on webhook ingest (>3 fails in 5 min)
- Data corruption across multiple threads
- Signature validation bypass
- Memory leak / service degradation

**Escalation contact:** [Dev on-call] / Slack: #omnichannel-incidents

---

## Prevention Checklist

- [ ] Staging validation completed before every production deploy
- [ ] Load drill executed on prod-copy (results documented)
- [ ] Backup taken and tested (restore walkthrough)
- [ ] Monitoring/alerts configured (Sentry / CloudWatch)
- [ ] On-call rotation scheduled
- [ ] War room / incident bridge ready

---

## References

- [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)
- [DAY_0_GO_LIVE_CHECKLIST.md](DAY_0_GO_LIVE_CHECKLIST.md)
- [STAGING_BLUEPRINT.md](STAGING_BLUEPRINT.md)
- Emergency contacts file (internal docs)
