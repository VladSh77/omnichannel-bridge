# Legal Facts Pack — Camp Domain Baseline

## Purpose

This file defines approved legal fact sources for bot responses in camp sales scenarios.
Bot responses on legal topics must be grounded in these sources only.

## Source of Truth (Repository Paths)

- `camp/knowledge-base/legal/terms.html`
- `camp/knowledge-base/legal/rodo.html`
- `camp/knowledge-base/legal/cookie-policy.html`
- `camp/knowledge-base/legal/child-protection.html`
- `camp/knowledge-base/legal/umowa-v1-2026.html` (archive reference only)

## Usage Rules

- Prefer linking to canonical pages instead of freeform legal interpretation.
- Do not invent legal statements not explicitly present in approved sources.
- Archived contract (`umowa-v1-2026`) is historical and non-current.

## Canonical Live URLs (from legal package)

- `https://campscout.eu/terms`
- `https://campscout.eu/privacy-policy`
- `https://campscout.eu/cookie-policy`
- `https://campscout.eu/child-protection`

## Public campaign landing (marketing baseline, not price authority)

- **URL:** [CampScout 2026 — лендінг «Літо 2026»](https://lato2026.campscout.eu/)
- **Призначення для бота:** назви програм і напрямків, загальний тон преміум-продукту, **посилання** на Telegram / WhatsApp / форму заявки, публічні формулювання про ліцензію, гарантії, методологію — як **орієнтир для діалогу** і для відправки клієнта на сторінку з деталями.
- **Не є джерелом правди для:** конкретної **ціни в чаті**, **вільних місць**, **доступності зміни**, індивідуального розрахунку розстрочки — усе це лише з **Odoo ORM** (товари, події, реєстрації, кастомні поля) згідно з політикою strict grounding.
- **Юридичні формулювання в чаті:** якщо питання юридичне або суперечливе — посилання на блок **Canonical Live URLs** вище, не «переписувати» договір з лендінгу з пам’яті моделі.

## Legal Response Boundaries

- Bot can provide concise factual pointers.
- Bot must escalate to manager for disputed, sensitive, or case-specific legal questions.
- Any child safety concern is immediate human escalation.

## Next Step (Implementation)

- Move key legal facts into a structured Odoo model or managed config block.
- Version legal facts with changelog and effective dates.
