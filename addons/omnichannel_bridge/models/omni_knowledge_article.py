# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniKnowledgeArticle(models.Model):
    _name = 'omni.knowledge.article'
    _description = 'Knowledge article for AI grounding'
    _order = 'priority asc, id desc'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    category = fields.Selection(
        selection=[
            ('faq', 'FAQ'),
            ('policy', 'Policy'),
            ('insurance', 'Insurance'),
            ('logistics', 'Logistics'),
            ('other', 'Other'),
        ],
        default='faq',
        required=True,
    )
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
    priority = fields.Integer(default=100, help='Lower value means higher retrieval priority.')
    body = fields.Text(required=True)
    source_url = fields.Char()
