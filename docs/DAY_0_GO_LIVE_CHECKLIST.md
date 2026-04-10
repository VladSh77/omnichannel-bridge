# Day-0 Go-Live Checklist

**Release:** omnichannel_bridge v17.0.1.0.37
**Date:** 2026-04-XX
**Prepared by:** [Team]
**Approved by:** [Product Owner]

---

## Pre-Deployment (T-24h)

### Code Review & Testing

- [ ] All contract tests pass locally (`pytest tests/ -v`)
- [ ] No new linter errors in modified files (`ruff check addons/omnichannel_bridge`)
- [ ] Load drill executed on prod-copy database; metrics documented
- [ ] Backup/restore drill executed; RTO/RPO recorded
- [ ] PII masking verified in logs; no sensitive values exposed
- [ ] Translation completeness verified (UA/PL)

### Staging Validation

- [ ] Staging environment running on parity Odoo version (17.0)
- [ ] All custom modules load cleanly (no DB errors)
- [ ] Meta test app webhook delivers messages to Discuss
- [ ] Telegram test bot webhook delivers messages to Discuss
- [ ] Website livechat integration active and working
- [ ] AI reply path works; fallback message appears on AI outage
- [ ] No bot/human double-reply in 10-thread test run
- [ ] Rate limiting active; no duplicate messages from replayed webhooks
- [ ] Right-to-erasure action accessible on partner card
- [ ] Retention cron jobs scheduled

### Data Integrity

- [ ] Production DB backup taken and verified (restore tested)
- [ ] Filestore backup taken and verified
- [ ] Chat history integrity validated (count messages)
- [ ] Partner deduplication run; no critical conflicts
- [ ] Webhook event idempotency records cleaned (no stale orphans)

---

## Deployment (T-0)

### Pre-Flight

- [ ] Maintenance window scheduled (announce 1h before)
- [ ] Incident commander assigned
- [ ] Rollback procedure reviewed with ops team
- [ ] Stakeholder comms approved (close-message, ETA)

### Module Update

```bash
# SSH to production Odoo container
docker exec campscout_web bash

# Backup existing module
cp -r addons/omnichannel_bridge addons/omnichannel_bridge.backup_$(date +%s)

# Pull new code
git pull origin main

# Update module in Odoo
python3 -m odoo.cli shell -c /etc/odoo/odoo.conf \
  -d campscout_prod \
  -u omnichannel_bridge --stop-after-init

# Run contract tests on prod environment (read-only verification)
pytest tests/test_contract_regressions.py -v --tb=short
```

- [ ] Module update completed without errors
- [ ] No new "ERROR" or "CRITICAL" logs in past 2 minutes
- [ ] Odoo web service still responsive (`curl http://localhost:8069/web/health`)

### Post-Deployment Validation

- [ ] Version check: `SELECT name FROM ir_module_module WHERE name='omnichannel_bridge'`
- [ ] Settings available: Omnichannel > Settings page loads
- [ ] Integrations active: Meta/Telegram/Viber/WhatsApp row for company
- [ ] AI job queue responsive: Create test job via Python shell
- [ ] Discuss conversations visible: Filter by provider
- [ ] Manager dashboard loads: Omnichannel > Conversations
- [ ] PII masking active: Check logs for masked email/phone

---

## Post-Deployment (T+1h)

### Smoke Tests

Execute critical user journeys:

1. **Inbound Message (Meta)**
   - [ ] Send test message via Meta test user
   - [ ] Message appears in Discuss within 5 seconds
   - [ ] Partner correctly identified/created
   - [ ] Thread status = "awaiting_bot_reply"

2. **Bot Reply (AI)**
   - [ ] Bot reply sent within 10 seconds
   - [ ] Outbound delivered to Meta user
   - [ ] Bot marked last reply timestamp
   - [ ] No second bot reply sent (race guard active)

3. **Manager Handoff**
   - [ ] Manager joins conversation
   - [ ] Bot paused (`omni_bot_paused=True`)
   - [ ] No bot reply while manager active
   - [ ] Manager reply goes to customer

4. **Telegram Webhook**
   - [ ] Send test Telegram message
   - [ ] Message appears in Discuss
   - [ ] Bot considers language (UA/PL preference)
   - [ ] Outbound reaches Telegram user

### Error Monitoring

- [ ] Check error logs for past 1 hour
- [ ] Alert queue empty (no system alerts)
- [ ] Webhook event processing rate > 0 (if traffic available)
- [ ] No P1/P2 operational issues

### Performance Baseline

- [ ] Record P95 response times (target: <5s enqueue, <8s outbound)
- [ ] Record active thread count
- [ ] Record message throughput (msg/min)
- [ ] Record error rate (target: <2%)

---

## Rollback Decision Point (T+2h)

**Criteria for Rollback:**

❌ STOP if ANY of:
- P1 issue blocking chat ingest or outbound
- Data corruption detected (partner/message loss)
- Webhook signature validation broken
- PII masking not active (sensitive data in logs)
- >5% error rate sustained for >15 min
- AI backend unavailable AND fallback message not working

**Rollback Procedure:**

```bash
# Restore previous module
docker exec campscout_web bash
cp -r addons/omnichannel_bridge.backup_<timestamp> addons/omnichannel_bridge

# Downgrade module in Odoo
python3 -m odoo.cli shell -c /etc/odoo/odoo.conf \
  -d campscout_prod \
  --downgrade=omnichannel_bridge --stop-after-init

# Verify old version active
curl http://localhost:8069/web/health

# Announce rollback to stakeholders
```

---

## Post-Rollback Actions (if needed)

- [ ] Root cause analysis initiated
- [ ] Issue recorded in incident log
- [ ] Timeline documented for post-mortem
- [ ] Blocked issues escalated to dev team

---

## Sign-Off

**Deployment completed:** _______  (time)

**Validated by (Ops):** _________________ / Date: _______

**Approved by (Product):** _________________ / Date: _______

---

## Appendix: Contact Matrix

| Role | Name | Phone | Discord |
|------|------|-------|---------|
| Incident Commander | | | |
| Odoo Admin | | | |
| Product Owner | | | |
| Database Admin | | | |
| Network/Infra | | | |

---

## References

- [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) — Operational procedures
- [MIGRATION_GO_LIVE_PLAYBOOK.md](MIGRATION_GO_LIVE_PLAYBOOK.md) — Channel migration strategy
- [TEST_PLAN.md](TEST_PLAN.md) — Test outcomes from staging
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — Common issues and fixes
