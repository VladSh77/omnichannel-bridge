# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniModerationRule(models.Model):
    _name = 'omni.moderation.rule'
    _description = 'Правило модерації повідомлень клієнта'
    _order = 'priority asc, id asc'

    active = fields.Boolean(string='Активний', default=True)
    name = fields.Char(string='Назва', required=True)
    keyword = fields.Char(
        string='Ключове слово / фраза',
        required=True,
        help='Підрядок у тексті (без урахування регістру).',
    )
    priority = fields.Integer(
        string='Пріоритет',
        default=100,
        help='Менше число — перевіряється раніше.',
    )
    action = fields.Selection(
        selection=[
            ('escalate', 'Передати менеджеру'),
            ('escalate_pause', 'Передати менеджеру й зупинити бота'),
            ('note_only', 'Лише внутрішня нотатка'),
        ],
        string='Дія',
        default='escalate',
        required=True,
    )
