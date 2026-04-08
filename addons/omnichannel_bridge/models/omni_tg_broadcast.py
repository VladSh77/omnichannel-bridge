# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class OmniTgBroadcastWizard(models.TransientModel):
    _name = 'omni.tg.broadcast.wizard'
    _description = 'Telegram broadcast wizard'

    message_text = fields.Text(required=True)
    only_opted_in = fields.Boolean(default=True)
    exclude_recent_days = fields.Integer(default=7)
    sent_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)

    def action_send(self):
        self.ensure_one()
        Identity = self.env['omni.partner.identity'].sudo()
        Bridge = self.env['omni.bridge'].sudo()
        cutoff = fields.Datetime.now() - timedelta(days=max(0, int(self.exclude_recent_days or 0)))
        domain = [('provider', '=', 'telegram')]
        identities = Identity.search(domain)
        sent = 0
        skipped = 0
        seen_partner = set()
        for ident in identities:
            partner = ident.partner_id.commercial_partner_id.sudo()
            if not partner or partner.id in seen_partner:
                continue
            seen_partner.add(partner.id)
            if self.only_opted_in and not partner.omni_tg_marketing_opt_in:
                skipped += 1
                continue
            if partner.omni_tg_last_broadcast_at and partner.omni_tg_last_broadcast_at >= cutoff:
                skipped += 1
                continue
            Bridge.omni_send_outbound(
                'telegram',
                ident.external_id,
                partner,
                self.message_text,
            )
            partner.write({'omni_tg_last_broadcast_at': fields.Datetime.now()})
            sent += 1
        self.write({'sent_count': sent, 'skipped_count': skipped})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def create(self, vals):
        vals = dict(vals)
        vals.setdefault('exclude_recent_days', 7)
        vals.setdefault('only_opted_in', True)
        return super().create(vals)
