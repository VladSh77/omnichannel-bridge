# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniCouponRedemption(models.Model):
    _name = 'omni.coupon.redemption'
    _description = 'Public coupon redemption registry'
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade', index=True)
    code = fields.Char(required=True, index=True)
    discount_percent = fields.Float(required=True)
    discount_amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', required=True)
    redeemed_at = fields.Datetime(default=fields.Datetime.now, required=True)

    _sql_constraints = [
        (
            'omni_coupon_redemption_unique_partner_code',
            'unique(partner_id, code)',
            'This coupon code was already used by this customer.',
        ),
    ]
