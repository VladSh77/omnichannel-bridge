# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    omni_places_remaining = fields.Integer(
        string='Places / quota (chatbot)',
        help='Free places or seats for this offer. Leave empty to fall back to salable stock qty.',
    )
    omni_chat_terms = fields.Text(
        string='Offer terms (chatbot)',
        help='Short conditions shown to the bot (pricing rules, deadlines, what is included).',
    )
