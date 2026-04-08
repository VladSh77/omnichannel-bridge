# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    omni_coupon_code = fields.Char(copy=False)
    omni_coupon_validated = fields.Boolean(copy=False, default=False)
    omni_coupon_discount_amount = fields.Monetary(currency_field='currency_id', copy=False)

    def _omni_coupon_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        code = (icp.get_param('omnichannel_bridge.coupon_public_code', '') or '').strip().upper()
        try:
            discount_percent = float(icp.get_param('omnichannel_bridge.coupon_discount_percent', '5') or 5)
        except ValueError:
            discount_percent = 5.0
        return code, max(0.0, discount_percent)

    def _omni_is_camp_line(self, line):
        product = line.product_id
        if not product:
            return False
        if getattr(product, 'bs_event_id', False):
            return True
        tmpl = product.product_tmpl_id
        return bool(getattr(tmpl, 'bs_event_id', False)) or (product.detailed_type == 'event')

    def _omni_apply_public_coupon(self):
        configured_code, percent = self._omni_coupon_config()
        for order in self.sudo():
            code = (order.omni_coupon_code or '').strip().upper()
            if not configured_code or not code or code != configured_code:
                order.write({
                    'omni_coupon_validated': False,
                    'omni_coupon_discount_amount': 0.0,
                })
                continue
            already_used = self.env['omni.coupon.redemption'].sudo().search_count([
                ('partner_id', '=', order.partner_id.id),
                ('code', '=', code),
            ]) > 0
            if already_used:
                order.write({
                    'omni_coupon_validated': False,
                    'omni_coupon_discount_amount': 0.0,
                })
                continue
            total_discount = 0.0
            for line in order.order_line:
                if not self._omni_is_camp_line(line):
                    continue
                if line.discount != percent:
                    line.write({'discount': percent})
                line_discount = (line.price_unit * line.product_uom_qty) * (percent / 100.0)
                total_discount += line_discount
            order.write({
                'omni_coupon_validated': True,
                'omni_coupon_discount_amount': total_discount,
            })

    def _omni_register_coupon_redemption(self):
        for order in self.sudo():
            if not order.omni_coupon_validated:
                continue
            code = (order.omni_coupon_code or '').strip().upper()
            if not code:
                continue
            exists = self.env['omni.coupon.redemption'].sudo().search_count([
                ('partner_id', '=', order.partner_id.id),
                ('code', '=', code),
            ])
            if exists:
                continue
            self.env['omni.coupon.redemption'].sudo().create({
                'partner_id': order.partner_id.id,
                'order_id': order.id,
                'code': code,
                'discount_percent': (order._omni_coupon_config() or (None, 0.0))[1],
                'discount_amount': order.omni_coupon_discount_amount,
                'currency_id': order.currency_id.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders.sudo():
            if order.omni_coupon_code:
                order._omni_apply_public_coupon()
            if order.state in ('sale', 'done'):
                order._omni_register_coupon_redemption()
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
        if 'omni_coupon_code' in vals or 'order_line' in vals:
            tracked._omni_apply_public_coupon()
        if 'state' not in vals:
            return res
        for order in tracked:
            prev = before.get(order.id)
            now = order.state
            if prev != now and now in ('sale', 'done'):
                order._omni_register_coupon_redemption()
                self.env['omni.notify'].sudo().notify_purchase_confirmed(
                    partner=order.partner_id,
                    order=order,
                    source='sale_order_state',
                )
        return res
