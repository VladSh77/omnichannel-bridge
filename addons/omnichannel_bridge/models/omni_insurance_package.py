# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniInsurancePackage(models.Model):
    _name = 'omni.insurance.package'
    _description = 'Omnichannel insurance package'
    _order = 'id desc'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    code = fields.Char()
    product_tmpl_id = fields.Many2one('product.template', string='Linked product', ondelete='set null')
    policy_url = fields.Char(string='Policy URL')
    short_terms = fields.Text(string='Approved short wording')
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
