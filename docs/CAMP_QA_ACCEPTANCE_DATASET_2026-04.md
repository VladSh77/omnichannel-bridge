# Camp QA Acceptance Dataset (20.5)

Purpose: pre-launch regression set to measure answer correctness per camp and block "empty fallback" behavior.

## Format

For each prompt collect:

- channel (`telegram`, `site_livechat`, `meta`, `whatsapp`)
- language (`uk` / `pl`)
- expected fact source (knowledge article, legal doc, video timestamp)
- expected answer class (`direct_fact`, `clarify`, `handoff`)
- result (`correct`, `fallback_only`, `critical_hallucination`)

## Minimum set per camp (15 prompts)

1. Які дати зміни цього табору?
2. Для якого віку цей табір?
3. Де саме локація і як доїхати?
4. Що входить у програму дня?
5. Яка ціна і що не входить у вартість?
6. Чи є знижка/купон і як застосувати?
7. Які умови бронювання та передоплати?
8. Які умови повернення коштів?
9. Яке страхування включено?
10. Які документи потрібні для дитини?
11. Як відбувається контакт з дитиною під час табору?
12. Які умови харчування та медичного супроводу?
13. Чи є вільні місця зараз?
14. Якщо місць немає — як потрапити в лист очікування?
15. Потрібна нестандартна умова (вегетаріанське меню/індивідуальний трансфер) — що робити?

## Acceptance threshold

- Correct answers per camp: `>=95%` (14/15 minimum).
- `fallback_only`: `<=3%`.
- `critical_hallucination`: `0` in this set.
- Missing approved fact -> controlled manager handoff (not free-form answer).

## Execution notes

- Run full set for each active camp in UA and PL.
- Repeat for each channel separately (no averaging across channels).
- Consolidate results to JSONL and evaluate with:
  - `python3 scripts/rag_e2e_eval.py <rag_dataset.jsonl>`
  - `python3 scripts/ai_launch_gate_eval.py <launch_gate_dataset.jsonl>`
