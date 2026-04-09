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
            ('tiktok', 'TikTok (stub)'),
            ('line', 'LINE (stub)'),
        ]

    @api.model
    def omni_ensure_all_provider_integration_rows(self):
        """
        One row per (company, provider) so the integrations list shows every channel.

        New rows are inactive except ``site_livechat`` (on by default). Operators
        enable a row and fill tokens when connecting that messenger; credentials
        code only uses rows with ``active=True``.
        """
        companies = self.env['res.company'].sudo().search([])
        providers = [key for key, _label in self._selection_providers()]
        Integration = self.sudo()
        for company in companies:
            for provider in providers:
                integration = Integration.search(
                    [
                        ('company_id', '=', company.id),
                        ('provider', '=', provider),
                    ],
                    limit=1,
                )
                if integration:
                    if provider == 'site_livechat' and not integration.active:
                        integration.write({'active': True})
                    continue
                Integration.create(
                    {
                        'company_id': company.id,
                        'provider': provider,
                        'active': provider == 'site_livechat',
                    }
                )

        icp_model = self.env['ir.config_parameter'].sudo()
        icp_model.set_param('omnichannel_bridge.site_livechat_enabled', 'True')
        return True

    @api.model
    def omni_ensure_site_livechat_defaults(self):
        """Backward-compatible entry point (install / legacy calls)."""
        return self.omni_ensure_all_provider_integration_rows()
