# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging
import re
import time

import requests
from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.tools import html2plaintext

from ..utils.webhook_parsers import (
    extract_meta_mid,
    extract_telegram_update_id,
    extract_twilio_whatsapp_message_id,
    extract_viber_message_token,
    extract_whatsapp_message_id,
)

_logger = logging.getLogger(__name__)
_EMAIL_LOG_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_PHONE_LOG_RE = re.compile(r'\+?\d[\d\-\s\(\)]{7,}\d')

META_GRAPH_VERSION = 'v21.0'


class OmniBridge(models.AbstractModel):
    _name = 'omni.bridge'
    _description = 'Omnichannel ingest / outbound orchestration'

    @api.model
    def omni_process_webhook(self, provider, payload, headers=None):
        headers = headers or {}
        if provider == 'meta':
            return self._omni_process_meta(payload, headers)
        if provider == 'telegram':
            return self._omni_process_telegram(payload, headers)
        if provider == 'viber':
            return self._omni_process_viber_stub(payload, headers)
        if provider == 'twilio_whatsapp':
            return self._omni_process_twilio_whatsapp(payload, headers)
        if provider == 'whatsapp':
            return self._omni_process_whatsapp_stub(payload, headers)
        _logger.warning('Unknown omnichannel provider: %s', provider)
        return {'ok': False, 'error': 'unknown_provider'}

    def _omni_extract_external_event_id(self, provider, data):
        if provider == 'telegram':
            return extract_telegram_update_id(data)
        if provider == 'meta':
            return extract_meta_mid(data)
        if provider == 'whatsapp':
            return extract_whatsapp_message_id(data)
        if provider == 'twilio_whatsapp':
            return extract_twilio_whatsapp_message_id(data)
        if provider == 'viber':
            return extract_viber_message_token(data)
        return ''

    def _omni_register_webhook_event(self, provider, data):
        Event = self.env['omni.webhook.event'].sudo()
        payload_hash = Event.omni_payload_hash(data)
        external_event_id = self._omni_extract_external_event_id(provider, data)
        vals = {
            'provider': provider,
            'external_event_id': external_event_id or False,
            'payload_hash': payload_hash,
            'state': 'received',
        }
        try:
            with self.env.cr.savepoint():
                event = Event.create(vals)
                return event
        except IntegrityError:
            _logger.info(
                'Duplicate webhook ignored provider=%s external_event_id=%s',
                provider,
                external_event_id or '-',
            )
            return False

    def _omni_meta_credentials(self):
        ICP = self.env['ir.config_parameter'].sudo()
        row = self.env['omni.integration'].sudo().search(
            [
                ('active', '=', True),
                ('provider', '=', 'meta'),
                ('company_id', '=', self.env.company.id),
            ],
            limit=1,
        )
        page_token = ''
        app_secret = ''
        if row:
            page_token = (row.api_token or '').strip()
            app_secret = (row.webhook_secret or '').strip()
        if not page_token:
            page_token = ICP.get_param('omnichannel_bridge.meta_page_access_token', '').strip()
        if not app_secret:
            app_secret = ICP.get_param('omnichannel_bridge.meta_app_secret', '').strip()
        return page_token, app_secret

    def _omni_whatsapp_credentials(self):
        ICP = self.env['ir.config_parameter'].sudo()
        row = self.env['omni.integration'].sudo().search(
            [
                ('active', '=', True),
                ('provider', '=', 'whatsapp'),
                ('company_id', '=', self.env.company.id),
            ],
            limit=1,
        )
        token = ''
        app_secret = ''
        if row:
            token = (row.api_token or '').strip()
            app_secret = (row.webhook_secret or '').strip()
        if not token:
            token = ICP.get_param('omnichannel_bridge.meta_page_access_token', '').strip()
        if not app_secret:
            app_secret = (
                ICP.get_param('omnichannel_bridge.whatsapp_app_secret', '').strip() or
                ICP.get_param('omnichannel_bridge.meta_app_secret', '').strip()
            )
        phone_number_id = (ICP.get_param('omnichannel_bridge.whatsapp_phone_number_id', '') or '').strip()
        return token, app_secret, phone_number_id

    def _omni_viber_credentials(self):
        ICP = self.env['ir.config_parameter'].sudo()
        row = self.env['omni.integration'].sudo().search(
            [
                ('active', '=', True),
                ('provider', '=', 'viber'),
                ('company_id', '=', self.env.company.id),
            ],
            limit=1,
        )
        token = ''
        webhook_secret = ''
        if row:
            token = (row.api_token or '').strip()
            webhook_secret = (row.webhook_secret or '').strip()
        if not token:
            token = ICP.get_param('omnichannel_bridge.viber_bot_token', '').strip()
        if not webhook_secret:
            webhook_secret = ICP.get_param('omnichannel_bridge.viber_webhook_secret', '').strip()
        return token, webhook_secret

    def _omni_verify_meta_signature(self, raw_body, headers):
        _, app_secret = self._omni_meta_credentials()
        if not app_secret:
            return True
        sig = headers.get('X-Hub-Signature-256') or headers.get('x-hub-signature-256') or ''
        if not sig.startswith('sha256='):
            return False
        expected = 'sha256=' + hmac.new(
            app_secret.encode('utf-8'),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(sig, expected)

    def _omni_verify_whatsapp_signature(self, raw_body, headers):
        _, app_secret, _ = self._omni_whatsapp_credentials()
        if not app_secret:
            return True
        sig = headers.get('X-Hub-Signature-256') or headers.get('x-hub-signature-256') or ''
        if not sig.startswith('sha256='):
            return False
        expected = 'sha256=' + hmac.new(
            app_secret.encode('utf-8'),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(sig, expected)

    def _omni_verify_viber_signature(self, raw_body, headers):
        _, webhook_secret = self._omni_viber_credentials()
        if not webhook_secret:
            return True
        got = headers.get('X-Viber-Content-Signature') or headers.get('x-viber-content-signature') or ''
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(got, expected)

    @api.model
    def _omni_deliver_inbound(
        self,
        provider,
        thread_id,
        external_user_id,
        display_name,
        text,
        phone,
        email,
        metadata_obj,
    ):
        Partner = self.env['res.partner'].sudo()
        metadata_json = json.dumps(metadata_obj) if metadata_obj is not None else None
        partner = Partner.omni_find_or_create_customer({
            'provider': provider,
            'external_id': str(external_user_id),
            'name': display_name,
            'display_name': display_name,
            'phone': phone or False,
            'email': email or False,
            'metadata_json': metadata_json,
        })
        partner = Partner.omni_resolve_from_clues(
            partner,
            provider,
            str(external_user_id),
            text,
        )
        label = _('[%(p)s] %(name)s') % {
            'p': dict(self.env['omni.integration']._selection_providers()).get(provider, provider),
            'name': partner.display_name,
        }
        channel, is_new = self.env['discuss.channel'].omni_get_or_create_thread(
            provider,
            str(thread_id),
            partner,
            label,
        )
        if is_new:
            self.env['omni.notify'].sudo().notify_new_thread(channel, partner, provider)
            self._omni_maybe_create_crm_lead(partner, provider)
        channel.sudo().message_post(
            body=text,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=partner.id,
        )
        self.env['omni.sales.intel'].sudo().omni_apply_inbound_triggers(
            channel=channel,
            partner=partner,
            text=text,
            provider=provider,
        )
        channel.sudo().write({
            'omni_last_customer_inbound_at': fields.Datetime.now(),
            # New inbound resets reminder cycle window.
            'omni_window_reminder_sent_at': False,
        })
        # Manager session lock: do not race bot against active manager.
        if channel.omni_bot_paused and channel.omni_bot_pause_reason == 'manager_session_active':
            if channel.omni_manager_session_active_now():
                return
            channel.sudo().write({
                'omni_bot_paused': False,
                'omni_bot_pause_reason': False,
            })
        self.env['omni.memory'].sudo().omni_apply_inbound_learning(partner, text)
        delay = self.env['omni.ai'].sudo().omni_autoreply_delay_seconds_for_inbound()
        # Telegram test/live dialogs should not feel silent while waiting for SLA window.
        if provider == 'telegram':
            delay = 0
        job = self.env['omni.ai.job'].sudo().omni_enqueue_autoreply(
            channel=channel,
            partner=partner,
            text=text,
            provider=provider,
            delay_seconds=delay,
        )
        # Telegram UX: avoid "silent bot" while waiting for cron tick.
        # Run the queued job immediately in the same request.
        if provider == 'telegram' and job:
            try:
                job.sudo()._omni_run_single()
            except Exception:
                _logger.exception('Immediate Telegram AI run failed, cron fallback will retry')

    def _omni_maybe_create_crm_lead(self, partner, provider):
        """Новий клієнт → CRM нагода (якщо увімкнено в налаштуваннях)."""
        ICP = self.env['ir.config_parameter'].sudo()
        if str(ICP.get_param('omnichannel_bridge.new_contact_as_lead', 'False')).lower() not in (
            '1', 'true', 'yes',
        ):
            return
        if 'crm.lead' not in self.env:
            return
        try:
            provider_label = dict(
                self.env['omni.integration']._selection_providers()
            ).get(provider, provider)
            self.env['crm.lead'].sudo().create({
                'name': '[%s] %s' % (provider_label, partner.display_name or 'New contact'),
                'partner_id': partner.id,
                'description': 'Новий контакт через %s. Призначте менеджера.' % provider_label,
                'tag_ids': [],
            })
        except Exception:
            _logger.exception('Failed to create CRM lead for new omnichannel contact')

    def _omni_process_meta(self, payload, headers):
        raw_body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload).encode('utf-8')
        if not self._omni_verify_meta_signature(raw_body, headers):
            return {'ok': False, 'error': 'bad_signature'}
        data = json.loads(raw_body.decode('utf-8'))
        webhook_event = self._omni_register_webhook_event('meta', data)
        if not webhook_event:
            return {'ok': True, 'deduplicated': True}
        if data.get('object') not in ('page', 'instagram'):
            webhook_event.sudo().write({
                'state': 'processed',
                'processed_at': fields.Datetime.now(),
            })
            return {'ok': True, 'skipped': True}
        for entry in data.get('entry', []):
            for event in entry.get('messaging', []):
                msg = event.get('message') or {}
                if msg.get('is_echo'):
                    continue
                text = (msg.get('text') or '').strip()
                if not text:
                    continue
                sender = str(event.get('sender', {}).get('id') or '')
                if not sender:
                    continue
                label = 'Instagram' if data.get('object') == 'instagram' else 'Facebook'
                display_name = _('%s user %s') % (label, sender)
                self._omni_deliver_inbound(
                    'meta',
                    thread_id=sender,
                    external_user_id=sender,
                    display_name=display_name,
                    text=text,
                    phone='',
                    email='',
                    metadata_obj=event,
                )
        webhook_event.sudo().write({
            'state': 'processed',
            'processed_at': fields.Datetime.now(),
        })
        return {'ok': True}

    def _omni_verify_telegram_secret(self, headers):
        ICP = self.env['ir.config_parameter'].sudo()
        secret = ICP.get_param('omnichannel_bridge.telegram_webhook_secret')
        if not secret:
            return True
        got = headers.get('X-Telegram-Bot-Api-Secret-Token')
        return got == secret

    def _omni_is_tg_marketing_subscribe(self, text):
        txt = (text or '').strip().lower()
        return txt in ('/subscribe', '/subscribe@campscoutbot', 'підписка', 'згода на розсилку')

    def _omni_is_tg_marketing_unsubscribe(self, text):
        txt = (text or '').strip().lower()
        return txt in ('/unsubscribe', '/unsubscribe@campscoutbot', 'відписка', 'стоп розсилка')

    def _omni_telegram_token(self):
        row = self.env['omni.integration'].sudo().search(
            [
                ('active', '=', True),
                ('provider', '=', 'telegram'),
                ('company_id', '=', self.env.company.id),
            ],
            limit=1,
        )
        if row and row.api_token:
            return row.api_token.strip()
        return (
            self.env['ir.config_parameter']
            .sudo()
            .get_param('omnichannel_bridge.telegram_bot_token', '')
            .strip()
        )

    def _omni_process_telegram(self, payload, headers):
        if not self._omni_verify_telegram_secret(headers):
            return {'ok': False, 'error': 'invalid_secret'}
        data = json.loads(payload.decode('utf-8')) if isinstance(payload, bytes) else payload
        webhook_event = self._omni_register_webhook_event('telegram', data)
        if not webhook_event:
            return {'ok': True, 'deduplicated': True}
        message = data.get('message') or data.get('edited_message')
        if not message:
            webhook_event.sudo().write({
                'state': 'processed',
                'processed_at': fields.Datetime.now(),
            })
            return {'ok': True, 'skipped': True}
        text = (message.get('text') or message.get('caption') or '').strip()
        if not text:
            # Keep inbound flow alive for first non-text touchpoints (sticker/photo/voice),
            # otherwise the customer may never be created in Odoo.
            if message.get('sticker'):
                text = '[sticker]'
            elif message.get('photo'):
                text = '[photo]'
            elif message.get('voice'):
                text = '[voice]'
            elif message.get('video'):
                text = '[video]'
            elif message.get('document'):
                text = '[document]'
            else:
                text = '[non-text]'
        from_user = message.get('from') or {}
        chat = message.get('chat') or {}

        # --- Kill switch / bot commands (від адміна) ---
        if text.startswith('/') and self._omni_is_admin_telegram_user(from_user):
            webhook_event.sudo().write({
                'state': 'processed',
                'processed_at': fields.Datetime.now(),
            })
            return self._omni_handle_bot_command(text, from_user, chat)

        external_user_id = str(from_user.get('id') or chat.get('id') or '')
        thread_id = str(chat.get('id') or external_user_id)
        display_name = ' '.join(
            filter(
                None,
                [from_user.get('first_name'), from_user.get('last_name')],
            )
        ).strip() or from_user.get('username') or thread_id
        self._omni_deliver_inbound(
            'telegram',
            thread_id=thread_id,
            external_user_id=external_user_id,
            display_name=display_name,
            text=text,
            phone=from_user.get('phone_number'),
            email='',
            metadata_obj={'telegram': from_user, 'chat': chat},
        )
        partner = self.env['res.partner'].sudo().omni_find_or_create_customer({
            'provider': 'telegram',
            'external_id': external_user_id,
            'name': display_name,
            'display_name': display_name,
            'phone': from_user.get('phone_number') or False,
            'email': False,
            'metadata_json': json.dumps({'telegram': from_user, 'chat': chat}),
        })
        if self._omni_is_tg_marketing_subscribe(text):
            partner.sudo().write({
                'omni_tg_marketing_opt_in': True,
                'omni_tg_marketing_opt_in_at': fields.Datetime.now(),
            })
            self._omni_telegram_send_message(
                thread_id,
                '✅ Дякуємо! Ви підписані на Telegram-розсилки CampScout. '
                'Відписка: /unsubscribe',
            )
        elif self._omni_is_tg_marketing_unsubscribe(text):
            partner.sudo().write({
                'omni_tg_marketing_opt_in': False,
            })
            self._omni_telegram_send_message(
                thread_id,
                '🛑 Ви відписались від Telegram-розсилок CampScout. '
                'Повернути підписку: /subscribe',
            )
        webhook_event.sudo().write({
            'state': 'processed',
            'processed_at': fields.Datetime.now(),
        })
        return {'ok': True}

    def _omni_is_admin_telegram_user(self, from_user):
        """Перевіряємо чи команда від адміна (за internal_tg_chat_id або окремим admin_tg_id)."""
        ICP = self.env['ir.config_parameter'].sudo()
        admin_ids_raw = ICP.get_param('omnichannel_bridge.admin_tg_user_ids', '')
        if not admin_ids_raw:
            return False
        allowed = {s.strip() for s in admin_ids_raw.split(',') if s.strip()}
        return str(from_user.get('id', '')) in allowed

    def _omni_handle_bot_command(self, text, from_user, chat):
        """Telegram-команди для управління ботом без деплою."""
        ICP = self.env['ir.config_parameter'].sudo()
        cmd = text.split()[0].lower().split('@')[0]  # /stop_bot@MyBot → /stop_bot
        chat_id = str(chat.get('id', ''))

        if cmd == '/stop_bot':
            ICP.set_param('omnichannel_bridge.llm_enabled', 'False')
            ICP.set_param('omnichannel_bridge.bot_reply_mode', 'never')
            self._omni_telegram_send_message(chat_id, '🔴 Бот ВИМКНЕНО. Всі відповіді — вручну.')
            _logger.warning('Bot stopped via Telegram command by user %s', from_user.get('id'))

        elif cmd == '/start_bot':
            ICP.set_param('omnichannel_bridge.llm_enabled', 'True')
            ICP.set_param('omnichannel_bridge.bot_reply_mode', 'outside_manager_hours')
            self._omni_telegram_send_message(chat_id, '🟢 Бот УВІМКНЕНО. Режим: поза робочими годинами.')
            _logger.info('Bot started via Telegram command by user %s', from_user.get('id'))

        elif cmd == '/restart_bot':
            # Скидаємо будь-який stuck стан: включаємо LLM і режим auto
            ICP.set_param('omnichannel_bridge.llm_enabled', 'True')
            ICP.set_param('omnichannel_bridge.bot_reply_mode', 'outside_manager_hours')
            self._omni_telegram_send_message(
                chat_id,
                '🔄 Бот ПЕРЕЗАПУЩЕНО. LLM: qwen2.5:7b. Режим: поза робочими годинами.',
            )
            _logger.info('Bot restarted via Telegram command by user %s', from_user.get('id'))

        elif cmd == '/bot_status':
            enabled = ICP.get_param('omnichannel_bridge.llm_enabled', 'False')
            mode = ICP.get_param('omnichannel_bridge.bot_reply_mode', 'outside_manager_hours')
            model = ICP.get_param('omnichannel_bridge.ollama_model', 'qwen2.5:7b')
            status = '🟢' if enabled in ('True', '1', 'true') else '🔴'
            self._omni_telegram_send_message(
                chat_id,
                '%s Статус бота\nLLM: %s\nРежим: %s\nМодель: %s' % (status, enabled, mode, model),
            )

        else:
            self._omni_telegram_send_message(
                chat_id,
                'Команди: /stop_bot | /start_bot | /restart_bot | /bot_status',
            )

        return {'ok': True, 'command': cmd}

    def _omni_process_viber_stub(self, payload, headers):
        raw_body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload).encode('utf-8')
        if not self._omni_verify_viber_signature(raw_body, headers):
            return {'ok': False, 'error': 'bad_signature'}
        data = json.loads(raw_body.decode('utf-8'))
        webhook_event = self._omni_register_webhook_event('viber', data)
        if not webhook_event:
            return {'ok': True, 'deduplicated': True}
        event_type = (data.get('event') or '').strip().lower()
        if event_type != 'message':
            webhook_event.sudo().write({
                'state': 'processed',
                'processed_at': fields.Datetime.now(),
            })
            return {'ok': True, 'skipped': True}
        message = data.get('message') or {}
        text = (message.get('text') or '').strip()
        sender = data.get('sender') or {}
        user_id = str(sender.get('id') or '')
        if text and user_id:
            display_name = sender.get('name') or _('Viber user %s') % user_id
            self._omni_deliver_inbound(
                'viber',
                thread_id=user_id,
                external_user_id=user_id,
                display_name=display_name,
                text=text,
                phone='',
                email='',
                metadata_obj=data,
            )
        webhook_event.sudo().write({
            'state': 'processed',
            'processed_at': fields.Datetime.now(),
        })
        return {'ok': True}

    def _omni_process_whatsapp_stub(self, payload, headers):
        raw_body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload).encode('utf-8')
        if not self._omni_verify_whatsapp_signature(raw_body, headers):
            return {'ok': False, 'error': 'bad_signature'}
        data = json.loads(raw_body.decode('utf-8'))
        webhook_event = self._omni_register_webhook_event('whatsapp', data)
        if not webhook_event:
            return {'ok': True, 'deduplicated': True}
        if data.get('object') not in ('whatsapp_business_account',):
            webhook_event.sudo().write({
                'state': 'processed',
                'processed_at': fields.Datetime.now(),
            })
            return {'ok': True, 'skipped': True}
        for entry in data.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value') or {}
                contacts = value.get('contacts') or []
                messages = value.get('messages') or []
                for msg in messages:
                    msg_type = msg.get('type')
                    text = ''
                    if msg_type == 'text':
                        text = ((msg.get('text') or {}).get('body') or '').strip()
                    elif msg_type == 'button':
                        text = ((msg.get('button') or {}).get('text') or '').strip()
                    elif msg_type == 'interactive':
                        interactive = msg.get('interactive') or {}
                        button_reply = (interactive.get('button_reply') or {}).get('title')
                        list_reply = (interactive.get('list_reply') or {}).get('title')
                        text = (button_reply or list_reply or '').strip()
                    if not text:
                        continue
                    sender = str(msg.get('from') or '')
                    if not sender:
                        continue
                    contact = next((c for c in contacts if str(c.get('wa_id') or '') == sender), {}) or {}
                    profile = contact.get('profile') or {}
                    display_name = profile.get('name') or _('WhatsApp user %s') % sender
                    self._omni_deliver_inbound(
                        'whatsapp',
                        thread_id=sender,
                        external_user_id=sender,
                        display_name=display_name,
                        text=text,
                        phone=sender,
                        email='',
                        metadata_obj=msg,
                    )
        webhook_event.sudo().write({
            'state': 'processed',
            'processed_at': fields.Datetime.now(),
        })
        return {'ok': True}

    def _omni_process_twilio_whatsapp(self, payload, headers):
        data = json.loads(payload.decode('utf-8')) if isinstance(payload, (bytes, bytearray)) else (payload or {})
        webhook_event = self._omni_register_webhook_event('twilio_whatsapp', data)
        if not webhook_event:
            return {'ok': True, 'deduplicated': True}
        body = (data.get('Body') or data.get('body') or '').strip()
        from_raw = (data.get('From') or data.get('from') or '').strip()
        sender = from_raw.replace('whatsapp:', '').strip()
        if not body or not sender:
            webhook_event.sudo().write({
                'state': 'processed',
                'processed_at': fields.Datetime.now(),
            })
            return {'ok': True, 'skipped': True}
        profile = (data.get('ProfileName') or data.get('profile_name') or '').strip()
        display_name = profile or _('WhatsApp user %s') % sender
        self._omni_deliver_inbound(
            'twilio_whatsapp',
            thread_id=sender,
            external_user_id=sender,
            display_name=display_name,
            text=body,
            phone=sender,
            email='',
            metadata_obj=data,
        )
        webhook_event.sudo().write({
            'state': 'processed',
            'processed_at': fields.Datetime.now(),
        })
        return {'ok': True}

    @api.model
    def omni_send_outbound(self, provider, external_thread_id, customer_partner, body_html):
        text = (html2plaintext(body_html or '') or '').strip()
        if not text:
            return
        if provider == 'telegram':
            self._omni_telegram_send_message(str(external_thread_id), text)
        elif provider == 'meta':
            self._omni_meta_send_psid(str(external_thread_id), text)
        elif provider in ('whatsapp', 'twilio_whatsapp'):
            self._omni_whatsapp_send_to_wa_id(str(external_thread_id), text)
        elif provider == 'viber':
            self._omni_viber_send_to_user(str(external_thread_id), text)
        else:
            _logger.info(
                'Outbound not implemented for provider=%s thread=%s',
                provider,
                external_thread_id,
            )

    def _omni_http_post_with_retries(
        self,
        url,
        *,
        json=None,
        params=None,
        headers=None,
        max_attempts=4,
        timeout=30,
    ):
        """Graph / Telegram: retry transient failures (TZ §14.1)."""
        delay = 1.0
        last_resp = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(url, json=json, params=params, headers=headers, timeout=timeout)
            except requests.RequestException as exc:
                last_resp = None
                _logger.warning(
                    'HTTP POST attempt %s/%s failed: %s %s',
                    attempt,
                    max_attempts,
                    url[:80],
                    exc,
                )
                if attempt >= max_attempts:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 16.0)
                continue
            last_resp = resp
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                _logger.warning(
                    'HTTP POST %s status=%s, retrying in %.1fs',
                    url[:80],
                    resp.status_code,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * 2, 16.0)
                continue
            return resp
        return last_resp

    def _omni_log_outbound_delivery(self, provider, external_thread_id, endpoint, ok, status_code=0, error=''):
        try:
            self.env['omni.outbound.log'].sudo().create({
                'provider': provider or '',
                'external_thread_id': str(external_thread_id or ''),
                'endpoint': endpoint or '',
                'ok': bool(ok),
                'status_code': int(status_code or 0),
                'error_snippet': (error or '')[:240],
            })
        except Exception:
            _logger.debug('Failed to write omni.outbound.log', exc_info=True)

    def _omni_mask_pii_for_logs(self, text):
        if not text:
            return ''
        icp = self.env['ir.config_parameter'].sudo()
        enabled = str(icp.get_param('omnichannel_bridge.log_pii_masking', 'True')).lower() in (
            '1', 'true', 'yes',
        )
        if not enabled:
            return text
        result = _EMAIL_LOG_RE.sub('[email]', str(text))
        result = _PHONE_LOG_RE.sub('[phone]', result)
        return result[:500]

    def _omni_telegram_send_message(self, chat_id, text):
        token = self._omni_telegram_token()
        if not token:
            _logger.warning('Telegram bot token is not configured.')
            return
        url = 'https://api.telegram.org/bot%s/sendMessage' % token
        try:
            resp = self._omni_http_post_with_retries(
                url,
                json={'chat_id': chat_id, 'text': text},
            )
        except requests.RequestException:
            _logger.exception('Telegram sendMessage failed after retries')
            self._omni_log_outbound_delivery('telegram', chat_id, url, False, 0, 'request_exception')
            return
        if not resp.ok:
            _logger.error(
                'Telegram sendMessage failed: %s %s',
                resp.status_code,
                self._omni_mask_pii_for_logs(resp.text),
            )
        self._omni_log_outbound_delivery(
            'telegram',
            chat_id,
            url,
            resp.ok,
            resp.status_code,
            '' if resp.ok else self._omni_mask_pii_for_logs(resp.text),
        )

    def _omni_meta_send_psid(self, psid, text):
        token, _ = self._omni_meta_credentials()
        if not token:
            _logger.warning('Meta page access token is not configured.')
            return
        url = 'https://graph.facebook.com/%s/me/messages' % META_GRAPH_VERSION
        try:
            resp = self._omni_http_post_with_retries(
                url,
                params={'access_token': token},
                json={
                    'recipient': {'id': psid},
                    'messaging_type': 'RESPONSE',
                    'message': {'text': text[:2000]},
                },
            )
        except requests.RequestException:
            _logger.exception('Meta send message failed after retries')
            self._omni_log_outbound_delivery('meta', psid, url, False, 0, 'request_exception')
            return
        if not resp.ok:
            _logger.error(
                'Meta send message failed: %s %s',
                resp.status_code,
                self._omni_mask_pii_for_logs(resp.text),
            )
        self._omni_log_outbound_delivery(
            'meta',
            psid,
            url,
            resp.ok,
            resp.status_code,
            '' if resp.ok else self._omni_mask_pii_for_logs(resp.text),
        )

    def _omni_whatsapp_send_to_wa_id(self, wa_id, text):
        token, _, phone_number_id = self._omni_whatsapp_credentials()
        if not token or not phone_number_id:
            _logger.warning('WhatsApp token or phone_number_id is not configured.')
            return
        url = 'https://graph.facebook.com/%s/%s/messages' % (META_GRAPH_VERSION, phone_number_id)
        try:
            resp = self._omni_http_post_with_retries(
                url,
                params={'access_token': token},
                json={
                    'messaging_product': 'whatsapp',
                    'recipient_type': 'individual',
                    'to': wa_id,
                    'type': 'text',
                    'text': {'preview_url': False, 'body': text[:2000]},
                },
            )
        except requests.RequestException:
            _logger.exception('WhatsApp send message failed after retries')
            self._omni_log_outbound_delivery('whatsapp', wa_id, url, False, 0, 'request_exception')
            return
        if not resp.ok:
            _logger.error(
                'WhatsApp send message failed: %s %s',
                resp.status_code,
                self._omni_mask_pii_for_logs(resp.text),
            )
        self._omni_log_outbound_delivery(
            'whatsapp',
            wa_id,
            url,
            resp.ok,
            resp.status_code,
            '' if resp.ok else self._omni_mask_pii_for_logs(resp.text),
        )

    def _omni_viber_send_to_user(self, viber_id, text):
        token, _ = self._omni_viber_credentials()
        if not token:
            _logger.warning('Viber bot token is not configured.')
            return
        url = 'https://chatapi.viber.com/pa/send_message'
        try:
            resp = self._omni_http_post_with_retries(
                url,
                headers={'X-Viber-Auth-Token': token},
                json={
                    'receiver': viber_id,
                    'type': 'text',
                    'text': text[:1000],
                },
            )
        except requests.RequestException:
            _logger.exception('Viber send message failed after retries')
            self._omni_log_outbound_delivery('viber', viber_id, url, False, 0, 'request_exception')
            return
        if not resp.ok:
            _logger.error(
                'Viber send message failed: %s %s',
                resp.status_code,
                self._omni_mask_pii_for_logs(resp.text),
            )
        self._omni_log_outbound_delivery(
            'viber',
            viber_id,
            url,
            resp.ok,
            resp.status_code,
            '' if resp.ok else self._omni_mask_pii_for_logs(resp.text),
        )
