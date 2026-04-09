# -*- coding: utf-8 -*-
import logging
import hashlib
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.fields import Datetime

_logger = logging.getLogger(__name__)


class MailChannel(models.Model):
    _inherit = 'discuss.channel'

    omni_provider = fields.Selection(
        selection=lambda self: self.env['omni.integration']._selection_providers(),
        index=True,
    )
    omni_external_thread_id = fields.Char(index=True)
    omni_customer_partner_id = fields.Many2one('res.partner', index=True, ondelete='set null')
    omni_bot_paused = fields.Boolean(default=False, index=True)
    omni_bot_pause_reason = fields.Char()
    omni_last_human_reply_at = fields.Datetime()
    omni_last_bot_reply_at = fields.Datetime()
    omni_last_manager_activity_at = fields.Datetime()
    omni_last_outbound_at = fields.Datetime()
    omni_last_outbound_hash = fields.Char()
    omni_last_outbound_author_kind = fields.Selection(
        selection=[('bot', 'Bot'), ('manager', 'Manager')],
    )
    omni_legal_notice_sent_at = fields.Datetime()
    omni_reserve_lead_id = fields.Many2one('crm.lead', ondelete='set null')
    omni_reserve_entry_id = fields.Many2one('omni.reserve.entry', ondelete='set null')
    omni_reserve_requested_at = fields.Datetime()
    omni_last_customer_inbound_at = fields.Datetime()
    omni_window_reminder_sent_at = fields.Datetime()
    omni_window_last_call_sent_at = fields.Datetime()
    omni_window_reminder_count = fields.Integer(default=0)
    omni_last_fomo_notify_at = fields.Datetime()
    omni_last_marketing_touch_at = fields.Datetime()
    omni_last_marketing_touch_type = fields.Selection(
        selection=[('reminder', 'Reminder'), ('fomo', 'FOMO'), ('last_call', 'Last call')],
    )
    omni_livechat_entry_state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('awaiting_name', 'Awaiting name'),
            ('awaiting_contact', 'Awaiting contact'),
            ('ready', 'Ready'),
        ],
        default='new',
        index=True,
    )
    omni_livechat_entry_topic = fields.Selection(
        selection=[
            ('company', 'About company'),
            ('camps', 'Camp programs'),
            ('other_services', 'Other services'),
            ('prices', 'Prices and terms'),
            ('contact', 'Leave contact'),
            ('unknown', 'Unknown'),
        ],
    )
    omni_livechat_contact_attempts = fields.Integer(default=0)
    omni_detected_lang = fields.Selection(
        selection=[('uk', 'Ukrainian'), ('pl', 'Polish')],
        help='Detected client language for this thread (runtime hint for AI).',
    )

    _sql_constraints = [
        (
            'omni_thread_unique',
            'unique(omni_provider, omni_external_thread_id)',
            'A Discuss thread for this messenger conversation already exists.',
        ),
    ]

    def action_omni_pause_bot(self):
        self.sudo().write({
            'omni_bot_paused': True,
            'omni_bot_pause_reason': 'manual_manager_takeover',
        })
        return True

    def action_omni_resume_bot(self):
        self.sudo().write({
            'omni_bot_paused': False,
            'omni_bot_pause_reason': False,
        })
        return True

    def _omni_thread_key_parts(self):
        self.ensure_one()
        return self.omni_provider, self.omni_external_thread_id

    def _omni_is_website_livechat_channel(self):
        self.ensure_one()
        if self.omni_provider == 'site_livechat':
            return True
        if 'livechat_channel_id' in self._fields and self.livechat_channel_id:
            return True
        return self.channel_type == 'livechat'

    def _omni_is_internal_author(self, partner):
        if not partner:
            return False
        # Live chat runs as public user; reading user_ids on res.partner needs elevated env.
        partner = partner.sudo()
        return bool(partner.user_ids.filtered(lambda u: u.has_group('base.group_user')))

    def _omni_client_requests_human(self, text):
        lowered = (text or '').lower()
        keys = (
            'менеджер',
            'оператор',
            'людина',
            'з\'єднайте з менеджером',
            'покличте менеджера',
            'human',
            'manager',
            'operator',
        )
        return any(k in lowered for k in keys)

    def _omni_detect_livechat_topic(self, text):
        txt = (text or '').lower()
        if not txt:
            return 'unknown'
        mapping = {
            'company': ('про компан', 'про campscout', 'хто ви', 'about company', 'o firmie'),
            'camps': ('табір', 'табор', 'зміна', 'програма', 'camp', 'obóz', 'turnus'),
            'other_services': ('інші послуги', 'інша послуга', 'other service', 'inne usługi'),
            'prices': ('ціна', 'ціни', 'вартіст', 'price', 'cena', 'koszt'),
            'contact': ('звʼяж', 'звяж', 'контакт', 'передзвон', 'email', 'телефон', 'kontakt'),
        }
        for topic, keys in mapping.items():
            if any(k in txt for k in keys):
                return topic
        return 'unknown'

    def _omni_livechat_entry_menu_text(self):
        return self._omni_livechat_entry_menu_text_lang(is_pl=False)

    def _omni_livechat_online_manager_name(self, is_pl=False):
        manager = self.env['omni.notify'].sudo()._peek_online_manager_user()
        if not manager:
            return ''
        # Prefer per-user livechat display name configured in Odoo user settings.
        livechat_name = ''
        for attr in ('livechat_username', 'im_livechat_username'):
            if attr in manager._fields:
                livechat_name = (getattr(manager, attr, '') or '').strip()
                if livechat_name:
                    break
        name = (livechat_name or manager.name or '').strip()
        if not name:
            return ''
        # For UA prompts prefer natural addressing (vocative/known transliteration);
        # for PL keep manager-entered display name.
        if is_pl:
            return name[:60]
        words = name.split()
        first = words[0]
        first_key = first.lower()
        voc = self.env['omni.memory'].sudo().omni_suggest_vocative_from_name(first)
        if not voc:
            translit_hint = {
                'volodymyr': 'Володимире',
                'vladimir': 'Володимире',
                'oleksandr': 'Олександре',
                'andrii': 'Андрію',
                'andriy': 'Андрію',
                'serhii': 'Сергію',
                'sergey': 'Сергію',
                'yevhen': 'Євгене',
            }
            voc = translit_hint.get(first_key, '')
        if voc:
            name = ' '.join([voc] + words[1:]).strip()
        return name[:60]

    def _omni_livechat_entry_menu_text_lang(self, is_pl=False):
        manager_name = self._omni_livechat_online_manager_name(is_pl=is_pl)
        if is_pl:
            intro = (
                '🟢 Na czacie jest dostępny manager: %s.\n' % manager_name
                if manager_name else
                '🟡 Manager odpowie, gdy tylko będzie online.\n'
            )
            return intro + (
                '👋 Jak mogę pomóc na start?\n'
                'Napisz jednym zdaniem, co jest teraz najważniejsze: program, cena, terminy, dojazd czy bezpieczeństwo.'
            )
        intro = (
            '🟢 Зараз у чаті доступний менеджер: %s.\n' % manager_name
            if manager_name else
            '🟡 Менеджер підключиться, щойно буде онлайн.\n'
        )
        return intro + (
            '👋 Як можу допомогти на старті?\n'
            'Напишіть одним реченням, що для вас зараз головне: програма, ціна, дати, доїзд чи безпека.'
        )

    def _omni_livechat_contact_prompt_text(self):
        return self._omni_livechat_contact_prompt_text_lang(is_pl=False)

    def _omni_livechat_contact_prompt_text_lang(self, is_pl=False):
        manager_name = self._omni_livechat_online_manager_name(is_pl=is_pl)
        privacy_url = (
            self.env['ir.config_parameter'].sudo().get_param('omnichannel_bridge.legal_privacy_url')
            or ''
        ).strip()
        if not privacy_url:
            base_url = (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').strip().rstrip('/')
            if base_url:
                privacy_url = '%s/privacy-policy' % base_url
        if is_pl:
            base = (
                ('🟢 Twój manager na czacie: %s.\n' % manager_name) if manager_name else ''
            ) + (
                '📞 Aby manager mógł się z Tobą skontaktować, zostaw proszę telefon lub email.\n'
                '✉️ Przykład: +48 500 600 700 lub rodzic@email.com\n'
                '🛡️ Wysyłając kontakt, zgadzasz się na przetwarzanie danych w celu doboru obozu.'
            )
            if privacy_url:
                base += '\n🔐 RODO / Polityka prywatności: %s' % privacy_url
            return base
        base = (
            ('🟢 Ваш менеджер у чаті: %s.\n' % manager_name) if manager_name else ''
        ) + (
            '📞 Щоб менеджер міг звʼязатися з вами, залиште, будь ласка, телефон або email.\n'
            '✉️ Приклад: +380 67 123 45 67 або parent@email.com\n'
            '🛡️ Надсилаючи контакт, ви погоджуєтесь на обробку даних для підбору табору.'
        )
        if privacy_url:
            base += '\n🔐 RODO / Політика приватності: %s' % privacy_url
        return base

    def _omni_livechat_name_prompt_text_lang(self, is_pl=False):
        if is_pl:
            return '🙂 Na start napisz proszę, jak mamy się do Ciebie zwracać (imię).'
        return '🙂 Для початку підкажіть, будь ласка, як до вас звертатися (імʼя).'

    def _omni_livechat_contact_invalid_text(self, is_pl=False):
        if is_pl:
            return (
                '⚠️ Nie widzę jeszcze poprawnego kontaktu. Aby kontynuować, wyślij telefon lub email w formacie:\n'
                '• +48 500 600 700\n'
                '• rodzic@email.com'
            )
        return (
            '⚠️ Поки не бачу коректного контакту. Щоб продовжити, надішліть телефон або email у форматі прикладу:\n'
            '• +380 67 123 45 67\n'
            '• parent@email.com'
        )

    def _omni_livechat_prefers_polish(self, text):
        txt = (text or '').lower()
        if not txt:
            return False
        if any(ch in txt for ch in ('ą', 'ć', 'ę', 'ł', 'ń', 'ó', 'ś', 'ź', 'ż')):
            return True
        keys = ('dzień dobry', 'obóz', 'turnus', 'cena', 'kontakt')
        return any(k in txt for k in keys)

    def _omni_extract_contact_from_text(self, text):
        Partner = self.env['res.partner'].sudo()
        email = Partner.omni_parse_email(text or '')
        phone = Partner.omni_parse_phone(text or '')
        return email, phone

    def _omni_extract_name_from_text(self, text):
        txt = re.sub(r'\s+', ' ', (text or '').strip())
        if not txt:
            return ''
        if any(ch.isdigit() for ch in txt):
            return ''
        if '@' in txt:
            return ''
        if len(txt) > 60:
            return ''
        bad = ('ціна', 'табір', 'camp', 'kontakt', 'phone', 'email')
        lowered = txt.lower()
        if any(k in lowered for k in bad):
            return ''
        return txt[:60]

    def _omni_is_visitor_name(self, name):
        txt = (name or '').strip().lower()
        return bool(re.match(r'^(visitor|відвідувач)\s*#\d+', txt))

    def _omni_livechat_name_needs_clarification(self, author):
        name = (author.name or '').strip()
        if not name:
            return True
        if self._omni_is_visitor_name(name):
            return True
        # One-letter aliases like "B" look robotic in chat;
        # ask how to address the person before contact handoff flow.
        if len(name) < 2:
            return True
        return False

    def _omni_resolve_livechat_customer_partner(self, message):
        """Resolve a stable customer partner for website livechat inbound."""
        self.ensure_one()
        sudo_channel = self.sudo()
        author = message.author_id or sudo_channel.omni_customer_partner_id
        if author:
            return author.sudo()
        guest = getattr(message, 'author_guest_id', False)
        guest_name = (getattr(guest, 'name', '') or '').strip()
        guest_name = re.sub(r'^(?:visitor|відвідувач)\s*#\d+\s*', '', guest_name, flags=re.IGNORECASE).strip()
        partner = self.env['res.partner'].sudo().create({
            'name': (guest_name or 'Гість сайту')[:80],
            'comment': 'Auto-created from website livechat guest inbound.',
        })
        sudo_channel.write({'omni_customer_partner_id': partner.id})
        return partner

    def _omni_refresh_livechat_contact_identity(self, author):
        author = author.sudo()
        if not self._omni_is_visitor_name(author.name):
            return
        new_name = ''
        if author.email:
            new_name = (author.email.split('@')[0] or '').strip()
        if not new_name and (author.phone or author.mobile):
            digits = re.sub(r'\D', '', author.phone or author.mobile or '')
            new_name = 'Клієнт сайту %s' % (digits[-4:] if digits else '')
        if not new_name:
            new_name = 'Клієнт сайту'
        author.write({'name': new_name[:80]})

    def _omni_refresh_livechat_channel_label(self, author):
        author = author.sudo()
        display = (author.display_name or author.name or 'Клієнт сайту').strip()
        if self._omni_is_visitor_name(display):
            return
        if self.name != display:
            self.sudo().write({'name': display[:120]})

    def _omni_handle_livechat_entry_flow(self, author, body, odoobot):
        """Returns True when entry flow consumed message and AI should be skipped."""
        self.ensure_one()
        author = author.sudo()
        state = self.omni_livechat_entry_state or 'new'
        is_pl = self._omni_livechat_prefers_polish(body)
        topic = self._omni_detect_livechat_topic(body)
        email, phone = self._omni_extract_contact_from_text(body)
        has_contact = bool(author.email or author.phone or author.mobile or email or phone)
        manager_hours_now = self.env['omni.ai'].sudo()._omni_manager_hours_active_now()
        if state == 'new':
            vals = {'omni_livechat_entry_topic': topic}
            if self._omni_livechat_name_needs_clarification(author):
                self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                    body=self._omni_livechat_name_prompt_text_lang(is_pl=is_pl),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                vals['omni_livechat_entry_state'] = 'awaiting_name'
                self.sudo().write(vals)
                return True
            # Off-hours policy: before long bot dialog we require at least one contact point.
            if not manager_hours_now and not has_contact:
                self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                    body=self._omni_livechat_contact_prompt_text_lang(is_pl=is_pl),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                vals['omni_livechat_entry_state'] = 'awaiting_contact'
                vals['omni_livechat_contact_attempts'] = 0
                self.sudo().write(vals)
                return True
            if topic == 'unknown':
                self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                    body=self._omni_livechat_entry_menu_text_lang(is_pl=is_pl),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                if has_contact:
                    vals['omni_livechat_entry_state'] = 'ready'
                else:
                    vals['omni_livechat_entry_state'] = 'awaiting_contact'
                    vals['omni_livechat_contact_attempts'] = 0
                self.sudo().write(vals)
                return True
            if topic == 'contact' and not has_contact:
                self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                    body=self._omni_livechat_contact_prompt_text_lang(is_pl=is_pl),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                vals['omni_livechat_entry_state'] = 'awaiting_contact'
                vals['omni_livechat_contact_attempts'] = 0
                self.sudo().write(vals)
                return True
            vals['omni_livechat_entry_state'] = 'ready'
            vals['omni_livechat_contact_attempts'] = 0
            self.sudo().write(vals)
            return False
        if state == 'awaiting_name':
            guessed_name = self._omni_extract_name_from_text(body)
            if guessed_name:
                author.write({'name': guessed_name})
                self._omni_refresh_livechat_channel_label(author)
                if not has_contact:
                    self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                        body=self._omni_livechat_contact_prompt_text_lang(is_pl=is_pl),
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=odoobot.id,
                    )
                    self.sudo().write({
                        'omni_livechat_entry_state': 'awaiting_contact',
                        'omni_livechat_contact_attempts': 0,
                    })
                    return True
                self.sudo().write({'omni_livechat_entry_state': 'ready'})
                return False
            self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                body=self._omni_livechat_name_prompt_text_lang(is_pl=is_pl),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=odoobot.id,
            )
            return True
        if state == 'awaiting_contact':
            if self._omni_livechat_name_needs_clarification(author):
                guessed_name = self._omni_extract_name_from_text(body)
                if guessed_name:
                    author.write({'name': guessed_name})
                    self._omni_refresh_livechat_channel_label(author)
                    self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                        body=self._omni_livechat_contact_prompt_text_lang(is_pl=is_pl),
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=odoobot.id,
                    )
                    return True
                self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                    body=self._omni_livechat_name_prompt_text_lang(is_pl=is_pl),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                self.sudo().write({'omni_livechat_entry_state': 'awaiting_name'})
                return True
            if email or phone or author.email or author.phone or author.mobile:
                upd = {}
                if email and not author.email:
                    upd['email'] = email
                if phone and not (author.phone or author.mobile):
                    upd['phone'] = phone
                if upd:
                    author.write(upd)
                self._omni_refresh_livechat_contact_identity(author)
                self._omni_refresh_livechat_channel_label(author)
                self.sudo().write({
                    'omni_livechat_entry_state': 'ready',
                    'omni_livechat_contact_attempts': 0,
                    'omni_customer_partner_id': author.id,
                })
                self.env['omni.bridge'].sudo()._omni_maybe_create_crm_lead(author, 'site_livechat')
                return False
            attempts = int(self.omni_livechat_contact_attempts or 0) + 1
            self.sudo().write({'omni_livechat_contact_attempts': attempts})
            prompt = self._omni_livechat_contact_prompt_text_lang(is_pl=is_pl)
            text_has_contact_intent = any(k in (body or '').lower() for k in ('mail', '@', 'пошта', 'email', 'телефон', 'phone'))
            if attempts >= 2 or text_has_contact_intent:
                prompt = self._omni_livechat_contact_invalid_text(is_pl=is_pl)
            # Avoid "bot monologue": after the first failed contact attempt,
            # continue normal AI dialog and keep contact as soft requirement.
            if attempts <= 1:
                self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                    body=prompt,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                return True
            self.sudo().write({'omni_livechat_entry_state': 'ready'})
            return False
        return False

    @api.model
    def _omni_operator_partner_ids(self):
        """Partners who should always see omnichannel threads in Discuss."""
        notify = self.env['omni.notify'].sudo()
        users = notify._manager_pool_users()
        # Fallback: if manager pool is empty, expose chats to internal users
        # so operators are not blocked by an empty Discuss inbox.
        if not users:
            users = self.env['res.users'].sudo().search([
                ('share', '=', False),
                ('active', '=', True),
            ])
        partners = users.mapped('partner_id').filtered(lambda p: p and p.active)
        return partners.ids

    @api.model
    def omni_get_or_create_thread(self, provider, external_thread_id, partner, label):
        existing = self.sudo().search([
            ('omni_provider', '=', provider),
            ('omni_external_thread_id', '=', str(external_thread_id)),
        ], limit=1)
        if existing:
            existing.sudo().omni_thread_align_customer(partner)
            return existing, False
        # Fallback: if identity/thread id changed upstream, reuse latest channel
        # of the same customer/provider instead of creating duplicates.
        if partner:
            existing = self.sudo().search([
                ('omni_provider', '=', provider),
                ('omni_customer_partner_id', '=', partner.id),
            ], order='write_date desc, id desc', limit=1)
            if existing:
                existing.sudo().write({'omni_external_thread_id': str(external_thread_id)})
                existing.sudo().omni_thread_align_customer(partner)
                return existing, False
        odoobot = self.env.ref('base.partner_root')
        operator_partner_ids = self._omni_operator_partner_ids()
        member_ids = list(dict.fromkeys([partner.id, odoobot.id] + operator_partner_ids))
        channel = self.sudo().create({
            'name': label or _('[%(provider)s] %(name)s') % {
                'provider': provider,
                'name': partner.display_name,
            },
            'channel_type': 'group',
            'omni_provider': provider,
            'omni_external_thread_id': str(external_thread_id),
            'omni_customer_partner_id': partner.id,
        })
        if hasattr(channel, 'add_members'):
            channel.add_members(partner_ids=member_ids)
        else:
            channel.channel_partner_ids = [(6, 0, member_ids)]
        return channel, True

    def omni_thread_align_customer(self, partner):
        self.ensure_one()
        if not partner:
            return
        self.sudo().write({'omni_customer_partner_id': partner.id})
        member_partner_ids = self.channel_partner_ids.ids if 'channel_partner_ids' in self._fields else []
        must_have = list(dict.fromkeys([partner.id] + self._omni_operator_partner_ids()))
        missing = [pid for pid in must_have if pid not in member_partner_ids]
        if missing:
            if hasattr(self, 'add_members'):
                self.add_members(partner_ids=missing)
            else:
                self.channel_partner_ids = [(4, pid) for pid in missing]

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        skip_livechat_inbound = self.env.context.get('omni_skip_livechat_inbound')
        odoobot = self.env.ref('base.partner_root')
        for channel in self:
            if message.author_id == odoobot:
                channel.sudo().write({'omni_last_bot_reply_at': fields.Datetime.now()})
            elif message.author_id and channel._omni_is_internal_author(message.author_id):
                now = fields.Datetime.now()
                vals = {
                    'omni_last_human_reply_at': now,
                    'omni_last_manager_activity_at': now,
                }
                # Final race semantics: manager reply in thread pauses bot session.
                if channel.omni_provider:
                    vals.update({
                        'omni_bot_paused': True,
                        'omni_bot_pause_reason': 'manager_session_active',
                    })
                channel.sudo().write(vals)
            if not skip_livechat_inbound:
                channel._omni_handle_website_livechat_inbound(message)
            channel._omni_route_operator_reply_to_messenger(message)
        return message

    def omni_manager_session_active_now(self):
        self.ensure_one()
        if not self.omni_last_manager_activity_at:
            return False
        icp = self.env['ir.config_parameter'].sudo()
        try:
            timeout_min = int(icp.get_param('omnichannel_bridge.manager_session_timeout_minutes', '30'))
        except ValueError:
            timeout_min = 30
        timeout_min = max(5, timeout_min)
        return Datetime.now() < (self.omni_last_manager_activity_at + timedelta(minutes=timeout_min))

    def _omni_handle_website_livechat_inbound(self, message):
        self.ensure_one()
        sudo_channel = self.sudo()
        if self.omni_provider:
            # Messenger channels are handled by webhook ingest flow.
            return
        if not self._omni_is_website_livechat_channel():
            return
        icp = self.env['ir.config_parameter'].sudo()
        if str(icp.get_param('omnichannel_bridge.site_livechat_enabled', 'True')).lower() not in (
            '1', 'true', 'yes',
        ):
            return
        body = (message.body or '').strip()
        if not body:
            return
        plain = re.sub(r'<[^>]+>', ' ', body)
        plain = re.sub(r'\s+', ' ', plain).strip()
        # Ignore only fully empty/non-word noise; single-letter words like "я"/"I"
        # are valid in real chats and must still trigger bot processing.
        if len(re.sub(r'[\W_]+', '', plain, flags=re.UNICODE)) < 1:
            return
        if getattr(message, 'message_type', '') == 'notification':
            # Ignore service/feedback notifications posted by livechat internals.
            return
        if message.subtype_id and getattr(message.subtype_id, 'internal', False):
            return
        author = self._omni_resolve_livechat_customer_partner(message)
        odoobot = self.env.ref('base.partner_root')
        if author == odoobot:
            return
        if self._omni_is_internal_author(author):
            # Manager joined the dialog -> stop bot until explicit resume.
            self.sudo().write({
                'omni_last_human_reply_at': fields.Datetime.now(),
                'omni_bot_paused': True,
                'omni_bot_pause_reason': 'manager_joined_livechat',
            })
            return
        if self._omni_client_requests_human(body):
            self.sudo().write({
                'omni_bot_paused': True,
                'omni_bot_pause_reason': 'client_requested_human',
            })
            if author:
                author = author.sudo()
                old_stage, new_stage, changed = author.omni_set_sales_stage(
                    'handoff',
                    channel=self.sudo(),
                    reason='client_requested_human_livechat',
                    source='mail_channel',
                )
                if changed:
                    self.env['omni.notify'].sudo().notify_stage_change(
                        channel=self.sudo(),
                        partner=author,
                        old_stage=old_stage,
                        new_stage=new_stage,
                        reason='client_requested_human_livechat',
                    )
            self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                body=_('Передаю діалог менеджеру. Будь ласка, зачекайте трохи.'),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=odoobot.id,
            )
            self.env['omni.notify'].sudo().notify_escalation(
                channel=self.sudo(),
                partner=author.sudo() if author else author,
                reason='🧑‍💼 Клієнт попросив менеджера у live chat',
            )
            return
        author_adm = author.sudo() if author else author
        if not sudo_channel.omni_last_customer_inbound_at:
            self.env['omni.notify'].sudo().notify_new_thread(
                channel=sudo_channel,
                partner=author_adm,
                provider='site_livechat',
            )
        if self._omni_handle_livechat_entry_flow(author_adm, body, odoobot):
            return
        # Auto-resume after manager takeover when client writes again.
        # Keep pause if client explicitly requested a human.
        if self.omni_bot_paused and self.omni_bot_pause_reason == 'manager_joined_livechat':
            self.sudo().write({
                'omni_bot_paused': False,
                'omni_bot_pause_reason': False,
            })
        # Website visitor message -> same AI queue and sales/memory pipeline.
        if author:
            sudo_channel.write({'omni_customer_partner_id': author.id})
        self.env['omni.sales.intel'].sudo().omni_apply_inbound_triggers(
            channel=sudo_channel,
            partner=author_adm,
            text=body,
            provider='site_livechat',
        )
        self.env['omni.memory'].sudo().omni_apply_inbound_learning(author_adm, body)
        # Anti-silence UX for livechat: instant acknowledge, then async AI reply.
        if not self.omni_last_bot_reply_at:
            self.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                body=_('Дякуємо! Отримали ваше повідомлення, підбираю варіанти табору...'),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=odoobot.id,
            )
        try:
            self.env['omni.ai'].sudo().omni_maybe_autoreply(
                channel=self.sudo(),
                partner=author.sudo() if author else author,
                text=body,
                provider='site_livechat',
            )
        except Exception:
            _logger.exception('Immediate livechat AI reply failed, sending fallback')
            self.env['omni.ai'].sudo()._omni_send_fallback(
                channel=self.sudo(),
                partner=author.sudo() if author else author,
                icp=self.env['ir.config_parameter'].sudo(),
            )

    def _omni_route_operator_reply_to_messenger(self, message):
        self.ensure_one()
        sudo_channel = self.sudo()
        if not self.omni_provider or not self.omni_external_thread_id:
            return
        author = message.author_id
        customer = sudo_channel.omni_customer_partner_id
        if not author or author == customer:
            return
        if message.subtype_id and getattr(message.subtype_id, 'internal', False):
            return
        body = message.body
        if not body:
            return
        # Never forward service/system discuss notifications to customers.
        plain_service = re.sub(r'<[^>]+>', ' ', body or '')
        plain_service = re.sub(r'\s+', ' ', plain_service).strip().lower()
        if 'o_mail_notification' in (body or ''):
            return
        service_markers = (
            'запрошено', 'до каналу',
            'invited', 'joined the channel', 'left the channel',
            'приєднався до каналу', 'покинув канал',
        )
        if any(marker in plain_service for marker in service_markers):
            return
        odoobot = self.env.ref('base.partner_root')
        is_bot_author = author == odoobot
        now = fields.Datetime.now()
        icp = self.env['ir.config_parameter'].sudo()
        try:
            conflict_sec = int(icp.get_param('omnichannel_bridge.outbound_conflict_guard_seconds', '20'))
        except ValueError:
            conflict_sec = 20
        conflict_sec = max(5, conflict_sec)
        # If manager has just replied, suppress near-simultaneous bot outbound.
        if is_bot_author and self.omni_last_human_reply_at:
            if now <= self.omni_last_human_reply_at + timedelta(seconds=conflict_sec):
                _logger.info(
                    'Skip bot outbound due manager recent reply channel=%s guard=%ss',
                    self.id,
                    conflict_sec,
                )
                return
        plain = plain_service
        outbound_hash = hashlib.sha1(plain.encode('utf-8')).hexdigest() if plain else ''
        # Anti-duplicate safeguard for retried posts.
        if (
            outbound_hash and
            self.omni_last_outbound_hash == outbound_hash and
            self.omni_last_outbound_at and
            now <= self.omni_last_outbound_at + timedelta(seconds=conflict_sec)
        ):
            _logger.info('Skip duplicate outbound channel=%s', self.id)
            return
        try:
            self.env['omni.bridge'].sudo().omni_send_outbound(
                self.omni_provider,
                self.omni_external_thread_id,
                customer,
                body,
            )
            self.sudo().write({
                'omni_last_outbound_at': now,
                'omni_last_outbound_hash': outbound_hash or False,
                'omni_last_outbound_author_kind': 'bot' if is_bot_author else 'manager',
            })
        except Exception:
            _logger.exception('Omnichannel outbound failed for channel %s', self.id)

    @api.model
    def omni_cron_send_window_reminders(self, limit=80):
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = str(ICP.get_param('omnichannel_bridge.window_reminder_enabled', 'False')).lower() in (
            '1', 'true', 'yes',
        )
        if not enabled:
            return
        try:
            trigger_h = float(ICP.get_param('omnichannel_bridge.window_reminder_trigger_hours', '20'))
        except ValueError:
            trigger_h = 20.0
        try:
            max_h = float(ICP.get_param('omnichannel_bridge.window_message_window_hours', '24'))
        except ValueError:
            max_h = 24.0
        reminder_text = (
            ICP.get_param('omnichannel_bridge.window_reminder_text') or
            'Підкажіть, будь ласка, чи встигли обрати програму табору? '
            'Якщо зручно, допоможу коротко звузити до 1-2 варіантів.'
        ).strip()
        last_call_text = (
            ICP.get_param('omnichannel_bridge.window_last_call_text') or
            'Нагадуємо: вікно повідомлень скоро закриється. Якщо зручно, напишіть короткий апдейт — '
            'і я підключу менеджера без втрати контексту.'
        ).strip()
        try:
            last_call_before_h = float(ICP.get_param('omnichannel_bridge.window_last_call_hours_before_close', '2'))
        except ValueError:
            last_call_before_h = 2.0
        now = Datetime.now()
        domain = [
            ('omni_provider', 'in', ('meta', 'whatsapp', 'twilio_whatsapp')),
            ('omni_external_thread_id', '!=', False),
            ('omni_customer_partner_id', '!=', False),
            ('omni_last_customer_inbound_at', '!=', False),
            ('omni_bot_paused', '=', False),
        ]
        channels = self.sudo().search(domain, order='omni_last_customer_inbound_at asc', limit=max(1, int(limit)))
        for ch in channels:
            inbound_at = ch.omni_last_customer_inbound_at
            if not inbound_at:
                continue
            if now < inbound_at + timedelta(hours=max(0.1, trigger_h)):
                continue
            if now > inbound_at + timedelta(hours=max(0.5, max_h)):
                continue
            if ch.omni_window_reminder_sent_at and ch.omni_window_reminder_sent_at >= inbound_at:
                pass
            # Do not remind when handoff is already in progress.
            customer = ch.omni_customer_partner_id.sudo()
            if customer and customer.omni_sales_stage == 'handoff':
                continue
            window_close_at = inbound_at + timedelta(hours=max(0.5, max_h))
            last_call_at = window_close_at - timedelta(hours=max(0.1, last_call_before_h))
            can_remind = (
                now >= inbound_at + timedelta(hours=max(0.1, trigger_h))
                and (not ch.omni_window_reminder_sent_at or ch.omni_window_reminder_sent_at < inbound_at)
                and self._omni_marketing_touch_allowed(ch, 'reminder', now, ICP)
            )
            can_last_call = (
                now >= last_call_at
                and now <= window_close_at
                and (not ch.omni_window_last_call_sent_at or ch.omni_window_last_call_sent_at < inbound_at)
                and self._omni_marketing_touch_allowed(ch, 'last_call', now, ICP)
            )
            if not can_remind and not can_last_call:
                continue
            try:
                sent_touch = ''
                self.env['omni.bridge'].sudo().omni_send_outbound(
                    ch.omni_provider,
                    ch.omni_external_thread_id,
                    customer,
                    reminder_text if can_remind else last_call_text,
                )
                vals = {
                    'omni_last_marketing_touch_at': now,
                    'omni_last_marketing_touch_type': 'reminder' if can_remind else 'last_call',
                }
                if can_remind:
                    vals['omni_window_reminder_sent_at'] = now
                    vals['omni_window_reminder_count'] = (ch.omni_window_reminder_count or 0) + 1
                    sent_touch = 'reminder'
                else:
                    vals['omni_window_last_call_sent_at'] = now
                    sent_touch = 'last_call'
                ch.write(vals)
                _logger.info('Window marketing touch sent channel=%s type=%s', ch.id, sent_touch)
            except Exception:
                _logger.exception('Window reminder send failed for channel %s', ch.id)

    def _omni_marketing_touch_allowed(self, channel, touch_type, now_dt, icp):
        channel = channel.sudo()
        def _mins(key, default):
            try:
                return max(0, int(icp.get_param(key, str(default))))
            except ValueError:
                return default
        global_cd = _mins('omnichannel_bridge.cooldown_global_minutes', 60)
        type_map = {
            'reminder': _mins('omnichannel_bridge.cooldown_reminder_minutes', 180),
            'fomo': _mins('omnichannel_bridge.cooldown_fomo_minutes', 180),
            'last_call': _mins('omnichannel_bridge.cooldown_last_call_minutes', 180),
        }
        type_cd = type_map.get(touch_type, 0)
        if channel.omni_last_marketing_touch_at:
            if now_dt < channel.omni_last_marketing_touch_at + timedelta(minutes=global_cd):
                return False
        if touch_type == 'fomo' and channel.omni_last_fomo_notify_at:
            if now_dt < channel.omni_last_fomo_notify_at + timedelta(minutes=type_cd):
                return False
        if touch_type == 'reminder' and channel.omni_window_reminder_sent_at:
            if now_dt < channel.omni_window_reminder_sent_at + timedelta(minutes=type_cd):
                return False
        if touch_type == 'last_call' and channel.omni_window_last_call_sent_at:
            if now_dt < channel.omni_window_last_call_sent_at + timedelta(minutes=type_cd):
                return False
        return True

    @api.model
    def omni_cron_purge_old_messages(self, limit=500):
        icp = self.env['ir.config_parameter'].sudo()
        try:
            retention_days = int(icp.get_param('omnichannel_bridge.retention_message_days', '180'))
        except ValueError:
            retention_days = 180
        retention_days = max(7, retention_days)
        cutoff = Datetime.now() - timedelta(days=retention_days)
        omni_channels = self.sudo().search([('omni_provider', '!=', False)]).ids
        if not omni_channels:
            return
        messages = self.env['mail.message'].sudo().search(
            [
                ('model', '=', 'discuss.channel'),
                ('res_id', 'in', omni_channels),
                ('create_date', '<', cutoff),
                ('message_type', '=', 'comment'),
            ],
            order='id asc',
            limit=max(1, int(limit)),
        )
        if messages:
            messages.unlink()
