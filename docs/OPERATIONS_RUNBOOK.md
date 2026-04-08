# Operations Runbook — `omnichannel_bridge`

## Deployment Guardrail

- No direct server edits from uncommitted local code.
- Required sequence:
  1. Local verification.
  2. Commit and push.
  3. Server update only after explicit approval.

## Incident Classes

- P1: Webhooks fully down, no inbound processing.
- P2: Inbound works, AI replies fail.
- P3: Partial degradation (single provider, intermittent errors).

## Fast Triage Checklist

1. Confirm provider webhook traffic is arriving.
2. Check Odoo logs for parser/signature errors.
3. Confirm AI backend reachability from Odoo host.
4. Validate fallback reply behavior.
5. Verify no bot/human double-reply happened in active threads.

## Bot schedule and webhooks (settings)

- `omnichannel_bridge.bot_inside_hours_if_manager_quiet`: during manager hours, AI jobs for Meta/Telegram wait `sla_no_human_seconds` before running (manager-first).
- `omnichannel_bridge.night_bot_enabled` + `night_bot_start` / `night_bot_end`: optional local window where bot may always reply (company timezone).
- `omnichannel_bridge.webhook_max_body_bytes`: reject oversized POST to `/omni/webhook/*` (default 1 MiB).
- Outbound Meta/Telegram: transient HTTP failures retry with exponential backoff in code.

## Known High-Risk Areas

- Duplicate webhook delivery without idempotency guard.
- Long synchronous AI calls causing timeout/retry storms.
- Misconfigured provider tokens/secrets.
- AI backend unavailable or overloaded.

## Rollback Policy

- Rollback unit: git commit.
- Rollback flow:
  1. Revert offending commit locally.
  2. Push revert commit.
  3. Apply on server after approval.
- Never hotfix directly on server filesystem.

## Direct vs Bridge Decision Rule

- Default operation mode: direct provider integration through `omnichannel_bridge`.
- Backup mode: SendPulse bridge is allowed only as temporary continuity path.
- Switch to backup mode only after explicit approval and failed direct-wave exit criteria.
- While backup mode is active, keep data mapping compatibility for partner identity fields and channel metadata.
- Return to direct mode immediately after fix + smoke validation.

## Operational Readiness Targets

- Staging smoke test required before production rollout.
- Fallback message always enabled for AI outage scenarios.
- Admin kill switch path documented and tested.
- Baseline load criteria documented in `docs/LOAD_CRITERIA.md`.
- Pre-go-live manual scenarios on production DB copy documented in `docs/PROD_COPY_MANUAL_SCENARIOS.md`.
- Staging Meta test checklist documented in `docs/STAGING_META_TEST_PAGE.md`.
- Backup/restore drill procedure documented in `docs/BACKUP_RESTORE_DRILL.md`.
- Secret encryption baseline policy documented in `docs/SECRET_ENCRYPTION_POLICY.md`.

## Platform Window Policy

- Meta (Messenger/Instagram Direct) and WhatsApp Business typically operate with an about-24h customer-initiated window for free-form proactive messaging.
- This must be treated as an operational constraint and re-validated against current provider docs before campaign launches.
- Telegram channel/bot flow is not bound by the same 24h rule, but anti-spam and explicit consent rules still apply.

## Expanded Failure SOP

### Ollama unavailable / overloaded

1. Verify `omnichannel_bridge.ollama_base_url` reachability from Odoo host.
2. If repeated failures: set `omnichannel_bridge.llm_enabled=False` (human-only mode).
3. Confirm fallback message is delivered and internal escalation notifications are active.
4. Record incident with model/version and host resource pressure details.

### Resource pressure (RAM/GPU/CPU)

1. Reduce concurrency sources (pause campaigns / temporary queue reduction).
2. Switch to lighter model if pre-approved by product owner.
3. Keep strict grounding on; do not disable compliance blocks to gain speed.

### Provider rate limit / API throttling

1. Check outbound retries and error patterns by provider.
2. Slow non-critical broadcasts first; keep handoff/escalation traffic prioritized.
3. Re-check tokens/secrets and webhook validity after transient provider incidents.

### Expired or revoked tokens

1. Rotate token in settings/integration config.
2. Re-run minimal webhook verification test and outbound smoke test.
3. Update token rotation log (owner, date, expiry) in operations notes.

## Token Rotation Policy

- Owner field: `omnichannel_bridge.token_rotation_owner`.
- Next planned rotation date: `omnichannel_bridge.token_rotation_next_date`.
- Minimum cadence recommendation: every 90 days or earlier on suspected compromise.
- Rotation checklist:
  1. update token/secret,
  2. verify inbound webhook challenge/signature,
  3. verify outbound send test,
  4. record actor/date/next date.

## Release Fingerprint Policy

- Keep release identifiers in settings before each production deploy:
  - `omnichannel_bridge.release_odoo_version`
  - `omnichannel_bridge.release_custom_hash`
  - `omnichannel_bridge.release_ollama_model_version`
- These values must be copied to release notes for reproducible rollback and incident analysis.

## Post-Incident Record

Each incident must include:
- Timestamp and environment.
- Impact and blast radius.
- Root cause.
- Mitigation.
- Permanent fix backlog item.

## Go-Live Livechat Checklist

Use this checklist on production right before client-facing bot tests.

1. Deploy and module update
- Pull latest `main` on production code path.
- Upgrade module `omnichannel_bridge` in Odoo.
- Confirm commit hash on server matches git remote target.

2. Critical settings
- `omnichannel_bridge.llm_enabled = True`
- `omnichannel_bridge.site_livechat_enabled = True`
- `omnichannel_bridge.llm_backend = ollama`
- `omnichannel_bridge.ollama_base_url = http://77.42.20.195:11434`
- `omnichannel_bridge.llm_strict_grounding = True`

3. Live widget and routing
- Odoo website livechat widget is visible on public page.
- New visitor message appears in `Discuss` as `discuss.channel`.
- No frontend RPC errors on feedback/notifications.

4. Functional smoke (must pass all)
- RU/BE inbound -> normal Ukrainian answer (no policy explanation).
- PL inbound -> normal Polish answer.
- Camp question -> answer includes factual camp context.
- Qualification -> bot asks next missing question (age/period/city/budget/contact).
- Manager request -> bot pauses and escalation is sent.

5. Data quality checks
- Partner card updates `omni_*` sales profile fields.
- `omni_sales_stage` transitions are visible (`qualifying/proposal/handoff`).
- Recommendation block uses 1-2 camp options, not long catalog dump.

6. Rollback trigger
- If any P1/P2 symptom appears, disable bot (`llm_enabled=False`) and keep livechat human-only until fix.
