# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniOutboundLog(models.Model):
    _name = 'omni.outbound.log'
    _description = 'Outbound delivery log'
    _order = 'id desc'

    created_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    provider = fields.Char(index=True)
    external_thread_id = fields.Char(index=True)
    endpoint = fields.Char()
    event_type = fields.Char(default='message')
    ok = fields.Boolean(default=False, index=True)
    status_code = fields.Integer()
    error_snippet = fields.Char()
