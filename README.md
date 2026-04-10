# 🤖 Omnichannel Bridge for Odoo 17

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-purple)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LLM](https://img.shields.io/badge/LLM-Ollama%20%2F%20qwen2.5-red)
![License](https://img.shields.io/badge/License-LGPL--3.0-green.svg)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)

**Developed by [Fayna Digital](https://fayna.agency) — Author: Volodymyr Shevchenko**

Єдиний робочий простір для менеджерів: діалоги з **Instagram, Facebook Messenger, Telegram** (та інших каналів за доробкою) агрегуються в **Odoo Discuss**, клієнти прив’язуються до **res.partner**, бот відповідає **лише на основі фактів, які Python збирає з Odoo** (каталог, ціни, квоти місць, оплати, поля картки, звернення на ім’я), плюс **локальний LLM (Ollama)** з відкритими вагами — без обов’язкових платних API та без купівлі модулів на маркетплейсі.

## Навіщо це (проблема SendPulse + Odoo)

| Було (типовий SendPulse-флоу) | Куди рухаємось |
|-------------------------------|----------------|
| Боти без повноцінного ШІ, жорсткі сценарії | LLM + дані з Odoo + керовані політики відповіді |
| Повторні питання (наприклад, адреса 10 разів) | Пам’ять діалогу / стан звернення / поля партнера |
| Довге очікування відповіді менеджера | Бот поза годинами / миттєві чернетки + ескалація |
| Помилки в текстах менеджера | (опційно) підказки / чернетки ШІ перед відправкою |
| Мало гнучкості під продажі | ТЗ рівня «відділ продажів»: акції, умови, страхові продукти, handoff |

Повний перелік вимог і статус реалізації — у **[чеклісті ТЗ](docs/TZ_CHECKLIST.md)**.

**Інтеграція з вашим Odoo:** у вас є **власні кастомні модулі** поза базовим Odoo — саме з ними мусить **співпрацювати** `omnichannel_bridge`. Тому логіку «квиток / подія / місця / резерв» і купони **не описують абстрактно в ТЗ** — її знімають **з вашого коду і БД на сервері** (`models/*.py`, ORM), а не з «типового» Odoo; переклади в UI додатково не завжди відповідають технічним іменам. Деталі — у ТЗ, розділ **«Інтеграція з існуючим Odoo»**.

## Структура репозиторію

```
Fajna/
├── addons/
│   └── omnichannel_bridge/    # кастомний модуль Odoo 17
├── docs/
│   └── TZ_CHECKLIST.md        # ТЗ у вигляді чекліста (готово / частково / ні)
├── requirements.txt           # Python-залежності для Odoo (requests, pytz)
└── README.md
```

## Стек (відкритий код / безкоштовно)

- **Odoo** (LGPL) + власний модуль у репозиторії.
- **Ollama** + модель з відкритими вагами (наприклад Llama, Mistral тощо) — інференс **на вашому сервері**; HTTP API без ліцензій App Store.
- **Python**: `requests`, `pytz` — лише для HTTP і часу; **факти для бота збираються ORM-запитами**, не «з голови» моделі.
- **OpenAI API** — **опційно** (пропрієтарний хмарний сервіс), якщо оберете бекенд `openai` у налаштуваннях.

## Вимоги

- **Odoo 17** (Community або Enterprise), Python 3.10+ (як у вашому образі Odoo).
- Модулі Odoo (залежності моста): `base_setup`, `mail`, `crm`, `sale_management`, `stock`, `account`.
- Для **Ollama**: встановлений сервіс (типово `http://127.0.0.1:11434`), завантажена модель; Odoo має мати мережевий доступ до Ollama.
- Для **Meta**: Page Access Token, App Secret, Verify Token, публічний HTTPS для вебхуків.

## Швидкий старт (розробка)

1. Додайте шлях до `addons/` у `addons_path` конфігурації Odoo.
2. Оновіть список додатків, встановіть модуль **Omnichannel Bridge**.
3. Перевірте, що `Website Live Chat` увімкнено як дефолтний канал (`site_livechat`) і віджет живого чату видимий на сайті.
4. **Налаштування → Omnichannel** (група System): Meta, розклад бота, **LLM** (увімкнути автовідповіді, бекенд **Ollama** або OpenAI, суворе підґрунтя фактів).
5. Альтернативно: **Продажі → Налаштування → Omnichannel → Integrations** — токени по компаніях.
6. Вебхуки (після валідації livechat-first):
   - Meta: `GET/POST` `https://<ваш-домен>/omni/webhook/meta`
   - Telegram: `POST` `https://<ваш-домен>/omni/webhook/telegram`

Деталі полів товарів (місця, умови для бота) — на формі шаблону продукту, група **Chatbot (Omnichannel)**. На картці клієнта (вкладка **Omnichannel**): **стиль звернення**, **зворот** («пані Ольго»), **пам’ять з чату** (доповнюється правилами з повідомлень). У ТЗ (§ 8.1) — **внутрішній Telegram-канал** для менеджера та керівника: потік по клієнтах + окремі сповіщення для проблемних і термінових кейсів (не плутати з клієнтським ботом у § 13).

## Delivery strategy (approved)

- Primary route: **direct provider integration** (Meta/Telegram/Website Live Chat -> `omnichannel_bridge`) without SendPulse in the main path.
- Backup route: **SendPulse as bridge** only if direct delivery fails release criteria for a wave.
- Migration rule: preserve compatibility mapping for SendPulse fields (`contact_id`, phone, email, avatar, language, profile URL) to enable fast fallback without redesign.

## Мовна політика модуля (UA/PL)

- Робочі мови інтерфейсу для команди: **українська** та **польська**.
- Англійська лишається технічним fallback для рядків без перекладу.
- Після оновлень модуля обов'язково:
  1. `-u omnichannel_bridge`
  2. оновлення перекладів (`uk_UA`, `pl_PL`) в Odoo.
- Для чат-відповідей клієнтам діє runtime-політика: UA/PL за мовою звернення; російська для відповідей не використовується.

## Останні зміни перед launch

- Окремий контур `Інсайти клієнта` з керованим доступом (тільки обрані користувачі).
- Livechat стабілізація: anti-loop, коректна атрибуція автора (guest/customer/bot), mobile chunking + pacing.
- Додано online-routing менеджерів: queue pool + round-robin тільки по `online`.
- В перших повідомленнях livechat показується доступний онлайн-менеджер (якщо є).
- Базу знань розширено з `camp` repo: компанія, гарантії, страхування, add-ons, RODO/contract/policies + картки таборів.

## Документація для команди

| Документ | Призначення |
|----------|-------------|
| [docs/TZ_CHECKLIST.md](docs/TZ_CHECKLIST.md) | Повне ТЗ + чекліст готовності |
| [docs/TZ_EXECUTION_QUEUE.md](docs/TZ_EXECUTION_QUEUE.md) | Черга виконання ТЗ з DoD по хвилях |
| [docs/TECHNICAL_PASSPORT.md](docs/TECHNICAL_PASSPORT.md) | Технічний паспорт модуля (архітектура, інтеграції, SLA) |
| [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) | Операційні процедури (інциденти, відновлення, rollback); **`-u` у Docker з `--no-http`**, дані playbook не з `camp` |
| [docs/SECURITY_RODO.md](docs/SECURITY_RODO.md) | Правила безпеки та обробки даних (RODO/GDPR) |
| [docs/LEGAL_FACTS_PACK.md](docs/LEGAL_FACTS_PACK.md) | Дозволені юридичні факти для бота (джерела з camp repo) |
| [docs/TEST_PLAN.md](docs/TEST_PLAN.md) | Тест-план для локального/staging/prod контурів |
| [docs/CHANNEL_PARITY_E2E_CHECKLIST.md](docs/CHANNEL_PARITY_E2E_CHECKLIST.md) | Канальний E2E checklist (S1..S11) перед go-live |
| [docs/MIGRATION_GO_LIVE_PLAYBOOK.md](docs/MIGRATION_GO_LIVE_PLAYBOOK.md) | Покроковий план міграції ботів SendPulse/каналів у Odoo |
| [docs/CAMP_MIGRATION_MAP_2026-04.md](docs/CAMP_MIGRATION_MAP_2026-04.md) | Пер-camp migration map (20.4) |
| [docs/FAQ_MASTER_REGISTRY_2026-04.md](docs/FAQ_MASTER_REGISTRY_2026-04.md) | Master FAQ/objections registry + source traceability (20.5) |
| [docs/RAG_E2E_ACCEPTANCE_2026-04.md](docs/RAG_E2E_ACCEPTANCE_2026-04.md) | E2E retrieval/answer quality gates (20.7) |
| [docs/AI_ONLY_LAUNCH_GATE_2026-04.md](docs/AI_ONLY_LAUNCH_GATE_2026-04.md) | AI-only + phase gating criteria (20.9/20.10) |
| [docs/SENDPULSE_CONVERSATION_CARD_REFERENCE.md](docs/SENDPULSE_CONVERSATION_CARD_REFERENCE.md) | Еталон «карти розмови» SendPulse в Odoo: поля, форма, панель, зв’язки (паритет § 20.8) |
| [docs/STAGING_BLUEPRINT.md](docs/STAGING_BLUEPRINT.md) | Blueprint staging-середовища з parity вимогами |
| [docs/ENGINEERING_DESIGN_V1.md](docs/ENGINEERING_DESIGN_V1.md) | Технічний дизайн v1: idempotency + async queue + race guard |
| [docs/PROD_CAMP_MAPPING_AUDIT_2026-04-08.md](docs/PROD_CAMP_MAPPING_AUDIT_2026-04-08.md) | Read-only аудит прод-мепінгу місць (кастомні модулі + DB) |
| [docs/LIVECHAT_ENTRY_UX_TREE.md](docs/LIVECHAT_ENTRY_UX_TREE.md) | Узгоджене дерево livechat entry (UA/PL) + правила contact-first/free-text |
| [docs/STAGING_META_TEST_PAGE.md](docs/STAGING_META_TEST_PAGE.md) | Чекліст staging-прогону Meta test page перед прод-релізом |
| [docs/BACKUP_RESTORE_DRILL.md](docs/BACKUP_RESTORE_DRILL.md) | Процедура drill для backup/restore (DB + filestore + chat integrity) |
| [docs/SECRET_ENCRYPTION_POLICY.md](docs/SECRET_ENCRYPTION_POLICY.md) | Базова політика шифрування/ротації секретів інтеграцій |
| [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md) | Журнал реалізації (ведеться під час розробки) |
| `addons/omnichannel_bridge/__manifest__.py` | Залежності та дані модуля |

## Ліцензія модуля

Модуль `omnichannel_bridge` у маніфесті вказано як **LGPL-3** (як типово для Odoo-додатків). Юридичні умови всього продукту Fajna уточнюйте окремо.

---

*Оновлення статусів у чеклісті варто робити після кожного релізу модуля або спринту.*
