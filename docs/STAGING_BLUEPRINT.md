# Staging Blueprint — `omnichannel_bridge`

## Goal

Create a staging environment with production-like behavior for safe validation of omnichannel and AI flows before production rollout.

## Mandatory Parity Requirements

- Same Odoo major version as production.
- Same custom modules set in `addons_path`.
- Same module load order and dependency graph.
- Same webhook controller routes.
- Same data model shape for camp/event/order/partner relations.

## Isolation Requirements

- Separate database: `campscout_staging`.
- Separate Odoo container/service (for example `campscout_web_staging`).
- Separate domain/subdomain (for example `staging.campscout.eu`).
- Separate provider credentials (test app/test bot only).
- Separate integration records in Odoo (`omni.integration`) from production.

## AI Backend Strategy

- Preferred: use the existing AI hub endpoint with staging-only settings.
- Required:
  - separate model config profile for staging,
  - clear request tagging in logs (`env=staging`),
  - strict fallback enabled.
- Optional DR: local Ollama fallback endpoint near staging Odoo.

## Network and Security

- No direct public exposure of internal Odoo or DB ports.
- HTTPS required for webhook callbacks.
- Staging secrets are unique and never reused from production.
- Access to staging admin endpoints is restricted to approved users.

## Data Policy

- Preferred: sanitized production clone.
- If clone is used:
  - mask personal data fields,
  - remove sensitive child health details unless required for test case,
  - preserve relational consistency for integration tests.

## Webhook Test Topology

- Meta:
  - connect only a test page/app to staging webhook URL.
  - validate signature verification with test secret.
- Telegram:
  - connect only dedicated staging bot token.
  - set staging webhook secret token.

## Validation Checklist (Go/No-Go)

### A. Baseline

- Odoo starts with all required custom modules.
- `omnichannel_bridge` installs/updates cleanly.
- Staging settings do not reference production credentials.

### B. Functional

- Inbound Meta test message creates/updates Discuss thread.
- Inbound Telegram test message creates/updates Discuss thread.
- AI reply path works in enabled mode.
- Fallback reply appears when AI backend is intentionally unavailable.

### C. Safety

- No bot/human double-reply in tested scenarios.
- No sensitive values leaked to logs.
- Legal links in responses point to canonical pages only.

### D. Exit

- Test results written to `docs/TEST_PLAN.md` outcomes section.
- Deployment approval gate signed off before production actions.

## Rollout Rule

No production deploy is allowed until staging checklist passes and is recorded in implementation log.

## Production Parity Snapshot (2026-04-08)

Observed on production host `91.98.122.195`:

- Custom addons root:
  - `/opt/campscout/custom-addons/campscout_management`
  - `/opt/campscout/custom-addons/odoo_chatwoot_connector`
  - `/opt/campscout/custom-addons/omnichannel_bridge`
  - `/opt/campscout/custom-addons/zadarma_odoo`
- Additional addon path used by business logic:
  - `/opt/campscout/addons/bs_campscout_addon`

Staging parity target is this exact addon set and compatible module versions.
