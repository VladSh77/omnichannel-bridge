# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniKnowledgeArticle(models.Model):
    _name = 'omni.knowledge.article'
    _description = 'Стаття бази знань для фактів у ШІ'
    _order = 'priority asc, id desc'

    active = fields.Boolean(string='Активна', default=True)
    name = fields.Char(string='Назва', required=True)
    category = fields.Selection(
        selection=[
            ('faq', 'FAQ'),
            ('policy', 'Політика / правила'),
            ('insurance', 'Страхування'),
            ('logistics', 'Логістика'),
            ('other', 'Інше'),
        ],
        string='Категорія',
        default='faq',
        required=True,
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
    priority = fields.Integer(
        string='Пріоритет',
        default=100,
        help='Менше значення — вища релевантність при відборі.',
    )
    body = fields.Text(string='Текст', required=True)
    source_url = fields.Char(string='Джерело (URL)')
    source_type = fields.Selection(
        selection=[
            ('knowledge_article', 'Стаття бази знань'),
            ('policy_doc', 'Політика / документ'),
            ('youtube', 'YouTube'),
            ('other', 'Інше'),
        ],
        string='Тип джерела',
        default='knowledge_article',
        required=True,
    )
    source_ref = fields.Char(
        string='Посилання на запис',
        help='Ключ запису, URL або зовнішній ідентифікатор.',
    )
    source_timestamp = fields.Char(
        string='Мітка часу у джерелі',
        help='Наприклад, таймкод YouTube 12:34.',
    )
    editorial_approved = fields.Boolean(
        string='Схвалено редакцією',
        default=True,
        help='Лише схвалені статті потрапляють у production RAG.',
    )
    fact_expires_on = fields.Date(
        string='Дійсна до',
        help='Після цієї дати стаття не потрапляє в контекст RAG.',
    )
