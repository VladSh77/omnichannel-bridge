# -*- coding: utf-8 -*-
from odoo import api, models


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
        return res
