# ТЗ: Кастомний шаблон підтвердження замовлення (sale.order)

**Статус:** Готовий до реалізації  
**Пріоритет:** ⭐ (зірочка від Volodymyr)  
**Дата:** 2026-04-13  
**Цільовий шаблон Odoo:** "Sales: Order Confirmation" (`mail.template` ID=18, model=`sale.order`)

---

## Мета

Замінити стандартний Odoo email підтвердження замовлення (`sale.order_confirmation_mail`) на брендований шаблон CampScout в стилі компанії (червоний акцент `#952426`, україномовний, Segoe UI).

---

## Спосіб реалізації

Перевизначити шаблон через `data/` XML в `omnichannel_bridge` (або `campscout_management`):

```xml
<record id="sale.order_confirmation_mail" model="mail.template" forcecreate="False">
    <field name="body_html"><![CDATA[...HTML нижче...]]></field>
</record>
```

---

## HTML шаблон (зразок від Volodymyr, 2026-04-13)

```html
<div style="margin: 0; padding: 20px; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #333; background-color: #f4f4f4;">
    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e1e1e1; box-shadow: 0 4px 6px #f2f2f2;">
        
        <div style="padding: 30px 40px 10px 40px; border-top: 6px solid #952426;">
            <t t-set="tx_sudo" t-value="object.get_portal_last_transaction()"></t>
            <h2 style="box-sizing:border-box;line-height:1.2;font-family:'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Ubuntu, 'Noto Sans', Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';margin: 0; font-size: 24px; color: #952426; font-weight: 600;">
                Чудова новина! 🎉
            </h2>
            <p style="box-sizing:border-box;margin:15px 0 16px 0; font-size: 15px; line-height: 1.6; color: #444;">
                Вітаємо! Ваше замовлення <strong t-out="object.name or ''" style="box-sizing:border-box;font-weight:bolder;">S00049</strong> на суму <strong t-out="format_amount(object.amount_total, object.currency_id)" style="box-sizing:border-box;font-weight:bolder;"></strong> 
                <t t-if="object.state == 'sale' or (tx_sudo and tx_sudo.state in ('done', 'authorized'))">
                    <span style="color: #28a745; font-weight: bold;">підтверджено</span>. Дякуємо за довіру!
                </t>
                <t t-elif="tx_sudo and tx_sudo.state == 'pending'">
                    <span style="color: #CE4C21; font-weight: bold;">очікується</span>. Буде підтверджено після отримання оплати.
                </t>
            </p>
        </div>

        <div style="padding: 0 40px;">
            <t t-foreach="object.order_line" t-as="line">
                <t t-if="not line.display_type">
                    <table width="100%" style="box-sizing: border-box; caption-side: bottom; border-collapse: collapse; font-size: 13px; color: #454748; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
                        <thead style="border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;">
                            <tr style="border-style:solid;box-sizing:border-box;border-bottom-color:#952426;border-left-width:0px;border-bottom-width:2px;border-right-width:0px;border-top-width:0px;border-bottom: 2px solid #952426;">
                                <th align="left" style="border-style:none;box-sizing:border-box;font-weight:500;padding: 10px 5px;">Послуга</th>
                                <th align="center" style="border-style:none;box-sizing:border-box;font-weight:500;padding: 10px 5px;">Кіл-ть</th>
                                <th align="right" style="border-style:none;box-sizing:border-box;font-weight:500;padding: 10px 5px;">Сума</th>
                            </tr>
                        </thead>
                        <tbody style="border-style:none;box-sizing:border-box;">
                            <tr style="border-style:solid;box-sizing:border-box;border-bottom-color:#eeeeee;border-left-width:0px;border-bottom-width:1px;border-right-width:0px;border-top-width:0px;">
                                <td style="border-style:none;box-sizing:border-box;padding: 15px 5px;">
                                    <strong t-out="line.product_id.name" style="box-sizing:border-box;font-weight:bolder;"></strong>
                                </td>
                                <td align="center" t-out="line.product_uom_qty" style="border-style:none;box-sizing:border-box;">&nbsp;</td>
                                <td align="right" style="border-style:none;box-sizing:border-box;font-weight: bold; color: #952426;">
                                    <t t-out="format_amount(line.price_total, object.currency_id)"></t>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </t>
            </t>

            <table width="100%" style="border-style: solid none none; margin: 15px 0px 0px; box-sizing: border-box; border-collapse: collapse; border-top-width: 1px; border-top-color: #952426; color: #333333; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
                <tbody>
                    <tr>
                        <td align="right" style="border-style:none;box-sizing:border-box;padding: 10px 0; font-size: 16px;">
                            <strong style="box-sizing:border-box;font-weight:bolder;">Разом: </strong>
                            <span style="font-size: 20px; color: #952426; font-weight: bold;" t-out="format_amount(object.amount_total, object.currency_id)"></span>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div style="text-align: center; padding: 25px 40px;">
            <a t-att-href="object.get_portal_url()" style="box-sizing:border-box;display: inline-block; padding: 14px 32px; background-color: #952426; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">
                Переглянути деталі бронювання
            </a>
        </div>

        <div style="margin: 0 40px 25px 40px; padding: 20px; background-color: #f9f9f9; border-radius: 8px; font-size: 11px; color: #666; line-height: 1.5; border: 1px solid #eee;">
            <div style="margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                <strong style="box-sizing:border-box;font-weight:bolder;color: #952426; text-transform: uppercase;">Офіційна інформація Організатора:</strong>
            </div>
            <strong style="box-sizing:border-box;font-weight:bolder;">CampScout - Volodymyr Shevchenko</strong> | NIP: 6222847059 | Реєстр: 1129<br>
            Страхова гарантія <strong style="box-sizing:border-box;font-weight:bolder;">Compensa TU S.A. VIG</strong> № COR766003 (до 31.03.2027)<br>
            Сума покриття: 31 617,00 PLN
            
            <div style="margin-top: 15px; text-align: center;">
                <img src="https://cdn.prod.website-files.com/69825a713170075c8ad2de43/69b1752e353f7049d46c0aea_Wzor_3_Pieczec_Informacyjna_KRD_PL.png" width="180" style="box-sizing: border-box; vertical-align: middle; display: block; margin: 0px auto; width: 180px; height: 91px;" alt="KRD BIG SA" height="91">
                <p style="margin:5px 0 16px 0;box-sizing:border-box;margin-top: 5px; font-size: 9px; color: #999;">Фінансова прозорість підтверджена Krajowy Rejestr Długów</p>
            </div>
        </div>

        <div style="padding: 10px 40px 30px 40px; font-size: 15px; color: #444; line-height: 1.6;">
            <p style="margin:0px 0 16px 0;box-sizing:border-box;">Дякуємо за довіру! Чекаємо на зустріч у таборі!</p>
            <t t-if="not is_html_empty(object.user_id.signature)">
                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee;">
                    <t t-out="object.user_id.signature"></t>
                </div>
            </t>
        </div>

        <div style="padding: 20px 40px; background-color: #fcfcfc; border-top: 1px solid #eeeeee; font-size: 10px; line-height: 1.4; color: #999; text-align: center;">
            Послуги туризму оподатковуються за системою <strong style="box-sizing:border-box;font-weight:bolder;">VAT Marża</strong>. <br>
            Лист згенеровано автоматично системою Odoo для <strong style="box-sizing:border-box;font-weight:bolder;">Camp Scout</strong>.
        </div>
    </div>
</div>
```

---

## Питання перед реалізацією

1. **Де реалізувати?** У `omnichannel_bridge` (поточний) або новий data XML у `campscout_management`?
   - Рекомендую `campscout_management` — це бізнес-шаблон CampScout, не частина омніканалу.

2. **`t-foreach` для рядків замовлення** — у поточному шаблоні рендер таблиці всередині циклу. Odoo email templates рендерять через Qweb — потрібно перевірити чи `t-foreach` правильно виводить кожен рядок або треба винести таблицю назовні циклу.

3. **Тригер надсилання** — шаблон `sale.order_confirmation_mail` надсилається автоматично при підтвердженні замовлення (кнопка "Підтвердити"). Переконатись, що поточний тригер залишається.

4. **Мультимовність** — зараз шаблон лише українською. Odoo підтримує `lang="object.partner_id.lang"` — додати чи залишити тільки UA?

---

## Чеклист реалізації

- [ ] Визначити репо: `campscout_management` або `omnichannel_bridge`
- [ ] Створити `data/sale_order_email_template.xml` з `<record forcecreate="False">`
- [ ] Зареєструвати XML в `__manifest__.py`
- [ ] Задеплоїти `-u campscout_management` (або `omnichannel_bridge`)
- [ ] Протестувати: підтвердити тестове замовлення → email виглядає правильно
- [ ] Перевірити: рядки замовлення відображаються правильно у відправленому листі
