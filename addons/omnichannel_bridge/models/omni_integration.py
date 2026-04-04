# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OmniIntegration(models.Model):
    _name = 'omni.integration'
    _description = 'Messenger / gateway credentials'
    _rec_name = 'provider'

    active = fields.Boolean(default=True)
    provider = fields.Selection(
        selection='_selection_providers',
        required=True,
        index=True,
    )
    api_token = fields.Char(
        string='API token / bot token',
        help='Store server-side only; restrict access via security groups.',
    )
    webhook_secret = fields.Char(
        help='Optional shared secret for webhook verification headers.',
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            'omni_integration_company_provider_uniq',
            'unique(company_id, provider)',
            'Only one integration row per provider and company.',
        ),
    ]

    @api.model
    def _selection_providers(self):
        return [
            ('telegram', 'Telegram'),
            ('viber', 'Viber'),
            ('whatsapp', 'WhatsApp'),
            ('meta', 'Facebook / Instagram'),
            ('twilio_whatsapp', 'Twilio (WhatsApp)'),
            ('site_livechat', 'Website Live Chat'),
        ]
