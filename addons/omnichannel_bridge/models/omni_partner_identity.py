# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class OmniPartnerIdentity(models.Model):
    _name = 'omni.partner.identity'
    _description = 'External messenger identity linked to a partner'
    _rec_name = 'display_name'

    partner_id = fields.Many2one(
        'res.partner',
        required=True,
        ondelete='cascade',
        index=True,
    )
    provider = fields.Selection(
        selection='_selection_providers',
        required=True,
        index=True,
    )
    external_id = fields.Char(
        required=True,
        index=True,
        help='Stable user/chat id from the messenger API.',
    )
    display_name = fields.Char()
    metadata_json = fields.Text(
        help='Optional JSON snapshot (username, locale, etc.).',
    )

    _sql_constraints = [
        (
            'omni_identity_provider_external_uniq',
            'unique(provider, external_id)',
            _('This external id is already linked for this provider.'),
        ),
    ]

    @api.model
    def _selection_providers(self):
        return self.env['omni.integration']._selection_providers()
