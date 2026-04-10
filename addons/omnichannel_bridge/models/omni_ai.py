# -*- coding: utf-8 -*-
import json
import logging
import re
import time
from datetime import datetime, timedelta, time as time_cls

import pytz
import requests
from requests import exceptions as req_exc

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
        if self._omni_is_weather_message(normalized):
            self._omni_post_bot_message(channel, self._omni_weather_to_camp_reply(normalized))
            self._omni_update_sales_stage_after_reply(partner, channel=channel)
            return
        if self._omni_is_paid_or_booked_message(normalized):
            self.env['omni.memory'].sudo()._omni_attach_paid_booking_facts(partner, normalized)
            parsed_email = self.env['res.partner'].sudo().omni_parse_email(normalized)
            known_email = (partner.email or '').strip().lower() if partner else ''
            if not parsed_email and not known_email:
                self._omni_post_bot_message(
                    channel,
                    'Щоб чітко ідентифікувати ваше бронювання, надішліть, будь ласка, email, який вказували при замовленні.',
                )
                return
            booking_facts = self._omni_extract_booking_facts_from_memory(partner)
            if booking_facts:
                camp_or_event = booking_facts.get('camp') or booking_facts.get('event')
                ref = booking_facts.get('booking_ref')
                invoice = booking_facts.get('invoice')
                fragments = []
                if camp_or_event:
                    fragments.append('Табір/подія: %s.' % camp_or_event)
                if ref:
                    fragments.append('Бронювання: %s.' % ref)
                if invoice:
                    fragments.append('Фактура: %s.' % invoice)
                if fragments:
                    self._omni_post_bot_message(
                        channel,
                        'Знайшла ваше замовлення за email. %s Підкажіть, вас цікавлять дати заїзду чи оргдеталі виїзду?'
                        % (' '.join(fragments)),
                    )
                    self._omni_update_sales_stage_after_reply(partner, channel=channel)
                    return
        if self._omni_is_vague_followup(normalized):
            self._omni_post_bot_message(channel, self._omni_clarify_vague_followup(normalized))
            self._omni_update_sales_stage_after_reply(partner, channel=channel)
            return
        if self._omni_is_short_affirmation(normalized):
            follow = self._omni_next_step_after_affirmation(partner, normalized)
            if follow:
                self._omni_post_bot_message(channel, follow)
                self._omni_update_sales_stage_after_reply(partner, channel=channel)
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
        behavioral_coaching = self.env['omni.sales.intel'].sudo().omni_behavioral_coaching_block()
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
        if behavioral_coaching:
            system_parts.append(behavioral_coaching)
        system_parts.append(self._omni_warm_style_policy())
        system_parts.append(self._omni_reply_language_instruction(normalized, channel=channel))
        system_parts.append(facts)
        system = '\n\n'.join(system_parts)
        system = self._omni_compact_system_prompt(system, ICP)
        user_prompt = self._omni_compact_user_text(text, ICP)

        reply = self._llm_complete(backend, ICP, system, user_prompt)
        if not reply:
            self._omni_send_fallback(channel, partner, ICP)
            return
        reply = self._omni_sales_guard_reply(reply, partner, normalized)
        reply = self._omni_append_next_question(reply, partner, normalized)
        reply = self._omni_apply_reserve_flow(channel, partner, normalized, facts, reply)
        reply = self._omni_finalize_client_reply(reply)
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
            '- Keep concise, helpful, and factual.\n'
            '- No russian words/lexemes; use clean Ukrainian or Polish only.\n'
            '- Write like a real human manager, not a legal document.\n'
            '- Avoid robotic meta-phrases like "у нашій системі", "з емпатією", '
            '"немає конкретних гарантій".\n'
            '- Mobile-first: one short paragraph, no long walls of text.\n'
            '- Sales mode: discover client needs first, not "catalog dump".\n'
            '- Do NOT lead with price in first replies unless client explicitly asks about price.\n'
            '- Present max 1-2 relevant camp options, each with value first, then practical details.\n'
            '- Use clear structure: short intro + bullets + one next-step question.\n'
            '- Ask at most one question per reply.\n'
            '- If more details are needed, continue step-by-step in next turns.'
        )

    def _omni_user_asks_price(self, user_text):
        txt = (user_text or '').lower()
        keys = (
            'ціна', 'ціни', 'скільки', 'вартість', 'коштує',
            'cena', 'koszt', 'ile kosztuje',
            'price', 'cost', 'how much',
        )
        return any(k in txt for k in keys)

    def _omni_contains_ru_lexemes(self, text):
        txt = (' %s ' % ((text or '').lower(),))
        # Frequent ru-only or ru-heavy words we never want in UA/PL replies.
        bad_words = (
            ' спасибо ', ' пожалуйста ', ' ребён', ' ребенок', ' конечно ',
            ' обращени', ' ближайш', ' подключит', ' сейчас у нас ',
        )
        return any(w in txt for w in bad_words)

    def _omni_cleanup_ru_lexemes(self, text):
        out = text or ''
        replacements = {
            'Спасибо': 'Дякуємо',
            'спасибо': 'дякуємо',
            'пожалуйста': 'будь ласка',
            'Пожалуйста': 'Будь ласка',
            'обращение': 'звернення',
            'Обращение': 'Звернення',
            'ребенок': 'дитина',
            'Ребенок': 'Дитина',
            'ребёнок': 'дитина',
            'Ребёнок': 'Дитина',
            'ближайшим': 'найближчим',
            'подключится': 'підключиться',
            'подскажите': 'підкажіть',
            'Подскажите': 'Підкажіть',
            'что': 'що',
            'Что': 'Що',
            'это': 'це',
            'Это': 'Це',
            'если': 'якщо',
            'Если': 'Якщо',
            'ваш': 'ваш',
            'Ваш': 'Ваш',
            'Понята': 'Зрозуміло',
            'понята': 'зрозуміло',
            'Начина': 'Почина',
            'начина': 'почина',
        }
        for src, dst in replacements.items():
            out = out.replace(src, dst)
        return out

    def _omni_has_ru_markers(self, text):
        txt = (' %s ' % ((text or '').lower(),))
        markers = (
            ' спасибо ', ' пожалуйста ', ' обращени', ' ребён', ' ребенок',
            ' ближайш', ' подключит', ' подскаж', ' пожалуйста', ' конечно ',
            ' понята ', ' понятно ', ' понимаю, что вы ',
            ' уточните ', ' это ', ' если ', ' чтобы ', ' который ', ' какая ',
            ' какие ', ' вас интересует ', ' могу предложить ',
        )
        return any(m in txt for m in markers)

    def _omni_strip_price_lines(self, text):
        lines = (text or '').splitlines()
        kept = []
        price_pattern = re.compile(
            r'(\b\d[\d\s]{1,8}\s?(?:pln|uah|eur|€|usd|zł|грн)\b|'
            r'\b(?:ціна|вартість|cena|koszt|price|cost)\b)',
            re.IGNORECASE,
        )
        for ln in lines:
            if price_pattern.search(ln):
                continue
            kept.append(ln)
        return '\n'.join(kept).strip()

    def _omni_sales_guard_reply(self, reply, partner, user_text):
        out = (reply or '').strip()
        if not out:
            return out
        if self._omni_contains_ru_lexemes(out):
            out = self._omni_cleanup_ru_lexemes(out)
        out = self._omni_humanize_sales_tone(out)
        # Premium sales flow: price only after qualification or direct price request.
        is_profile_ready = bool(
            partner and partner.omni_child_age and partner.omni_preferred_period
        )
        if not is_profile_ready and not self._omni_user_asks_price(user_text):
            out = self._omni_strip_price_lines(out) or out
        out = self._omni_cleanup_reply_structure(out)
        out = self._omni_grammar_polish_reply(out)
        return out

    def _omni_humanize_sales_tone(self, text):
        out = text or ''
        replacements = {
            'Я адміністратор та консультант для CampScout.': '',
            'Я адміністратор і консультант для CampScout.': '',
            'Я консультант для CampScout.': '',
            'Я консультант CampScout.': '',
            'Я допомагаю клієнтам знайти': 'Допоможу підібрати',
            'Я допомагаю знайти': 'Допоможу підібрати',
            'Щоб я могла': 'Щоб підібрати',
            'щоб я могла': 'щоб підібрати',
            'Щоб я міг': 'Щоб підібрати',
            'щоб я міг': 'щоб підібрати',
            'Звертаюся до вас з емпатією': 'Розумію ваш запит',
            'звертаюся до вас з емпатією': 'розумію ваш запит',
            'У нашій системі немає конкретних гарантій, які можна надати безпосередньо.': (
                'Безпека дитини для нас у пріоритеті, і це підтверджується стандартами табору.'
            ),
            'у нашій системі немає конкретних гарантій, які можна надати безпосередньо.': (
                'безпека дитини для нас у пріоритеті, і це підтверджується стандартами табору.'
            ),
            'Однак ми маємо кілька важливих погоджень та процедур:': (
                'Ось коротко, як ми забезпечуємо безпеку:'
            ),
            'однак ми маємо кілька важливих погоджень та процедур:': (
                'ось коротко, як ми забезпечуємо безпеку:'
            ),
        }
        for src, dst in replacements.items():
            out = out.replace(src, dst)
        return out.strip()

    def _omni_cleanup_reply_structure(self, text):
        lines = [(ln or '').rstrip() for ln in (text or '').splitlines()]
        cleaned = []
        for idx, ln in enumerate(lines):
            s = ln.strip()
            if not s:
                if cleaned and cleaned[-1]:
                    cleaned.append('')
                continue
            # Remove accidental lonely numbering lines like "2".
            if re.fullmatch(r'\d+[.)]?', s):
                continue
            # Normalize markdown-heavy bullets for chat readability.
            s = s.replace('**', '')
            # Keep simple numeric lists consistent.
            if re.match(r'^\d+\.\s*$', s):
                continue
            if idx == 0 and s.endswith(':') and len(lines) > 1:
                s = s[:-1]
            cleaned.append(s)
        out = '\n'.join(cleaned).strip()
        out = re.sub(r'\n{3,}', '\n\n', out)
        out = self._omni_enforce_single_question(out)
        out = self._omni_enforce_reply_size(out)
        return out

    def _omni_grammar_polish_reply(self, text):
        out = (text or '').strip()
        if not out:
            return out
        # Common typo/wording fixes seen in production dialogs.
        replacements = {
            'Звісно, розумію.': 'Звісно, розумію ваш запит.',
            'Можливо ви': 'Можливо, ви',
            'Якщо потрібно факту': 'Якщо потрібного факту',
            'в нашій системі': 'у нашій системі',
            'ізбране': 'найкраще',
            'Избране': 'Найкраще',
            'подобрать': 'підібрати',
            'Подобрать': 'Підібрати',
            'кліент': 'клієнт',
            'Кліент': 'Клієнт',
            'щоб я могла': 'щоб підібрати',
            'Щоб я могла': 'Щоб підібрати',
            'щоб я міг': 'щоб підібрати',
            'Щоб я міг': 'Щоб підібрати',
            'мені потрібно уточнити': 'уточніть, будь ласка',
            'для бі': '',
            'Понякь': 'Підкажіть',
            'понякь': 'підкажіть',
            'іншее': 'інше',
            'логистику': 'логістику',
            'табор': 'табір',
            '  ': ' ',
        }
        for src, dst in replacements.items():
            out = out.replace(src, dst)
        # Collapse verbose office-style phrasing into short sales-dialog wording.
        out = re.sub(
            r'щоб підібрати[^.!?]{0,120}мені потрібно уточнити',
            'щоб підібрати релевантний варіант, уточніть, будь ласка',
            out,
            flags=re.IGNORECASE,
        )
        # Normalize punctuation/spacing.
        out = re.sub(r'\s+([,.;:!?])', r'\1', out)
        out = re.sub(r'([,.;:!?])([^\s])', r'\1 \2', out)
        out = re.sub(r'[ \t]{2,}', ' ', out)
        out = re.sub(r'\n{3,}', '\n\n', out).strip()
        # Remove role self-intros that make replies robotic or off-brand.
        out = re.sub(
            r'^\s*я\s+(?:адміністратор(?:ка)?\s+та\s+)?консультант(?:ка)?[^.!?]*[.!?]\s*',
            '',
            out,
            flags=re.IGNORECASE,
        )
        # Remove duplicated neighboring words.
        out = re.sub(r'\b([А-Яа-яA-Za-zІіЇїЄєŁłŚśŻżŹźĆćŃńÓóĘęĄą]{2,})\s+\1\b', r'\1', out, flags=re.IGNORECASE)
        return out.strip()

    def _omni_finalize_client_reply(self, text):
        out = (text or '').strip()
        if not out:
            return out
        out = self._omni_cleanup_reply_structure(out)
        out = self._omni_grammar_polish_reply(out)
        out = self._omni_cleanup_ru_lexemes(out)
        if self._omni_has_ru_markers(out):
            # Deterministic hard-stop: never send mixed/ru-looking phrasing to client.
            out = 'Підкажіть, що для вас зараз найважливіше: програма, дати, доїзд чи безпека?'
        # Keep max 2 short sentences in final client-facing message.
        parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+', out) if p.strip()]
        if len(parts) > 2:
            out = ' '.join(parts[:2]).strip()
        out = self._omni_enforce_single_question(out)
        out = self._omni_enforce_reply_size(out)
        return out.strip()

    def _omni_enforce_single_question(self, text):
        out = (text or '').strip()
        if not out:
            return out
        first_q = out.find('?')
        if first_q < 0:
            return out
        head = out[: first_q + 1]
        tail = out[first_q + 1 :].replace('?', '.')
        tail = re.sub(r'\.{2,}', '.', tail)
        return (head + tail).strip()

    def _omni_enforce_reply_size(self, text):
        out = (text or '').strip()
        if not out:
            return out
        icp = self.env['ir.config_parameter'].sudo()
        try:
            max_chars = int(icp.get_param('omnichannel_bridge.reply_max_chars', '260'))
        except Exception:
            max_chars = 260
        max_chars = max(140, min(max_chars, 700))
        if len(out) <= max_chars:
            return out
        cut = out.rfind('\n', 0, max_chars + 1)
        if cut < int(max_chars * 0.55):
            cut = out.rfind('. ', 0, max_chars + 1)
            if cut != -1:
                cut += 1
        if cut < int(max_chars * 0.45):
            cut = max_chars
        # Never cut in the middle of a word when hard-limiting reply length.
        if cut < len(out):
            ws_cut = out.rfind(' ', 0, cut + 1)
            if ws_cut >= int(max_chars * 0.45):
                cut = ws_cut
        compact = out[:cut].strip().rstrip(',:;')
        # Drop dangling 1-2 character tail tokens like "бі", "з", "і".
        compact = re.sub(r'\s+[^\s]{1,2}$', '', compact).strip()
        if not compact.endswith(('.', '!', '?')):
            compact += '.'
        return compact

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
        channel = channel.sudo()
        # Anti-flood: fallback should be sent at most once per cooldown window.
        # Default is 15 minutes to avoid repeated "assistant unavailable" spam.
        raw_cd = (icp.get_param('omnichannel_bridge.fallback_cooldown_seconds') or '').strip()
        try:
            cooldown_sec = max(60, int(raw_cd or 900))
        except Exception:
            cooldown_sec = 900
        # Row-level lock removes concurrent duplicate fallbacks when two webhooks
        # are processed in parallel for the same thread.
        self.env.cr.execute(
            "SELECT omni_last_bot_reply_at FROM discuss_channel WHERE id=%s FOR UPDATE",
            [channel.id],
        )
        row = self.env.cr.fetchone() or [False]
        last_bot_reply_at = row[0]
        if last_bot_reply_at and Datetime.now() <= last_bot_reply_at + timedelta(seconds=cooldown_sec):
            return
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
        if channel._omni_is_website_livechat_channel():
            # Compact legal block for livechat to avoid multi-bubble URL fragmentation.
            return (
                '%(consent)s\n'
                'Політики: %(privacy)s | %(terms)s | %(cookie)s | %(child)s'
            ) % {
                'consent': consent_line,
                'privacy': privacy_url,
                'terms': terms_url,
                'cookie': cookie_url,
                'child': child_url,
            }
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

    def _omni_max_message_len(self, channel):
        channel = channel.sudo()
        provider = channel.omni_provider or 'site_livechat'
        # Operational caps are intentionally far below platform hard limits.
        # Goal: readable mobile bubbles across channels.
        if provider in ('meta', 'whatsapp', 'twilio_whatsapp', 'viber'):
            return 320
        if provider == 'telegram':
            return 500
        return 360

    def _omni_split_mobile_chunks(self, text, max_len):
        txt = re.sub(r'\s+\n', '\n', re.sub(r'\n\s+', '\n', (text or '').strip()))
        if len(txt) <= max_len:
            return [txt] if txt else []
        chunks = []
        remaining = txt
        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining.strip())
                break
            cut = remaining.rfind('\n', 0, max_len + 1)
            if cut < int(max_len * 0.55):
                cut = remaining.rfind('. ', 0, max_len + 1)
                if cut != -1:
                    cut += 1
            if cut < int(max_len * 0.45):
                cut = max_len
            # Prefer word boundary for last-resort split as well.
            if cut < len(remaining):
                ws_cut = remaining.rfind(' ', 0, cut + 1)
                if ws_cut >= int(max_len * 0.45):
                    cut = ws_cut
            piece = remaining[:cut].strip()
            if piece:
                chunks.append(piece)
            remaining = remaining[cut:].strip()
        return [c for c in chunks if c]

    def _omni_post_bot_message(self, channel, body):
        channel = channel.sudo()
        bot_partner = self._omni_resolve_bot_partner()
        legal = self._omni_legal_notice_block(channel)
        final_body = self._omni_finalize_client_reply((body or '').strip())
        if not final_body:
            final_body = 'Підкажіть, що для вас зараз найважливіше: програма, дати, доїзд чи безпека?'
        if channel._omni_is_website_livechat_channel() and not final_body.startswith('🤖'):
            final_body = '🤖 %s' % final_body
        if legal and not channel.omni_legal_notice_sent_at:
            final_body = '%s\n\n%s' % (final_body, legal)
        max_len = self._omni_max_message_len(channel)
        chunks = self._omni_split_mobile_chunks(final_body, max_len=max_len)
        if not chunks:
            return
        is_livechat = channel._omni_is_website_livechat_channel()
        if is_livechat:
            # Tiny delay makes bot responses feel natural instead of instant packet bursts.
            time.sleep(0.9)
        for idx, chunk in enumerate(chunks):
            channel.with_context(omni_skip_livechat_inbound=True).message_post(
                body=chunk,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=bot_partner.id,
            )
            if is_livechat and idx < (len(chunks) - 1):
                time.sleep(0.55)
        channel.write({'omni_last_bot_reply_at': Datetime.now()})
        if legal and not channel.omni_legal_notice_sent_at:
            channel.write({'omni_legal_notice_sent_at': Datetime.now()})

    def _omni_resolve_bot_partner(self):
        """Use stable bot identity, not admin profile."""
        icp = self.env['ir.config_parameter'].sudo()
        pid_raw = icp.get_param('omnichannel_bridge.bot_partner_id', '')
        pid = int(pid_raw) if str(pid_raw).isdigit() else 0
        partner = self.env['res.partner'].sudo().browse(pid) if pid else self.env['res.partner']
        if not partner or not partner.exists():
            partner = self.env['res.partner'].sudo().search([('name', 'ilike', 'OdooBot')], limit=1)
        if not partner or not partner.exists():
            partner = self.env.ref('base.partner_root')
        icp.set_param('omnichannel_bridge.bot_partner_id', str(partner.id))
        return partner

    def _omni_is_weather_message(self, user_text):
        txt = (user_text or '').lower()
        if not txt:
            return False
        weather_keys = (
            'погод',
            'погода',
            'дощ',
            'дощить',
            'сонячно',
            'спека',
            'холодно',
            'weather',
            'forecast',
            'rain',
            'sunny',
            'pogoda',
            'deszcz',
        )
        return any(k in txt for k in weather_keys)

    def _omni_weather_to_camp_reply(self, user_text):
        is_pl = self._omni_is_polish_message(user_text or '')
        if is_pl:
            return (
                'Pogoda jest ważna przy wyborze obozu — dobieramy program i wyposażenie do warunków, '
                'aby dziecku było komfortowo i bezpiecznie.\n\n'
                'Proszę podać wiek dziecka, a zaproponuję najlepszy format obozu.'
            )
        return (
            'Сьогодні погода — якраз привід обрати табір правильно: підбираємо програму та формат так, '
            'щоб дитині було комфортно і безпечно за будь-яких умов.\n\n'
            'Підкажіть вік дитини, і я запропоную найкращі варіанти табору.'
        )

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

    def _omni_is_paid_or_booked_message(self, user_text):
        txt = (user_text or '').strip().lower()
        if not txt:
            return False
        keys = (
            'вже оплат', 'оплатив', 'оплатила', 'оплачено', 'сплатив', 'сплатила',
            'вже заброн', 'забронював', 'забронювала', 'бронював', 'бронювала',
            'вже купив', 'вже купила', 'вже купили', 'купив табір', 'купила табір', 'купили табір',
            'придбав', 'придбала', 'кпив',
            'already paid', 'already booked', 'i paid', 'i booked',
            'już opłaci', 'opłacone', 'już zarezerw', 'zarezerwowa',
            'faktura', 'invoice',
        )
        return any(k in txt for k in keys)

    def _omni_extract_booking_facts_from_memory(self, partner):
        import re
        if not partner:
            return {}
        mem = (partner.omni_chat_memory or '').strip()
        if not mem:
            return {}
        facts = {}
        for key in ('booking_identity_email', 'booking_ref', 'camp', 'invoice', 'invoice_state', 'event'):
            matches = re.findall(r'%s:([^;\n]+)' % key, mem, flags=re.IGNORECASE)
            if matches:
                facts[key] = (matches[-1] or '').strip()
        return facts

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

    def _omni_is_vague_followup(self, user_text):
        txt = re.sub(r'\s+', ' ', (user_text or '').strip().lower())
        if not txt:
            return False
        vague_phrases = (
            'щось інше',
            'інше',
            'далі',
            'ще',
            'що ще',
            'шо ше',
            'something else',
            'other',
            'coś innego',
            'inne',
        )
        if txt in vague_phrases:
            return True
        if len(txt) <= 14 and any(p in txt for p in vague_phrases):
            return True
        return False

    def _omni_clarify_vague_followup(self, user_text):
        if self._omni_is_polish_message(user_text or ''):
            return 'Co dokładnie jest dla Państwa najważniejsze: program, terminy, dojazd czy bezpieczeństwo?'
        return 'Що саме для вас важливіше зараз: програма, дати, доїзд чи безпека?'

    def _omni_is_short_affirmation(self, user_text):
        txt = re.sub(r'\s+', ' ', (user_text or '').strip().lower())
        if not txt:
            return False
        return bool(re.match(r'^(так|ок|добре|ага|yes|ok|yep|tak|dobrze)\b[.!?]*$', txt))

    def _omni_next_step_after_affirmation(self, partner, user_text):
        if not partner:
            return (
                'Дякую. Що для вас зараз важливіше: програма, дати, доїзд чи бюджет?'
                if not self._omni_is_polish_message(user_text or '')
                else
                'Dziękuję. Co jest teraz najważniejsze: program, terminy, dojazd czy budżet?'
            )
        is_pl = self._omni_is_polish_message(user_text or '')
        next_q = self._omni_pick_next_question(partner, user_text)
        if next_q:
            return (
                'Дякую, рухаємось далі. %s' % next_q
                if not is_pl else
                'Dziękuję, idziemy dalej. %s' % next_q
            )
        return (
            'Дякую. Уже маю базові дані, тож підберу 1-2 найрелевантніші варіанти табору.'
            if not is_pl else
            'Dziękuję. Mam już podstawowe dane, więc dobiorę 1-2 najbardziej trafne obozy.'
        )

    def _omni_moderation_policy_hit(self, user_text):
        txt = (user_text or '').lower().strip()
        if not txt:
            return {}
        rules = self.env['omni.moderation.rule'].sudo().search([('active', '=', True)], order='priority asc, id asc')
        for rule in rules:
            key = (rule.keyword or '').strip().lower()
            if key and key in txt:
                return {'keyword': key, 'action': (rule.action or 'escalate').strip(), 'source': 'rule'}
        icp = self.env['ir.config_parameter'].sudo()
        raw = (icp.get_param('omnichannel_bridge.moderation_keywords', '') or '').strip()
        if not raw:
            return {}
        keys = [k.strip().lower() for k in raw.split(',') if k and k.strip()]
        for key in keys:
            if key and key in txt:
                action = (icp.get_param('omnichannel_bridge.moderation_action', 'escalate') or 'escalate').strip()
                return {'keyword': key, 'action': action, 'source': 'settings'}
        return {}

    def _omni_apply_moderation_action(self, channel, partner, user_text, policy_hit):
        action = (policy_hit.get('action') or 'escalate').strip()
        hit_keyword = (policy_hit.get('keyword') or 'unknown').strip()
        source = (policy_hit.get('source') or 'unknown').strip()
        note = 'moderation_policy_hit:%s:%s' % (source, hit_keyword)
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
                (icp.get_param('omnichannel_bridge.openai_base_url') or 'https://api.openai.com/v1').strip(),
                system_prompt,
                user_text,
                icp=icp,
            )
        if backend == 'ollama':
            if not self._omni_ollama_cb_allows(icp):
                _logger.warning('Ollama circuit breaker open: skipping LLM call')
                return ''
            base = (icp.get_param('omnichannel_bridge.ollama_base_url') or 'http://127.0.0.1:11434').strip()
            model = (icp.get_param('omnichannel_bridge.ollama_model') or 'llama3.2').strip()
            try:
                text = self._ollama_chat_completion(base, model, system_prompt, user_text)
            except req_exc.Timeout:
                self._omni_ollama_cb_mark_failure(icp, 'timeout')
                return ''
            except Exception:
                self._omni_ollama_cb_mark_failure(icp, 'error')
                return ''
            if text:
                self._omni_ollama_cb_mark_success(icp)
                return text
            self._omni_ollama_cb_mark_failure(icp, 'empty')
            return ''
        return ''

    def _openai_chat_completion(self, api_key, model, base_url, system_prompt, user_text, icp=None):
        if not api_key:
            return ''
        base = (base_url or 'https://api.openai.com/v1').strip().rstrip('/')
        url = '%s/chat/completions' % base
        icp = icp or self.env['ir.config_parameter'].sudo()
        try:
            connect_timeout = max(2, int(icp.get_param('omnichannel_bridge.openai_connect_timeout_seconds', '5')))
        except Exception:
            connect_timeout = 5
        try:
            read_timeout = max(10, int(icp.get_param('omnichannel_bridge.openai_read_timeout_seconds', '30')))
        except Exception:
            read_timeout = 30
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
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=(connect_timeout, read_timeout))
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
        icp = self.env['ir.config_parameter'].sudo()
        try:
            connect_timeout = max(2, int(icp.get_param('omnichannel_bridge.ollama_connect_timeout_seconds', '5')))
        except Exception:
            connect_timeout = 5
        try:
            read_timeout = max(15, int(icp.get_param('omnichannel_bridge.ollama_read_timeout_seconds', '60')))
        except Exception:
            read_timeout = 60
        try:
            num_predict = int(icp.get_param('omnichannel_bridge.ollama_num_predict', '160'))
        except Exception:
            num_predict = 160
        num_predict = max(64, min(400, num_predict))
        keep_alive = (icp.get_param('omnichannel_bridge.ollama_keep_alive', '30m') or '30m').strip()
        openai_url = '%s/v1/chat/completions' % base
        payload_oa = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_text},
            ],
            'temperature': 0.15,
            'stream': False,
            'max_tokens': num_predict,
            'keep_alive': keep_alive,
        }
        try:
            resp = requests.post(openai_url, json=payload_oa, timeout=(connect_timeout, read_timeout))
            if resp.ok:
                data = resp.json()
                return (data.get('choices') or [{}])[0].get('message', {}).get('content', '').strip()
        except req_exc.Timeout:
            _logger.warning('Ollama /v1/chat/completions timeout')
            raise
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
            'keep_alive': keep_alive,
            'options': {'temperature': 0.15, 'num_predict': num_predict},
        }
        try:
            resp = requests.post(native_url, json=payload_native, timeout=(connect_timeout, read_timeout))
            if not resp.ok:
                _logger.error('Ollama error %s: %s', resp.status_code, resp.text)
                return ''
            data = resp.json()
            return (data.get('message') or {}).get('content', '').strip()
        except req_exc.Timeout:
            _logger.warning('Ollama /api/chat timeout')
            raise
        except Exception:
            _logger.exception('Ollama request failed')
            raise

    def _omni_compact_system_prompt(self, text, icp):
        txt = (text or '').strip()
        try:
            max_chars = int(icp.get_param('omnichannel_bridge.ollama_max_system_chars', '9000'))
        except Exception:
            max_chars = 9000
        max_chars = max(2000, min(20000, max_chars))
        return txt if len(txt) <= max_chars else txt[:max_chars]

    def _omni_compact_user_text(self, text, icp):
        txt = re.sub(r'\s+', ' ', (text or '').strip())
        try:
            max_chars = int(icp.get_param('omnichannel_bridge.ollama_max_user_chars', '1200'))
        except Exception:
            max_chars = 1200
        max_chars = max(200, min(4000, max_chars))
        return txt if len(txt) <= max_chars else txt[:max_chars]

    def _omni_ollama_cb_allows(self, icp):
        open_until_raw = (icp.get_param('omnichannel_bridge.ollama_cb_open_until') or '').strip()
        if not open_until_raw:
            return True
        try:
            open_until = Datetime.from_string(open_until_raw)
        except Exception:
            icp.set_param('omnichannel_bridge.ollama_cb_open_until', '')
            return True
        return Datetime.now() >= open_until

    def _omni_ollama_cb_mark_success(self, icp):
        icp.set_param('omnichannel_bridge.ollama_cb_fail_count', '0')
        icp.set_param('omnichannel_bridge.ollama_cb_open_until', '')

    def _omni_ollama_cb_mark_failure(self, icp, reason):
        try:
            threshold = int(icp.get_param('omnichannel_bridge.ollama_cb_fail_threshold', '3'))
        except Exception:
            threshold = 3
        try:
            cooldown_seconds = int(icp.get_param('omnichannel_bridge.ollama_cb_cooldown_seconds', '180'))
        except Exception:
            cooldown_seconds = 180
        threshold = max(1, min(20, threshold))
        cooldown_seconds = max(30, min(3600, cooldown_seconds))
        try:
            fail_count = int(icp.get_param('omnichannel_bridge.ollama_cb_fail_count', '0'))
        except Exception:
            fail_count = 0
        fail_count += 1
        if fail_count >= threshold:
            open_until = Datetime.now() + timedelta(seconds=cooldown_seconds)
            icp.set_param('omnichannel_bridge.ollama_cb_open_until', Datetime.to_string(open_until))
            icp.set_param('omnichannel_bridge.ollama_cb_fail_count', '0')
            _logger.warning(
                'Ollama circuit breaker opened for %ss (reason=%s)',
                cooldown_seconds,
                reason,
            )
            return
        icp.set_param('omnichannel_bridge.ollama_cb_fail_count', str(fail_count))

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
        mem = (partner.omni_chat_memory or '').lower()
        has_age = bool(partner.omni_child_age) or ('age:' in mem) or self._omni_text_has_age(user_text)
        has_period = bool(partner.omni_preferred_period) or ('period:' in mem) or self._omni_text_has_period(user_text)
        has_city = bool(partner.omni_departure_city) or ('city:' in mem) or self._omni_text_has_departure_city(user_text)
        has_budget = bool(partner.omni_budget_amount) or ('budget:' in mem) or self._omni_text_has_budget(user_text)
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
        if age and (not partner.omni_child_age or int(partner.omni_child_age) != int(age)):
            vals['omni_child_age'] = age
        period = self._omni_extract_period(txt)
        if period and ((partner.omni_preferred_period or '').strip().lower() != period.strip().lower()):
            vals['omni_preferred_period'] = period
        city = self._omni_extract_departure_city(txt)
        if city and ((partner.omni_departure_city or '').strip().lower() != city.strip().lower()):
            vals['omni_departure_city'] = city
        budget_amount, budget_currency = self._omni_extract_budget(txt)
        if budget_amount and (
            not partner.omni_budget_amount
            or float(partner.omni_budget_amount or 0.0) != float(budget_amount)
            or (budget_currency and (partner.omni_budget_currency or '').lower() != budget_currency.lower())
        ):
            vals['omni_budget_amount'] = budget_amount
            if budget_currency:
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
