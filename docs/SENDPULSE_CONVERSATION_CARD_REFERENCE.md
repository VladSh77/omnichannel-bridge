# Еталонна «карта розмови» SendPulse в Odoo — повний розбір

Документ фіксує **реальну реалізацію** в модулі **SendPulse Odo** (репозиторій `sendpulse-odoo`, технічне ім’я Python/XML-модуля **`odoo_chatwoot_connector`**, шляхи в `__manifest__.py` починаються з `odoo_chatwoot_connector/…`). Потрібен для паритету **`omnichannel_bridge`** з еталоном UI/даних.

**Пов’язано:** сценарій **вітального ланцюжка CampScoutbot** у конструкторі SendPulse (змінні, кнопки, гілки меню) — [SENDPULSE_CAMPSCOUTBOT_WELCOME_FLOW.md](./SENDPULSE_CAMPSCOUTBOT_WELCOME_FLOW.md).  
**REST API (огляд, curl, куди класти локальний ключ):** [SENDPULSE_REST_API_PUBLIC_OVERVIEW.md](./SENDPULSE_REST_API_PUBLIC_OVERVIEW.md).

---

## 1. Два пов’язані UI (одна розмова)

| Поверхня | Файли | Призначення |
|----------|--------|-------------|
| **Бічна панель Discuss** | OWL-клас **`SendpulseInfoPanel`** (`sendpulse_info_panel.js`), шаблон `odoo_chatwoot_connector.SendpulseInfoPanel` (`sendpulse_info_panel.xml`); реєстрація **`sendpulse_thread_actions.js`** (`sendpulse-client-info`) | Компактна картка; RPC `sendpulse.connect.get_connect_for_channel(channel_id)` |
| **Модальна форма «карта розмови»** | `sendpulse-odoo/views/sendpulse_connect_views.xml` → `view_sendpulse_connect_form`, модель `sendpulse.connect` | Повний екран полів + вкладка історії повідомлень; відкривається з панелі через `action.doAction({ res_model: "sendpulse.connect", res_id, views: [[false,"form"]], target: "new" })` (`sendpulse_info_panel.js`, `onOpenFormClick`) |

Заголовок вікна в клієнті Odoo часто показує бренд **«Odoo»** у шапці модалки — це **стандарт web-клієнта**, не `string` форми. У XML форма має `string="Розмова SendPulse"`.

---

## 2. Модель `sendpulse.connect` — поля та відповідальність

Джерело: `sendpulse-odoo/models/sendpulse_connect.py`.

### 2.1 Ідентифікація та життєвий цикл

| Поле | Тип | Підпис у формі / зміст |
|------|-----|-------------------------|
| `name` | Char | Ім’я контакту (обов’язкове, індекс); у списку «Контакт» |
| `partner_id` | Many2one `res.partner` | Секція **«Клієнт»** — якщо порожньо, контакт не ідентифікований; у скріншоті може бути технічний/гостьовий запис на кшталт «Public User» |
| `stage` | Selection | **Statusbar** у шапці форми: `new` → **Новий**, `in_progress` → **В роботі**, `new_message` → **Нове повідомлення**, `close` → **Закрито** |
| `stage_sort` | Integer computed, stored | Внутрішнє сортування списку (не на формі) |

### 2.2 Канал месенджера

| Поле | Тип | Секція **«Канал»** |
|------|-----|---------------------|
| `service` | Selection `SERVICE_SELECTION` | Telegram, Instagram, Facebook, Messenger, Viber, WhatsApp, TikTok, LiveChat |
| `social_username` | Char | Підпис **Username** |
| `social_profile_url` | Char | **URL профілю**, віджет `url` |
| `bot_name` | Char | **Бот** (назва бота SendPulse) |
| `bot_id` | Char | У формі не показано окремо (є в моделі) |

### 2.3 SendPulse / API

| Поле | Тип | Секція **«Профіль SendPulse»** / **«SendPulse»** |
|------|-----|--------------------------------------------------|
| `avatar_url` | Char | У формі: **Аватар (URL)** (`widget="url"`), `invisible` якщо порожньо |
| `language_code` | Char | **Мова** |
| `subscription_status` | Selection | **Статус підписки**: active → «Активний», unsubscribed, deleted, unconfirmed |
| `sendpulse_contact_id` | Char | **Contact ID** (UUID у SendPulse) |
| `last_message_date` | Datetime | **Останнє повідомлення** (час) |
| `last_message_preview` | Char | У дереві списку; на формі в описі логіки |
| `channel_id` | Many2one `discuss.channel` | **Discuss Канал** — зв’язок 1:1 з тредом Odoo Discuss |

### 2.4 Змінні бота (збір у боті SendPulse)

| Поле | Тип | Секція **«Дані бота»** |
|------|-----|-------------------------|
| `sp_child_name` | Char | **Ім'я дитини** (`child_name` з variables API) |
| `sp_booking_email` | Char | **Email бронювання** (`booking_email`) |

Заповнення з API: `_extract_contact_vals()` після `action_fetch_contact_info()`.

### 2.5 Оператори та неідентифікований контакт

| Поле | Тип | Секція |
|------|-----|--------|
| `user_ids` | Many2many `res.users` | **«Оператори»**, віджет `many2many_tags`, domain без portal-користувачів |
| `unidentified_email` | Char | Показ **лише якщо** `partner_id` порожній — **Email (з SendPulse)** |
| `unidentified_phone` | Char | Аналогічно — **Телефон** |

### 2.6 Повідомлення (вкладка)

| Поле | Тип | Вкладка **«Повідомлення»** |
|------|-----|----------------------------|
| `message_ids` | One2many → `sendpulse.message` | Дерево: **Дата** (`date`), **Напрямок** (`direction`: incoming/outgoing), **Текст** (`text_message`), **Вкладення** (`attachment_url`) |

Модель **`sendpulse.message`**: `sendpulse-odoo/models/sendpulse_message.py` — `raw_json`, обчислюваний `text_message`, `direction`, `message_type`, `attachment_url`.

---

## 3. Форма `view_sendpulse_connect_form` — структура XML

Файл: `sendpulse-odoo/views/sendpulse_connect_views.xml`, запис `view_sendpulse_connect_form`.

### 3.1 Header (кнопки + statusbar)

| Кнопка / елемент | `name` методу | Умова `invisible` |
|------------------|---------------|-------------------|
| **Відкрити чат** | `action_open_discuss` | `stage == 'close'` |
| **Ідентифікувати клієнта** | `action_identify_partner` | `partner_id != False` або `stage == 'close'` |
| **Оновити профіль** | `action_fetch_contact_info` | `not sendpulse_contact_id` |
| **Закрити розмову** | `action_close` | `stage == 'close'` |
| **Відновити** | `action_reopen` | `stage != 'close'` |
| **Statusbar** | `field name="stage"` | `statusbar_visible="new,in_progress,new_message,close"` |

`action_open_discuss` повертає `ir.actions.client` з `tag: mail.action_discuss` і `context.active_id` = `channel_id` (див. `sendpulse_connect.py`).

### 3.2 Sheet — сітка груп (двоколонковий макет Odoo)

1. **Ряд 1:** `group` → ліва **«Клієнт»** (`partner_id`, умовно `unidentified_email`, `unidentified_phone`), права **«Канал»** (`service`, `social_username`, `social_profile_url`, `bot_name`).
2. **Ряд 2:** ліва **«Дані бота»** (`sp_child_name`, `sp_booking_email`), права **«Профіль SendPulse»** (`avatar_url`, `language_code`, `subscription_status`).
3. **Ряд 3:** ліва **«Оператори»** (`user_ids`), права **«SendPulse»** (`sendpulse_contact_id`, `last_message_date`, `channel_id`).
4. **Notebook** → сторінка **«Повідомлення»**: `message_ids` у `tree readonly`.

Стандартний **footer** Odoo: **Зберегти** / **Відмінити** — додає web-клієнт для редагованої форми.

### 3.3 Розміри та геометрія (що зафіксовано в коді)

| Елемент | Значення | Де |
|---------|----------|-----|
| Ширина бічної панелі SendPulse | `width: 280px; min-width: 240px` | `sendpulse_info_panel.xml`, кореневий `div.o-sendpulse-InfoPanel` |
| Аватар у панелі | `64px × 64px`, `rounded-circle` | той самий файл, блок аватара |
| Іконки в рядках контакту | ширина іконки `14px` | `sendpulse_info_panel.xml` |
| Префікси назв каналів для Discuss | `[TG]`, `[IG]`, `[FB]`, `[MSG]`, `[VB]`, `[WA]`, `[TT]`, `[LC]` | `sendpulse_thread_actions.js` |

Модальна форма **не** задає явну ширину в XML — розмір визначає **Odoo Dialog** (залежить від теми / `dialog_size` у action, тут `target="new"` без кастомного класу в цьому action).

---

## 4. Зв’язок з `discuss.channel`

Файл: `sendpulse-odoo/models/mail_channel.py`, `_inherit = 'discuss.channel'`.

- Поле **`sendpulse_connect_id`** → Many2one на `sendpulse.connect`.
- **`_to_store`**: у store потрапляє `sendpulse_connect_id` для фронтенду.
- **`thread_patch.js`**: на об’єкт Thread мапиться `sendpulseConnectId` (camelCase).

Створення каналу: `DiscussChannel.sendpulse_channel_get` — ім’я на кшталт `[{service_label}] {connect.name}`.

---

## 5. Майстер ідентифікації

- Модель: `sendpulse.identify.wizard` — `sendpulse-odoo/models/sendpulse_identify_wizard.py`, views `sendpulse_identify_wizard_views.xml`.
- Відкриття: `sendpulse.connect.action_identify_partner` з `default_connect_id` у контексті.

---

## 6. Додаткові посилання в репозиторії SendPulse

| Що | Шлях |
|----|------|
| Детальна технічна документація (діаграми, потоки) | `sendpulse-odoo/TECHNICAL_DOCS.md` |
| Форма окремого повідомлення | `view_sendpulse_message_form` у `sendpulse_connect_views.xml` |
| Меню «Всі розмови» / «Нові чати» | `action_sendpulse_connect_*` у тому ж XML |
| Webhook вхід | `sendpulse-odoo/controllers/main.py` → `_process_incoming_event` на `sendpulse.connect` |

---

## 7. Відповідність у `omnichannel_bridge` (орієнтир, не 1:1)

| SendPulse | Omnichannel (поточний задум) |
|-----------|------------------------------|
| `sendpulse.connect` (центральний запис розмови) | **`discuss.channel`** (`omni_*` поля) + дзеркало **`omni.inbox.thread`** для операторського інбоксу |
| `partner_id` на connect | `discuss.channel.omni_customer_partner_id` + `omni.inbox.thread.partner_id` |
| `message_ids` / `sendpulse.message` | **`mail.message`** на `discuss.channel` (немає окремої таблиці-логу як `sendpulse.message` у bridge) |
| `stage` + statusbar | Частково **`omni.inbox.thread.operator_status`** та поля каналу; **повного FSM як у SendPulse в одній моделі** немає |
| `user_ids` (оператори на розмові) | Не дубльовано тією ж семантикою на `omni.inbox.thread` |
| Панель Discuss | **`OmniClientInfoPanel`** + RPC `discuss.channel.omni_get_client_info_for_channel` |
| Модалка «карта розмови» | Замість форми рівня `sendpulse.connect`: **`view_omni_inbox_thread_form_conversation`** + майстри; **візуально не клон форми SendPulse** (зафіксовано в `TZ_CHECKLIST` § 20.8.1) |

---

## 8. Відповідність скріншоту (чекліст)

- Верхні кнопки: **Відкрити чат**, **Оновити профіль**, **Закрити розмову** / **Відновити** + **statusbar** стадій — відповідають `header` у `view_sendpulse_connect_form`.
- Ліва колонка: **Клієнт**, **Дані бота**, **Оператори** — групи з тими ж `string` у XML.
- Права: **Канал**, **Профіль SendPulse**, **SendPulse** — відповідають другій колонці груп.
- Нижче: вкладка **Повідомлення** з колонками дата / напрямок / текст / вкладення — `message_ids` tree.
- Сині «?» біля підписів — **підказки Odoo** з `help` на полях моделі або з перекладів; у XML форми явних `widget` для цього не потрібно.

---

*Останнє оновлення змісту документа: 2026-04-10 (додано посилання на вітальний flow CampScoutbot). Репозиторій еталону: `sendpulse-odoo` (модуль `odoo_chatwoot_connector`).*
