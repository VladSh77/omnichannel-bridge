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
