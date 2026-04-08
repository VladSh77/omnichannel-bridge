# -*- coding: utf-8 -*-
from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def write(self, vals):
        tracked = self.sudo()
        before = {tx.id: tx.state for tx in tracked}
        res = super().write(vals)
        if 'state' not in vals:
            return res
        for tx in tracked:
            prev = before.get(tx.id)
            now = tx.state
            if prev == now or now not in ('done', 'authorized'):
                continue
            partner = tx.partner_id or tx.sale_order_ids[:1].partner_id
            if not partner:
                continue
            currency = tx.currency_id.name if tx.currency_id else ''
            amount_line = '%s %s' % (tx.amount or 0.0, currency or '')
            self.env['omni.notify'].sudo().notify_purchase_confirmed(
                partner=partner,
                source='payment_transaction_%s' % now,
                order_ref=tx.reference or tx.provider_reference or tx.name or 'payment_tx',
                amount_line=amount_line.strip(),
            )
            self.env['omni.payment.event'].sudo().create({
                'partner_id': partner.id,
                'order_id': tx.sale_order_ids[:1].id if tx.sale_order_ids else False,
                'transaction_id': tx.id,
                'source': 'payment.transaction',
                'state': now,
                'amount_line': amount_line.strip(),
                'external_ref': tx.reference or tx.provider_reference or tx.name or '',
            })
        return res
