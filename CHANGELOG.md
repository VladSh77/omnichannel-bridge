# CHANGELOG — omnichannel_bridge

## [17.0.1.0.48] — 2026-04-10

### Додано

- `data/omni_kb_ai_source_hierarchy.xml` — стаття бази знань про **ієрархію джерел** (каталог vs юридичні документи vs OCR-брошура); не генерується з `camp/knowledge-base`.

### Змінено

- Версія модуля **17.0.1.0.48**; маніфест підключає новий data-файл після `omni_camp_knowledge_articles.xml`.
- Документація: `docs/IMPLEMENTATION_LOG.md`, `docs/TZ_CHECKLIST.md`, `docs/TZ_EXECUTION_QUEUE.md`; контрактний тест на наявність seed у маніфесті.

## [17.0.1.0.47] — 2026-04-10

### Змінено

- **`omni_knowledge`:** блок пріоритету джерел для LLM, rerank RAG для «юридичних» запитів (документи ↑, брошура OCR ↓), константа **`_OMNI_LEGAL_RAG_HINT_TERMS`**.
- **`omni_ai`:** у **`_STRICT_POLICY_UK`** додано правило: договір / legal / RODO / cookies — за **LEGAL_CONTEXT**, **LEGAL_DOCUMENTS** та офіційними URL, а не за полем умов у каталозі чи OCR.

## [17.0.1.0.45] — 2026-04-10

### Додано

- `data/omni_playbook_defaults.xml` — стартові **переходи етапів** (`omni.stage.transition`), **правило модерації** (кризовий маркер), **політики заперечень** (`omni.objection.policy`); `noupdate="1"`.
- `data/omni_legal_documents.xml` — початкові записи юридичних документів (узгоджено з маніфестом).

### Змінено

- Версія модуля **17.0.1.0.45**; підключення нових data-файлів у `__manifest__.py`.
- Українські підписи полів і UI для **Операції** (політики заперечень, модерація, переходи, база знань тощо); оновлення `uk_UA.po` / `pl.po`.
- База знань (XML + генератор): UA для cookie/child policy, поля джерела в скрипті генерації.
- Документація: `docs/IMPLEMENTATION_LOG.md`, `docs/OPERATIONS_RUNBOOK.md` (оновлення модуля в Docker з `--no-http`), примітки в `docs/TZ_CHECKLIST.md`, `docs/TZ_EXECUTION_QUEUE.md`.

### Операційно

- Продакшен CampScout: після `git pull` виконано `-u omnichannel_bridge` з **`--no-http`** (див. runbook).

## [0.1.0] — 2026-04-04

### Додано
- `omni_bridge` — основний міст: routing вебхуків, маппінг каналів, бот on/off логіка
- `omni_ai` — LLM інтеграція (Ollama / OpenAI), промпт-менеджер, strict grounding
- `omni_knowledge` — збір фактів з Odoo ORM (продукти, події, квоти місць, ціни)
- `omni_memory` — пам'ять діалогу: стиль звернення, зворот, нотатки з чату
- `omni_partner_identity` — ідентифікація клієнта по platform ID → res.partner
- `omni_sales_intel` — аналіз намірів, стан угоди, ескалація до менеджера
- `omni_integration` — конфігурація каналів (Meta токени, Telegram bot token)
- `mail_channel` — розширення: поля omnichannel, bot_active, assigned_manager
- `res_partner` — розширення: вкладка Omnichannel, стиль звернення, пам'ять
- `product_template` — розширення: поля для бота (квоти, умови, chatbot група)
- `res_config_settings` — глобальні налаштування: LLM бекенд, розклад бота, kill switch
- Controllers: `GET/POST /omni/webhook/meta`, `POST /omni/webhook/telegram`
- Views: omni_integration, mail_channel, res_partner (вкладка), product_template, settings
- Security: `ir.model.access.csv` для всіх нових моделей
- `docs/TZ_CHECKLIST.md` — повне ТЗ з чеклістом готовності
- `MEMORY.md` — архітектурні рішення, критичні застереження продакшену
