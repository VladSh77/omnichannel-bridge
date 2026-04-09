# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OmniPartnerBindWizard(models.TransientModel):
    _name = 'omni.partner.bind.wizard'
    _description = 'Bind existing partner to omnichannel thread'

    channel_id = fields.Many2one('discuss.channel', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, string='Контакт')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        channel_id = int(self.env.context.get('default_channel_id') or 0)
        if channel_id:
            values['channel_id'] = channel_id
        return values

    def action_bind_partner(self):
        self.ensure_one()
        self.env['discuss.channel'].sudo().omni_bind_partner_to_channel(
            self.channel_id.id,
            self.partner_id.id,
        )
        return {'type': 'ir.actions.act_window_close'}
