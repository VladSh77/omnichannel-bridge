# -*- coding: utf-8 -*-
import re

from odoo import _, api, models

FOMO_THRESHOLD = 5


class OmniSalesIntel(models.AbstractModel):
    _name = 'omni.sales.intel'
    _description = 'Sales psychology helpers (FOMO, catalog hints)'

    # Ключові слова для детекції запиту менеджера (UA/PL/EN)
    _ESCALATION_KEYWORDS = [
        'менеджер', 'оператор', 'людина', 'живий', 'зателефонуй', 'передай',
        'manager', 'operator', 'human', 'agent', 'call me', 'speak to',
        'proszę człowieka', 'proszę managera', 'zadzwoń',
    ]

    @api.model
    def omni_apply_inbound_triggers(self, channel, partner, text, provider):
        fomo_line = self._omni_build_fomo_line_from_message(text)
        if fomo_line:
            channel.sudo().message_post(
                body=fomo_line,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

        # Детекція запиту ескалації
        if self._omni_detect_escalation(text):
            self.env['omni.notify'].sudo().notify_escalation(
                channel=channel,
                partner=partner,
                reason=_('Клієнт запитав менеджера: "%s"') % text[:120],
            )

    @api.model
    def _omni_detect_escalation(self, text):
        if not text:
            return False
        text_lower = text.lower()
        return any(kw in text_lower for kw in self._ESCALATION_KEYWORDS)

    @api.model
    def _omni_build_fomo_line_from_message(self, text):
        """If message references a product by name, check stock / places and return hint."""
        if not text:
            return ''
        Product = self.env['product.product'].sudo()
        tokens = [t for t in re.split(r'\s+', text.strip()) if len(t) > 2]
        if not tokens:
            return ''
        domain = ['|'] * (len(tokens) - 1) + [('name', 'ilike', t) for t in tokens[:5]]
        products = Product.search(domain, limit=3)
        lines = []
        for product in products:
            tmpl = product.product_tmpl_id
            if tmpl.omni_places_remaining is not False:
                qty = tmpl.omni_places_remaining
            else:
                qty = self._omni_product_free_qty(product)
            if qty is None:
                continue
            if qty < FOMO_THRESHOLD:
                lines.append(
                    _(
                        'Low availability hint: "%(name)s" — only %(qty)s left.',
                        name=product.display_name,
                        qty=int(qty),
                    )
                )
        return '\n'.join(lines)

    def _omni_product_free_qty(self, product):
        for attr in ('free_qty', 'qty_available'):
            if hasattr(product, attr):
                try:
                    val = getattr(product, attr)
                    if val is not None:
                        return val
                except Exception:
                    continue
        return None

    @api.model
    def omni_optional_product_lines(self, product_template):
        tmpl = product_template[:1]
        if not tmpl:
            return self.env['product.product']
        optional = tmpl.optional_product_ids
        return optional.product_variant_ids

    @api.model
    def omni_draft_sale_order(self, partner, product, quantity=1.0):
        if not partner or not product:
            return self.env['sale.order']
        order = self.env['sale.order'].sudo().create({
            'partner_id': partner.id,
        })
        self.env['sale.order.line'].sudo().create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': quantity,
        })
        return order
