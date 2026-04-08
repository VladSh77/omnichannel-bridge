# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging
import time

import requests
from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.tools import html2plaintext

from ..utils.webhook_parsers import extract_meta_mid, extract_telegram_update_id

_logger = logging.getLogger(__name__)

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
        if provider in ('whatsapp', 'twilio_whatsapp'):
            return self._omni_process_whatsapp_stub(payload, headers)
        _logger.warning('Unknown omnichannel provider: %s', provider)
        return {'ok': False, 'error': 'unknown_provider'}

    def _omni_extract_external_event_id(self, provider, data):
        if provider == 'telegram':
            return extract_telegram_update_id(data)
        if provider == 'meta':
            return extract_meta_mid(data)
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
        self.env['omni.memory'].sudo().omni_apply_inbound_learning(partner, text)
        delay = self.env['omni.ai'].sudo().omni_autoreply_delay_seconds_for_inbound()
        self.env['omni.ai.job'].sudo().omni_enqueue_autoreply(
            channel=channel,
            partner=partner,
            text=text,
            provider=provider,
            delay_seconds=delay,
        )

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
            webhook_event.sudo().write({
                'state': 'processed',
                'processed_at': fields.Datetime.now(),
            })
            return {'ok': True, 'skipped': True}
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
        _logger.info('Viber webhook stub (implement Viber parser).')
        return {'ok': True, 'stub': 'viber'}

    def _omni_process_whatsapp_stub(self, payload, headers):
        _logger.info('WhatsApp webhook stub (Meta/Twilio parser).')
        return {'ok': True, 'stub': 'whatsapp'}

    @api.model
    def omni_send_outbound(self, provider, external_thread_id, customer_partner, body_html):
        text = (html2plaintext(body_html or '') or '').strip()
        if not text:
            return
        if provider == 'telegram':
            self._omni_telegram_send_message(str(external_thread_id), text)
        elif provider == 'meta':
            self._omni_meta_send_psid(str(external_thread_id), text)
        else:
            _logger.info(
                'Outbound not implemented for provider=%s thread=%s',
                provider,
                external_thread_id,
            )

    def _omni_http_post_with_retries(self, url, *, json=None, params=None, max_attempts=4, timeout=30):
        """Graph / Telegram: retry transient failures (TZ §14.1)."""
        delay = 1.0
        last_resp = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(url, json=json, params=params, timeout=timeout)
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
            return
        if not resp.ok:
            _logger.error('Telegram sendMessage failed: %s %s', resp.status_code, resp.text)

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
            return
        if not resp.ok:
            _logger.error('Meta send message failed: %s %s', resp.status_code, resp.text)
