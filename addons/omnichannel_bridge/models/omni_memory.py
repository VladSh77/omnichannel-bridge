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
        self._omni_capture_sales_clues(partner, text)

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

    @api.model
    def _omni_capture_sales_clues(self, partner, text):
        txt = (text or '').strip()
        if not txt:
            return
        partner = partner.sudo()
        updates = {}
        clues = []
        age_m = re.search(r'(\d{1,2})\s*(?:рок[аів]?|р\.|lat|lata)', txt, re.IGNORECASE)
        if age_m:
            age = int(age_m.group(1))
            clues.append('age:%s' % age)
            if 5 <= age <= 18:
                updates['omni_child_age'] = age
        budget_m = re.search(
            r'(\d{3,6})\s*(грн|uah|zl|pln|zł|€|eur)',
            txt,
            re.IGNORECASE,
        )
        if budget_m:
            amount = float(budget_m.group(1))
            curr = budget_m.group(2).lower()
            clues.append('budget:%s%s' % (budget_m.group(1), curr))
            updates['omni_budget_amount'] = amount
            updates['omni_budget_currency'] = curr
        period_m = re.search(
            r'(черв(?:ень|ня)|лип(?:ень|ня)|серп(?:ень|ня)|wrzesie[nń]|lipiec|sierpie[nń]|july|august)',
            txt,
            re.IGNORECASE,
        )
        if period_m:
            period = period_m.group(1).lower()
            clues.append('period:%s' % period)
            updates['omni_preferred_period'] = period
        city_m = re.search(
            r'(?:з|из|from)\s+([A-Za-zА-Яа-яІіЇїЄєҐґŁłŚśŻżŹźĆćŃńÓóĘęĄą\-]{3,30})',
            txt,
            re.IGNORECASE,
        )
        if city_m:
            city = city_m.group(1)
            clues.append('city:%s' % city)
            updates['omni_departure_city'] = city
        if updates:
            partner.write(updates)
            partner.omni_set_sales_stage(
                'qualifying',
                reason='memory_sales_clues',
                source='omni_memory',
            )
        if clues:
            self._omni_append_chat_memory(partner, '; '.join(clues))
