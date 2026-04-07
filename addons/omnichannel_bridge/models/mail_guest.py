# -*- coding: utf-8 -*-
import re

from odoo import models


class MailGuest(models.Model):
    _inherit = 'mail.guest'

    def name_get(self):
        result = super().name_get()
        cleaned = []
        pattern = re.compile(r'^(?:visitor|відвідувач)\s*#\d+\s*', re.IGNORECASE)
        for rec_id, name in result:
            new_name = pattern.sub('', (name or '')).strip()
            cleaned.append((rec_id, new_name or 'Гість'))
        return cleaned
