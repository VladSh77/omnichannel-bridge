# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniStageTransition(models.Model):
    _name = 'omni.stage.transition'
    _description = 'Дозволений перехід між етапами продажу'
    _order = 'id asc'

    active = fields.Boolean(string='Активний', default=True)
    from_stage = fields.Selection(
        selection=[
            ('new', 'Новий запит'),
            ('qualifying', 'Кваліфікація'),
            ('proposal', 'Підібрано варіанти'),
            ('handoff', 'Передано менеджеру'),
        ],
        string='З етапу',
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
        string='На етап',
        required=True,
        index=True,
    )
    note = fields.Char(string='Примітка')
