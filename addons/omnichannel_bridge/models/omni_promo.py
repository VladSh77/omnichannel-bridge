# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OmniPromo(models.Model):
    _name = 'omni.promo'
    _description = 'Omnichannel promo campaign'
    _order = 'id desc'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    code = fields.Char(help='Promo/coupon code shown to clients.')
    discount_percent = fields.Float(default=0.0)
    date_start = fields.Date()
    date_end = fields.Date()
    channel_scope = fields.Selection(
        selection=[
            ('all', 'All channels'),
            ('meta', 'Meta/Instagram'),
            ('telegram', 'Telegram'),
            ('site', 'Website'),
        ],
        default='all',
        required=True,
    )
    product_tmpl_ids = fields.Many2many(
        'product.template',
        'omni_promo_product_tmpl_rel',
        'promo_id',
        'product_tmpl_id',
        string='Allowed products',
    )
    terms = fields.Text()

    @api.model
    def omni_find_active_by_code(self, code):
        coupon = (code or '').strip().upper()
        if not coupon:
            return self.browse()
        today = fields.Date.context_today(self)
        promos = self.sudo().search([
            ('active', '=', True),
            ('code', '!=', False),
        ], order='id desc')
        for promo in promos:
            if (promo.code or '').strip().upper() != coupon:
                continue
            if promo.date_start and promo.date_start > today:
                continue
            if promo.date_end and promo.date_end < today:
                continue
            return promo
        return self.browse()
