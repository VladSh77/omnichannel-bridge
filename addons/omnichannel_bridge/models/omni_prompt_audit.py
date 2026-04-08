# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniPromptAudit(models.Model):
    _name = 'omni.prompt.audit'
    _description = 'Prompt/rules change audit log'
    _order = 'id desc'

    changed_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    changed_by = fields.Many2one('res.users', ondelete='set null')
    key_name = fields.Char(required=True, index=True)
    old_value = fields.Text()
    new_value = fields.Text()
    note = fields.Char()
