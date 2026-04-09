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
