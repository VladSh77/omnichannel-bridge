# -*- coding: utf-8 -*-
import re
from datetime import date

from odoo import api, models

# Типові імена → зворот (без зовнішніх NLP-бібліотек, лише Python).
_UA_VOCATIVE_MAP = {
    'оля': 'Ольго',
    'світлана': 'Світлано',
    'наталія': 'Наталіє',
    'наташа': 'Наташо',
    'марія': 'Маріє',
    'катерина': 'Катерино',
    'юлія': 'Юліє',
    'іван': 'Іване',
    'андрій': 'Андрію',
    'олександр': 'Олександре',
    'михайло': 'Михайле',
}


class OmniMemory(models.AbstractModel):
    _name = 'omni.memory'
    _description = 'Extract preferences from chat; append partner memory (rules only, no ML)'

    @api.model
    def omni_apply_inbound_learning(self, partner, text):
        """Regex: звернення, «на ти», ім'я — у поля партнера + рядок у пам'ять."""
        if not partner or not text:
            return
        partner = partner.sudo()
        lowered = text.lower().strip()
        changed = []
        if re.search(r'можна\s+на\s+ти|звертай(?:те)?сь\s+на\s+ти', lowered):
            if partner.omni_addressing_style != 'informal':
                partner.write({'omni_addressing_style': 'informal'})
                changed.append('стиль: на ти')
        name_hit = None
        for regex in (
            r'називайте\s+мене\s+["«]?([^"»\n\.]{2,50})',
            r'звертай(?:те)?сь\s+до\s+мене\s+["«]?([^"»\n\.]{2,50})',
            r'мене\s+звуть\s+["«]?([^"»\n\.]{2,50})',
            r'я\s+—\s*["«]?([^"»\n\.]{2,50})',
        ):
            m = re.search(regex, text.strip(), re.IGNORECASE)
            if m:
                name_hit = m.group(1).strip(' "\'«».,!?')
                break
        if name_hit and len(name_hit) <= 80:
            voc = self._omni_normalize_vocative(name_hit)
            if voc and partner.omni_addressing_vocative != voc:
                partner.write({'omni_addressing_vocative': voc})
                changed.append('звертання: %s' % voc)
        if changed:
            self._omni_append_chat_memory(partner, '; '.join(changed))

    @api.model
    def _omni_normalize_vocative(self, phrase):
        phrase = (phrase or '').strip()
        if not phrase:
            return ''
        first = phrase.split()[0]
        key = first.lower()
        if key in _UA_VOCATIVE_MAP:
            return _UA_VOCATIVE_MAP[key]
        if phrase[0].isupper() and len(phrase) <= 40:
            return phrase
        return phrase[:1].upper() + phrase[1:] if phrase else ''

    @api.model
    def _omni_append_chat_memory(self, partner, line):
        line = (line or '').strip()
        if not line:
            return
        entry = '%s: %s' % (date.today().isoformat(), line)
        prev = (partner.omni_chat_memory or '').strip()
        merged = (prev + '\n' + entry).strip() if prev else entry
        max_len = 4000
        if len(merged) > max_len:
            merged = merged[-max_len:]
        partner.write({'omni_chat_memory': merged})

    @api.model
    def omni_suggest_vocative_from_name(self, display_name):
        if not display_name:
            return ''
        first = display_name.strip().split()[0].lower()
        return _UA_VOCATIVE_MAP.get(first, '')
