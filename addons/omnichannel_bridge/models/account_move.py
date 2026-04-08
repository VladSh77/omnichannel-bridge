# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        tracked = self.sudo().filtered(lambda m: m.move_type in ('out_invoice', 'out_refund'))
        before = {m.id: m.payment_state for m in tracked}
        res = super().write(vals)
        if 'payment_state' not in vals:
            return res
        for move in tracked:
            prev = before.get(move.id)
            now = move.payment_state
            if prev == now or now not in ('paid', 'in_payment'):
                continue
            currency = move.currency_id.name if move.currency_id else ''
            amount_line = '%s %s' % (move.amount_total or 0.0, currency or '')
            self.env['omni.notify'].sudo().notify_purchase_confirmed(
                partner=move.partner_id,
                source='account_move_%s' % now,
                order_ref=move.name or move.ref or 'invoice',
                amount_line=amount_line.strip(),
            )
        return res
