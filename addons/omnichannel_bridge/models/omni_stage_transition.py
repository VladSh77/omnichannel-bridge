# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniStageTransition(models.Model):
    _name = 'omni.stage.transition'
    _description = 'Allowed sales stage transition'
    _order = 'id asc'

    active = fields.Boolean(default=True)
    from_stage = fields.Selection(
        selection=[
            ('new', 'Новий запит'),
            ('qualifying', 'Кваліфікація'),
            ('proposal', 'Підібрано варіанти'),
            ('handoff', 'Передано менеджеру'),
        ],
        required=True,
        index=True,
    )
    to_stage = fields.Selection(
        selection=[
            ('new', 'Новий запит'),
            ('qualifying', 'Кваліфікація'),
            ('proposal', 'Підібрано варіанти'),
            ('handoff', 'Передано менеджеру'),
        ],
        required=True,
        index=True,
    )
    note = fields.Char()
