# SendPulse REST API — публічний огляд (без секретів)

Офіційне кореневе URL: [https://api.sendpulse.com](https://api.sendpulse.com). Відповіді — **JSON**. Крос-доменні Ajax-запити з браузера не підтримуються документацією.

Повна документація методів: [SendPulse Service REST API](https://sendpulse.com/integrations/api).

---

## Авторизація

У кожному запиті заголовок:

```http
Authorization: Bearer <token>
```

**Два способи отримати токен:**

| Спосіб | Опис |
|--------|------|
| **API Key (статичний)** | Довгоживучий ключ: SendPulse → **Settings → API → API keys → Generate**. До **5** ключів; можна обмежити по **IP**. Зручно, коли не хочеться оновлювати OAuth. |
| **OAuth 2.0** | `POST https://api.sendpulse.com/oauth/access_token` з `grant_type=client_credentials`, `client_id`, `client_secret`. Токен типово **~1 год** — перевикористовувати до закінчення, не запитувати на кожен виклик (див. кеш у `sendpulse-odoo`). |

---

## Приклади методів (загальний акаунт)

| Що | HTTP | Шлях |
|----|------|------|
| Інфо про акаунт | GET | `/user/info` |
| Запрошені користувачі | GET | `/user/invited-users-list` |
| Баланс / тарифи | GET | `/user/balance/detail` |

У Odoo для месенджерів використовуються **окремі** шляхи (Telegram тощо), наприклад `https://api.sendpulse.com/telegram/contacts` — див. `sendpulse-odoo/models/sendpulse_connect.py` та [SENDPULSE_CONVERSATION_CARD_REFERENCE.md](./SENDPULSE_CONVERSATION_CARD_REFERENCE.md).

---

## Ліміти

Квоти **на хвилину / на день** залежать від тарифу; при перевищенні — **429 Too many requests**. Деталі — на сторінці [API](https://sendpulse.com/integrations/api).

---

## Локальна перевірка curl (ключ не в Git)

1. Скопіюй шаблон: `docs/SENDPULSE_API.local.env.example` → **`docs/SENDPULSE_API.local.env`** (файл **в .gitignore**, не комітити).
2. Встав **новий** ключ у змінну `SENDPULSE_API_KEY` (один рядок, без лапок якщо немає пробілів).
3. У терміналі з кореня репозиторію:

```bash
set -a && source docs/SENDPULSE_API.local.env && set +a
curl -sS -H "Authorization: Bearer ${SENDPULSE_API_KEY}" "https://api.sendpulse.com/user/info"
```

Для **zsh/bash** на macOS/Linux `source` очікує шлях до файлу з `KEY=value` без `export` можна додати в файл рядок `export SENDPULSE_API_KEY=...` або використати `export` у прикладі нижче.

**Безпека:** ключ з чату / скрінів вважати скомпрометованим — **ревок** у SendPulse і **новий** ключ лише в `.local.env` або в Odoo.

---

## Зв’язок з Odoo

- Прод: **client_id / client_secret** або налаштування модуля → `ir.config_parameter` (`odoo_chatwoot_connector.*`), не дублювати в markdown репозиторію.

---

*Файл без секретів; оновлено: 2026-04-10.*
