# -*- coding: utf-8 -*-
import json
import re
from datetime import timedelta

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

    _OMNI_STAGE_TRANSITIONS = {
        'new': {'qualifying', 'handoff'},
        'qualifying': {'proposal', 'handoff'},
        'proposal': {'handoff', 'qualifying'},
        'handoff': {'qualifying'},
    }

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
    omni_purchase_confirmed_at = fields.Datetime(string='Purchase confirmed at')
    omni_tg_marketing_opt_in = fields.Boolean(string='Telegram marketing consent')
    omni_tg_marketing_opt_in_at = fields.Datetime(string='Telegram marketing consent at')
    omni_tg_last_broadcast_at = fields.Datetime(string='Telegram last broadcast at')
    omni_erased_at = fields.Datetime(string='Omni data erased at')
    omni_last_stage_change_at = fields.Datetime(string='Last stage change at')
    omni_last_stage_change_reason = fields.Char(string='Last stage change reason')
    omni_lead_score = fields.Integer(string='Omni lead score', default=0)
    omni_lead_score_reason = fields.Char(string='Omni lead score reason')

    def omni_set_sales_stage(self, new_stage, channel=None, reason='', source=''):
        self.ensure_one()
        old_stage = self.omni_sales_stage or 'new'
        if old_stage == new_stage:
            return old_stage, new_stage, False
        Transition = self.env['omni.stage.transition'].sudo()
        custom = Transition.search([('active', '=', True), ('from_stage', '=', old_stage)])
        if custom:
            allowed = set(custom.mapped('to_stage'))
        else:
            allowed = self._OMNI_STAGE_TRANSITIONS.get(old_stage, set())
        if new_stage not in allowed:
            return old_stage, old_stage, False
        self.sudo().write({
            'omni_sales_stage': new_stage,
            'omni_last_stage_change_at': fields.Datetime.now(),
            'omni_last_stage_change_reason': reason or False,
        })
        self.env['omni.stage.event'].sudo().create({
            'partner_id': self.id,
            'channel_id': channel.id if channel else False,
            'old_stage': old_stage,
            'new_stage': new_stage,
            'reason': reason or '',
            'source': source or '',
        })
        return old_stage, new_stage, True

    def action_omni_right_to_erasure(self):
        """Anonymize omnichannel personal data while keeping accounting references."""
        for partner in self.sudo():
            anon_name = _('Removed Contact #%s') % partner.id
            vals = {
                'name': anon_name,
                'phone': False,
                'mobile': False,
                'email': False,
                'omni_addressing_vocative': False,
                'omni_chat_memory': False,
                'omni_child_age': False,
                'omni_preferred_period': False,
                'omni_departure_city': False,
                'omni_budget_amount': False,
                'omni_budget_currency': False,
                'omni_erased_at': fields.Datetime.now(),
            }
            partner.write(vals)
            partner.omni_identity_ids.sudo().write({
                'display_name': 'erased',
                'metadata_json': '{"erased": true}',
            })
        return True

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
    def _omni_merge_telegram_identity_metadata(self, old_json, new_json):
        """Deep-merge inbound Telegram snapshots into identity.metadata_json (tg_getchat, contact, user, chat)."""
        try:
            old = json.loads(old_json or '{}') or {}
        except Exception:
            old = {}
        try:
            new = json.loads(new_json or '{}') or {}
        except Exception:
            new = {}
        for key in ('telegram', 'chat'):
            if key not in new or not new[key]:
                continue
            if not isinstance(new[key], dict):
                old[key] = new[key]
                continue
            if key not in old or not isinstance(old.get(key), dict):
                old[key] = dict(new[key])
            else:
                old[key] = {**old[key], **new[key]}
        if new.get('tg_getchat') and isinstance(new['tg_getchat'], dict):
            prev = old.get('tg_getchat') if isinstance(old.get('tg_getchat'), dict) else {}
            old['tg_getchat'] = {**prev, **new['tg_getchat']}
        if new.get('telegram_contact'):
            old['telegram_contact'] = new['telegram_contact']
        return json.dumps(old, ensure_ascii=False)

    @api.model
    def omni_find_or_create_customer(self, vals):
        """vals: name, phone, email, provider, external_id, display_name, metadata_json"""
        Identity = self.env['omni.partner.identity'].sudo()
        provider = vals['provider']
        external_id = str(vals['external_id'])
        metadata = {}
        if vals.get('metadata_json'):
            try:
                metadata = json.loads(vals.get('metadata_json') or '{}') or {}
            except Exception:
                metadata = {}
        email_candidates = []
        if vals.get('email'):
            email_candidates.append(vals.get('email'))
        # Channel-specific payloads may carry additional customer emails.
        for key in ('user_email', 'booking_email', 'email'):
            v = metadata.get(key)
            if v:
                email_candidates.append(v)
        for nested_key in ('telegram', 'meta', 'whatsapp', 'viber', 'contact'):
            nested = metadata.get(nested_key) or {}
            if isinstance(nested, dict):
                v = nested.get('email')
                if v:
                    email_candidates.append(v)
        # Optional custom metadata variants from external bridges.
        for key in ('secondary_email', 'alt_email', 'parent_email', 'billing_email'):
            v = metadata.get(key)
            if v:
                email_candidates.append(v)
        existing = Identity.search([
            ('provider', '=', provider),
            ('external_id', '=', external_id),
        ], limit=1)
        if existing:
            partner = existing.partner_id.sudo()
            if vals.get('metadata_json') and provider == 'telegram':
                merged_meta = self._omni_merge_telegram_identity_metadata(
                    existing.metadata_json,
                    vals['metadata_json'],
                )
                if merged_meta != (existing.metadata_json or ''):
                    existing.sudo().write({'metadata_json': merged_meta})
            patch_vals = {}
            # Keep customer card enriched even when identity already exists.
            current_name = (partner.name or '').strip()
            placeholder_name = (
                not current_name
                or current_name.lower().startswith('telegram:')
                or current_name.lower().startswith('meta:')
                or current_name.lower().startswith('whatsapp:')
                or current_name.lower().startswith('viber:')
                or current_name.lower().startswith('tiktok:')
                or current_name.lower().startswith('line:')
            )
            if vals.get('display_name') and placeholder_name:
                patch_vals['name'] = vals.get('display_name')
            if vals.get('name') and placeholder_name:
                patch_vals['name'] = vals.get('name')
            if not partner.email:
                candidate_email = next(
                    (e for e in [((x or '').strip().lower()) for x in email_candidates] if e),
                    '',
                )
                if candidate_email:
                    patch_vals['email'] = candidate_email
            if not (partner.phone or partner.mobile) and vals.get('phone'):
                patch_vals['phone'] = vals.get('phone')
            if patch_vals:
                partner.write(patch_vals)
            return partner

        def _search_by_email(addr):
            addr = (addr or '').strip().lower()
            if not addr:
                return self.browse()
            # Identity cascade standard: external_id -> email -> additional email-like fields -> phone.
            partner = self.sudo().search([('email', '=', addr)], limit=1)
            if partner:
                return partner
            # Best-effort for custom DBs: inspect email-like char fields.
            email_like_fields = []
            for fname, field in self._fields.items():
                if fname == 'email':
                    continue
                if field.type != 'char':
                    continue
                if 'email' not in fname.lower():
                    continue
                email_like_fields.append(fname)
            for fname in email_like_fields[:30]:
                try:
                    partner = self.sudo().search([(fname, '=', addr)], limit=1)
                except Exception:
                    partner = self.browse()
                if partner:
                    return partner
            return self.browse()

        partner = self.browse()
        for email in email_candidates:
            partner = _search_by_email(email)
            if partner:
                break
        if not partner and vals.get('phone'):
            partner = self._omni_find_by_phone(vals['phone'])
        if not partner:
            crm_lead_type = (
                self.env['ir.config_parameter']
                .sudo()
                .get_param('omnichannel_bridge.new_contact_as_lead', 'False')
            )
            partner_vals = {
                'name': vals.get('name') or vals.get('display_name') or external_id,
                'phone': vals.get('phone'),
                'email': next((e for e in [((x or '').strip().lower()) for x in email_candidates] if e), vals.get('email')),
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
        # Best-effort duplicate merge by strict email/phone rules.
        if partner:
            partner = partner.sudo().omni_merge_duplicates_by_rules()
        return partner

    def omni_merge_duplicates_by_rules(self):
        self.ensure_one()
        partner = self.sudo()
        email = (partner.email or '').strip().lower()
        phone = _normalize_phone(partner.phone or partner.mobile or '')
        if not email and not phone:
            return partner
        domain = [('id', '!=', partner.id)]
        candidates = self.sudo().search(domain, limit=200)
        duplicate = self.browse()
        for cand in candidates:
            cand_email = (cand.email or '').strip().lower()
            cand_phone = _normalize_phone(cand.phone or cand.mobile or '')
            email_match = bool(email and cand_email and email == cand_email)
            phone_match = bool(phone and cand_phone and cand_phone.endswith(phone[-9:]))
            if email_match or phone_match:
                duplicate = cand
                break
        if not duplicate:
            return partner
        # Keep the richer card; move identities to the winner.
        winner = partner
        loser = duplicate.sudo()
        if len((loser.omni_chat_memory or '')) > len((winner.omni_chat_memory or '')):
            winner, loser = loser, winner
        loser.omni_identity_ids.sudo().write({'partner_id': winner.id})
        vals = {}
        for field_name in ('email', 'phone', 'mobile', 'omni_preferred_period', 'omni_departure_city'):
            if not getattr(winner, field_name) and getattr(loser, field_name):
                vals[field_name] = getattr(loser, field_name)
        if not winner.omni_child_age and loser.omni_child_age:
            vals['omni_child_age'] = loser.omni_child_age
        if not winner.omni_budget_amount and loser.omni_budget_amount:
            vals['omni_budget_amount'] = loser.omni_budget_amount
            if not winner.omni_budget_currency and loser.omni_budget_currency:
                vals['omni_budget_currency'] = loser.omni_budget_currency
        if vals:
            winner.write(vals)
        # Soft anonymize loser to avoid duplicate active profile.
        loser.write({
            'name': _('[Merged duplicate] %s') % (loser.name or loser.id),
            'email': False,
            'phone': False,
            'mobile': False,
            'active': False,
        })
        return winner

    def omni_recompute_lead_score(self, reason=''):
        for partner in self.sudo():
            score = 0
            if partner.omni_child_age:
                score += 10
            if partner.omni_preferred_period:
                score += 10
            if partner.omni_departure_city:
                score += 8
            if partner.omni_budget_amount:
                score += 10
            if partner.phone or partner.mobile or partner.email:
                score += 12
            if partner.omni_sales_stage == 'proposal':
                score += 15
            if partner.omni_sales_stage == 'handoff':
                score += 12
            mem = (partner.omni_chat_memory or '').lower()
            if 'purchase_intent' in mem:
                score += 18
            if 'objection:' in mem:
                score -= 6
            partner.write({
                'omni_lead_score': max(0, min(100, score)),
                'omni_lead_score_reason': (reason or 'auto')[:120],
            })

    @api.model
    def omni_cron_purge_child_sensitive_fields(self, limit=500):
        """Minimize child-related fields after retention window."""
        icp = self.env['ir.config_parameter'].sudo()
        try:
            retention_days = int(icp.get_param('omnichannel_bridge.retention_child_data_days', '365'))
        except ValueError:
            retention_days = 365
        retention_days = max(30, retention_days)
        cutoff = fields.Datetime.now() - timedelta(days=retention_days)
        partners = self.sudo().search(
            [
                ('omni_child_age', '!=', False),
                '|',
                ('omni_last_stage_change_at', '=', False),
                ('omni_last_stage_change_at', '<', cutoff),
            ],
            limit=max(1, int(limit)),
        )
        for partner in partners:
            partner.write({
                'omni_child_age': False,
            })
