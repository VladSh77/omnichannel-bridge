# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniObjectionPolicy(models.Model):
    _name = 'omni.objection.policy'
    _description = 'Політика відповіді на заперечення клієнта (для контексту ШІ)'
    _order = 'objection_type, id desc'

    active = fields.Boolean(string='Активний', default=True)
    objection_type = fields.Selection(
        selection=[
            ('price', 'Ціна / бюджет'),
            ('timing', 'Терміни / «не зараз»'),
            ('trust', 'Довіра / ризики'),
            ('need_to_think', 'Потрібно подумати'),
            ('competitor', 'Конкуренти'),
            ('not_decision_maker', 'Не ЛПР'),
        ],
        string='Тип заперечення',
        required=True,
        index=True,
    )
    body = fields.Text(
        string='Текст для бота',
        required=True,
        help='Інструкція UA/PL для моделі; перекриває значення з налаштувань, якщо заповнено.',
    )
    channel_scope = fields.Selection(
        selection=[
            ('all', 'Усі канали'),
            ('meta', 'Meta'),
            ('telegram', 'Telegram'),
            ('site', 'Чат на сайті'),
        ],
        string='Канал',
        default='all',
        required=True,
    )
