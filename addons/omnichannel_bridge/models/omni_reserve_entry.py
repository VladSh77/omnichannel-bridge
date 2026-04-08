# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniReserveEntry(models.Model):
    _name = 'omni.reserve.entry'
    _description = 'Reserve waitlist entry'
    _order = 'id desc'

    active = fields.Boolean(default=True)
    requested_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('contacted', 'Contacted'),
            ('waitlist', 'On waitlist'),
            ('converted', 'Converted'),
            ('cancelled', 'Cancelled'),
        ],
        default='new',
        required=True,
        index=True,
    )
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    channel_id = fields.Many2one('discuss.channel', ondelete='set null', index=True)
    lead_id = fields.Many2one('crm.lead', ondelete='set null', index=True)
    provider = fields.Selection(
        selection=lambda self: self.env['omni.integration']._selection_providers(),
        index=True,
    )
    user_text = fields.Text()
    note = fields.Text()
