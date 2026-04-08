# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniStageEvent(models.Model):
    _name = 'omni.stage.event'
    _description = 'Omnichannel sales stage transition event'
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    channel_id = fields.Many2one('discuss.channel', ondelete='set null', index=True)
    old_stage = fields.Char(required=True)
    new_stage = fields.Char(required=True)
    reason = fields.Char()
    source = fields.Char()
    changed_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
