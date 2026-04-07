# Test Plan — `omnichannel_bridge`

## Environments

- Local: developer validation only.
- Staging: required for integration tests before production.
- Production: smoke verification only after approved deploy.

## Wave 1 Scope

- Provider priority: Website Live Chat first, then Meta and Telegram.
- Language baseline: Ukrainian.
- AI mode: strict grounding.

## Mandatory Test Suites

### A. Webhook Inbound

- Meta webhook signature validation.
- Telegram secret validation.
- Correct thread creation in Discuss.
- Partner identity linkage and reuse.

### A0. Website Live Chat First (mandatory before messengers)

- `site_livechat` integration row exists and is active for each company.
- `omnichannel_bridge.site_livechat_enabled=True` after module update.
- Public website widget visible and opens a new Discuss livechat channel.
- Visitor message creates AI job and gets bot reply with `delay_seconds=0`.
- If manager replies in thread, bot is paused (`omni_bot_paused=True`).
- If client asks for manager, bot pauses and sends escalation notice.
- Livechat feedback/system notifications do not trigger RPC errors.

### B. AI Reply Orchestration

- Reply generated only when AI is enabled.
- Reply mode behavior (`always`, `outside_manager_hours`, `never`).
- Fallback reply when backend unavailable.
- RU/BE inbound message path: normal camp answer in Ukrainian (without policy explanation).
- PL inbound message path: normal camp answer in Polish.
- Out-of-scope inbound message path: send camp-scope notice + manager escalation.

### C. Fact Grounding

- Prices/places come from ORM-derived facts.
- For each recommended camp, response includes: price, short program, places_left (from explicit field or fallback source).
- Missing fact path returns explicit uncertainty + escalation.
- No fabricated legal terms in response.
- Bot stays within camp domain; off-topic asks are escalated to manager.
- RU input gets UA/PL response policy reminder (no RU replies).
- Sales discovery flow asks missing qualifiers only: age, period, logistics, budget, contact.
- Anti-repeat check: bot does not ask again for clues already present in CRM/chat memory.
- When qualifiers are sufficient, bot proposes 1-2 recommended camps from catalog context (not a long list).
- Compact mode check: transcript and FAQ snippets are shortened (token-saving mode).
- Auto-next-question: if reply has no question mark and qualifiers are missing, bot appends exactly one next-step qualifier question.
- Debug mode check: when enabled, catalog/recommendation lines include source markers for program and places fields.

### D. Human Handoff

- Manager-request trigger path.
- Bot pause on manager join in website livechat.
- Manual pause/resume actions on channel.
- Escalation notification includes compact handoff packet (age/period/city/budget/stage).

### E. Regression and Stability

- Duplicate webhook replay behavior (to be implemented).
- Long LLM latency behavior (to be implemented async path).

## Exit Criteria for Wave 1

- A0/A/B/C tests green.
- No P1/P2 issues open.
- Staging smoke validated and documented.

## Fallback Validation (SendPulse Bridge)

- Keep a documented field map for SendPulse compatibility: contact id, phone, email, avatar URL, language, profile URL.
- Run a periodic bridge-readiness smoke test in staging (no production traffic switch).
- If direct path fails wave exit criteria, execute approved fallback checklist and validate end-to-end message flow before reopening traffic.
