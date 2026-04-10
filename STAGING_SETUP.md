# Staging Setup for Omnichannel Bridge

Comprehensive staging environment for validating omnichannel ingest + AI flows before production.

## Quick Start

### Prerequisites
- Docker & Docker Compose 3.8+
- 4GB RAM minimum (6GB recommended for local Ollama)
- `.env` file with staging credentials (see `.env.example`)

### 1. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit with staging credentials
export DB_PASSWORD=staging_db_pass_123
export METAL_APP_ID=your_test_app_id
export META_APP_SECRET=your_test_secret
export TELEGRAM_BOT_TOKEN=your_test_bot_token
export WEBHOOK_DOMAIN=staging.campscout.eu
```

### 2. Start Services

```bash
# Bring up core services (Odoo + DB + Redis)
docker compose -f docker-compose.staging.yml up -d

# Monitor Odoo startup (wait for "ready to serve" log)
docker compose -f docker-compose.staging.yml logs -f web

# (Optional) Start local Ollama for AI fallback
docker compose -f docker-compose.staging.yml --profile local-ai up -d ollama
```

### 3. Initialize Staging Database

```bash
# Bootstrap staging data (providers, integrations, test data)
docker compose -f docker-compose.staging.yml --profile init up init

# Connect to Odoo
# URL: http://localhost:8069
# Login: admin / admin
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Reverse Proxy / CDN                   │
│              (staging.campscout.eu + mngmt)            │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌─────▼──────┐  ┌────▼────┐
    │  Odoo   │    │    Redis   │  │ Ollama  │
    │   Web   │    │  (session) │  │  (AI)   │
    └────┬────┘    └────────────┘  └─────────┘
         │
    ┌────▼────┐
    │ Postgres │
    │ (staging)│
    └──────────┘
```

## Webhook Testing

### Meta (Messenger) Test

```bash
# 1. Register test app in Meta developer dashboard
# 2. Update .env with test APP_ID + SECRET
# 3. Set webhook URL to: https://staging.campscout.eu/omni/webhook/meta

# 4. Send test message via Messenger test user
curl -X POST http://localhost:8069/omni/webhook/meta \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=abc123..." \
  -d @webhook_test_meta.json
```

### Telegram Test

```bash
# 1. Create Telegram test bot via @TelegramBotFather
# 2. Update .env with TELEGRAM_BOT_TOKEN
# 3. Set webhook: https://staging.campscout.eu/omni/webhook/telegram/<token>

# 4. Send test message
curl -X POST http://localhost:8069/omni/webhook/telegram \
  -H "Content-Type: application/json" \
  -d @webhook_test_telegram.json
```

## Validation Checklist

- [ ] Odoo starts cleanly with all required modules
- [ ] `omnichannel_bridge` installed and no DB errors
- [ ] Meta webhook creates/updates Discuss thread
- [ ] Telegram webhook creates/updates Discuss thread
- [ ] AI reply path works (with Ollama or fallback message)
- [ ] No bot/human double-reply in tested scenarios
- [ ] PII masking enabled; sensitive values not in logs
- [ ] Legal links in responses point to canonical pages
- [ ] Rate limiting active; webhook idempotency works

## Common Issues

### Odoo won't start
```bash
# Check logs
docker compose -f docker-compose.staging.yml logs web

# Restart
docker compose -f docker-compose.staging.yml down
docker compose -f docker-compose.staging.yml up -d web
```

### Webhook secret mismatch
```bash
# Verify webhook signature validation in logs
docker compose -f docker-compose.staging.yml logs web | grep "bad_signature"

# Re-generate signature in test webhook
# (See docs/MESSENGER_WEBHOOK_IDENTITY_SCHEMA.md)
```

### AI backend unavailable
```bash
# If Ollama isn't running, system falls back to configured message
# Check fallback is active in Odoo Settings > Omnichannel

# Start Ollama
docker compose -f docker-compose.staging.yml --profile local-ai up ollama
```

## Database Backup

```bash
# Export staging DB
docker compose -f docker-compose.staging.yml exec db \
  pg_dump -U odoo campscout_staging > staging_backup.sql

# Restore
cat staging_backup.sql | docker compose -f docker-compose.staging.yml \
  exec -T db psql -U odoo -d campscout_staging
```

## Security Notes

- Staging database, Odoo master password, and tokens are **test-only**. Not production-grade.
- Webhook URLs must be HTTPS in production (use reverse proxy / Let's Encrypt in staging).
- Store `.env` in `.gitignore`; never commit secrets.
- Isolate staging network from production via security groups / firewall rules.

## Teardown

```bash
# Stop all services
docker compose -f docker-compose.staging.yml down

# Clean volumes (irreversible)
docker compose -f docker-compose.staging.yml down -v
```

## References

- [STAGING_BLUEPRINT.md](../docs/STAGING_BLUEPRINT.md) - Architecture expectations
- [TEST_PLAN.md](../docs/TEST_PLAN.md) - Mandatory test scenarios
- [OPERATIONS_RUNBOOK.md](../docs/OPERATIONS_RUNBOOK.md) - Day-0 operational procedures
- [Dockerfile.staging](./Dockerfile.staging) - Container image build
