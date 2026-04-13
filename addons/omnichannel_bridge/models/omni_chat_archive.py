# -*- coding: utf-8 -*-
from odoo import models, fields, api


class OmniChatArchive(models.Model):
    """
    Архів чат-повідомлень з нагод CRM, перенесених із chatter.
    Зберігає повідомлення з попередньої системи (helpcrunch),
    щоб не засмічувати активний chatter нагоди.
    """
    _name = 'omni.chat.archive'
    _description = 'Архів чату нагоди'
    _order = 'date asc'
    _rec_name = 'author_name'

    lead_id = fields.Many2one(
        'crm.lead', string='Нагода',
        required=True, ondelete='cascade', index=True,
    )
    date = fields.Datetime(string='Дата', required=True)
    author_name = fields.Char(string='Автор', required=True)
    body = fields.Html(string='Повідомлення', sanitize=True)

    def _get_display_body(self):
        """Plain text preview for list view."""
        from odoo.tools import html2plaintext
        return html2plaintext(self.body or '')


class CrmLeadChatArchive(models.Model):
    _inherit = 'crm.lead'

    omni_chat_archive_ids = fields.One2many(
        'omni.chat.archive', 'lead_id',
        string='Повідомлення архіву',
    )
    omni_chat_archive_count = fields.Integer(
        string='Архів чату',
        compute='_compute_omni_chat_archive_count',
    )

    @api.depends('omni_chat_archive_ids')
    def _compute_omni_chat_archive_count(self):
        counts = {
            r['lead_id']: r['lead_id_count']
            for r in self.env['omni.chat.archive'].read_group(
                [('lead_id', 'in', self.ids)],
                ['lead_id'],
                ['lead_id'],
            )
        }
        for lead in self:
            lead.omni_chat_archive_count = counts.get(lead.id, 0)

    def action_open_chat_archive(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Архів чату',
            'res_model': 'omni.chat.archive',
            'view_mode': 'list',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id},
        }
