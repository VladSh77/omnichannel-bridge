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
