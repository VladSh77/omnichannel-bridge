# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniLlmFallbackSession(models.Model):
    _name = 'omni.llm.fallback.session'
    _description = 'LLM Fallback Session Log'
    _order = 'id desc'

    state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('restored', 'Restored'),
        ],
        default='active',
        required=True,
        index=True,
    )
    primary_backend = fields.Char(required=True)
    fallback_backend = fields.Char(required=True)
    reason = fields.Char()
    started_at = fields.Datetime(required=True, index=True)
    ended_at = fields.Datetime()
    duration_seconds = fields.Integer()
    restore_backend = fields.Char()
