# -*- coding: utf-8 -*-
import re
from collections import Counter
from datetime import timedelta

from odoo import _, api, fields, models

FOMO_THRESHOLD = 5


class OmniSalesIntel(models.AbstractModel):
    _name = 'omni.sales.intel'
    _description = 'Sales psychology helpers (FOMO, catalog hints)'

    # Ключові слова для детекції запиту менеджера (UA/PL/EN)
    _ESCALATION_KEYWORDS = [
        'менеджер', 'оператор', 'людина', 'живий', 'зателефонуй', 'передай',
        'manager', 'operator', 'human', 'agent', 'call me', 'speak to',
        'proszę człowieka', 'proszę managera', 'zadzwoń',
    ]
    _OBJECTION_KEYWORDS = {
        'price': (
            'дорого', 'ціна висока', 'ціна', 'бюджет', 'не по кишені',
            'za drogo', 'cena', 'budżet', 'too expensive', 'price',
        ),
        'timing': (
            'пізніше', 'потім', 'не зараз', 'після відпустки', 'подумаю пізніше',
            'później', 'nie teraz', 'po wakacjach', 'later', 'not now',
        ),
        'trust': (
            'не знаю вас', 'довіра', 'боюсь', 'шахрай', 'обман',
            'nie znam was', 'zaufanie', 'boję się', 'scam', 'fraud',
        ),
        'need_to_think': (
            'треба подумати', 'я подумаю', 'порадитись', 'подумаємо',
            'muszę pomyśleć', 'muszę się zastanowić', 'i need to think',
        ),
        'competitor': (
            'конкурент', 'в іншому таборі', 'інший табір дешевше',
            'konkurencja', 'u konkurencji', 'competitor',
        ),
        'not_decision_maker': (
            'вирішує чоловік', 'вирішує дружина', 'вирішують батьки', 'не я вирішую',
            'decyduje mąż', 'decyduje żona', 'nie ja decyduję', 'not my decision',
        ),
    }
    _PURCHASE_INTENT_KEYWORDS = (
        'хочу купити', 'хочу оплатити', 'готовий оплатити', 'готова оплатити',
        'як оплатити', 'куди платити', 'хочу бронювати', 'хочу забронювати',
        'оформляю', 'оформити', 'реєструюсь', 'готові до оплати',
        'chcę kupić', 'chcę zapłacić', 'jak zapłacić', 'chcę zarezerwować',
        'rejestruję', 'jestem gotów zapłacić',
        'i want to buy', 'ready to pay', 'how do i pay', 'book now',
    )
    _CONFLICT_KEYWORDS = (
        'конфлікт', 'скарга', 'непорозум', 'agres', 'complaint', 'problem with manager',
    )
    _TECH_PROBLEM_KEYWORDS = (
        'не працює', 'помилка', 'error', 'bug', 'site down', 'оплата не проходить',
        'купон не працює', 'реєстрація не працює',
    )

    @api.model
    def omni_apply_inbound_triggers(self, channel, partner, text, provider):
        fomo_line = self._omni_build_fomo_line_from_message(text)
        if fomo_line:
            channel.sudo().message_post(
                body=fomo_line,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            self._omni_notify_fomo_hot_lead(channel, partner, fomo_line)

        # Детекція запиту ескалації
        if self._omni_detect_escalation(text):
            self.env['omni.notify'].sudo().notify_escalation(
                channel=channel,
                partner=partner,
                reason=_('Клієнт запитав менеджера: "%s"') % text[:120],
            )
        objection = self.omni_detect_objection_type(text)
        if objection:
            self._omni_log_objection(channel, partner, objection)
        if self._omni_detect_purchase_intent(text):
            self._omni_log_purchase_intent(channel, partner, text)
            self._omni_mark_handoff_stage(channel, partner, 'purchase_intent')
        if self._omni_detect_conflict_or_human_request(text):
            self.env['omni.notify'].sudo().notify_problematic(
                channel=channel,
                partner=partner,
                note='conflict_or_human_request',
            )
        if self._omni_detect_technical_problem(text):
            self.env['omni.notify'].sudo().notify_problematic(
                channel=channel,
                partner=partner,
                note='technical_problem',
            )
        if partner:
            partner.sudo().omni_recompute_lead_score(reason='sales_intel_triggers')

    @api.model
    def _omni_detect_escalation(self, text):
        if not text:
            return False
        text_lower = text.lower()
        return any(kw in text_lower for kw in self._ESCALATION_KEYWORDS)

    @api.model
    def _omni_detect_purchase_intent(self, text):
        txt = (text or '').lower()
        if not txt:
            return False
        return any(k in txt for k in self._PURCHASE_INTENT_KEYWORDS)

    @api.model
    def _omni_detect_conflict_or_human_request(self, text):
        txt = (text or '').lower()
        if not txt:
            return False
        human_keys = ('менеджер', 'оператор', 'людина', 'human', 'manager')
        return any(k in txt for k in self._CONFLICT_KEYWORDS) or any(k in txt for k in human_keys)

    @api.model
    def _omni_detect_technical_problem(self, text):
        txt = (text or '').lower()
        if not txt:
            return False
        return any(k in txt for k in self._TECH_PROBLEM_KEYWORDS)

    @api.model
    def omni_detect_objection_type(self, text):
        txt = (text or '').lower()
        if not txt:
            return ''
        scored = []
        tokens = [t for t in re.split(r'[^a-zA-Zа-яА-ЯіІїЇєЄ0-9]+', txt) if len(t) >= 3]
        for objection_type, keys in self._OBJECTION_KEYWORDS.items():
            phrase_hits = sum(2 for k in keys if k in txt)
            token_hits = sum(1 for t in tokens if any(t in k or k in t for k in keys))
            score = phrase_hits + token_hits
            if score > 0:
                scored.append((score, objection_type))
        if scored:
            scored.sort(reverse=True)
            return scored[0][1]
        return ''

    @api.model
    def omni_objection_guidance_block(self, text):
        """Short, controlled playbook line for current user message."""
        objection_type = self.omni_detect_objection_type(text)
        if not objection_type:
            return ''
        templates = self._omni_objection_playbook_templates()
        return templates.get(objection_type, '')

    @api.model
    def omni_objection_next_step_block(self, text):
        objection_type = self.omni_detect_objection_type(text)
        if not objection_type:
            return ''
        prompts = {
            'price': 'OBJECTION_NEXT_STEP: Ask for acceptable budget corridor and offer one best-fit camp option.',
            'timing': 'OBJECTION_NEXT_STEP: Ask preferred reconnect time and offer a manager callback slot.',
            'trust': 'OBJECTION_NEXT_STEP: Provide one verifiable source link and ask if manager handoff is needed.',
            'need_to_think': 'OBJECTION_NEXT_STEP: Ask one blocking question and offer low-pressure follow-up.',
            'competitor': 'OBJECTION_NEXT_STEP: Ask one comparison criterion and answer only with ORM facts.',
            'not_decision_maker': 'OBJECTION_NEXT_STEP: Ask who decides and offer convenient manager contact format.',
        }
        return prompts.get(objection_type, '')

    @api.model
    def omni_pain_script_block(self):
        script = (
            self.env['ir.config_parameter'].sudo().get_param('omnichannel_bridge.pain_script', '') or ''
        ).strip()
        if script:
            return 'PAIN_SCRIPT:\n%s' % script
        return (
            'PAIN_SCRIPT:\n'
            '- Ask one blocker question (budget/timing/logistics/safety).\n'
            '- Reflect client concern with empathy.\n'
            '- Resolve only with ORM-confirmed facts and propose one next step.'
        )

    @api.model
    def omni_upsell_script_block(self):
        script = (
            self.env['ir.config_parameter'].sudo().get_param('omnichannel_bridge.upsell_script', '') or ''
        ).strip()
        if script:
            return 'UPSELL_SCRIPT:\n%s' % script
        return (
            'UPSELL_SCRIPT:\n'
            '- Offer at most one relevant add-on/upgrade after core fit is confirmed.\n'
            '- Keep non-aggressive wording and provide manager help option.'
        )

    @api.model
    def omni_behavioral_coaching_block(self, lookback_days=28):
        """Inject recent sales-psychology signals into AI prompt."""
        if 'omni.conversation.audit' not in self.env:
            return ''
        cutoff = fields.Datetime.now() - timedelta(days=max(1, int(lookback_days or 28)))
        audits = self.env['omni.conversation.audit'].sudo().search(
            [('run_at', '>=', cutoff)],
            order='run_at desc',
            limit=8,
        )
        if not audits:
            return ''

        behavior_counts = Counter()
        manager_error_counts = Counter()
        silence_counts = Counter()
        for audit in audits:
            for line in audit.line_ids:
                if line.section == 'behavior':
                    behavior_counts[line.key] += line.count
                elif line.section == 'manager_error':
                    manager_error_counts[line.key] += line.count
                elif line.section == 'silence':
                    silence_counts[line.key] += line.count

        if not behavior_counts and not manager_error_counts and not silence_counts:
            return ''

        playbook = {
            'price_expensive': '- If price objection appears: ask budget corridor and offer one best-fit option.',
            'think_later': '- If client says "later": set a gentle follow-up checkpoint and ask one blocker question.',
            'self_followup': '- If client says "I will write myself": confirm and schedule one light reminder only.',
            'need_family_consult': '- If family approval is needed: give a concise 3-point summary for forwarding.',
            'ask_children_first': '- If child decision pending: ask when to reconnect and keep message pressure-free.',
            'distance_far': '- If distance/logistics concern: answer transport plan first, before upsell topics.',
            'silence_wording': '- If "not now/not relevant": respect pause and avoid aggressive next-step push.',
        }
        lines = ['BEHAVIORAL_COACHING (recent real dialogs):']
        for key, count in behavior_counts.most_common(5):
            guidance = playbook.get(key, '- %s: keep reply concise and propose one clear next step.' % key)
            lines.append('%s [seen %s]' % (guidance, count))
        if manager_error_counts:
            lines.append(
                '- Manager errors observed (%s): AI should bridge with clear interim guidance and handoff CTA.'
                % sum(manager_error_counts.values())
            )
        if silence_counts:
            lines.append(
                '- Silence patterns observed (%s): end replies with one simple CTA and low-friction follow-up option.'
                % sum(silence_counts.values())
            )
        return '\n'.join(lines)

    @api.model
    def _omni_notify_fomo_hot_lead(self, channel, partner, fomo_line):
        if not channel:
            return
        icp = self.env['ir.config_parameter'].sudo()
        enabled = str(icp.get_param('omnichannel_bridge.fomo_internal_notify', 'True')).lower() in ('1', 'true', 'yes')
        if not enabled:
            return
        now = fields.Datetime.now()
        if hasattr(channel, '_omni_marketing_touch_allowed') and not channel._omni_marketing_touch_allowed(
            channel, 'fomo', now, icp,
        ):
            return
        channel.sudo().write({
            'omni_last_fomo_notify_at': now,
            'omni_last_marketing_touch_at': now,
            'omni_last_marketing_touch_type': 'fomo',
        })
        self.env['omni.notify'].sudo().notify_problematic(
            channel=channel,
            partner=partner,
            note='fomo_hot_lead: %s' % (fomo_line[:180] if fomo_line else 'low_availability'),
        )

    @api.model
    def _omni_objection_playbook_templates(self):
        defaults = {
            'price': (
                'OBJECTION_PLAYBOOK: type=price. '
                'UA: Спочатку емпатія ("Розумію, бюджет важливий"), далі лише факти з ORM '
                '(що входить у вартість, розстрочка якщо є), потім 1 уточнення про комфортний бюджет. '
                'PL: Najpierw empatia, potem tylko fakty z ORM (co zawiera cena, raty jeśli dostępne), '
                'na końcu 1 pytanie o komfortowy budżet.'
            ),
            'timing': (
                'OBJECTION_PLAYBOOK: type=timing. '
                'UA: Повага до таймінгу, без тиску; запропонувати 1 легкий next step '
                '(коли зручно повернутись / зворотний звʼязок менеджера). '
                'PL: Uszanuj timing klienta, bez presji; zaproponuj 1 lekki kolejny krok '
                '(kiedy wrócić / kontakt managera).'
            ),
            'trust': (
                'OBJECTION_PLAYBOOK: type=trust. '
                'UA: Тільки перевірні факти й посилання (ліцензія, оферта, політики), без непідтверджених обіцянок; '
                'запропонувати підключення менеджера. '
                'PL: Tylko weryfikowalne fakty i linki (licencja, umowa/oferta, polityki), bez obietnic; '
                'zaproponuj przekazanie do managera.'
            ),
            'need_to_think': (
                'OBJECTION_PLAYBOOK: type=need_to_think. '
                'UA: Уточнити, що саме заважає рішенню; закрити 1 конкретний сумнів фактами з ORM; '
                'за потреби передати менеджеру. '
                'PL: Doprecyzuj, co dokładnie blokuje decyzję; odpowiedz na 1 konkretną wątpliwość faktami z ORM; '
                'w razie potrzeby przekaż do managera.'
            ),
            'competitor': (
                'OBJECTION_PLAYBOOK: type=competitor. '
                'UA: Не знецінювати конкурентів; порівнювати лише складники власної пропозиції з ORM/легальних лінків; '
                'поставити 1 кваліфікаційне запитання. '
                'PL: Nie krytykuj konkurencji; porównuj tylko elementy własnej oferty z ORM/linków prawnych; '
                'zadaj 1 pytanie kwalifikujące.'
            ),
            'not_decision_maker': (
                'OBJECTION_PLAYBOOK: type=not_decision_maker. '
                'UA: Уточнити, хто приймає рішення, і запропонувати зручний формат підключення '
                '(дзвінок/чат/повідомлення менеджера). '
                'PL: Ustal, kto podejmuje decyzję, i zaproponuj wygodny format kontaktu '
                '(telefon/czat/wiadomość od managera).'
            ),
        }
        ICP = self.env['ir.config_parameter'].sudo()
        overrides = {
            'price': (ICP.get_param('omnichannel_bridge.objection_playbook_price') or '').strip(),
            'timing': (ICP.get_param('omnichannel_bridge.objection_playbook_timing') or '').strip(),
            'trust': (ICP.get_param('omnichannel_bridge.objection_playbook_trust') or '').strip(),
            'need_to_think': (
                ICP.get_param('omnichannel_bridge.objection_playbook_need_to_think') or ''
            ).strip(),
            'competitor': (ICP.get_param('omnichannel_bridge.objection_playbook_competitor') or '').strip(),
            'not_decision_maker': (
                ICP.get_param('omnichannel_bridge.objection_playbook_not_decision_maker') or ''
            ).strip(),
        }
        templates = {k: (overrides.get(k) or v) for k, v in defaults.items()}
        policies = self.env['omni.objection.policy'].sudo().search([('active', '=', True)], order='id desc')
        for p in policies:
            if p.objection_type and p.body:
                templates[p.objection_type] = p.body.strip()
        return templates

    @api.model
    def _omni_log_objection(self, channel, partner, objection_type):
        if not objection_type:
            return
        if partner:
            partner = partner.sudo()
            memory = self.env['omni.memory'].sudo()
            memory._omni_append_chat_memory(partner, 'objection:%s' % objection_type)
        if channel:
            self._omni_tag_latest_customer_message(
                channel,
                ['omni:objection', 'objection:%s' % objection_type],
            )

    @api.model
    def _omni_log_purchase_intent(self, channel, partner, text):
        if channel:
            channel.sudo().with_context(omni_skip_livechat_inbound=True).message_post(
                body='[auto] purchase_intent_detected',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            self._omni_tag_latest_customer_message(
                channel,
                ['omni:purchase_intent'],
            )
        if partner:
            self.env['omni.notify'].sudo().notify_purchase_intent(
                channel=channel,
                partner=partner,
                user_text=text or '',
            )

    @api.model
    def _omni_mark_handoff_stage(self, channel, partner, reason=''):
        if not partner:
            return
        partner = partner.sudo()
        old_stage, new_stage, changed = partner.omni_set_sales_stage(
            'handoff',
            channel=channel,
            reason=reason or 'purchase_intent',
            source='omni_sales_intel',
        )
        if not changed:
            return
        if channel:
            self._omni_tag_latest_customer_message(channel, ['omni:handoff'])
            self.env['omni.notify'].sudo().notify_stage_change(
                channel=channel,
                partner=partner,
                old_stage=old_stage,
                new_stage=new_stage,
                reason=reason or 'purchase_intent',
            )

    @api.model
    def _omni_tag_latest_customer_message(self, channel, tags):
        if not channel:
            return
        channel = channel.sudo()
        customer = channel.omni_customer_partner_id
        if not customer:
            return
        msg = self.env['mail.message'].sudo().search(
            [
                ('model', '=', 'discuss.channel'),
                ('res_id', '=', channel.id),
                ('author_id', '=', customer.id),
                ('message_type', '=', 'comment'),
            ],
            order='id desc',
            limit=1,
        )
        if msg:
            msg.omni_attach_tags(tags)

    @api.model
    def _omni_build_fomo_line_from_message(self, text):
        """If message references a product by name, check stock / places and return hint."""
        if not text:
            return ''
        cleaned_text = re.sub(r'<[^>]+>', ' ', text)
        cleaned_text = re.sub(r'&[a-zA-Z#0-9]+;', ' ', cleaned_text)
        Product = self.env['product.product'].sudo()
        tokens = [t for t in re.split(r'\s+', cleaned_text.strip()) if len(t) > 2]
        terms = tokens[:5]
        if not terms:
            return ''
        if len(terms) == 1:
            domain = [('name', 'ilike', terms[0])]
        else:
            domain = ['|'] * (len(terms) - 1) + [('name', 'ilike', t) for t in terms]
        products = Product.search(domain, limit=3)
        lines = []
        for product in products:
            tmpl = product.product_tmpl_id
            if tmpl.omni_places_remaining is not False:
                qty = tmpl.omni_places_remaining
            else:
                qty = self._omni_product_free_qty(product)
            if qty is None:
                continue
            if qty < FOMO_THRESHOLD:
                lines.append(
                    _(
                        'Low availability hint: "%(name)s" — only %(qty)s left.',
                        name=product.display_name,
                        qty=int(qty),
                    )
                )
        return '\n'.join(lines)

    def _omni_product_free_qty(self, product):
        for attr in ('free_qty', 'qty_available'):
            if hasattr(product, attr):
                try:
                    val = getattr(product, attr)
                    if val is not None:
                        return val
                except Exception:
                    continue
        return None

    @api.model
    def omni_optional_product_lines(self, product_template):
        tmpl = product_template[:1]
        if not tmpl:
            return self.env['product.product']
        optional = tmpl.optional_product_ids
        return optional.product_variant_ids

    @api.model
    def omni_draft_sale_order(self, partner, product, quantity=1.0):
        if not partner or not product:
            return self.env['sale.order']
        order = self.env['sale.order'].sudo().create({
            'partner_id': partner.id,
        })
        self.env['sale.order.line'].sudo().create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': quantity,
        })
        return order
