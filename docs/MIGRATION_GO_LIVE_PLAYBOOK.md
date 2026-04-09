# Migration Go-Live Playbook (SendPulse -> Odoo Omnichannel)

## Purpose

Prepare safe migration of client conversations from SendPulse/scenario bots to `omnichannel_bridge` with AI + manager handoff, without traffic loss during ad campaigns.

## Non-negotiable deployment order

1. Local changes complete.
2. Commit + push to git.
3. Server pull + module upgrade.
4. Only then channel cutover.

## Readiness gates (must be green)

- `omnichannel_bridge` upgraded on target DB (`-u omnichannel_bridge`).
- Livechat smoke passed (no loops, correct bot/customer attribution).
- AI backend reachable (`ollama`/`openai`) and fallback message verified.
- UA/PL UI translations updated.
- Manager online queue configured (`Manager queue pool`) and tested with at least 2 users.
- Knowledge articles loaded and visible in Operations.
- Legal links and consent texts configured in Settings.
- Webhook events arriving and deduplicated correctly.

## Channel migration strategy

### Wave 1 (recommended first): Telegram test bot

- Register test bot token in Odoo Integrations/Settings.
- Set Telegram webhook to `https://<domain>/omni/webhook/telegram`.
- Set `telegram_webhook_secret` and same `secret_token` in Telegram webhook.
- Run scripted test set:
  - short intents (`погода`, `ціна`, `дати`);
  - confusion (`нічого не ясно`);
  - handoff (`потрібен менеджер`);
  - contact capture.
- Verify:
  - inbound in Discuss,
  - no fallback loops,
  - manager routing works,
  - outbound reaches Telegram.

### Wave 2: Website livechat (primary)

- Keep livechat-first policy enabled.
- Validate first greeting, manager presence line, and contact flow.
- Validate legal notice rendered once.

### Wave 3: Meta/Instagram

- Configure app secret/verify token/page token.
- Set webhook URL to `.../omni/webhook/meta`.
- Run Meta test page scenarios before enabling production ad traffic.

### Wave 4: WhatsApp (Cloud or Twilio)

- Configure provider credentials and verify webhook route.
- Test inbound + outbound + retry behavior.

## SendPulse migration policy

- Do not hard cut all bots at once.
- Use controlled overlap window:
  - Odoo as primary for selected channels,
  - SendPulse disabled or limited to backup-only responses.
- Preserve field mapping compatibility:
  - external contact id,
  - phone/email,
  - display name/avatar,
  - language hint.
- For each bot chain:
  - map trigger -> Odoo intent/policy,
  - map fallback -> manager handoff,
  - map legal/consent block -> approved Odoo settings.

## Day-0 cutover checklist

- [ ] Confirm latest commit hash on server.
- [ ] Restart Odoo services/containers after upgrade.
- [ ] Verify `Webhook events` list receives fresh events.
- [ ] Verify AI response is not fallback-only.
- [ ] Verify one manager online and receives priority notifications.
- [ ] Verify `Інсайти клієнта` access is restricted.
- [ ] Verify UA/PL language switch for operations screens.
- [ ] Verify rollback command prepared and tested.

## Rollback (fast)

- Disable AI replies (`llm_enabled=False`) and set manual mode if needed.
- Re-enable previous SendPulse chain for affected channel only.
- Keep webhook ingest logs for incident analysis.
- Create incident note in `IMPLEMENTATION_LOG.md`.

## Ownership

- Product owner: approves migration wave and channel priority.
- Tech owner: performs git -> server deploy and webhook cutover.
- Sales owner: validates reply quality and handoff SLA on live traffic.

