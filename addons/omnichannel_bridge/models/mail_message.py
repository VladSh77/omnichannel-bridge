# -*- coding: utf-8 -*-
from odoo import fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    # Reserved for tagging (CRM funnel, "hot lead", etc.) via automation rules.
    omni_tag_ids = fields.Many2many(
        'crm.tag',
        'mail_message_omni_tag_rel',
        'message_id',
        'tag_id',
        string='Omnichannel tags',
    )

    def omni_attach_tags(self, tags):
        tag_names = [t.strip() for t in (tags or []) if t and t.strip()]
        if not tag_names:
            return
        Tag = self.env['crm.tag'].sudo()
        ids = []
        for name in tag_names:
            tag = Tag.search([('name', '=', name)], limit=1)
            if not tag:
                tag = Tag.create({'name': name})
            ids.append(tag.id)
        if ids:
            self.sudo().write({'omni_tag_ids': [(4, tid) for tid in ids]})
