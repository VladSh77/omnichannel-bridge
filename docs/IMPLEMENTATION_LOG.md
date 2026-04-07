# Implementation Log — `omnichannel_bridge`

## 2026-04-07 — Phase 0 Bootstrap

### Scope

- Initialized documentation package for controlled delivery.
- Added baseline technical and operational documents.
- Set explicit local -> git -> server workflow policy.

### Artifacts Added

- `docs/TECHNICAL_PASSPORT.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/SECURITY_RODO.md`
- `docs/LEGAL_FACTS_PACK.md`
- `docs/TEST_PLAN.md`
- `README.md` docs table update

### Notes

- No server-side actions performed.
- Next target: staging blueprint + idempotency/async technical design.

## 2026-04-07 — Phase 0.1 Staging and Design

### Scope

- Added staging environment blueprint with parity and isolation rules.
- Added engineering design v1 for idempotency and async AI queue foundation.

### Artifacts Added

- `docs/STAGING_BLUEPRINT.md`
- `docs/ENGINEERING_DESIGN_V1.md`
- `README.md` docs table update

### Notes

- No server-side actions performed.
- Next target: implement models and flow changes for idempotency and job queue (local only).

## 2026-04-07 — Phase 1 Foundation (Local Code)

### Scope

- Implemented webhook idempotency registry model.
- Implemented async AI job queue model and cron processor.
- Added channel-level race guard metadata fields.
- Switched inbound AI trigger from sync call to queued job.

### Code Artifacts

- `addons/omnichannel_bridge/models/omni_webhook_event.py`
- `addons/omnichannel_bridge/models/omni_ai_job.py`
- `addons/omnichannel_bridge/data/omni_ai_job_cron.xml`
- `addons/omnichannel_bridge/models/omni_bridge.py` (queue + idempotency integration)
- `addons/omnichannel_bridge/models/mail_channel.py` (bot/human timestamps + pause fields)
- `addons/omnichannel_bridge/security/ir.model.access.csv` (new model access)
- `addons/omnichannel_bridge/models/__init__.py`
- `addons/omnichannel_bridge/__manifest__.py`

### Notes

- No server-side actions performed.
- Next target: add operational views and staged validation scenarios for new models.

## 2026-04-07 — Knowledge Base Update (Interview FAQ)

### Scope

- Added curated interview FAQ knowledge file for CampScout.
- Wired FAQ retrieval into `omni.knowledge` with keyword-based snippet selection.
- Passed current user text into grounding bundle to improve FAQ relevance.

### Code Artifacts

- `addons/omnichannel_bridge/data/knowledge/interview_faq_ua.md`
- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `addons/omnichannel_bridge/models/omni_ai.py`

### Notes

- FAQ is contextual support data, not source of truth for prices/dates/availability.
- No server-side actions performed.

## 2026-04-07 — Operations UI for Queue/Idempotency

### Scope

- Added operational UI for AI queue and webhook idempotency events.
- Added basic AI job actions from form view: retry and cancel.

### Code Artifacts

- `addons/omnichannel_bridge/views/omni_ops_views.xml`
- `addons/omnichannel_bridge/models/omni_ai_job.py` (`action_retry`, `action_cancel`)
- `addons/omnichannel_bridge/__manifest__.py` (view registration)

### Notes

- New menu: `Omnichannel -> Operations -> AI Jobs / Webhook Events`.
- No server-side actions performed.

## 2026-04-07 — Channel-Level Bot Pause Controls

### Scope

- Added manual pause/resume bot actions on `mail.channel` form.
- Exposed pause state and last human/bot reply timestamps in channel UI.

### Code Artifacts

- `addons/omnichannel_bridge/models/mail_channel.py`
- `addons/omnichannel_bridge/views/mail_channel_views.xml`

### Notes

- Supports manager takeover without editing global settings.
- No server-side actions performed.

## 2026-04-07 — Website Live Chat AI Bridge

### Scope

- Added dedicated setting to enable/disable AI for Odoo website live chat.
- Connected website live chat inbound customer messages to the same AI queue pipeline.
- Reused sales triggers and memory learning for site chat provider context.

### Code Artifacts

- `addons/omnichannel_bridge/models/res_config_settings.py`
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
- `addons/omnichannel_bridge/models/mail_channel.py`

### Notes

- Live chat bridge runs only for non-messenger channels and only when setting is enabled.
- Provider used for this path: `site_livechat`.
- No server-side actions performed.

## 2026-04-07 — TZ Checklist Reconciliation

### Scope

- Reviewed `docs/TZ_CHECKLIST.md` against actual repository implementation state.
- Updated statuses for delivered foundation items and marked partials where rollout rules are still pending.

### Status Changes Applied

- Marked as done: idempotency, async queue timeout mitigation, kill switch, fallback.
- Marked as partial: website live chat bridge, manager pause semantics, bot/human logging, knowledge base, runbook.
- Preserved pending status for unresolved business/domain items (coupons, event seat sync, legal full-pack grounding, SLA 3-min timer logic).

### Notes

- No server-side actions performed.

## 2026-04-07 — SLA Timer Baseline (3 min)

### Scope

- Added configurable SLA wait window before bot reply.
- Live chat AI jobs are queued with SLA delay.
- AI job runner cancels bot reply if manager replied inside SLA window.

### Code Artifacts

- `addons/omnichannel_bridge/models/res_config_settings.py`
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
- `addons/omnichannel_bridge/models/omni_ai_job.py`
- `addons/omnichannel_bridge/models/mail_channel.py`

### Notes

- Default SLA is 180 seconds; enforced minimum is 30 seconds.
- No server-side actions performed.

## 2026-04-07 — Production Compatibility Patch (`discuss.channel`)

### Scope

- Aligned channel integration to production Odoo model `discuss.channel`.
- Removed hard dependency on `mail.channel` in AI queue/thread flow.
- Updated Discuss form inheritance to real production view ID.

### Code Artifacts

- `addons/omnichannel_bridge/models/mail_channel.py`
- `addons/omnichannel_bridge/models/omni_bridge.py`
- `addons/omnichannel_bridge/models/omni_ai_job.py`
- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `addons/omnichannel_bridge/models/omni_notify.py`
- `addons/omnichannel_bridge/views/mail_channel_views.xml`
- `docs/TZ_CHECKLIST.md`

### Notes

- Compatibility validated against production metadata (`mail.discuss_channel_view_form`).
- No server-side write actions performed.

## 2026-04-07 — Strategy Lock: Direct-First + SendPulse Fallback

### Scope

- Formalized delivery strategy for channel rollout.
- Confirmed direct integrations as default target architecture.
- Retained SendPulse only as contingency bridge (Plan B).

### Artifacts Updated

- `README.md`
- `docs/TECHNICAL_PASSPORT.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/TEST_PLAN.md`

### Notes

- No server-side actions performed.

## 2026-04-07 — Livechat-First Defaults and Test Gate

### Scope

- Enforced `site_livechat` enable flag on every defaults run.
- Updated project quick start to validate website live chat before messengers.
- Expanded test plan with mandatory livechat-first acceptance suite.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_integration.py`
- `README.md`
- `docs/TEST_PLAN.md`

### Notes

- Keeps rollout aligned with current business priority: website chat first, then Meta/Telegram.
- No server-side actions performed.

## 2026-04-07 — Runtime Scope/Language Guards for Camp Chat

### Scope

- Added runtime guard for RU inbound messages (policy reply in UA/PL + escalation).
- Added runtime guard for out-of-scope requests (camp-only notice + escalation).
- Kept strict grounding and livechat-first behavior unchanged.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_ai.py`
- `docs/TEST_PLAN.md`

### Notes

- This is an execution-time safety layer on top of prompt policy.
- No server-side actions performed.

## 2026-04-07 — Sales Discovery Flow v1 (Camp Qualification)

### Scope

- Added extraction of sales clues from inbound messages (age, budget, period, city) into chat memory.
- Added `SALES_DISCOVERY_POLICY` block into grounding bundle to enforce consultative flow.
- Added anti-repeat behavior by deriving missing qualifiers from CRM + memory.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_memory.py`
- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `docs/TEST_PLAN.md`

### Notes

- This is a lightweight rule-based qualification layer before full FSM implementation.
- No server-side actions performed.

## 2026-04-07 — Structured Camp Profile on Partner

### Scope

- Added structured qualification fields on `res.partner` (age, period, city, budget, sales stage).
- Synced regex-based inbound clue extraction into those fields.
- Exposed structured profile on partner Omnichannel tab for manager control.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/res_partner.py`
- `addons/omnichannel_bridge/models/omni_memory.py`
- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `addons/omnichannel_bridge/views/res_partner_views.xml`

### Notes

- LLM now reads both free-text memory and structured profile hints.
- No server-side actions performed.

## 2026-04-07 — Auto Sales Stage Transitions

### Scope

- Added automatic stage transitions to `proposal` when minimum qualification is present (age + period).
- Added automatic transition to `handoff` on out-of-scope, fallback path, and explicit manager requests.
- Synced livechat human-request branch to set partner stage `handoff`.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_ai.py`
- `addons/omnichannel_bridge/models/mail_channel.py`

### Notes

- Keeps manager visibility aligned with real dialog state in chat.
- No server-side actions performed.

## 2026-04-07 — Profile-Based Camp Recommendations v1

### Scope

- Added a recommendation block with top 1-2 camps based on period, budget, and places.
- Injected recommendation context into strict grounding bundle for practical sales replies.
- Added test expectation for short recommendation output (1-2 options).

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `docs/TEST_PLAN.md`

### Notes

- Scoring is heuristic and intentionally lightweight for fast rollout.
- No server-side actions performed.

## 2026-04-07 — Token-Saving Compact Context Mode

### Scope

- Added compact-mode switch via config parameter `omnichannel_bridge.llm_compact_mode` (default enabled).
- Reduced context size in compact mode: catalog lines, transcript depth/length, FAQ count/length.
- Kept strict grounding structure unchanged while lowering token footprint.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `docs/TEST_PLAN.md`

### Notes

- Optimized for free/low-token usage without changing sales logic.
- No server-side actions performed.

## 2026-04-07 — Manager Handoff Packet

### Scope

- Added compact handoff packet to escalation notifications.
- Packet includes key sales qualifiers: age, period, city, budget, stage.
- Keeps manager takeover fast without opening full CRM card first.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_notify.py`
- `docs/TEST_PLAN.md`

### Notes

- Notification format remains concise for mobile Telegram reading.
- No server-side actions performed.

## 2026-04-07 — Auto Next Question for Faster Qualification

### Scope

- Added post-processing of LLM replies to append one missing qualifier question.
- Works only when model reply has no question and partner profile is incomplete.
- Language-aware question templates (UA/PL) based on inbound message language.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_ai.py`
- `docs/TEST_PLAN.md`

### Notes

- Keeps dialog moving toward booking readiness with minimal token cost.
- No server-side actions performed.

## 2026-04-07 — Camp Facts Resolver (Price/Program/Places)

### Scope

- Refactored catalog facts to camp-focused output with explicit fields per camp.
- Added robust source resolution for `places_left` with field-priority fallback.
- Added program extraction from product terms/descriptions for sales answers.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `docs/TEST_PLAN.md`

### Notes

- Resolver is designed for custom Odoo schemas and degrades gracefully if a field is missing.
- No server-side actions performed.

## 2026-04-07 — Debug Data Source Tracing

### Scope

- Added settings toggle to expose fact-source markers in LLM context.
- Catalog and recommendation lines now can include source traces for `program` and `places`.
- Keeps debug output internal and opt-in via config flag.

### Code/Docs Artifacts

- `addons/omnichannel_bridge/models/res_config_settings.py`
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
- `addons/omnichannel_bridge/models/omni_knowledge.py`
- `docs/TEST_PLAN.md`

### Notes

- Intended for fast production diagnostics of field mapping without code changes.
- No server-side actions performed.

## 2026-04-07 — Access Incident (SSH Password/Key Mismatch)

### Incident Summary

- Access to AI host was intermittently lost during security hardening.
- Root cause: password auth toggled while active agent keypair did not match key labeled on server (`MacBook fayna`), causing lockout for this environment.
- Temporary password-based recovery attempts used multiple credentials; some were stale/invalid.

### Recovery Actions

- Restored agent key access by adding current environment pubkey:
  - `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBYnE7AQXBiSfiga35soQKAxm4LeFpkHzhhXrNDynAZm agent-current`
- Verified non-interactive key login (`BatchMode=yes`) succeeded.
- Kept security intent: target state remains key-based access with controlled key inventory.

### Process Correction

- Enforced order for future access changes:
  1) validate key login end-to-end,
  2) only then disable password auth,
  3) re-test from active automation environment before session close.
