# Manual Scenarios on Production DB Copy

This document defines the minimum manual integration scenarios to run on a production DB copy before enabling critical runtime features in production.

## Scope

- Omnichannel thread ingestion (Meta, Telegram, WhatsApp, Viber, site livechat)
- AI runtime behavior with strict grounding
- Reserve/sold-out flow
- Coupon/promo validation rules
- Legal/consent and payment wording guards

## Core Scenarios

1. Inbound mapping and partner linking
- Send one inbound message per provider.
- Verify thread creation in `discuss.channel`.
- Verify `omni_customer_partner_id` mapping and identity linking.

2. Sold-out reserve flow
- Use camp with zero seats.
- Ask availability.
- Verify reserve CTA, stage handoff, reserve entry creation, escalation notify.

3. Coupon and promo validation
- Apply valid public code to camp line.
- Apply same code second time for same partner (must fail).
- Verify category/template restrictions are respected.

4. Language and consent
- RU/BE inbound must not produce RU answer.
- UA/PL inbound should remain in client language.
- Verify legal notice and channel consent policy appear in bot context.

5. Payment wording guard
- Ask payment status with known invoice states.
- Verify wording follows ORM facts only.
- Unknown status must trigger uncertainty + manager handoff suggestion.

## Exit Criteria

- No P1/P2 failures.
- No critical mismatch between ORM facts and bot statements.
- No duplicate outbound in conflict-guard window.
- All above scenarios recorded with date, tester, and pass/fail.
