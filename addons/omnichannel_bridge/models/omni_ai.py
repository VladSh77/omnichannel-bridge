# -*- coding: utf-8 -*-
import json
import logging
import time
from datetime import datetime, timedelta, time as time_cls

import pytz
import requests

from odoo import api, models
from odoo.fields import Datetime

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
- У legal/RODO темах посилайся на затверджені URL, не переказуй "від себе" умови договору.
- Мінімізуй дані про дітей: запитуй лише необхідне для підбору/бронювання.
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
    def _omni_parse_hm(self, s, default_h=9, default_m=0):
        parts = (s or '').replace('.', ':').split(':')
        h = int(parts[0]) if parts and str(parts[0]).isdigit() else default_h
        m = int(parts[1]) if len(parts) > 1 and str(parts[1]).isdigit() else default_m
        return time_cls(h % 24, min(m, 59))

    @api.model
    def _omni_company_local_time_now(self):
        tzname = self.env.company.partner_id.tz or 'UTC'
        try:
            tz = pytz.timezone(tzname)
        except Exception:
            tz = pytz.UTC
        return datetime.now(tz).time()

    @api.model
    def _omni_time_in_span(self, now_t, start_t, end_t):
        if start_t <= end_t:
            return start_t <= now_t <= end_t
        return now_t >= start_t or now_t <= end_t

    @api.model
    def _omni_night_bot_window_active_now(self, icp=None):
        """TZ §6.1: optional local window (e.g. deep night) where bot may always reply."""
        icp = icp or self.env['ir.config_parameter'].sudo()
        if str(icp.get_param('omnichannel_bridge.night_bot_enabled', 'False')).lower() not in (
            '1',
            'true',
            'yes',
        ):
            return False
        start_s = (icp.get_param('omnichannel_bridge.night_bot_start') or '22:00').strip()
        end_s = (icp.get_param('omnichannel_bridge.night_bot_end') or '07:00').strip()
        now_t = self._omni_company_local_time_now()
        start_t = self._omni_parse_hm(start_s, 22, 0)
        end_t = self._omni_parse_hm(end_s, 7, 0)
        return self._omni_time_in_span(now_t, start_t, end_t)

    @api.model
    def omni_bot_may_reply_now(self, channel=None):
        ICP = self.env['ir.config_parameter'].sudo()
        mode = (ICP.get_param('omnichannel_bridge.bot_reply_mode') or 'always').strip()
        if mode == 'never':
            return False
        if mode == 'always':
            return True
        if mode != 'outside_manager_hours':
            return True
        if self._omni_night_bot_window_active_now(ICP):
            return True
        sla_scope = (ICP.get_param('omnichannel_bridge.sla_scope') or 'manager_hours').strip()
        if sla_scope != 'always' and not self._omni_manager_hours_active_now():
            return True
        quiet = str(ICP.get_param('omnichannel_bridge.bot_inside_hours_if_manager_quiet', 'True')).lower() in (
            '1',
            'true',
            'yes',
        )
        if not quiet or not channel:
            return False
        try:
            sla = int(ICP.get_param('omnichannel_bridge.sla_no_human_seconds', '180'))
        except ValueError:
            sla = 180
        sla = max(30, sla)
        last_h = channel.omni_last_human_reply_at
        if not last_h:
            return True
        return (Datetime.now() - last_h) >= timedelta(seconds=sla)

    @api.model
    def _omni_manager_hours_active_now(self):
        ICP = self.env['ir.config_parameter'].sudo()
        start_s = (ICP.get_param('omnichannel_bridge.manager_hour_start') or '09:00').strip()
        end_s = (ICP.get_param('omnichannel_bridge.manager_hour_end') or '18:00').strip()
        now_t = self._omni_company_local_time_now()
        start = self._omni_parse_hm(start_s, 9, 0)
        end = self._omni_parse_hm(end_s, 18, 0)
        return self._omni_time_in_span(now_t, start, end)

    @api.model
    def omni_autoreply_delay_seconds_for_inbound(self):
        """Delay before running queued AI job: TZ §6.1 SLA during manager hours."""
        ICP = self.env['ir.config_parameter'].sudo()
        mode = (ICP.get_param('omnichannel_bridge.bot_reply_mode') or 'always').strip()
        if mode in ('never', 'always'):
            return 0
        if mode != 'outside_manager_hours':
            return 0
        if self._omni_night_bot_window_active_now(ICP):
            return 0
        sla_scope = (ICP.get_param('omnichannel_bridge.sla_scope') or 'manager_hours').strip()
        if sla_scope != 'always' and not self._omni_manager_hours_active_now():
            return 0
        quiet = str(ICP.get_param('omnichannel_bridge.bot_inside_hours_if_manager_quiet', 'True')).lower() in (
            '1',
            'true',
            'yes',
        )
        if not quiet:
            return 0
        try:
            return max(0, int(ICP.get_param('omnichannel_bridge.sla_no_human_seconds', '180')))
        except ValueError:
            return 180

    @api.model
    def omni_maybe_autoreply(self, channel, partner, text, provider):
        # Callers may pass recordsets from website/public env; re-bind so ORM reads use sudo.
        if channel:
            channel = channel.sudo()
        if partner:
            partner = partner.sudo()
        ICP = self.env['ir.config_parameter'].sudo()
        if not self._omni_llm_enabled():
            return
        normalized = (text or '').strip()
        self._omni_prefill_partner_from_inbound_text(partner, normalized, channel=channel)
        detected_lang = self._omni_detect_and_store_channel_language(channel, normalized)
        if self._omni_is_ru_or_be_message(normalized):
            self._omni_post_bot_message(channel, self._omni_ru_language_policy_reply(detected_lang))
            return
        policy_hit = self._omni_moderation_policy_hit(normalized)
        if policy_hit:
            self._omni_apply_moderation_action(channel, partner, normalized, policy_hit)
            return
        if provider == 'meta' and self._omni_is_coupon_question(normalized):
            self._omni_post_bot_message(channel, self._omni_coupon_meta_offer_text())
            return
        if self._omni_is_sensitive_message(normalized):
            self._omni_send_sensitive_escalation_reply(channel, normalized)
            self._omni_set_sales_stage(partner, 'handoff', channel, 'sensitive_topic')
            self.env['omni.notify'].sudo().notify_escalation(
                channel=channel,
                partner=partner,
                reason='🛟 Чутлива тема (діти/медицина/юридичне/безпека) — передано менеджеру',
            )
            return
        if self._omni_is_confusion_message(normalized):
            self._omni_send_confusion_safe_reply(channel, normalized)
            channel.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                body='[auto] confusion_detected: safe clarify + manager_offer',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            return
        if not self._omni_is_camp_scope_message(normalized):
            self._omni_send_out_of_scope_reply(channel)
            self._omni_set_sales_stage(partner, 'handoff', channel, 'out_of_scope')
            self.env['omni.notify'].sudo().notify_escalation(
                channel=channel,
                partner=partner,
                reason='🎯 Запит поза темою таборів — передано менеджеру',
            )
            return
        # Website live chat is bot-first: reply immediately regardless of manager-hours mode.
        if provider != 'site_livechat' and not self.omni_bot_may_reply_now(channel=channel):
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
        objection_guidance = self.env['omni.sales.intel'].sudo().omni_objection_guidance_block(normalized)
        objection_next_step = self.env['omni.sales.intel'].sudo().omni_objection_next_step_block(normalized)
        pain_script = self.env['omni.sales.intel'].sudo().omni_pain_script_block()
        upsell_script = self.env['omni.sales.intel'].sudo().omni_upsell_script_block()
        system_parts = [base_system]
        if strict:
            system_parts.append(_STRICT_POLICY_UK)
            system_parts.append(_CAMP_DOMAIN_POLICY_UK)
        if objection_guidance:
            system_parts.append(objection_guidance)
        if objection_next_step:
            system_parts.append(objection_next_step)
        if pain_script:
            system_parts.append(pain_script)
        if upsell_script:
            system_parts.append(upsell_script)
        system_parts.append(self._omni_warm_style_policy())
        system_parts.append(self._omni_reply_language_instruction(normalized, channel=channel))
        system_parts.append(facts)
        system = '\n\n'.join(system_parts)

        reply = self._llm_complete(backend, ICP, system, text)
        if not reply:
            self._omni_send_fallback(channel, partner, ICP)
            return
        reply = self._omni_append_next_question(reply, partner, normalized)
        reply = self._omni_apply_reserve_flow(channel, partner, normalized, facts, reply)
        self._omni_post_bot_message(channel, reply)
        self._omni_update_sales_stage_after_reply(partner, channel=channel)
        self._omni_route_manager_mention_if_needed(channel, partner, text, reply)

    def _omni_is_coupon_question(self, text):
        txt = (text or '').lower()
        if not txt:
            return False
        keys = (
            'купон', 'знижк', '-5', '5%', 'промокод', 'promo',
            'kod rabatowy', 'zniżk', 'rabat',
            'discount', 'coupon', 'promo code',
        )
        return any(k in txt for k in keys)

    def _omni_warm_style_policy(self):
        custom = (
            self.env['ir.config_parameter'].sudo().get_param('omnichannel_bridge.style_warm_policy', '') or ''
        ).strip()
        if custom:
            return 'STYLE_POLICY:\n%s' % custom
        return (
            'STYLE_POLICY:\n'
            '- Warm, respectful, premium communication for parents.\n'
            '- No aggressive urgency, no pressure tactics.\n'
            '- Keep concise, helpful, and factual.'
        )

    def _omni_coupon_meta_offer_text(self):
        icp = self.env['ir.config_parameter'].sudo()
        channel_url = (
            icp.get_param('omnichannel_bridge.coupon_public_channel_url', 'https://t.me/campscouting')
            or 'https://t.me/campscouting'
        ).strip()
        code = (icp.get_param('omnichannel_bridge.coupon_public_code', '') or '').strip()
        try:
            discount = float(icp.get_param('omnichannel_bridge.coupon_discount_percent', '5') or 5.0)
        except ValueError:
            discount = 5.0
        discount_str = ('%s' % discount).rstrip('0').rstrip('.')
        code_line = (
            ('Поточний код: %s. ' % code) if code
            else 'Актуальний код дивіться в закріпленому/останньому пості каналу. '
        )
        return (
            'Маємо прозору оферту для Meta/IG: -%s%% діє лише на табори CampScout. '
            '%s'
            'Як отримати: відкрийте Telegram-канал %s і скопіюйте код. '
            'Як застосувати: введіть купон під час реєстрації/оформлення замовлення. '
            'Якщо потрібна допомога з підбором програми — одразу підключу менеджера.'
        ) % (discount_str, code_line, channel_url)

    def _omni_apply_reserve_flow(self, channel, partner, user_text, facts, reply):
        """When catalog facts say no places, enforce manager reserve handoff."""
        if not channel or not partner:
            return reply
        if 'reserve: manager_waitlist_required' not in (facts or ''):
            return reply
        if not self._omni_user_asks_availability(user_text):
            return reply
        channel = channel.sudo()
        partner = partner.sudo()
        if not channel.omni_reserve_requested_at:
            reserve_entry = self._omni_create_or_get_reserve_entry(channel, partner, user_text)
            lead = self._omni_create_or_get_reserve_lead(channel, partner, user_text)
            vals = {'omni_reserve_requested_at': Datetime.now()}
            if reserve_entry:
                vals['omni_reserve_entry_id'] = reserve_entry.id
            if lead:
                vals['omni_reserve_lead_id'] = lead.id
            channel.write(vals)
            self.env['omni.notify'].sudo().notify_escalation(
                channel=channel,
                partner=partner,
                reason='📌 Sold out: клієнту запропоновано резерв через менеджера',
            )
        self._omni_set_sales_stage(partner, 'handoff', channel, 'reserve_waitlist')
        reserve_cta = (
            'Зараз по обраному варіанту місць немає. Можу передати ваш контакт менеджеру для резерву '
            '(лист очікування на випадок звільнення місця). Залиште, будь ласка, телефон або email.'
        )
        if self._omni_is_polish_message(user_text):
            reserve_cta = (
                'Obecnie na wybrany termin nie ma wolnych miejsc. Mogę przekazać kontakt do managera '
                'w celu wpisania na listę rezerwową. Proszę zostawić telefon lub email.'
            )
        if reserve_cta not in (reply or ''):
            return '%s\n\n%s' % ((reply or '').strip(), reserve_cta)
        return reply

    def _omni_create_or_get_reserve_entry(self, channel, partner, user_text):
        if 'omni.reserve.entry' not in self.env:
            return self.env['omni.reserve.entry']
        if channel.omni_reserve_entry_id:
            return channel.omni_reserve_entry_id.sudo()
        try:
            return self.env['omni.reserve.entry'].sudo().create({
                'partner_id': partner.id,
                'channel_id': channel.id,
                'provider': channel.omni_provider or 'site_livechat',
                'user_text': (user_text or '')[:2000],
                'state': 'new',
            })
        except Exception:
            _logger.exception('Failed creating reserve entry for channel %s', channel.id)
            return self.env['omni.reserve.entry']

    def _omni_create_or_get_reserve_lead(self, channel, partner, user_text):
        if 'crm.lead' not in self.env:
            return self.env['crm.lead']
        if channel.omni_reserve_lead_id:
            return channel.omni_reserve_lead_id.sudo()
        try:
            provider_label = dict(self.env['omni.integration']._selection_providers()).get(
                channel.omni_provider or 'site_livechat',
                channel.omni_provider or 'site_livechat',
            )
            return self.env['crm.lead'].sudo().create({
                'name': '[Reserve] %s' % (partner.display_name or 'Camp lead'),
                'partner_id': partner.id,
                'description': (
                    'Reserve request (sold-out) from %s.\nLast user message: %s\nDiscuss channel id: %s'
                ) % (provider_label, (user_text or '')[:400], channel.id),
            })
        except Exception:
            _logger.exception('Failed creating reserve lead for channel %s', channel.id)
            return self.env['crm.lead']

    def _omni_user_asks_availability(self, user_text):
        txt = (user_text or '').lower()
        keys = (
            'місц', 'є місця', 'наявн', 'заїзд', 'зміна', 'вільні',
            'miejsc', 'dostęp', 'wolne', 'turnus',
            'available', 'availability', 'spots left', 'free spots',
        )
        return any(k in txt for k in keys)

    def _omni_send_fallback(self, channel, partner, icp):
        """LLM недоступний — надсилаємо шаблонне повідомлення і сповіщаємо менеджера."""
        msg = (icp.get_param('omnichannel_bridge.fallback_message') or '').strip()
        if not msg:
            # Динамічний fallback: якщо зараз неробочий час — з часом відповіді
            if self._omni_manager_hours_active_now():
                msg = (
                    'Дякуємо за звернення. Зараз підключаю менеджера — '
                    'він відповість найближчим часом.'
                )
            else:
                start = (icp.get_param('omnichannel_bridge.manager_hour_start') or '09:00').strip()
                msg = (
                    'Дякуємо за звернення. Перевірили доступність менеджера: '
                    'він відповість вранці о %(start)s. '
                    'Якщо питання термінове — залиште номер телефону і ми зателефонуємо.'
                ) % {'start': start}
        # UX pacing for livechat so fallback is not visually abrupt.
        try:
            time.sleep(2)
        except Exception:
            pass
        self._omni_post_bot_message(channel, msg)
        # Сповіщаємо менеджера
        self.env['omni.notify'].sudo().notify_escalation(
            channel=channel,
            partner=partner,
            reason='⚙️ LLM недоступний — надіслано fallback повідомлення клієнту',
        )
        self._omni_set_sales_stage(partner, 'handoff', channel, 'llm_fallback')

    def _omni_send_out_of_scope_reply(self, channel):
        self._omni_post_bot_message(
            channel,
            (
                'Я допомагаю лише з питаннями щодо таборів CampScout '
                '(програми, умови, безпека, доїзд, оплата, реєстрація). '
                'Передаю ваш запит менеджеру.'
            ),
        )

    def _omni_send_sensitive_escalation_reply(self, channel, user_text):
        is_pl = self._omni_is_polish_message(user_text or '')
        body = (
            'Дякую за довіру. Це чутливе питання, тому передаю діалог менеджеру, '
            'щоб надати коректну і безпечну відповідь.'
            if not is_pl else
            'Dziękuję za zaufanie. To wrażliwy temat, dlatego przekazuję rozmowę '
            'do managera, aby udzielić poprawnej i bezpiecznej odpowiedzi.'
        )
        self._omni_post_bot_message(channel, body)

    def _omni_legal_notice_block(self, channel):
        channel = channel.sudo()
        if channel.omni_legal_notice_sent_at:
            return ''
        company = self.env.company.sudo()
        legal_name = (company.name or '').strip() or 'CampScout'
        icp = self.env['ir.config_parameter'].sudo()
        consent_site = (icp.get_param('omnichannel_bridge.consent_site_text') or '').strip()
        terms_url = (icp.get_param('omnichannel_bridge.legal_terms_url') or 'https://campscout.eu/terms').strip()
        privacy_url = (icp.get_param('omnichannel_bridge.legal_privacy_url') or 'https://campscout.eu/privacy-policy').strip()
        cookie_url = (icp.get_param('omnichannel_bridge.legal_cookie_url') or 'https://campscout.eu/cookie-policy').strip()
        child_url = (
            icp.get_param('omnichannel_bridge.legal_child_protection_url') or
            'https://campscout.eu/child-protection'
        ).strip()
        consent_line = consent_site or (
            'ℹ️ Коротко про дані: натискаючи "надіслати", ви погоджуєтесь на обробку контактних даних '
            'для підбору табору та звʼязку з менеджером.'
        )
        return (
            '%(consent)s\n'
            'Відповідає юридична особа: %(legal_name)s.\n'
            'Політики: '
            '<a href="%(privacy)s">Privacy</a> | '
            '<a href="%(terms)s">Terms</a> | '
            '<a href="%(cookie)s">Cookies</a> | '
            '<a href="%(child)s">Child protection</a>'
        ) % {
            'consent': consent_line,
            'legal_name': legal_name,
            'privacy': privacy_url,
            'terms': terms_url,
            'cookie': cookie_url,
            'child': child_url,
        }

    def _omni_post_bot_message(self, channel, body):
        channel = channel.sudo()
        legal = self._omni_legal_notice_block(channel)
        final_body = (body or '').strip()
        if channel._omni_is_website_livechat_channel() and not final_body.startswith('🤖'):
            final_body = '🤖 %s' % final_body
        if legal:
            final_body = '%s\n\n%s' % (final_body, legal)
        channel.with_context(omni_skip_livechat_inbound=True).message_post(
            body=final_body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=self.env.ref('base.partner_root').id,
        )
        if legal and not channel.omni_legal_notice_sent_at:
            channel.write({'omni_legal_notice_sent_at': Datetime.now()})

    def _omni_is_sensitive_message(self, user_text):
        txt = (user_text or '').lower()
        if not txt:
            return False
        sensitive_markers = (
            # child safety / abuse / police
            'насиль', 'побив', 'домаган', 'абюз', 'булінг', 'суїцид', 'самогуб', 'поліці',
            'abuse', 'violence', 'suicide', 'self-harm', 'harassment', 'policja',
            # medical / emergency
            'алергі', 'епілеп', 'астм', 'діабет', 'лікар', 'медич', 'травм', 'швидк',
            'allerg', 'epilep', 'asthma', 'diabet', 'medical', 'injury', 'ambulans',
            # legal / claims
            'суд', 'претензі', 'позов', 'адвокат', 'відповідальн', 'договор',
            'lawsuit', 'legal', 'claim', 'attorney', 'lawyer', 'umowa', 'roszczen',
            # insurance disputes
            'страхов', 'відшкодуван', 'компенсац',
            'insurance', 'compensation',
        )
        return any(k in txt for k in sensitive_markers)

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

    def _omni_detect_and_store_channel_language(self, channel, user_text):
        detected = self._omni_detect_language(user_text, channel=channel)
        if channel and detected in ('uk', 'pl') and channel.omni_detected_lang != detected:
            channel.sudo().write({'omni_detected_lang': detected})
        return detected

    def _omni_detect_language(self, user_text, channel=None):
        txt = (user_text or '').strip()
        low = txt.lower()
        if self._omni_is_polish_message(txt):
            return 'pl'
        if self._omni_is_ru_or_be_message(txt):
            return 'uk'
        uk_markers = (
            'доброго дня', 'будь ласка', 'дякую', 'табір', 'зміна', 'вартість', 'місця',
            'дитина', 'менеджер', 'реєстрація',
        )
        if any(k in low for k in uk_markers):
            return 'uk'
        if channel and channel.omni_detected_lang in ('uk', 'pl'):
            return channel.omni_detected_lang
        return 'uk'

    def _omni_ru_language_policy_reply(self, detected_lang='uk'):
        if detected_lang == 'pl':
            return (
                'Dla jakości i zgodności prowadzimy komunikację po ukraińsku lub po polsku. '
                'Proszę kontynuować po polsku lub po ukraińsku, a od razu pomogę z wyborem obozu.'
            )
        return (
            'Для якості та відповідності ми ведемо спілкування українською або польською. '
            'Будь ласка, продовжимо українською або польською — і я одразу допоможу з підбором табору.'
        )

    def _omni_reply_language_instruction(self, user_text, channel=None):
        txt = (user_text or '').lower()
        if self._omni_is_polish_message(txt):
            return 'LANGUAGE_RULE: Reply in Polish.'
        if self._omni_is_ru_or_be_message(txt):
            return 'LANGUAGE_RULE: Reply in Ukrainian.'
        if channel and channel.omni_detected_lang == 'pl':
            return 'LANGUAGE_RULE: Reply in Polish.'
        if channel and channel.omni_detected_lang == 'uk':
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
        if len(txt) <= 35:
            return True
        # Website livechat starter lines: browsing / docs without explicit "camp" words yet.
        onboarding_hints = (
            'документац',
            'інформац',
            'дивлю',
            'навколо',
            'цікав',
            'розповід',
            'dokumentacj',
            'szukam informacj',
            'documentation',
            'looking around',
            'just looking',
        )
        if any(k in txt for k in onboarding_hints):
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
            'цін',  # ціни, ціну, про ціни
            'вартіст',
            'дит',
            'підліт',
            'безпек',
            'дорог',
            'доїзд',
            'трансфер',
            'проживан',
            'харчуван',
            'cena',
            'obóz',
            'kolonia',
            'turnus',
            'price',
        )
        return any(k in txt for k in camp_terms)

    def _omni_is_confusion_message(self, user_text):
        txt = (user_text or '').lower()
        if not txt:
            return False
        confusion = (
            'не зрозум', 'незрозум', 'плута', 'не те', 'знову те саме',
            'не відповіли', 'не по темі', 'що ви маєте на увазі',
            'nie rozumiem', 'to nie o tym', 'powtarzasz się',
            'i do not understand', 'you repeat', 'off topic',
        )
        return any(k in txt for k in confusion)

    def _omni_send_confusion_safe_reply(self, channel, user_text):
        is_pl = self._omni_is_polish_message(user_text or '')
        body = (
            'Дякую, бачу що відповідь була не зовсім у точку. Сформулюю коротко і по фактах з системи. '
            'Якщо зручно, одразу підключу менеджера.'
            if not is_pl else
            'Dziękuję, widzę że odpowiedź nie była trafiona. Podam krótko i wyłącznie na podstawie faktów z systemu. '
            'Jeśli wygodnie, od razu podłączę managera.'
        )
        self._omni_post_bot_message(channel, body)

    def _omni_moderation_policy_hit(self, user_text):
        txt = (user_text or '').lower().strip()
        if not txt:
            return ''
        icp = self.env['ir.config_parameter'].sudo()
        raw = (icp.get_param('omnichannel_bridge.moderation_keywords', '') or '').strip()
        if not raw:
            return ''
        keys = [k.strip().lower() for k in raw.split(',') if k and k.strip()]
        for key in keys:
            if key and key in txt:
                return key
        return ''

    def _omni_apply_moderation_action(self, channel, partner, user_text, hit_keyword):
        icp = self.env['ir.config_parameter'].sudo()
        action = (icp.get_param('omnichannel_bridge.moderation_action', 'escalate') or 'escalate').strip()
        note = 'moderation_policy_hit:%s' % (hit_keyword or 'unknown')
        channel.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
            body='[auto] %s' % note,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        if action in ('escalate', 'escalate_pause'):
            self._omni_post_bot_message(
                channel,
                'Дякую за повідомлення. Для коректної відповіді передаю діалог менеджеру.',
            )
            self.env['omni.notify'].sudo().notify_problematic(
                channel=channel,
                partner=partner,
                note=note,
            )
            self._omni_set_sales_stage(partner, 'handoff', channel, note)
        if action == 'escalate_pause' and channel:
            channel.sudo().write({
                'omni_bot_paused': True,
                'omni_bot_pause_reason': 'moderation_policy',
            })

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
            resp = requests.post(openai_url, json=payload_oa, timeout=(3, 8))
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
            resp = requests.post(native_url, json=payload_native, timeout=(3, 8))
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
            self._omni_set_sales_stage(partner, 'handoff', channel, 'client_requested_human')
            channel.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                body='[auto] Client asked for a human — assign in Discuss / CRM.',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def _omni_update_sales_stage_after_reply(self, partner, channel=None):
        if not partner:
            return
        partner = partner.sudo()
        if partner.omni_sales_stage in ('handoff', 'proposal'):
            return
        if partner.omni_child_age and partner.omni_preferred_period:
            self._omni_set_sales_stage(partner, 'proposal', channel, 'profile_ready')
        elif partner.omni_sales_stage == 'new':
            self._omni_set_sales_stage(partner, 'qualifying', channel, 'first_qualification_step')

    def _omni_set_sales_stage(self, partner, new_stage, channel=None, reason=''):
        if not partner or not new_stage:
            return
        partner = partner.sudo()
        old_stage, final_stage, changed = partner.omni_set_sales_stage(
            new_stage,
            channel=channel,
            reason=reason or '',
            source='omni_ai',
        )
        if not changed:
            return
        if channel:
            self.env['omni.notify'].sudo().notify_stage_change(
                channel=channel,
                partner=partner,
                old_stage=old_stage,
                new_stage=final_stage,
                reason=reason,
            )

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
        has_age = bool(partner.omni_child_age) or self._omni_text_has_age(user_text)
        has_period = bool(partner.omni_preferred_period) or self._omni_text_has_period(user_text)
        has_city = bool(partner.omni_departure_city) or self._omni_text_has_departure_city(user_text)
        has_budget = bool(partner.omni_budget_amount) or self._omni_text_has_budget(user_text)
        has_contact = bool(partner.phone or partner.mobile or partner.email) or self._omni_text_has_contact(user_text)
        if not has_age:
            return (
                'Підкажіть, будь ласка, який вік дитини?'
                if not is_pl else
                'Proszę podać wiek dziecka.'
            )
        if not has_period:
            return (
                'На який період або зміну розглядаєте табір?'
                if not is_pl else
                'Na jaki termin lub turnus rozważają Państwo obóz?'
            )
        if not has_city:
            return (
                'З якого міста вам зручний виїзд?'
                if not is_pl else
                'Z jakiego miasta ma być wyjazd?'
            )
        if not has_budget:
            return (
                'Який орієнтовний бюджет на путівку ви плануєте?'
                if not is_pl else
                'Jaki orientacyjny budżet planują Państwo na obóz?'
            )
        if not has_contact:
            return (
                'Залиште, будь ласка, контакт (телефон або email), щоб я передав підбір менеджеру.'
                if not is_pl else
                'Proszę zostawić kontakt (telefon lub email), a przekażę dobór menedżerowi.'
            )
        return ''

    def _omni_prefill_partner_from_inbound_text(self, partner, user_text, channel=None):
        if not partner or not user_text:
            return
        partner = partner.sudo()
        txt = user_text.strip()
        Partner = self.env['res.partner'].sudo()
        vals = {}
        email = Partner.omni_parse_email(txt)
        phone = Partner.omni_parse_phone(txt)
        if email and not partner.email:
            vals['email'] = email
        if phone and not (partner.phone or partner.mobile):
            vals['phone'] = phone
        age = self._omni_extract_age(txt)
        if age and not partner.omni_child_age:
            vals['omni_child_age'] = age
        period = self._omni_extract_period(txt)
        if period and not partner.omni_preferred_period:
            vals['omni_preferred_period'] = period
        city = self._omni_extract_departure_city(txt)
        if city and not partner.omni_departure_city:
            vals['omni_departure_city'] = city
        budget_amount, budget_currency = self._omni_extract_budget(txt)
        if budget_amount and not partner.omni_budget_amount:
            vals['omni_budget_amount'] = budget_amount
            if budget_currency and not partner.omni_budget_currency:
                vals['omni_budget_currency'] = budget_currency
        if vals:
            partner.write(vals)
            self._omni_set_sales_stage(partner, 'qualifying', channel, 'profile_prefill_from_inbound')

    def _omni_extract_age(self, txt):
        import re
        m = re.search(r'(\d{1,2})\s*(?:рок[аів]?|р\.|lat|lata)', txt, re.IGNORECASE)
        if not m:
            return 0
        age = int(m.group(1))
        return age if 5 <= age <= 18 else 0

    def _omni_extract_period(self, txt):
        import re
        m = re.search(
            r'(черв(?:ень|ня)|лип(?:ень|ня)|серп(?:ень|ня)|wrzesie[nń]|lipiec|sierpie[nń]|july|august)',
            txt,
            re.IGNORECASE,
        )
        return m.group(1).lower() if m else ''

    def _omni_extract_departure_city(self, txt):
        import re
        m = re.search(
            r'(?:з|из|from)\s+([A-Za-zА-Яа-яІіЇїЄєҐґŁłŚśŻżŹźĆćŃńÓóĘęĄą\-]{3,30})',
            txt,
            re.IGNORECASE,
        )
        return m.group(1) if m else ''

    def _omni_extract_budget(self, txt):
        import re
        m = re.search(r'(\d{3,6})\s*(грн|uah|zl|pln|zł|€|eur)', txt, re.IGNORECASE)
        if not m:
            return 0.0, ''
        return float(m.group(1)), m.group(2).lower()

    def _omni_text_has_age(self, txt):
        return bool(self._omni_extract_age(txt or ''))

    def _omni_text_has_period(self, txt):
        return bool(self._omni_extract_period(txt or ''))

    def _omni_text_has_departure_city(self, txt):
        return bool(self._omni_extract_departure_city(txt or ''))

    def _omni_text_has_budget(self, txt):
        amount, _curr = self._omni_extract_budget(txt or '')
        return bool(amount)

    def _omni_text_has_contact(self, txt):
        Partner = self.env['res.partner'].sudo()
        return bool(Partner.omni_parse_email(txt or '') or Partner.omni_parse_phone(txt or ''))
