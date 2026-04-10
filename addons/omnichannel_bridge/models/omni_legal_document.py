# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniLegalDocument(models.Model):
    _name = 'omni.legal.document'
    _description = 'Реєстр юридичних документів для чат-бота та контексту ШІ'
    _order = 'id desc'

    active = fields.Boolean(string='Активний', default=True)
    name = fields.Char(string='Назва', required=True)
    doc_type = fields.Selection(
        selection=[
            ('offer', 'Оферта / умови'),
            ('privacy', 'Конфіденційність / RODO'),
            ('cookies', 'Файли cookie'),
            ('child_safety', 'Захист дітей'),
            ('insurance', 'Страхування'),
            ('other', 'Інше'),
        ],
        string='Тип документа',
        required=True,
        default='other',
    )
    url = fields.Char(string='Посилання (URL)', required=True)
    version_tag = fields.Char(
        string='Мітка версії',
        help='Ідентифікатор версії документа, наприклад v2026.04.',
    )
    effective_from = fields.Date(string='Діє з')
    is_pdf = fields.Boolean(string='Це PDF', default=False)
    allow_in_bot = fields.Boolean(
        string='Дозволити в боті',
        default=True,
        help='Якщо увімкнено, посилання потрапляє в фактичний контекст бота (блок LEGAL_DOCUMENTS).',
    )
    approved_by = fields.Char(
        string='Погодив (ПІБ / роль)',
        help='Хто затвердив документ для використання в боті.',
    )
    approved_at = fields.Datetime(string='Дата погодження')
    short_quote = fields.Text(
        string='Коротка дозволена цитата',
        help='Схвалений короткий фрагмент тексту, який бот може повторювати дослівно.',
    )
