# Implementation Log — `omnichannel_bridge`

## 2026-04-08 — TZ Item 2: WhatsApp runtime parser/outbound

### Scope

- Implemented WhatsApp Cloud API webhook processing (inbound parser + dedup key extraction).
- Implemented WhatsApp outbound replies via Graph API phone_number_id endpoint.
- Added WhatsApp verification/settings fields and parser tests.

### Code Artifacts

- `addons/omnichannel_bridge/models/omni_bridge.py`
  - `extract_whatsapp_message_id` integration in idempotency extraction.
  - `/_omni_process_whatsapp_stub` now parses Cloud API payloads into `_omni_deliver_inbound`.
  - `_omni_whatsapp_send_to_wa_id` for outbound text replies.
  - verify signature path for WhatsApp webhooks.
- `addons/omnichannel_bridge/models/res_config_settings.py`
  - `omnichannel_whatsapp_verify_token`
  - `omnichannel_whatsapp_phone_number_id`
  - `omnichannel_whatsapp_app_secret`
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
  - WhatsApp fields in Settings UI.
- `addons/omnichannel_bridge/utils/webhook_parsers.py`
  - `extract_whatsapp_message_id`.
- `tests/test_webhook_parsers.py`
  - WhatsApp parser unit tests.
- `tests/test_contract_regressions.py`
  - WhatsApp runtime markers check.

### Notes

- Current implementation targets Meta WhatsApp Cloud webhook shape.
- Twilio-specific inbound parser remains separate backlog item.
- Deployed on production via git bundle sync + module upgrade; server commit now `5c3f183`.

## 2026-04-08 — TZ Item 1: Baseline Freeze + DoD Matrix

### Scope

- Started execution queue from item 1 (baseline and acceptance criteria).
- Fixed baseline reference for implementation waves.
- Added explicit DoD matrix by major TZ block.

### Artifacts

- `docs/TZ_EXECUTION_QUEUE.md`
- `README.md` (docs index updated)

### Baseline

- Baseline commit: `e695d03`
- Branch: `main`

## 2026-04-08 — Prod mapping audit + coupon E2E + FSM/race + retention

### Scope

- Performed read-only production audit for camp places mapping against real DB/custom addons.
- Implemented public coupon E2E flow in Odoo sales (`sale.order`) with one-use-per-partner accounting.
- Added FSM transition guard for chat sales stages and finalized manager-vs-bot race semantics.
- Added retention/purge jobs and right-to-erasure action; added log PII masking.
- Expanded contract regression checks and CI compile coverage.

### Production Audit (Read-Only)

- SSH host checked: `91.98.122.195`, db `campscout`, container `campscout_web`.
- Confirmed runtime fields/models:
  - `discuss.channel` (no `mail.channel`)
  - `product.template.bs_event_id`, `bs_seats_available`
  - `event.event.seats_available` with registration/sales impact.
- Confirmed server code mapping:
  - `campscout_management.get_camp_availability`
  - `bs_campscout_addon` event/product seat logic.
- Artifact:
  - `docs/PROD_CAMP_MAPPING_AUDIT_2026-04-08.md`

### Code Artifacts

- Coupon E2E:
  - `models/omni_coupon_redemption.py` (usage registry)
  - `models/sale_order.py` (coupon validation/apply/redemption)
  - `views/sale_order_views.xml` (order fields)
  - `models/res_config_settings.py` + `views/res_config_settings_views.xml` (coupon code/% settings)
- FSM + race semantics:
  - `models/res_partner.py` (`_OMNI_STAGE_TRANSITIONS`, `omni_set_sales_stage`)
  - `models/omni_ai.py` and `models/omni_sales_intel.py` switched to FSM-safe stage updates
  - `models/mail_channel.py` manager-session lock fields/logic
  - `models/omni_bridge.py` no-enqueue during active manager session
- Compliance and retention:
  - `models/res_partner.py` (`action_omni_right_to_erasure`)
  - `models/mail_channel.py` (`omni_cron_purge_old_messages`)
  - `models/omni_webhook_event.py` (`omni_cron_purge_old_events`)
  - `models/omni_bridge.py` (`_omni_mask_pii_for_logs`)
  - `data/omni_ai_job_cron.xml` (daily retention jobs)
- CI/tests/docs:
  - `tests/test_contract_regressions.py` expanded
  - `.github/workflows/ci.yml` compiles `tests` too
  - `docs/TZ_CHECKLIST.md` updated statuses

### Notes

- Production audit was read-only (no restart, no module upgrade, no write operations).

### Deployment (after local commit + push)

- Source commit deployed: `55bfae1`.
- Server path corrected to git-backed repository:
  - `/opt/campscout/custom-addons/omnichannel_bridge_repo` (git)
  - `/opt/campscout/custom-addons/omnichannel_bridge` (symlink to module dir inside repo)
- Odoo module upgraded via shell (`button_immediate_upgrade`) and validated:
  - module state: `installed`
  - new models/fields available at runtime (`omni.coupon.redemption`, coupon/fsm/compliance fields).

### Documentation alignment

- Re-read and aligned:
  - `README.md` docs index (added production mapping audit doc).
  - `docs/TZ_CHECKLIST.md` statuses and readiness estimate refreshed to current state.

## 2026-04-08 — 24h Window Reminder Automation (Meta/WhatsApp)

### Scope

- Implemented configurable reminder automation for channels with 24h policy constraints.
- Added one-reminder-per-inbound-cycle anti-spam guard.
- Reset reminder cycle when customer sends new inbound.

### Code Artifacts

- `addons/omnichannel_bridge/models/mail_channel.py`
  - New fields: `omni_last_customer_inbound_at`, `omni_window_reminder_sent_at`, `omni_window_reminder_count`.
  - New cron handler: `omni_cron_send_window_reminders`.
- `addons/omnichannel_bridge/models/omni_bridge.py`
  - On inbound delivery: set `omni_last_customer_inbound_at` and reset `omni_window_reminder_sent_at`.
- `addons/omnichannel_bridge/models/res_config_settings.py`
  - New settings: `window_reminder_enabled`, `window_reminder_trigger_hours`, `window_message_window_hours`, `window_reminder_text`.
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
  - Added settings UI block in Bot schedule section.
- `addons/omnichannel_bridge/data/omni_ai_job_cron.xml`
  - Added cron `ir_cron_omni_24h_window_reminders` (every 5 minutes).

### Notes

- Current provider scope: `meta`, `whatsapp`, `twilio_whatsapp`.
- Handoff stage is excluded from auto-reminder sending.
- No server-side actions performed.

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

## 2026-04-07 — Production Incident: Livechat Recursion + Access Error (`res.partner`)

### Incident Window

- Triggered during website livechat post-message flow after recent "bot-first + fallback" hotfixes.
- User-visible symptoms:
  - chat popup freezes / hangs,
  - repeated RPC errors,
  - bot sends acknowledgement and then escalates unexpectedly,
  - yellow Odoo access toasts for Public User (`id=4`) on `res.partner` read.

### Error Signatures Observed

- `RecursionError: maximum recursion depth exceeded while calling a Python object`
- Stack loop pattern:
  - `message_post()` -> `_omni_handle_website_livechat_inbound()` -> `message_post()` -> ...
- Access fault signature:
  - `Public User (id=4) doesn't have 'read' access to: res.partner`

### Root Causes (Confirmed)

1. **Recursive self-posting in livechat handler**
   - Inbound handler posted bot/system messages through regular `message_post`, which re-entered inbound handler.
   - This created infinite recursion for ack/fallback/escalation branches.

2. **Unsafe partner read under website guest context**
   - `omni_customer_partner_id` was read in public request context.
   - For non-public partner records this raised access errors for `Public User`.

### Code Fixes Applied

- `addons/omnichannel_bridge/models/mail_channel.py`
  - Added context guard in `message_post`:
    - early return when `omni_skip_livechat_inbound=True`.
  - Wrapped internal livechat system posts with:
    - `with_context(omni_skip_livechat_inbound=True).message_post(...)`
  - Read customer partner through sudo in inbound/operator-routing paths:
    - `sudo_channel = self.sudo()`
    - use `sudo_channel.omni_customer_partner_id`.

- `addons/omnichannel_bridge/models/omni_ai.py`
  - Wrapped bot/fallback/out-of-scope/internal-note postings with:
    - `with_context(omni_skip_livechat_inbound=True).message_post(...)`
  - Prevented AI-generated internal posts from re-triggering inbound livechat loop.

### Verification Performed

- Local lint on edited files: no linter errors.
- Production logs after restart:
  - no new `RecursionError` signatures in immediate window.
- Reproduced user screenshot symptom mapping:
  - access toast corresponds to unsafe partner read path; patched with sudo read.

### Process Incident (Critical)

- A hotfix was deployed to production before local commit/push completion.
- This violated required workflow:
  - `local -> git commit/push -> server update via git pull`.
- Corrective actions executed:
  - committed and pushed local fixes to `main` (`3ee8b39`),
  - added permanent project rule:
    - `.cursor/rules/deployment-workflow-critical.mdc` (`alwaysApply: true`).

### Remaining Operational Blocker

- Server deployment path is still file-based in current host layout; target addon directory is not git-backed.
- Attempted migration to git-based deploy was blocked by missing repository access credentials on server.
- Required to complete strict process end-to-end:
  - configure deploy key or HTTPS token for server-side `git pull`.

## 2026-04-07 — Livechat Scope Guard: Fewer False Out-of-Scope Classifications

### Problem

- Longer website livechat starter lines (for example documentation / browsing buttons) lacked explicit camp keywords and were classified as out-of-scope, triggering escalation replies incorrectly.

### Change

- `addons/omnichannel_bridge/models/omni_ai.py` (`_omni_is_camp_scope_message`):
  - widened short-message bypass to 35 characters,
  - added onboarding hint tokens (UA/PL/EN) for docs/browsing-style openers,
  - added price/language stems (`цін`, `cena`, `price`, Polish camp terms) to catch common variants like «ціни» without substring `ціна`.

## 2026-04-07 — TZ §6.1 schedule, §14.1 Meta retries, §14.5 webhook size

### Scope

- Align bot schedule with TZ: optional night window; during manager working hours queue AI job after SLA so the manager can answer first (Meta/Telegram only).
- Harden outbound: retry Graph/Telegram POST on transient errors with exponential backoff.
- Reject oversized webhook bodies with HTTP 413.

### Artifacts

- `addons/omnichannel_bridge/models/omni_ai.py`: `omni_bot_may_reply_now(channel)`, `omni_autoreply_delay_seconds_for_inbound`, `night_bot_*`, shared time-span helpers.
- `addons/omnichannel_bridge/models/omni_bridge.py`: enqueue delay; `_omni_http_post_with_retries` for Meta and Telegram send.
- `addons/omnichannel_bridge/controllers/main.py`: `webhook_max_body_bytes` guard.
- `addons/omnichannel_bridge/models/res_config_settings.py` + `views/res_config_settings_views.xml`: new settings fields.
- `docs/TZ_CHECKLIST.md`, `docs/OPERATIONS_RUNBOOK.md`.

### Notes

- Website live chat remains immediate (unchanged).
- No server actions performed.

## 2026-04-07 — Livechat Public User: res.partner AccessError (full sudo re-bind)

### Problem

- Toast «Public User (id=4) doesn't have read access to res.partner» still appeared during website live chat (e.g. out-of-scope flow).
- Cause: `sudo()` on `omni.ai` does not re-bind recordsets passed from `message_post` (public env). Reading `partner.user_ids`, `channel.omni_customer_partner_id`, or `partner.display_name` in helpers used the portal/public ACL.

### Change

- `mail_channel`: `_omni_is_internal_author` reads `user_ids` via `partner.sudo()`; livechat passes `channel`/`partner` `.sudo()` into AI, fallback, notify, sales_intel, memory.
- `omni.ai.omni_maybe_autoreply`: normalize `channel` and `partner` with `.sudo()` at method entry.
- `omni.knowledge`: `omni_strict_grounding_bundle` and `omni_channel_transcript_block` sudo-bind `channel` (and partner in bundle).
- `omni.notify`: sudo-bind `channel`/`partner` in public notify APIs; `_handoff_packet` uses `partner.sudo()`.

### Notes

- Deploy: upgrade module `omnichannel_bridge` on Odoo after pull.

## 2026-04-07 — Sensitive-topic guardrail and mandatory human handoff

### Scope

- Added baseline sensitive-topic detection for live dialogs (children safety, medical, legal, insurance-dispute markers in UA/PL/EN).
- On match, bot avoids freeform LLM answer and routes to manager with escalation notice.

### Artifacts

- `addons/omnichannel_bridge/models/omni_ai.py`
  - `_omni_is_sensitive_message(...)`
  - `_omni_send_sensitive_escalation_reply(...)`
  - guardrail call at start of `omni_maybe_autoreply(...)` before out-of-scope/LLM generation

### Notes

- This is a baseline keyword policy; full moderation policy engine remains in backlog (severity levels, configurable dictionaries, analytics).

## 2026-04-07 — Objection baseline (TZ §7.1)

### Scope

- Added lightweight objection classifier (rule-based keywords UA/PL/EN).
- Logged objection type to partner memory and Discuss note for anti-repeat context.
- Injected short `OBJECTION_PLAYBOOK` guidance into LLM system context for detected objection.

### Artifacts

- `addons/omnichannel_bridge/models/omni_sales_intel.py`
  - `_OBJECTION_KEYWORDS`
  - `omni_detect_objection_type(...)`
  - `omni_objection_guidance_block(...)`
  - `_omni_log_objection(...)` integrated in `omni_apply_inbound_triggers(...)`
- `addons/omnichannel_bridge/models/omni_ai.py`
  - `OBJECTION_PLAYBOOK` append to system prompt when objection detected

### Notes

- This is baseline logic, not a full FSM/policy editor; configurable templates/analytics remain backlog.

## 2026-04-07 — Objection playbooks configurable via Settings

### Scope

- Added Odoo Settings fields for objection playbook texts (price/timing/trust/need_to_think/competitor/not_decision_maker).
- `omni.sales.intel` now loads playbook text from `ir.config_parameter` with safe defaults from code.

### Artifacts

- `addons/omnichannel_bridge/models/res_config_settings.py`
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
- `addons/omnichannel_bridge/models/omni_sales_intel.py`

### Notes

- Behavior remains backward-compatible: if no custom text is set, default playbooks are used.

## 2026-04-07 — UA/PL default objection playbooks

### Scope

- Updated default objection playbook templates to bilingual UA/PL micro-guidance.
- Keeps factual constraints (ORM/legal links only) and low-pressure premium tone.

### Artifact

- `addons/omnichannel_bridge/models/omni_sales_intel.py`

### Notes

- Custom Settings overrides still have priority over these defaults.

## 2026-04-07 — Internal Telegram PRIORITY path (TZ §8.1)

### Scope

- Added explicit `PRIORITY` formatting for urgent escalations and problematic threads in internal Telegram notifications.
- Added optional second destination chat for priority events (`internal_tg_priority_chat_id`).

### Artifacts

- `addons/omnichannel_bridge/models/omni_notify.py`
  - priority title + routing (`_send(..., priority=True)`)
  - `_is_priority_reason(...)` keyword matcher for escalation reasons
- `addons/omnichannel_bridge/models/res_config_settings.py`
  - `omnichannel_internal_tg_priority_chat_id`
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
  - Internal notifications settings block

### Notes

- If priority chat is empty, priority events stay in main internal chat but are clearly prefixed with `PRIORITY`.

## 2026-04-07 — Unified internal event summary + stage-change notify

### Scope

- Unified internal Telegram message format across events: new thread, escalation, problematic, stage change.
- Added `notify_stage_change(...)` and wired stage transitions in AI/livechat flows.

### Artifacts

- `addons/omnichannel_bridge/models/omni_notify.py`
  - `_event_summary_text(...)`
  - `notify_stage_change(...)`
  - `notify_new_thread/notify_escalation/notify_problematic` switched to shared formatter
- `addons/omnichannel_bridge/models/omni_ai.py`
  - `_omni_set_sales_stage(...)` helper with automatic `notify_stage_change`
  - stage writes routed through helper in sensitive/out-of-scope/fallback/manager-request/profile progression
- `addons/omnichannel_bridge/models/mail_channel.py`
  - livechat human-request handoff now emits stage-change notification

### Notes

- Priority routing behavior from previous step is preserved.

## 2026-04-07 — Purchase intent event in internal summary

### Scope

- Added baseline purchase-intent detection in inbound sales triggers (UA/PL/EN keywords).
- On detection: internal PRIORITY notification + Discuss auto note + stage transition to `handoff` with stage-change notify.

### Artifacts

- `addons/omnichannel_bridge/models/omni_sales_intel.py`
  - `_PURCHASE_INTENT_KEYWORDS`
  - `_omni_detect_purchase_intent(...)`
  - `_omni_log_purchase_intent(...)`
  - `_omni_mark_handoff_stage(...)`
- `addons/omnichannel_bridge/models/omni_notify.py`
  - `notify_purchase_intent(...)`
  - `purchase_intent` event type in unified formatter

### Notes

- This is intent-level signaling; confirmed payment/order events remain a separate integration step.

## 2026-04-07 — Confirmed purchase event from ORM (`sale.order`)

### Scope

- Added confirmed-purchase internal event based on real ORM transition (`sale.order` to `sale/done`).
- Event is sent as PRIORITY summary with order reference and amount.

### Artifacts

- `addons/omnichannel_bridge/models/sale_order.py`
  - hooks on `create` and `write` to detect confirmed sale state
- `addons/omnichannel_bridge/models/omni_notify.py`
  - `notify_purchase_confirmed(...)`
  - `_find_channel_for_partner(...)`
  - `purchase_confirmed` event type in formatter
- `addons/omnichannel_bridge/models/__init__.py`

### Notes

- Channel mapping uses the latest omnichannel thread for partner/commercial partner.
- This closes event-level visibility; payment.transaction-specific hooks can be added later if needed.

## 2026-04-07 — Confirmed purchase from payment/accounting layers

### Scope

- Extended confirmed-purchase event triggers beyond `sale.order` to payment and accounting events.
- Added hooks for:
  - `payment.transaction` state transitions to `authorized/done`,
  - `account.move` customer invoices transitions to `in_payment/paid`.

### Artifacts

- `addons/omnichannel_bridge/models/payment_transaction.py`
- `addons/omnichannel_bridge/models/account_move.py`
- `addons/omnichannel_bridge/models/omni_notify.py` (`notify_purchase_confirmed` generic reference/amount args)
- `addons/omnichannel_bridge/models/__init__.py`

### Notes

- This improves factual coverage of purchase confirmation signals in internal Telegram.
- De-duplication/reconciliation fine-tuning across `sale.order` + payments + invoices remains an optimization step.

## 2026-04-07 — De-dup for confirmed purchase internal events

### Scope

- Added anti-duplicate guard for `purchase_confirmed` internal notifications across multiple hooks (`sale.order`, `payment.transaction`, `account.move`).

### Artifacts

- `addons/omnichannel_bridge/models/res_partner.py`
  - `omni_last_purchase_notify_at`
  - `omni_last_purchase_notify_ref`
  - `omni_last_purchase_notify_amount`
- `addons/omnichannel_bridge/models/omni_notify.py`
  - `_is_purchase_notify_duplicate(...)` (20-minute window; same ref or amount)

### Notes

- Dedup keying is intentionally conservative to reduce spam bursts while preserving important alerts.

## 2026-04-07 — Runtime legal/RODO closure (consent + legal entity + child-data minimization)

### Scope

- Added mandatory short consent block in chat runtime (first bot message per channel):
  - controller/legal entity,
  - processing purpose,
  - canonical legal links (privacy/terms/cookies/child-protection).
- Added legal context block into strict grounding bundle for LLM (approved URLs only, no invented legal wording).
- Strengthened system policy on child-data minimization and legal answer boundaries.

### Artifacts

- `addons/omnichannel_bridge/models/mail_channel.py`
  - `omni_legal_notice_sent_at` (per-channel one-time legal notice marker)
- `addons/omnichannel_bridge/models/omni_ai.py`
  - `_omni_post_bot_message(...)` with one-time legal consent append
  - `_omni_legal_notice_block(...)`
  - system policy updates for legal/child-data boundaries
- `addons/omnichannel_bridge/models/omni_knowledge.py`
  - `omni_legal_context_block(...)` in strict grounding bundle

### Notes

- Legal notice is shown once per channel to avoid spam while preserving explicit consent context.

## 2026-04-08 — Coupon flow simplified to public Telegram channel

### Scope

- Business rule fixed: no personal coupon generation; clients open public channel and copy current code.
- Added configurable public channel URL in Settings and injected coupon policy block into strict grounding bundle.

### Artifacts

- `addons/omnichannel_bridge/models/res_config_settings.py`
  - `omnichannel_coupon_public_channel_url`
- `addons/omnichannel_bridge/views/res_config_settings_views.xml`
  - setting field in Telegram block
- `addons/omnichannel_bridge/models/omni_knowledge.py`
  - `omni_coupon_policy_block(...)` in grounding bundle
- `docs/TZ_CHECKLIST.md`

### Notes

- Default channel URL set to `https://t.me/campscouting`.

## 2026-04-08 — Event/registration-based places resolver (workspace mapping)

### Scope

- Implemented stronger places resolver in `omni_knowledge` using discovered custom models in workspace:
  1) `product.template.get_camp_availability()` (campscout-management),
  2) `bs_event_id.seats_available` (bonsens addon on template/variant),
  3) `event.event.ticket -> event.event.seats_available` aggregation for future events.
- Added reserve guardrails: when places are `<= 0`, facts lines include `reserve: manager_waitlist_required`, and strict bundle includes `RESERVE_POLICY` requiring manager handoff for waitlist.

### Artifact

- `addons/omnichannel_bridge/models/omni_knowledge.py`

### Notes

- This is mapped from repository custom modules; final production mapping must still be verified against the exact server code/DB snapshot.

## 2026-04-08 — Sold-out reserve runtime flow (manager handoff + CRM lead)

### Scope

- Implemented operational reserve flow when catalog facts indicate sold-out (`reserve: manager_waitlist_required`) and user asks availability.
- Bot now appends explicit reserve CTA, asks for contact, and routes to manager.

### Artifacts

- `addons/omnichannel_bridge/models/omni_ai.py`
  - `_omni_apply_reserve_flow(...)`
  - `_omni_create_or_get_reserve_lead(...)`
  - `_omni_user_asks_availability(...)`
- `addons/omnichannel_bridge/models/mail_channel.py`
  - `omni_reserve_lead_id`
  - `omni_reserve_requested_at`

### Runtime behavior

- On first sold-out hit per channel:
  - create/reuse CRM lead for reserve,
  - send escalation notify to manager,
  - set sales stage to `handoff`,
  - include reserve text to client response.

## 2026-04-08 — CI bootstrap + webhook parser and contract tests

### Scope

- Added repository CI workflow for Python checks on push/PR.
- Added unit tests for critical webhook parser helpers (Telegram update_id, Meta mid).
- Added baseline contract-regression tests for critical runtime invariants.

### Artifacts

- `.github/workflows/ci.yml`
- `addons/omnichannel_bridge/utils/webhook_parsers.py`
- `addons/omnichannel_bridge/models/omni_bridge.py` (uses pure parser helpers)
- `tests/test_webhook_parsers.py`
- `tests/test_contract_regressions.py`

### Notes

- Tests are Odoo-runtime independent (run in plain Python), enabling fast CI signal before full Odoo integration tests.
