# Test Plan — `omnichannel_bridge`

## Environments

- Local: developer validation only.
- Staging: required for integration tests before production.
- Production: smoke verification only after approved deploy.

## Wave 1 Scope

- Providers: Meta, Telegram.
- Language baseline: Ukrainian.
- AI mode: strict grounding.

## Mandatory Test Suites

### A. Webhook Inbound

- Meta webhook signature validation.
- Telegram secret validation.
- Correct thread creation in Discuss.
- Partner identity linkage and reuse.

### B. AI Reply Orchestration

- Reply generated only when AI is enabled.
- Reply mode behavior (`always`, `outside_manager_hours`, `never`).
- Fallback reply when backend unavailable.

### C. Fact Grounding

- Prices/places come from ORM-derived facts.
- Missing fact path returns explicit uncertainty + escalation.
- No fabricated legal terms in response.

### D. Human Handoff

- Manager-request trigger path.
- Bot pause conditions (to be implemented).

### E. Regression and Stability

- Duplicate webhook replay behavior (to be implemented).
- Long LLM latency behavior (to be implemented async path).

## Exit Criteria for Wave 1

- All A/B/C tests green.
- No P1/P2 issues open.
- Staging smoke validated and documented.

## Fallback Validation (SendPulse Bridge)

- Keep a documented field map for SendPulse compatibility: contact id, phone, email, avatar URL, language, profile URL.
- Run a periodic bridge-readiness smoke test in staging (no production traffic switch).
- If direct path fails wave exit criteria, execute approved fallback checklist and validate end-to-end message flow before reopening traffic.
