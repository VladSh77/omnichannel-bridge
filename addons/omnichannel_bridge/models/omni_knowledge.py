# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.tools import html2plaintext


class OmniKnowledge(models.AbstractModel):
    _name = 'omni.knowledge'
    _description = 'Catalog + payment facts for LLM context'

    @api.model
    def omni_partner_payment_summary(self, partner):
        if not partner:
            return _('No partner linked yet.')
        partner = partner.commercial_partner_id
        lines = []
        Move = self.env['account.move'].sudo()
        invoices = Move.search(
            [
                ('partner_id', 'child_of', partner.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
            ],
            order='invoice_date desc, id desc',
            limit=8,
        )
        paid_like = invoices.filtered(
            lambda m: m.payment_state in ('paid', 'in_payment')
        )
        if paid_like:
            refs = ', '.join(paid_like.mapped('name')[:5])
            lines.append(
                _(
                    'Customer has posted invoices with payment status paid/in_payment (e.g. %(refs)s).',
                    refs=refs,
                )
            )
        elif invoices:
            lines.append(
                _(
                    'Customer has posted invoices but none marked paid yet (latest: %(name)s, %(state)s).',
                    name=invoices[0].name,
                    state=invoices[0].payment_state,
                )
            )
        else:
            lines.append(_('No posted customer invoices found for this partner.'))
        return '\n'.join(lines)

    @api.model
    def omni_catalog_context_for_llm(self, partner, limit=40):
        """Published/sale_ok products with list price, optional places, terms."""
        Product = self.env['product.template'].sudo()
        domain = [('sale_ok', '=', True)]
        if 'is_published' in Product._fields:
            domain.append(('is_published', '=', True))
        order = 'website_sequence, name' if 'website_sequence' in Product._fields else 'name'
        products = Product.search(domain, order=order, limit=limit)
        chunks = []
        if partner:
            pricelist = partner.property_product_pricelist
        else:
            pricelist = self.env.company.property_product_pricelist_id
        for tmpl in products:
            variant = tmpl.product_variant_id
            price = tmpl.list_price
            if pricelist and variant:
                try:
                    price = pricelist._get_product_price(
                        variant,
                        1.0,
                        uom=variant.uom_id,
                    )
                except TypeError:
                    price = pricelist._get_product_price(variant, 1.0, partner=partner or False)
            if tmpl.omni_places_remaining is not False:
                places = tmpl.omni_places_remaining
            else:
                places = None
                if variant and hasattr(variant, 'free_qty'):
                    try:
                        places = int(variant.free_qty)
                    except (TypeError, ValueError):
                        places = None
                if places is None and variant and hasattr(variant, 'qty_available'):
                    try:
                        places = int(variant.qty_available)
                    except (TypeError, ValueError):
                        places = None
            terms = (tmpl.omni_chat_terms or tmpl.description_sale or '').strip()
            currency = tmpl.currency_id or self.env.company.currency_id
            line = '- %s | price: %s %s' % (
                tmpl.name,
                price,
                currency.name or '',
            )
            if places is not None:
                line += ' | places/qty: %s' % places
            if terms:
                line += ' | terms: %s' % terms[:500]
            chunks.append(line)
        if not chunks:
            return _('No catalog lines available (check sale_ok / website publish).')
        header = _('Use only this catalog data for offers; do not invent prices or seats.')
        return header + '\n' + '\n'.join(chunks)

    @api.model
    def omni_partner_core_facts(self, partner):
        """Лише поля з БД — один рядок на факт."""
        if not partner:
            return _('partner_linked: no')
        p = partner.commercial_partner_id
        lines = [
            'crm_display_name: %s' % (p.name or ''),
            'email: %s' % (p.email or ''),
            'phone: %s' % (p.phone or ''),
            'mobile: %s' % (p.mobile or ''),
            'street: %s' % (p.street or ''),
            'city: %s' % (p.city or ''),
            'preferred_vocative: %s' % (p.omni_addressing_vocative or ''),
            'addressing_style: %s' % (p.omni_addressing_style or 'neutral'),
        ]
        return '\n'.join(lines)

    @api.model
    def omni_greeting_instruction_block(self, partner):
        """Інструкції для моделі: шаблон звернення або уточнити один раз."""
        Memory = self.env['omni.memory']
        if not partner:
            return _('GREETING: немає прив’язаного партнера.')
        p = partner.commercial_partner_id
        voc = (p.omni_addressing_vocative or '').strip()
        style = p.omni_addressing_style or 'neutral'
        if not voc:
            hint = Memory.omni_suggest_vocative_from_name(p.name)
            if hint:
                return (
                    'GREETING: у картці ім’я «%s». Можлива форма звертання «%s». '
                    'Якщо клієнт не підтвердив — один раз ввічливо запитайте, як зручно звертатися, '
                    'і після відповіді дані збережуться в CRM.'
                ) % (p.name, hint)
            return (
                'GREETING: один раз уточніть, як звертатися до клієнта (на ім’я чи офіційно), '
                'і поясніть що збережете для наступних розмов. Ім’я в CRM: %s.'
            ) % (p.name,)
        if style == 'formal_female':
            return (
                'GREETING_TEMPLATE_UK: Почніть з точної фрази: «Доброго дня, пані %(voc)s!» '
                '(не змінюйте зворот).'
            ) % {'voc': voc}
        if style == 'formal_male':
            return (
                'GREETING_TEMPLATE_UK: Почніть з точної фрази: «Доброго дня, пане %(voc)s!» '
                '(не змінюйте зворот).'
            ) % {'voc': voc}
        if style == 'informal':
            return (
                'GREETING_TEMPLATE_UK: Можна на ти. Почніть з «Привіт, %(voc)s!» '
                '(ім’я як у полі preferred_vocative).'
            ) % {'voc': voc}
        return (
            'GREETING: стиль neutral — ввічливо, без «пані/пане», поки клієнт не уточнив. '
            'Можна звернутися за іменем з картки якщо доречно: %s.'
        ) % (p.name,)

    @api.model
    def omni_channel_transcript_block(self, channel, limit=8):
        ICP = self.env['ir.config_parameter'].sudo()
        if str(ICP.get_param('omnichannel_bridge.llm_include_transcript', 'True')).lower() not in (
            '1',
            'true',
            'yes',
        ):
            return ''
        if not channel:
            return ''
        try:
            lim = int(ICP.get_param('omnichannel_bridge.llm_transcript_messages', '8'))
        except ValueError:
            lim = limit
        Message = self.env['mail.message'].sudo()
        msgs = Message.search(
            [
                ('model', '=', 'mail.channel'),
                ('res_id', '=', channel.id),
                ('message_type', '=', 'comment'),
            ],
            order='id desc',
            limit=max(1, min(lim, 30)),
        )
        lines = [
            _(
                'RECENT_THREAD (context only; not financial truth; may contain typos):'
            ),
        ]
        odoobot = self.env.ref('base.partner_root')
        customer = channel.omni_customer_partner_id
        for m in reversed(msgs):
            body = (html2plaintext(m.body or '') or '').strip()
            if not body:
                continue
            auth = m.author_id
            if customer and auth == customer:
                role = 'client'
            elif auth == odoobot:
                role = 'bot'
            else:
                role = 'staff'
            lines.append('%s: %s' % (role, body[:500]))
        return '\n'.join(lines)

    @api.model
    def omni_partner_orders_block(self, partner):
        """Замовлення клієнта: назва табору, extras, статус, сума."""
        if not partner:
            return ''
        p = partner.commercial_partner_id
        Order = self.env['sale.order'].sudo()
        orders = Order.search(
            [('partner_id', 'child_of', p.id)],
            order='date_order desc',
            limit=5,
        )
        if not orders:
            return _('CLIENT_ORDERS: немає замовлень у системі.')
        lines = ['CLIENT_ORDERS:']
        for order in orders:
            status = dict(order._fields['state'].selection).get(order.state, order.state)
            lines.append('  Замовлення %s | %s | %s %s' % (
                order.name,
                status,
                order.amount_total,
                order.currency_id.name or '',
            ))
            for line in order.order_line:
                product_name = line.product_id.display_name or line.name
                lines.append('    - %s × %s' % (line.product_uom_qty, product_name))
        return '\n'.join(lines)

    @api.model
    def omni_strict_grounding_bundle(self, channel, partner):
        """Єдиний блок фактів для LLM: ORM + умови каталогу + звернення + пам’ять + тред."""
        parts = [
            '=== FACTS_FROM_DATABASE (єдине джерело правди про ціни, місця, оплати, ПІБ) ===',
            self.omni_partner_core_facts(partner),
            '---',
            self.omni_greeting_instruction_block(partner),
            '---',
            self.omni_partner_payment_summary(partner),
            '---',
            self.omni_partner_orders_block(partner),
            '---',
            self.omni_catalog_context_for_llm(partner),
        ]
        if partner and partner.omni_chat_memory:
            parts.append('---\nCLIENT_MEMORY_LINES:\n%s' % partner.omni_chat_memory.strip())
        transcript = self.omni_channel_transcript_block(channel)
        if transcript:
            parts.append('---\n%s' % transcript)
        return '\n'.join(parts)
