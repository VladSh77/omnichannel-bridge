# CHANGELOG — omnichannel_bridge

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
