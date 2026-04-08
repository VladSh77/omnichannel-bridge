# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniModerationRule(models.Model):
    _name = 'omni.moderation.rule'
    _description = 'Moderation policy rule'
    _order = 'priority asc, id asc'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    keyword = fields.Char(required=True, help='Case-insensitive substring to detect.')
    priority = fields.Integer(default=100, help='Lower value means higher priority.')
    action = fields.Selection(
        selection=[
            ('escalate', 'Escalate to manager'),
            ('escalate_pause', 'Escalate and pause bot'),
            ('note_only', 'Internal note only'),
        ],
        default='escalate',
        required=True,
    )
