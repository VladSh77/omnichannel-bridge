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
