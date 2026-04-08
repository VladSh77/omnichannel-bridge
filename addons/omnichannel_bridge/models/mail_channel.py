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
    omni_window_reminder_count = fields.Integer(default=0)
    omni_livechat_entry_state = fields.Selection(
        selection=[
            ('new', 'New'),
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
        return (
            'Щоб швидше допомогти, оберіть напрямок:\n'
            '1) Про компанію CampScout\n'
            '2) Табори/програми\n'
            '3) Інші послуги\n'
            '4) Ціни та умови\n'
            '5) Залишити контакт для менеджера\n\n'
            'Можна просто написати власне питання нижче.'
        )

    def _omni_livechat_contact_prompt_text(self):
        return (
            'Щоб менеджер міг звʼязатися з вами, залиште, будь ласка, телефон або email.\n'
            'Надсилаючи контакт, ви погоджуєтесь на обробку даних для підбору табору.'
        )

    def _omni_extract_contact_from_text(self, text):
        Partner = self.env['res.partner'].sudo()
        email = Partner.omni_parse_email(text or '')
        phone = Partner.omni_parse_phone(text or '')
        return email, phone

    def _omni_handle_livechat_entry_flow(self, author, body, odoobot):
        """Returns True when entry flow consumed message and AI should be skipped."""
        self.ensure_one()
        author = author.sudo()
        state = self.omni_livechat_entry_state or 'new'
        topic = self._omni_detect_livechat_topic(body)
        email, phone = self._omni_extract_contact_from_text(body)
        has_contact = bool(author.email or author.phone or author.mobile or email or phone)
        if state == 'new':
            vals = {'omni_livechat_entry_topic': topic}
            if topic == 'unknown':
                self.with_context(omni_skip_livechat_inbound=True).message_post(
                    body=self._omni_livechat_entry_menu_text(),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                if has_contact:
                    vals['omni_livechat_entry_state'] = 'ready'
                else:
                    vals['omni_livechat_entry_state'] = 'awaiting_contact'
                self.sudo().write(vals)
                return True
            if topic == 'contact' and not has_contact:
                self.with_context(omni_skip_livechat_inbound=True).message_post(
                    body=self._omni_livechat_contact_prompt_text(),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                )
                vals['omni_livechat_entry_state'] = 'awaiting_contact'
                self.sudo().write(vals)
                return True
            vals['omni_livechat_entry_state'] = 'ready'
            self.sudo().write(vals)
            return False
        if state == 'awaiting_contact':
            if email or phone or author.email or author.phone or author.mobile:
                upd = {}
                if email and not author.email:
                    upd['email'] = email
                if phone and not (author.phone or author.mobile):
                    upd['phone'] = phone
                if upd:
                    author.write(upd)
                self.sudo().write({'omni_livechat_entry_state': 'ready'})
                self.env['omni.bridge'].sudo()._omni_maybe_create_crm_lead(author, 'site_livechat')
                return False
            self.with_context(omni_skip_livechat_inbound=True).message_post(
                body=self._omni_livechat_contact_prompt_text(),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=odoobot.id,
            )
            return True
        return False

    @api.model
    def omni_get_or_create_thread(self, provider, external_thread_id, partner, label):
        existing = self.sudo().search([
            ('omni_provider', '=', provider),
            ('omni_external_thread_id', '=', str(external_thread_id)),
        ], limit=1)
        if existing:
            existing.sudo().omni_thread_align_customer(partner)
            return existing, False
        odoobot = self.env.ref('base.partner_root')
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
            channel.add_members(partner_ids=[partner.id, odoobot.id])
        else:
            channel.channel_partner_ids = [(6, 0, [partner.id, odoobot.id])]
        return channel, True

    def omni_thread_align_customer(self, partner):
        self.ensure_one()
        if not partner:
            return
        self.sudo().write({'omni_customer_partner_id': partner.id})
        member_partner_ids = self.channel_partner_ids.ids if 'channel_partner_ids' in self._fields else []
        if partner.id not in member_partner_ids:
            if hasattr(self, 'add_members'):
                self.add_members(partner_ids=[partner.id])
            else:
                self.channel_partner_ids = [(4, partner.id)]

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        if self.env.context.get('omni_skip_livechat_inbound'):
            return message
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
        # Ignore single-symbol pings that create noise and overload LLM queue.
        if len(re.sub(r'[\W_]+', '', plain, flags=re.UNICODE)) < 2:
            return
        if getattr(message, 'message_type', '') == 'notification':
            # Ignore service/feedback notifications posted by livechat internals.
            return
        if message.subtype_id and getattr(message.subtype_id, 'internal', False):
            return
        author = message.author_id or sudo_channel.omni_customer_partner_id
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
            self.with_context(omni_skip_livechat_inbound=True).message_post(
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
        if not author:
            # Guest visitor messages can come without author_id.
            # Keep AI dialog working; partner enrichment will be skipped.
            author = self.env.ref('base.public_partner')
        author_adm = author.sudo() if author else author
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
            self.with_context(omni_skip_livechat_inbound=True).message_post(
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
        plain = re.sub(r'<[^>]+>', ' ', body or '')
        plain = re.sub(r'\s+', ' ', plain).strip().lower()
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
                continue
            # Do not remind when handoff is already in progress.
            customer = ch.omni_customer_partner_id.sudo()
            if customer and customer.omni_sales_stage == 'handoff':
                continue
            try:
                self.env['omni.bridge'].sudo().omni_send_outbound(
                    ch.omni_provider,
                    ch.omni_external_thread_id,
                    customer,
                    reminder_text,
                )
                ch.write({
                    'omni_window_reminder_sent_at': now,
                    'omni_window_reminder_count': (ch.omni_window_reminder_count or 0) + 1,
                })
            except Exception:
                _logger.exception('Window reminder send failed for channel %s', ch.id)

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
