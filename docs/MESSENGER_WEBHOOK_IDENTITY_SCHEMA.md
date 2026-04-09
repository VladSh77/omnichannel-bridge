# Схеми webhook / identity для каналів Omnichannel Bridge

Документ фіксує **публічні** контракти API (офіційна документація та типові payload), відображення їх у **`omni.partner.identity.metadata_json`**, і поля бічної картки Discuss. Мета — не переробляти каркас після підключення реальних ключів і вебхуків.

Оновлювати цей файл при зміні збереженої форми metadata або додаванні провайдера.

---

## Загальні правила

1. У webhook **не** покладатися на PII, якого немає в payload (наприклад, ім’я людини в Meta часто потребує окремого Graph API з дозволами).
2. У UI **не** виводити сирі дампи webhook; тільки змістові рядки та дозволені посилання (`t.me`, `wa.me`, `m.me`, публічний URL аватара Viber тощо).
3. Ключі в `metadata_json` узгоджені з кодом: див. колонку «Наші ключі».

---

## Telegram (live)

| Джерело | URL |
|--------|-----|
| Bot API, типи User / Chat / getChat | https://core.telegram.org/bots/api#user , `#chat` , метод getChat |

| Поле Bot API | Наші ключі | Примітка |
|--------------|------------|----------|
| `message.from` (User) | `telegram`, `chat` (через merge у `res.partner`) | id, is_bot, is_premium, username, language_code |
| getChat | `tg_getchat` | bio, active_usernames, birthdate, custom emoji ids |
| contact message | `telegram_contact` | phone_number, vcard |

**Webhook:** власний формат оновлень Telegram; модуль збагачує identity через merge-логіку в `res.partner`.

---

## Meta: Messenger та Instagram Direct (live)

| Джерело | URL |
|--------|-----|
| Webhooks, формат `messaging` | https://developers.facebook.com/docs/messenger-platform/webhooks/ |
| Події | https://developers.facebook.com/docs/messenger-platform/reference/webhook-events/ |

Типовий фрагмент вхідного повідомлення:

```json
{
  "object": "page",
  "entry": [{
    "messaging": [{
      "sender": { "id": "<PSID>" },
      "recipient": { "id": "<PAGE_OR_IG_ID>" },
      "timestamp": 1234567890,
      "message": { "mid": "...", "text": "..." }
    }]
  }]
}
```

Для Instagram у полі `object` приходить `instagram` (аналогічна вкладена структура `messaging`).

| Поле webhook | Наші ключі | Примітка |
|--------------|------------|----------|
| Увесь `messaging[]` елемент | `meta_messaging_event` | обгортка в metadata |
| `object` (page / instagram) | `meta_webhook_object` | для підзаголовка картки |
| `sender.id` | `external_id` у identity + поля картки | PSID / IGSID залежно від продукту |

**Обмеження:** ім’я та аватар клієнта з webhook **зазвичай не приходять**; потрібні окремі виклики Graph API та дозволи застосунку. У картці показуємо надійно відомі ідентифікатори та посилання `m.me/<PSID>` де доречно.

---

## WhatsApp Cloud API (live)

| Джерело | URL |
|--------|-----|
| Webhook `messages` | https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages/ |

Структура `value` (спрощено):

- `messaging_product`: `"whatsapp"`
- `metadata`: `display_phone_number`, `phone_number_id`
- `contacts[]`: `wa_id`, `profile.name`
- `messages[]`: `from`, `id`, `timestamp`, `type`, типові вкладені об’єкти (`text.body`, тощо)

| Поле | Наші ключі | Примітка |
|------|------------|----------|
| Повний знімок для identity | `whatsapp_cloud` | `message`, `contacts`, `metadata` value (опційно) |
| `messages[].from` | усередині `whatsapp_cloud.message` + дубль для сумісності | основний zовнішній id |
| `contacts[].profile.name` | усередині `whatsapp_cloud.contacts` | відображення в картці |

**Зворотна сумісність:** старі identity, де в metadata збережено лише об’єкт повідомлення без обгортки, продовжують оброблятися (поле `from` на верхньому рівні).

---

## Twilio — вхідний WhatsApp (live)

| Джерело | URL |
|--------|-----|
| Webhook request parameters | https://www.twilio.com/docs/messaging/guides/webhook-request |

Типові поля форми: `MessageSid`, `From` (на кшталт `whatsapp:+...`), `To`, `Body`, `ProfileName`.

| Поле | Наші ключі | Примітка |
|------|------------|----------|
| Усе тіло запиту (JSON/форми) | metadata_json як об’єкт | парсинг у коді картки |

---

## Viber Public Accounts / Bot API (live)

| Джерело | URL |
|--------|-----|
| REST Bot API, callbacks | https://developers.viber.com/docs/api/rest-bot-api/ |

Callback `event: message` містить зокрема:

- `sender.id`, `sender.name`, `sender.avatar`, `sender.country`, `sender.language`
- `message.type`, `message.text`, …

| Поле | Наші ключі | Примітка |
|------|------------|----------|
| Повний callback JSON | metadata_json | аватар — URL, можна показати як посилання |

Підпис: заголовок `X-Viber-Content-Signature`.

---

## Живий чат сайту (live)

Не webhook зовнішнього месенджера: клієнт — гість Odoo Discuss / віджет. Identity може бути без багатого metadata; картка покладається на `res.partner` і поля каналу.

---

## TikTok (stub у модулі)

| Джерело (огляд) | URL |
|-----------------|-----|
| Webhooks overview | https://developers.tiktok.com/doc/webhooks-overview/ |
| Портал Business API | https://business-api.tiktok.com/portal |

Продуктові лінії (реклама, Shop, повідомлення бізнесу) мають **різні** портали та обмеження доступу. До появи реалізації в `omni.bridge` маршрут `/omni/webhook/tiktok` не обробляє бізнес-логіку; у реєстрі провайдерів канал позначений як **stub** (див. `utils/omni_provider_contracts.py`).

**План:** після отримання доступу до конкретного API — зафіксувати приклад JSON у цьому файлі та додати `tiktok` у `DELIVERY_LIVE` + обробник webhook.

---

## LINE Messaging API (stub у модулі)

| Джерело | URL |
|--------|-----|
| Огляд Messaging API | https://developers.line.biz/en/docs/messaging-api/overview/ |

Формат webhook подій (текст, sticker, follow тощо) описаний у документації LINE; реалізація в модулі — **stub** до підключення каналу.

---

## Мапінг на Discuss «Картка клієнта»

Бекенд збирає `channel_profile` у `discuss.channel.omni_get_client_info_for_channel`:

- `badges` — залежно від каналу (Telegram: Premium; усі live: «Активний» де доречно; stub: «Заглушка»).
- `section.rows` — текстові рядки та `link` з офіційно обґрунтованими URL.
- Контактний рядок: `identity.username` / `profile_url` / `contact_icon` за провайдером.

---

## Реєстр стану в коді

Актуальний список `live` / `stub`: **`omnichannel_bridge.utils.omni_provider_contracts`**, словник `OMNI_PROVIDER_DELIVERY`.
