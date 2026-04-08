# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models


_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    re.UNICODE,
)
_PHONE_RE = re.compile(
    r'(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2,3}',
    re.UNICODE,
)


def _normalize_phone(phone):
    if not phone:
        return ''
    return re.sub(r'\D', '', phone)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    omni_identity_ids = fields.One2many(
        'omni.partner.identity',
        'partner_id',
        string='Messenger identities',
    )
    omni_addressing_vocative = fields.Char(
        string='Звертання (зворот)',
        help='Наприклад: Ольго — для фрази «Доброго дня, пані Ольго!»',
    )
    omni_addressing_style = fields.Selection(
        selection=[
            ('neutral', 'Нейтрально (бот уточнить)'),
            ('formal_female', 'Офіційно (жін., пані …)'),
            ('formal_male', 'Офіційно (чол., пане …)'),
            ('informal', 'На ти'),
        ],
        string='Стиль звернення',
        default='neutral',
    )
    omni_chat_memory = fields.Text(
        string='Пам’ять діалогу (факти з чату)',
        help='Доповнюється правилами з повідомлень клієнта; перевіряйте перед використанням.',
    )
    omni_child_age = fields.Integer(string='Вік дитини (років)')
    omni_preferred_period = fields.Char(string='Бажаний період/зміна')
    omni_departure_city = fields.Char(string='Місто виїзду')
    omni_budget_amount = fields.Float(string='Орієнтовний бюджет')
    omni_budget_currency = fields.Char(string='Валюта бюджету')
    omni_sales_stage = fields.Selection(
        selection=[
            ('new', 'Новий запит'),
            ('qualifying', 'Кваліфікація'),
            ('proposal', 'Підібрано варіанти'),
            ('handoff', 'Передано менеджеру'),
        ],
        string='Етап продажу (чат)',
        default='new',
    )
    omni_last_purchase_notify_at = fields.Datetime(string='Last purchase notify at')
    omni_last_purchase_notify_ref = fields.Char(string='Last purchase notify reference')
    omni_last_purchase_notify_amount = fields.Char(string='Last purchase notify amount')

    def _omni_find_by_phone(self, phone):
        needle = _normalize_phone(phone)
        if not needle or len(needle) < 7:
            return self.browse()
        candidates = self.sudo().search([
            '|',
            ('phone', '!=', False),
            ('mobile', '!=', False),
        ])
        for partner in candidates:
            for value in (partner.phone, partner.mobile):
                if value and _normalize_phone(value).endswith(needle[-9:]):
                    return partner
        return self.browse()

    @api.model
    def omni_find_or_create_customer(self, vals):
        """vals: name, phone, email, provider, external_id, display_name, metadata_json"""
        Identity = self.env['omni.partner.identity'].sudo()
        provider = vals['provider']
        external_id = str(vals['external_id'])
        existing = Identity.search([
            ('provider', '=', provider),
            ('external_id', '=', external_id),
        ], limit=1)
        if existing:
            return existing.partner_id
        partner = self.browse()
        if vals.get('phone'):
            partner = self._omni_find_by_phone(vals['phone'])
        if not partner and vals.get('email'):
            partner = self.sudo().search(
                [('email', '=', vals['email'].strip().lower())],
                limit=1,
            )
        if not partner:
            crm_lead_type = (
                self.env['ir.config_parameter']
                .sudo()
                .get_param('omnichannel_bridge.new_contact_as_lead', 'False')
            )
            partner_vals = {
                'name': vals.get('name') or vals.get('display_name') or external_id,
                'phone': vals.get('phone'),
                'email': vals.get('email'),
            }
            partner_vals = {k: v for k, v in partner_vals.items() if v}
            if partner_vals.get('email'):
                partner_vals['email'] = partner_vals['email'].strip().lower()
            partner = self.sudo().create(partner_vals)
            if str(crm_lead_type).lower() in ('1', 'true', 'yes'):
                self.env['crm.lead'].sudo().create({
                    'name': _('New chat: %s') % partner.name,
                    'partner_id': partner.id,
                })
        Identity.create({
            'partner_id': partner.id,
            'provider': provider,
            'external_id': external_id,
            'display_name': vals.get('display_name'),
            'metadata_json': vals.get('metadata_json'),
        })
        return partner

    @api.model
    def omni_parse_email(self, text):
        if not text:
            return ''
        match = _EMAIL_RE.search(text)
        return match.group(0).strip().lower() if match else ''

    @api.model
    def omni_parse_phone(self, text):
        if not text:
            return ''
        match = _PHONE_RE.search(text)
        if not match:
            return ''
        raw = match.group(0)
        digits = _normalize_phone(raw)
        return raw.strip() if len(digits) >= 9 else ''

    @api.model
    def omni_resolve_from_clues(self, partner, provider, external_id, text):
        """Prefer existing customer if email/phone in message; relink messenger identity."""
        if not partner:
            return partner
        email = self.omni_parse_email(text)
        phone = self.omni_parse_phone(text)
        found = self.browse()
        if email:
            found = self.sudo().search([('email', '=', email)], limit=1)
        if not found and phone:
            found = self._omni_find_by_phone(phone)
        Identity = self.env['omni.partner.identity'].sudo()
        ident = Identity.search(
            [
                ('provider', '=', provider),
                ('external_id', '=', str(external_id)),
            ],
            limit=1,
        )
        if found and found.id != partner.id:
            if ident:
                ident.write({'partner_id': found.id})
            partner = found
        else:
            vals = {}
            if email and not partner.email:
                vals['email'] = email
            if phone and not partner.phone and not partner.mobile:
                vals['phone'] = phone
            if vals:
                partner.sudo().write(vals)
        return partner
