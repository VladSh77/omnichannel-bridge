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

_CAMP_DOMAIN_POLICY_UK = """
ДОМЕН ТА МОВА (обов'язково):
- Ти консультант лише з теми дитячих таборів CampScout: зміни, умови, безпека, доїзд, оплата, наявність місць.
- Якщо запит поза темою таборів або бракує фактів у системі, коротко повідом про обмеження і запропонуй підключити менеджера.
- Відповідай українською або польською за мовою клієнта.
- Не відповідай російською; якщо звернення російською, ввічливо запропонуй продовжити українською або польською.
- Не давай медичних або юридичних висновків від себе; у чутливих темах одразу ескалюй до менеджера.
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
        normalized = (text or '').strip()
        if not self._omni_is_camp_scope_message(normalized):
            self._omni_send_out_of_scope_reply(channel)
            if partner:
                partner.sudo().write({'omni_sales_stage': 'handoff'})
            self.env['omni.notify'].sudo().notify_escalation(
                channel=channel,
                partner=partner,
                reason='🎯 Запит поза темою таборів — передано менеджеру',
            )
            return
        # Website live chat is bot-first: reply immediately regardless of manager-hours mode.
        if provider != 'site_livechat' and not self.omni_bot_may_reply_now():
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
        facts = self.env['omni.knowledge'].omni_strict_grounding_bundle(
            channel,
            partner,
            user_text=text or '',
        )
        strict = str(ICP.get_param('omnichannel_bridge.llm_strict_grounding', 'True')).lower() in (
            '1',
            'true',
            'yes',
        )
        system_parts = [base_system]
        if strict:
            system_parts.append(_STRICT_POLICY_UK)
            system_parts.append(_CAMP_DOMAIN_POLICY_UK)
        system_parts.append(self._omni_reply_language_instruction(normalized))
        system_parts.append(facts)
        system = '\n\n'.join(system_parts)

        reply = self._llm_complete(backend, ICP, system, text)
        if not reply:
            self._omni_send_fallback(channel, partner, ICP)
            return
        reply = self._omni_append_next_question(reply, partner, normalized)
        channel.sudo().message_post(
            body=reply,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=self.env.ref('base.partner_root').id,
        )
        self._omni_update_sales_stage_after_reply(partner)
        self._omni_route_manager_mention_if_needed(channel, partner, text, reply)

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
        if partner:
            partner.sudo().write({'omni_sales_stage': 'handoff'})

    def _omni_send_out_of_scope_reply(self, channel):
        channel.sudo().message_post(
            body=(
                'Я допомагаю лише з питаннями щодо таборів CampScout '
                '(програми, умови, безпека, доїзд, оплата, реєстрація). '
                'Передаю ваш запит менеджеру.'
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=self.env.ref('base.partner_root').id,
        )

    def _omni_is_ru_or_be_message(self, user_text):
        txt = (user_text or '').lower()
        if not txt:
            return False
        cyrillic_only = any('а' <= ch <= 'я' or ch in 'іїєґў' for ch in txt)
        if not cyrillic_only:
            return False
        hard_ru_markers = ('ы', 'э', 'ъ', 'ё')
        hard_be_markers = ('ў',)
        if any(ch in txt for ch in hard_ru_markers + hard_be_markers):
            return True
        ru_be_words = (
            'привет',
            'здравствуйте',
            'здраствуйте',
            'лагерь',
            'смена',
            'путевка',
            'сколько стоит',
            'менеджер',
            'прывітанне',
            'лагер',
            'кошт',
            'менеджар',
        )
        return any(w in txt for w in ru_be_words)

    def _omni_reply_language_instruction(self, user_text):
        txt = (user_text or '').lower()
        if self._omni_is_polish_message(txt):
            return 'LANGUAGE_RULE: Reply in Polish.'
        if self._omni_is_ru_or_be_message(txt):
            return 'LANGUAGE_RULE: Reply in Ukrainian.'
        return 'LANGUAGE_RULE: Reply in the client language (Ukrainian or Polish).'

    def _omni_is_polish_message(self, user_text):
        txt = (user_text or '').lower()
        if not txt:
            return False
        if any(ch in txt for ch in ('ą', 'ć', 'ę', 'ł', 'ń', 'ó', 'ś', 'ź', 'ż')):
            return True
        pl_words = (
            'dzień dobry',
            'obóz',
            'kolonia',
            'turnus',
            'cena',
            'zapisać',
            'rejestracja',
            'dziecko',
            'miejsca',
        )
        return any(w in txt for w in pl_words)

    def _omni_is_camp_scope_message(self, user_text):
        txt = (user_text or '').lower()
        if not txt:
            return True
        # Do not overblock short neutral messages; let LLM continue dialog.
        if len(txt) <= 20:
            return True
        camp_terms = (
            'таб',
            'camp',
            'зміна',
            'заїзд',
            'програма',
            'місц',
            'реєстрац',
            'брон',
            'оплат',
            'ціна',
            'вартіст',
            'дит',
            'підліт',
            'безпек',
            'дорог',
            'доїзд',
            'трансфер',
            'проживан',
            'харчуван',
        )
        return any(k in txt for k in camp_terms)

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

    def _omni_route_manager_mention_if_needed(self, channel, partner, user_text, bot_reply):
        lowered = (user_text or '').lower()
        if any(k in lowered for k in ('менеджер', 'manager', 'людина', 'human')):
            if partner:
                partner.sudo().write({'omni_sales_stage': 'handoff'})
            channel.sudo().message_post(
                body='[auto] Client asked for a human — assign in Discuss / CRM.',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def _omni_update_sales_stage_after_reply(self, partner):
        if not partner:
            return
        partner = partner.sudo()
        if partner.omni_sales_stage in ('handoff', 'proposal'):
            return
        if partner.omni_child_age and partner.omni_preferred_period:
            partner.write({'omni_sales_stage': 'proposal'})
        elif partner.omni_sales_stage == 'new':
            partner.write({'omni_sales_stage': 'qualifying'})

    def _omni_append_next_question(self, reply, partner, user_text):
        base = (reply or '').strip()
        if not base or not partner:
            return base
        if any(q in base for q in ('?', '？')):
            return base
        question = self._omni_pick_next_question(partner, user_text)
        if not question:
            return base
        return '%s\n\n%s' % (base, question)

    def _omni_pick_next_question(self, partner, user_text):
        partner = partner.sudo()
        is_pl = self._omni_is_polish_message(user_text or '')
        if not partner.omni_child_age:
            return (
                'Підкажіть, будь ласка, який вік дитини?'
                if not is_pl else
                'Proszę podać wiek dziecka.'
            )
        if not partner.omni_preferred_period:
            return (
                'На який період або зміну розглядаєте табір?'
                if not is_pl else
                'Na jaki termin lub turnus rozważają Państwo obóz?'
            )
        if not partner.omni_departure_city:
            return (
                'З якого міста вам зручний виїзд?'
                if not is_pl else
                'Z jakiego miasta ma być wyjazd?'
            )
        if not partner.omni_budget_amount:
            return (
                'Який орієнтовний бюджет на путівку ви плануєте?'
                if not is_pl else
                'Jaki orientacyjny budżet planują Państwo na obóz?'
            )
        if not (partner.phone or partner.mobile or partner.email):
            return (
                'Залиште, будь ласка, контакт (телефон або email), щоб я передав підбір менеджеру.'
                if not is_pl else
                'Proszę zostawić kontakt (telefon lub email), a przekażę dobór menedżerowi.'
            )
        return ''
