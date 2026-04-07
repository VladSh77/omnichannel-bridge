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
3. **Налаштування → Omnichannel** (група System): Meta, розклад бота, **LLM** (увімкнути автовідповіді, бекенд **Ollama** або OpenAI, суворе підґрунтя фактів).
4. Альтернативно: **Продажі → Налаштування → Omnichannel → Integrations** — токени по компаніях.
5. Вебхуки:
   - Meta: `GET/POST` `https://<ваш-домен>/omni/webhook/meta`
   - Telegram: `POST` `https://<ваш-домен>/omni/webhook/telegram`

Деталі полів товарів (місця, умови для бота) — на формі шаблону продукту, група **Chatbot (Omnichannel)**. На картці клієнта (вкладка **Omnichannel**): **стиль звернення**, **зворот** («пані Ольго»), **пам’ять з чату** (доповнюється правилами з повідомлень). У ТЗ (§ 8.1) — **внутрішній Telegram-канал** для менеджера та керівника: потік по клієнтах + окремі сповіщення для проблемних і термінових кейсів (не плутати з клієнтським ботом у § 13).

## Документація для команди

| Документ | Призначення |
|----------|-------------|
| [docs/TZ_CHECKLIST.md](docs/TZ_CHECKLIST.md) | Повне ТЗ + чекліст готовності |
| [docs/TECHNICAL_PASSPORT.md](docs/TECHNICAL_PASSPORT.md) | Технічний паспорт модуля (архітектура, інтеграції, SLA) |
| [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) | Операційні процедури (інциденти, відновлення, rollback) |
| [docs/SECURITY_RODO.md](docs/SECURITY_RODO.md) | Правила безпеки та обробки даних (RODO/GDPR) |
| [docs/LEGAL_FACTS_PACK.md](docs/LEGAL_FACTS_PACK.md) | Дозволені юридичні факти для бота (джерела з camp repo) |
| [docs/TEST_PLAN.md](docs/TEST_PLAN.md) | Тест-план для локального/staging/prod контурів |
| [docs/STAGING_BLUEPRINT.md](docs/STAGING_BLUEPRINT.md) | Blueprint staging-середовища з parity вимогами |
| [docs/ENGINEERING_DESIGN_V1.md](docs/ENGINEERING_DESIGN_V1.md) | Технічний дизайн v1: idempotency + async queue + race guard |
| [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md) | Журнал реалізації (ведеться під час розробки) |
| `addons/omnichannel_bridge/__manifest__.py` | Залежності та дані модуля |

## Ліцензія модуля

Модуль `omnichannel_bridge` у маніфесті вказано як **LGPL-3** (як типово для Odoo-додатків). Юридичні умови всього продукту Fajna уточнюйте окремо.

---

*Оновлення статусів у чеклісті варто робити після кожного релізу модуля або спринту.*
