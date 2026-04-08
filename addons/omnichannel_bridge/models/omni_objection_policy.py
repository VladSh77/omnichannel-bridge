# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniObjectionPolicy(models.Model):
    _name = 'omni.objection.policy'
    _description = 'Objection policy block'
    _order = 'objection_type, id desc'

    active = fields.Boolean(default=True)
    objection_type = fields.Selection(
        selection=[
            ('price', 'Price'),
            ('timing', 'Timing'),
            ('trust', 'Trust'),
            ('need_to_think', 'Need to think'),
            ('competitor', 'Competitor'),
            ('not_decision_maker', 'Not decision maker'),
        ],
        required=True,
        index=True,
    )
    body = fields.Text(required=True)
    channel_scope = fields.Selection(
        selection=[
            ('all', 'All'),
            ('meta', 'Meta'),
            ('telegram', 'Telegram'),
            ('site', 'Website livechat'),
        ],
        default='all',
        required=True,
    )
