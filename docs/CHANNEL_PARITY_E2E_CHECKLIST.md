# Channel Parity E2E Checklist

Purpose: one acceptance matrix for all enabled channels before go-live, so `omnichannel_bridge` behavior is channel-agnostic and matches SendPulse critical flows.

Channels in scope:
- Telegram
- Meta Messenger
- Instagram Direct
- WhatsApp Cloud API
- Twilio WhatsApp
- Viber
- Website Livechat
- TikTok (if enabled in integration registry)

Legend:
- PASS = scenario works end-to-end with expected data in Discuss + Odoo
- FAIL = regression/blocker
- N/A = channel not enabled in this environment

---

## Preconditions (run once)

- Module upgraded to latest (`-u omnichannel_bridge`), web assets refreshed.
- At least 2 active internal users (operator A / operator B).
- Test company has active integrations for channels under test.
- `omni_notify` and bot settings are configured (token/chat IDs where required).
- Test checklist runner has access to Discuss + Omnichannel menus.

---

## Global Invariants (must hold for every channel)

- One incoming event creates/updates one `discuss.channel` thread.
- `omni.inbox.thread` row is synced to that thread.
- Identity dedup works: same customer can be linked to one `res.partner` across channels.
- Conversation card opens from panel arrow (not direct partner form).
- Operator actions do not break thread membership or bot routing.
- Message history is preserved after close/reopen.

---

## Scenario Matrix (execute per channel)

### S1. New Contact (Text First)

Steps:
1. Send first text from a new external account.
2. Open Discuss thread and conversation card.
3. Verify card fields and provider label.

Expected:
- New thread exists in Discuss.
- New/guest customer binding is present.
- `omni.inbox.thread` row exists and shows latest message/time.
- No RPC errors.

### S2. Known Contact Reuse (Identity Match)

Steps:
1. Use an external account already linked in `omni.partner.identity`.
2. Send a text.

Expected:
- Existing `res.partner` reused.
- No duplicate partner created.
- Thread binds to correct partner.

### S3. Cross-Channel Dedup by Email/Phone

Steps:
1. Send from a second channel with no pre-existing identity.
2. From conversation card, identify by email/phone and link to existing partner.
3. Send another message from same second channel.

Expected:
- Same `res.partner` is reused after linking.
- Identity record is attached to that partner.
- No duplicate contacts for same person.

### S4. Media-First Inbound (No Text)

Variants: photo, voice, document, sticker/video where supported.

Steps:
1. Send media as first message (without text).
2. Open thread/card.

Expected:
- Thread is created (not dropped).
- Message appears in history with non-text fallback content.
- Partner/identity flow still works.

### S5. Manager Handoff / Bot Pause

Steps:
1. Ensure bot can answer.
2. Operator sends manual reply in thread.
3. Send next client message.

Expected:
- Bot pause/manager-first guard applies according to config.
- No duplicate bot+human double-reply in same turn.
- Operator status reflects manager activity.

### S6. AI Success Path

Steps:
1. Send normal FAQ/sales text.
2. Wait for AI response.

Expected:
- AI job processed successfully.
- Response posted to Discuss and delivered to channel.
- Outbound log/status present where applicable.

### S7. AI Failure/Fallback Path

Steps:
1. Simulate backend failure (or disable model endpoint in staging).
2. Send message requiring AI.

Expected:
- Retry/backoff path executes.
- Fallback message is sent (not silent failure).
- Thread remains usable for operator takeover.

### S8. Close/Reopen Thread

Steps:
1. Close conversation from card.
2. Reopen conversation.
3. Send a new client message.

Expected:
- Stage/status transitions are valid.
- Same thread context/history remains.
- New inbound still routes correctly.

### S9. Operator Assignment

Steps:
1. Add/remove operators in conversation card.
2. Save form.

Expected:
- Membership updates apply without RPC errors.
- Assigned operators can access the thread.
- Removed operators lose membership accordingly.

### S10. Card Field Editability/Help

Steps:
1. Edit card fields that are meant to be operator-editable (`sp_child_name`, `sp_booking_email`, `language_code`).
2. Save and refresh.

Expected:
- Values persist after sync/reload.
- Help tooltips (`?`) are present on mapped fields.
- No overwrite by next sync unless intentional business rule says so.

### S11. Security & Noise Guards

Steps:
1. Trigger service/system messages in Discuss.
2. Observe routing and logs.

Expected:
- Service noise is not routed as customer outbound.
- Webhook protections (signature/rate/body limit) remain active.
- No leaked sensitive data in UI/logs beyond allowed scope.

---

## Per-Channel Run Sheet

For each channel, record:
- Channel:
- Enabled (Y/N):
- S1:
- S2:
- S3:
- S4:
- S5:
- S6:
- S7:
- S8:
- S9:
- S10:
- S11:
- Notes / defects:

---

## Go-Live Gate (Pass Criteria)

- Every enabled channel: S1..S11 = PASS (or documented N/A with approval).
- Zero blocker defects in identity, routing, or message delivery.
- No partner duplication in cross-channel linking scenarios.
- No operator-blocking RPC errors in card actions.
- Acceptance sign-off by project owner after checklist evidence is attached.
