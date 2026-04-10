# FAQ Master Registry (20.5)

Purpose: unified FAQ/objection registry with approved answers and source traceability.

## Schema

- `category`
- `question`
- `answer_ua`
- `answer_pl`
- `answer_en_fallback`
- `source_type` (`knowledge_article` / `policy_doc` / `youtube`)
- `source_ref` (URL or record key)
- `source_timestamp` (for youtube)
- `editorial_approved` (yes/no)

## Initial categories

- price_budget
- dates_period
- location_logistics
- safety_children
- legal_contract
- payments_refunds
- food_medical
- contact_manager

## Minimum registry (starter)

| category | question | source_type | source_ref | editorial_approved |
|---|---|---|---|---|
| price_budget | Яка ціна табору? | knowledge_article | `omni.knowledge.article` camp cards | yes |
| dates_period | Які є дати зміни? | knowledge_article | camp cards + Odoo events | yes |
| location_logistics | Де табір і як доїхати? | knowledge_article | camp cards/logistics | yes |
| safety_children | Як забезпечена безпека дітей? | policy_doc | `docs/LEGAL_FACTS_PACK.md` | yes |
| legal_contract | Де умови договору/RODO? | policy_doc | canonical legal URLs | yes |
| payments_refunds | Як оплата/повернення? | policy_doc | contract + payment policy | yes |
| food_medical | Харчування/медсупровід? | knowledge_article | FAQ/common + camp cards | yes |
| contact_manager | Хочу менеджера | policy_doc | handoff policy | yes |

## YouTube traceability policy

- YouTube facts can be used only with:
  - concrete video URL,
  - exact timestamp,
  - editorial approval flag.
- No unapproved YouTube snippet may enter production KB context.

## 95% pre-launch test set requirement

- Minimum 10-15 prompts per camp.
- Score metric:
  - correct factual answer,
  - no critical hallucination,
  - proper fallback/handoff when fact missing.
- Pass gate: `>=95%` correct.
