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
