# -*- coding: utf-8 -*-
# omni_coupon_code / omni_coupon_validated / omni_coupon_discount_amount
# ВИДАЛЕНО 2026-04-12: поля дублювали рідний функціонал Odoo "Код купона".
# Колонки в БД залишились (не видалені) — DROP при наступному рефакторі БД.
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders.sudo():
            if order.state in ('sale', 'done'):
                self.env['omni.notify'].sudo().notify_purchase_confirmed(
                    partner=order.partner_id,
                    order=order,
                    source='sale_order_create',
                )
        return orders

    def write(self, vals):
        tracked = self.sudo()
        before = {order.id: order.state for order in tracked}
        res = super().write(vals)
        if 'state' not in vals:
            return res
        for order in tracked:
            prev = before.get(order.id)
            now = order.state
            if prev != now and now in ('sale', 'done'):
                self.env['omni.notify'].sudo().notify_purchase_confirmed(
                    partner=order.partner_id,
                    order=order,
                    source='sale_order_state',
                )
                self.env['omni.payment.event'].sudo().create({
                    'partner_id': order.partner_id.id,
                    'order_id': order.id,
                    'source': 'sale.order',
                    'state': now,
                    'amount_line': '%s %s' % (order.amount_total or 0.0, order.currency_id.name or ''),
                    'external_ref': order.name or '',
                })
        return res
