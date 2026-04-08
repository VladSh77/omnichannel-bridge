# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniLegalDocument(models.Model):
    _name = 'omni.legal.document'
    _description = 'Omnichannel legal document registry'
    _order = 'id desc'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    doc_type = fields.Selection(
        selection=[
            ('offer', 'Offer/Terms'),
            ('privacy', 'Privacy/RODO'),
            ('cookies', 'Cookies'),
            ('child_safety', 'Child safety'),
            ('insurance', 'Insurance'),
            ('other', 'Other'),
        ],
        required=True,
        default='other',
    )
    url = fields.Char(required=True)
    version_tag = fields.Char(help='Document version identifier, e.g. v2026.04.')
    effective_from = fields.Date()
    is_pdf = fields.Boolean(default=False)
    allow_in_bot = fields.Boolean(
        default=True,
        help='If enabled, this URL can be included in bot factual context.',
    )
    approved_by = fields.Char(help='Legal approver name/role.')
    approved_at = fields.Datetime()
    short_quote = fields.Text(help='Approved short quote/snippet that bot may reuse.')
