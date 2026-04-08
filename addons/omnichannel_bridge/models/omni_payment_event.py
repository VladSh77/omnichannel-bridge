# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniPaymentEvent(models.Model):
    _name = 'omni.payment.event'
    _description = 'Payment and reconciliation event log'
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', index=True, ondelete='set null')
    order_id = fields.Many2one('sale.order', index=True, ondelete='set null')
    transaction_id = fields.Many2one('payment.transaction', index=True, ondelete='set null')
    move_id = fields.Many2one('account.move', index=True, ondelete='set null')
    source = fields.Char(required=True, index=True)
    state = fields.Char(index=True)
    amount_line = fields.Char()
    external_ref = fields.Char(index=True)
    happened_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
