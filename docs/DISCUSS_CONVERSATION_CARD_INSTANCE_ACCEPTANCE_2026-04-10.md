# Discuss Conversation Card Instance Acceptance (20.8.1)

Date: 2026-04-10

Acceptance step:
1. Upgrade module: `-u omnichannel_bridge`.
2. Refresh frontend assets.
3. Open omnichannel thread in Discuss.
4. Click external-link icon in client mini-card.

Expected:
- Opens dialog with title `Картка розмови`.
- Does not open direct Odoo contact form as first action.

Result:
- PASS.
- Dialog opens `omni.inbox.thread` conversation card flow with parity layout sections.
