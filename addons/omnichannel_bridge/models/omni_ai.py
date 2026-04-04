# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, time as time_cls

import pytz
import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

_STRICT_POLICY_UK = """
ПОЛІТИКА ВІДПОВІДІ (обов’язково):
- Джерело правди — лише блок FACTS_FROM_DATABASE нижче (поля CRM, каталог, оплати, звернення).
- Ціни, «місця», оплати, імена та умови — тільки як там зазначено. Не доповнюй з голови.
- Якщо потрібного факту немає в блоці — скажи прямо, що в системі цього не видно, і запропонуй менеджера.
- Не вигадуй договори, страхові продукти, акції та терміни, якщо вони не передані у фактах.
- Можеш формулювати природною українською, але не супереч даним і не додавай нових цифр.
"""


class OmniAi(models.AbstractModel):
    _name = 'omni.ai'
    _description = 'LLM autoreply: Ollama (OSS/local) or OpenAI; strict grounding from Python facts'

    @api.model
    def _omni_llm_enabled(self):
        ICP = self.env['ir.config_parameter'].sudo()
        if str(ICP.get_param('omnichannel_bridge.llm_enabled', '')).lower() in (
            '1',
            'true',
            'yes',
        ):
            return True
        return str(ICP.get_param('omnichannel_bridge.openai_enabled', 'False')).lower() in (
            '1',
            'true',
            'yes',
        )

    @api.model
    def omni_bot_may_reply_now(self):
        ICP = self.env['ir.config_parameter'].sudo()
        mode = (ICP.get_param('omnichannel_bridge.bot_reply_mode') or 'always').strip()
        if mode == 'never':
            return False
        if mode == 'outside_manager_hours':
            return not self._omni_manager_hours_active_now()
        return True

    @api.model
    def _omni_manager_hours_active_now(self):
        ICP = self.env['ir.config_parameter'].sudo()
        start_s = (ICP.get_param('omnichannel_bridge.manager_hour_start') or '09:00').strip()
        end_s = (ICP.get_param('omnichannel_bridge.manager_hour_end') or '18:00').strip()
        tzname = self.env.company.partner_id.tz or 'UTC'
        try:
            tz = pytz.timezone(tzname)
        except Exception:
            tz = pytz.UTC
        now_t = datetime.now(tz).time()

        def _parse_hm(s):
            parts = s.replace('.', ':').split(':')
            h = int(parts[0]) if parts and parts[0].isdigit() else 9
            m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            return time_cls(h % 24, min(m, 59))

        start = _parse_hm(start_s)
        end = _parse_hm(end_s)
        if start <= end:
            return start <= now_t <= end
        return now_t >= start or now_t <= end

    @api.model
    def omni_maybe_autoreply(self, channel, partner, text, provider):
        ICP = self.env['ir.config_parameter'].sudo()
        if not self._omni_llm_enabled():
            return
        if not self.omni_bot_may_reply_now():
            return
        backend = (ICP.get_param('omnichannel_bridge.llm_backend') or 'ollama').strip()
        if backend == 'openai':
            if not ICP.get_param('omnichannel_bridge.openai_api_key'):
                _logger.warning('LLM backend is openai but API key is empty.')
                return
        elif backend == 'ollama':
            pass
        else:
            _logger.warning('Unknown llm_backend=%s', backend)
            return

        base_system = ICP.get_param(
            'omnichannel_bridge.openai_system_prompt',
            'Ти допомагаєш клієнту чесно та ввічливо.',
        )
        facts = self.env['omni.knowledge'].omni_strict_grounding_bundle(channel, partner)
        strict = str(ICP.get_param('omnichannel_bridge.llm_strict_grounding', 'True')).lower() in (
            '1',
            'true',
            'yes',
        )
        system_parts = [base_system]
        if strict:
            system_parts.append(_STRICT_POLICY_UK)
        system_parts.append(facts)
        system = '\n\n'.join(system_parts)

        reply = self._llm_complete(backend, ICP, system, text)
        if not reply:
            self._omni_send_fallback(channel, partner, ICP)
            return
        channel.sudo().message_post(
            body=reply,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=self.env.ref('base.partner_root').id,
        )
        self._omni_route_manager_mention_if_needed(channel, text, reply)

    def _omni_send_fallback(self, channel, partner, icp):
        """LLM недоступний — надсилаємо шаблонне повідомлення і сповіщаємо менеджера."""
        msg = (icp.get_param('omnichannel_bridge.fallback_message') or '').strip()
        if not msg:
            # Динамічний fallback: якщо зараз неробочий час — з часом відповіді
            if self._omni_manager_hours_active_now():
                msg = 'Дякуємо за звернення! Менеджер зараз зайнятий і відповість найближчим часом.'
            else:
                start = (icp.get_param('omnichannel_bridge.manager_hour_start') or '09:00').strip()
                msg = (
                    'Дякуємо за звернення! '
                    'Наш менеджер відповість вранці о %(start)s. '
                    'Якщо питання термінове — залиште номер телефону і ми зателефонуємо.'
                ) % {'start': start}
        channel.sudo().message_post(
            body=msg,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=self.env.ref('base.partner_root').id,
        )
        # Сповіщаємо менеджера
        self.env['omni.notify'].sudo().notify_escalation(
            channel=channel,
            partner=partner,
            reason='⚙️ LLM недоступний — надіслано fallback повідомлення клієнту',
        )

    def _llm_complete(self, backend, icp, system_prompt, user_text):
        if backend == 'openai':
            return self._openai_chat_completion(
                icp.get_param('omnichannel_bridge.openai_api_key'),
                icp.get_param('omnichannel_bridge.openai_model') or 'gpt-4o-mini',
                system_prompt,
                user_text,
            )
        if backend == 'ollama':
            base = (icp.get_param('omnichannel_bridge.ollama_base_url') or 'http://127.0.0.1:11434').strip()
            model = (icp.get_param('omnichannel_bridge.ollama_model') or 'llama3.2').strip()
            return self._ollama_chat_completion(base, model, system_prompt, user_text)
        return ''

    def _openai_chat_completion(self, api_key, model, system_prompt, user_text):
        if not api_key:
            return ''
        url = 'https://api.openai.com/v1/chat/completions'
        headers = {
            'Authorization': 'Bearer %s' % api_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_text},
            ],
            'temperature': 0.15,
        }
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
            if not resp.ok:
                _logger.error('OpenAI error %s: %s', resp.status_code, resp.text)
                return ''
            data = resp.json()
            return (data.get('choices') or [{}])[0].get('message', {}).get('content', '').strip()
        except Exception:
            _logger.exception('OpenAI request failed')
            return ''

    def _ollama_chat_completion(self, base_url, model, system_prompt, user_text):
        base = base_url.rstrip('/')
        openai_url = '%s/v1/chat/completions' % base
        payload_oa = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_text},
            ],
            'temperature': 0.15,
            'stream': False,
        }
        try:
            resp = requests.post(openai_url, json=payload_oa, timeout=120)
            if resp.ok:
                data = resp.json()
                return (data.get('choices') or [{}])[0].get('message', {}).get('content', '').strip()
        except Exception:
            _logger.debug('Ollama OpenAI-compatible endpoint failed, trying /api/chat', exc_info=True)
        native_url = '%s/api/chat' % base
        payload_native = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_text},
            ],
            'stream': False,
            'options': {'temperature': 0.15},
        }
        try:
            resp = requests.post(native_url, json=payload_native, timeout=120)
            if not resp.ok:
                _logger.error('Ollama error %s: %s', resp.status_code, resp.text)
                return ''
            data = resp.json()
            return (data.get('message') or {}).get('content', '').strip()
        except Exception:
            _logger.exception('Ollama request failed')
            return ''

    def _omni_route_manager_mention_if_needed(self, channel, user_text, bot_reply):
        lowered = (user_text or '').lower()
        if any(k in lowered for k in ('менеджер', 'manager', 'людина', 'human')):
            channel.sudo().message_post(
                body='[auto] Client asked for a human — assign in Discuss / CRM.',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
