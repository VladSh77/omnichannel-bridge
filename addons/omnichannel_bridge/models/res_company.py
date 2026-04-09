# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    omni_integration_ids = fields.One2many(
        'omni.integration',
        'company_id',
        string='Omnichannel integrations',
        help='Messenger credentials for this company (tokens live here, not in the app menu).',
    )

    def action_omni_sync_messenger_channels(self):
        """Add every provider from the registry as a row (skips existing)."""
        self.ensure_one()
        self.env['omni.integration'].sudo().omni_ensure_integration_rows_for_company_ids(self.ids)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.company',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'views': [(False, 'form')],
        }
