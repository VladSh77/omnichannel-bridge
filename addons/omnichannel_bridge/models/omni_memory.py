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
    'анна': 'Анно',
    'інна': 'Інно',
    'вікторія': 'Вікторіє',
    'тетяна': 'Тетяно',
    'людмила': 'Людмило',
    'оксана': 'Оксано',
    'аліна': 'Аліно',
    'яна': 'Яно',
    'роман': 'Романе',
    'віталій': 'Віталію',
    'євген': 'Євгене',
    'сергій': 'Сергію',
    'максим': 'Максиме',
    'павло': 'Павле',
    'владислав': 'Владиславе',
}

_SOCIAL_URL_RE = re.compile(
    r'https?://(?:www\.)?(?:t\.me|instagram\.com|facebook\.com|m\.me)/[^\s]+',
    re.IGNORECASE,
)
_SOCIAL_HANDLE_RE = re.compile(r'@([A-Za-z0-9_.]{3,40})')


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
        self._omni_attach_paid_booking_facts(partner, text)

    def _omni_vocative_map(self):
        mapping = dict(_UA_VOCATIVE_MAP)
        raw = (
            self.env['ir.config_parameter'].sudo().get_param('omnichannel_bridge.vocative_map_extra', '') or ''
        ).strip()
        if not raw:
            return mapping
        # Format: "ім'я:Звертання, ім'я2:Звертання2"
        for pair in raw.split(','):
            pair = pair.strip()
            if ':' not in pair:
                continue
            k, v = pair.split(':', 1)
            key = (k or '').strip().lower()
            val = (v or '').strip()
            if key and val:
                mapping[key] = val
        return mapping

    @api.model
    def _omni_normalize_vocative(self, phrase):
        phrase = (phrase or '').strip()
        if not phrase:
            return ''
        first = phrase.split()[0]
        key = first.lower()
        mapping = self._omni_vocative_map()
        if key in mapping:
            return mapping[key]
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
        return self._omni_vocative_map().get(first, '')

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
                if not partner.omni_child_age or int(partner.omni_child_age) != age:
                    updates['omni_child_age'] = age
        else:
            # Accept bare age answers like "9" after qualification prompts.
            bare_m = re.fullmatch(r'\s*(\d{1,2})\s*', txt)
            if bare_m:
                age = int(bare_m.group(1))
                if 5 <= age <= 18 and (
                    not partner.omni_child_age or int(partner.omni_child_age) != age
                ):
                    clues.append('age:%s' % age)
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
        url_m = _SOCIAL_URL_RE.search(txt)
        if url_m and not partner.omni_social_profile_url:
            social_url = url_m.group(0).strip().rstrip(').,!?')
            clues.append('social_url:%s' % social_url)
            updates['omni_social_profile_url'] = social_url
        handle_m = _SOCIAL_HANDLE_RE.search(txt)
        if handle_m and not partner.omni_social_username:
            username = handle_m.group(1).strip()
            clues.append('social_username:%s' % username)
            updates['omni_social_username'] = username
        if updates:
            partner.write(updates)
            partner.omni_set_sales_stage(
                'qualifying',
                reason='memory_sales_clues',
                source='omni_memory',
            )
        if clues:
            self._omni_append_chat_memory(partner, '; '.join(clues))

    @api.model
    def _omni_is_paid_or_booked_message(self, text):
        txt = (text or '').strip().lower()
        if not txt:
            return False
        keys = (
            'вже оплат', 'оплатив', 'оплатила', 'оплачено', 'сплатив', 'сплатила',
            'вже заброн', 'забронював', 'забронювала', 'бронь зробив', 'бронь зробила',
            'вже купив', 'вже купила', 'вже купили', 'купив табір', 'купила табір', 'купили табір',
            'придбав', 'придбала', 'придбали', 'кпив', 'купували', 'купувал', 'купув',
            'already paid', 'i paid', 'already booked', 'i booked',
            'już opłaci', 'opłacone', 'już zarezerw', 'zarezerwowa',
            'faktura', 'invoice',
        )
        return any(k in txt for k in keys)

    @api.model
    def _omni_extract_camp_from_order(self, order):
        if not order:
            return ''
        order = order.sudo()
        for line in order.order_line:
            product = line.product_id
            if not product:
                continue
            event = getattr(product, 'bs_event_id', False) or getattr(product.product_tmpl_id, 'bs_event_id', False)
            if event:
                return (event.display_name or event.name or '').strip()
            name = (product.display_name or product.name or '').strip()
            if name:
                return name
        return ''

    @api.model
    def _omni_attach_paid_booking_facts(self, partner, text):
        if not partner or not self._omni_is_paid_or_booked_message(text):
            return
        partner = partner.sudo()
        Partner = self.env['res.partner'].sudo()
        parsed_email = Partner.omni_parse_email(text or '')
        partner_email = (partner.email or '').strip().lower()
        identity_email = (parsed_email or partner_email or '').strip().lower()
        if not identity_email:
            self._omni_append_chat_memory(partner, 'booking_identity_missing_email')
            return
        source_partner = Partner.search([('email', '=ilike', identity_email)], limit=1) or partner
        if parsed_email and not partner.email:
            partner.write({'email': parsed_email})
        details = []
        Order = self.env['sale.order'].sudo() if 'sale.order' in self.env else self.env['res.partner']
        Move = self.env['account.move'].sudo() if 'account.move' in self.env else self.env['res.partner']

        order = Order.search(
            [('partner_id', '=', source_partner.id)],
            order='write_date desc, id desc',
            limit=1,
        ) if 'sale.order' in self.env else False
        if order:
            if order.name:
                details.append('booking_ref:%s' % order.name)
            camp_name = self._omni_extract_camp_from_order(order)
            if camp_name:
                details.append('camp:%s' % camp_name)

        if 'account.move' in self.env:
            inv_domain = [
                ('partner_id', '=', source_partner.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
            ]
            invoice = Move.search(inv_domain, order='invoice_date desc, id desc', limit=1)
            if invoice and invoice.name:
                details.append('invoice:%s' % invoice.name)
                if invoice.payment_state:
                    details.append('invoice_state:%s' % invoice.payment_state)

        if 'event.registration' in self.env:
            Reg = self.env['event.registration'].sudo()
            reg = Reg.search([('partner_id', '=', source_partner.id)], order='write_date desc, id desc', limit=1)
            if reg and reg.event_id:
                details.append('event:%s' % (reg.event_id.display_name or reg.event_id.name or ''))

        details.insert(0, 'booking_identity_email:%s' % identity_email)
        if details:
            self._omni_append_chat_memory(partner, '; '.join(details))
