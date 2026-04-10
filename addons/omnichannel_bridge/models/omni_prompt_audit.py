# -*- coding: utf-8 -*-
from odoo import fields, models


class OmniPromptAudit(models.Model):
    _name = 'omni.prompt.audit'
    _description = 'Журнал змін промптів і погоджених текстів (ir.config_parameter)'
    _order = 'id desc'

    changed_at = fields.Datetime(
        string='Коли змінено',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    changed_by = fields.Many2one(
        'res.users',
        string='Хто змінив',
        ondelete='set null',
    )
    key_name = fields.Char(
        string='Ключ параметра',
        required=True,
        index=True,
        help='Технічний ключ у ir.config_parameter (наприклад omnichannel_bridge.llm_prompt_version).',
    )
    old_value = fields.Text(string='Старе значення')
    new_value = fields.Text(string='Нове значення')
    note = fields.Char(
        string='Примітка',
        help='Звідки змінено (зазвичай збереження форми налаштувань).',
    )
