# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniManagerReplyTemplate(models.Model):
    _name = 'omni.manager.reply.template'
    _description = 'Manager reply template'
    _order = 'id desc'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
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
    body_template = fields.Text(required=True, help='Use placeholders: {name}, {city}, {period}, {budget}.')
