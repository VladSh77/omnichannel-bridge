# Camp Migration Map (20.4)

Purpose: per-camp migration map from legacy bot chains to `omnichannel_bridge`.

## Standard structure per camp

- Camp key
- Inbound triggers
- CTA variants
- Handoff rules
- Facts source (Odoo + knowledge)
- Channel smoke status (Telegram / Web / Meta / WhatsApp)

## Camp maps

| Camp | Trigger intents | CTA | Handoff rules | Facts source |
|---|---|---|---|---|
| Цивілізація-Camp | ціна, дати, програма, вік | залишити контакт / менеджер | legal/medical/payment conflict, explicit manager request | `product.template` + `omni.knowledge.article` |
| Chill-Camp Швейцарія | швейцарія, преміум, безпека, проживання | підбір зміни / контакт | unclear availability, insurance dispute | same |
| Дослідники морів KIDS (1/2) | море, kids, вік, логістика | уточнення віку/дат + бронь | missing facts -> manager | same |
| Дослідники морів PRO (1/2) | pro, старші діти, програма | підбір табору + контакт | payment/legal-sensitive | same |
| Амбер Кемп | amber, програма, розклад | підбір + контакт | sold-out/reserve | same |
| Чіл Кемп Закопане | закопане, польща, проживання | підбір зміни | out-of-scope / risk topic | same |
| Таємниця Долини Карпа | карпа, активності, дати | короткий підбір + CTA | explicit handoff | same |
| CampScout Франція | франція, travel camp | підбір + контакт | legal/insurance | same |
| CampScout Італія | італія, ріміні | підбір + контакт | no verified facts | same |
| No Borders | мандрівний, de/ch/fr | уточнення логістики | complex logistics -> manager | same |
| Підкова Кемп | кінний, програма | підбір + контакт | child safety sensitive | same |
| CampScout Португалія | португалія, закордон | підбір + контакт | docs/payment uncertainty | same |
| Пошумимо (1/2) | пошумимо, зміна | підбір + бронь | sold-out -> reserve | same |
| Рейд Кемп | рейд, тестова зміна | підбір + контакт | нестача фактів -> manager | same |
| CampScout Іспанія | іспанія, costa brava | підбір + контакт | legal/insurance | same |
| На вовчій стежці | вовча стежка, програма | підбір + контакт | conflict/confusion | same |

## Channel smoke matrix template (mandatory per camp)

| Camp | TG | Web | Meta | WhatsApp | Notes |
|---|---|---|---|---|---|
| Цивілізація-Camp | TODO | TODO | TODO | TODO | |
| Chill-Camp Швейцарія | TODO | TODO | TODO | TODO | |
| ... | ... | ... | ... | ... | ... |

## Acceptance for 20.4 closure

- Each camp has explicit trigger -> flow map.
- Facts for each camp are listed and traceable to Odoo/knowledge records.
- Smoke matrix filled and appended to `docs/IMPLEMENTATION_LOG.md`.
