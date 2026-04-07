# -*- coding: utf-8 -*-
import os
import re

from odoo import _, api, models
from odoo.tools import html2plaintext


class OmniKnowledge(models.AbstractModel):
    _name = 'omni.knowledge'
    _description = 'Catalog + payment facts for LLM context'

    @api.model
    def _omni_compact_mode(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.llm_compact_mode',
            'True',
        )
        return str(val).lower() in ('1', 'true', 'yes')

    @api.model
    def _omni_debug_sources_enabled(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.llm_debug_data_sources',
            'False',
        )
        return str(val).lower() in ('1', 'true', 'yes')

    @api.model
    def omni_partner_payment_summary(self, partner):
        if not partner:
            return _('No partner linked yet.')
        partner = partner.commercial_partner_id
        lines = []
        Move = self.env['account.move'].sudo()
        invoices = Move.search(
            [
                ('partner_id', 'child_of', partner.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
            ],
            order='invoice_date desc, id desc',
            limit=8,
        )
        paid_like = invoices.filtered(
            lambda m: m.payment_state in ('paid', 'in_payment')
        )
        if paid_like:
            refs = ', '.join(paid_like.mapped('name')[:5])
            lines.append(
                _(
                    'Customer has posted invoices with payment status paid/in_payment (e.g. %(refs)s).',
                    refs=refs,
                )
            )
        elif invoices:
            lines.append(
                _(
                    'Customer has posted invoices but none marked paid yet (latest: %(name)s, %(state)s).',
                    name=invoices[0].name,
                    state=invoices[0].payment_state,
                )
            )
        else:
            lines.append(_('No posted customer invoices found for this partner.'))
        return '\n'.join(lines)

    @api.model
    def omni_catalog_context_for_llm(self, partner, limit=40):
        """Camp-focused catalog facts: price, program, places, terms."""
        if self._omni_compact_mode():
            limit = min(limit, 12)
        Product = self.env['product.template'].sudo()
        domain = [('sale_ok', '=', True)]
        if 'is_published' in Product._fields:
            domain.append(('is_published', '=', True))
        order = 'website_sequence, name' if 'website_sequence' in Product._fields else 'name'
        products = Product.search(domain, order=order, limit=max(limit * 3, 40))
        chunks = []
        if partner:
            pricelist = partner.property_product_pricelist
        else:
            pricelist = self.env.company.property_product_pricelist_id
        camp_products = [p for p in products if self._omni_is_camp_product(p)]
        for tmpl in camp_products[:limit]:
            variant = tmpl.product_variant_id
            price = tmpl.list_price
            if pricelist and variant:
                try:
                    price = pricelist._get_product_price(
                        variant,
                        1.0,
                        uom=variant.uom_id,
                    )
                except TypeError:
                    price = pricelist._get_product_price(variant, 1.0, partner=partner or False)
            places, places_src = self._omni_extract_places_with_source(tmpl)
            program, program_src = self._omni_extract_program_with_source(tmpl)
            terms = (tmpl.omni_chat_terms or '').strip()
            currency = tmpl.currency_id or self.env.company.currency_id
            line = '- %s | price: %s %s' % (
                tmpl.name,
                price,
                currency.name or '',
            )
            if places is not None:
                line += ' | places_left: %s' % places
            if program:
                prog_len = 140 if self._omni_compact_mode() else 260
                line += ' | program: %s' % program[:prog_len]
            if terms:
                term_len = 160 if self._omni_compact_mode() else 500
                line += ' | terms: %s' % terms[:term_len]
            if self._omni_debug_sources_enabled():
                line += ' | src(price=pricelist/list_price, program=%s, places=%s)' % (
                    program_src,
                    places_src,
                )
            chunks.append(line)
        if not chunks:
            return _('No camp catalog lines available (check product data and camp markers).')
        header = _('Use only these CAMP catalog facts for offers: price, program, places_left.')
        return header + '\n' + '\n'.join(chunks)

    @api.model
    def omni_recommended_catalog_context(self, partner, limit=2):
        """
        Build a short, profile-aware recommendation block for sales replies.
        Scoring is heuristic: period keyword match + budget fit + available places.
        """
        Product = self.env['product.template'].sudo()
        domain = [('sale_ok', '=', True)]
        if 'is_published' in Product._fields:
            domain.append(('is_published', '=', True))
        products = Product.search(domain, limit=80)
        if not products:
            return 'RECOMMENDED_CAMPS: no recommendations available.'
        products = [p for p in products if self._omni_is_camp_product(p)]
        if not products:
            return 'RECOMMENDED_CAMPS: no camp products matched.'

        period = ((partner.omni_preferred_period or '').strip().lower() if partner else '')
        budget = float(partner.omni_budget_amount or 0.0) if partner else 0.0

        if partner:
            pricelist = partner.property_product_pricelist
        else:
            pricelist = self.env.company.property_product_pricelist_id

        ranked = []
        for tmpl in products:
            variant = tmpl.product_variant_id
            price = tmpl.list_price
            if pricelist and variant:
                try:
                    price = pricelist._get_product_price(variant, 1.0, uom=variant.uom_id)
                except TypeError:
                    price = pricelist._get_product_price(variant, 1.0, partner=partner or False)
            terms = (tmpl.omni_chat_terms or tmpl.description_sale or '').lower()
            program, _program_src = self._omni_extract_program_with_source(tmpl)
            program = program.lower()
            score = 0
            if period and (period in (tmpl.name or '').lower() or period in terms or period in program):
                score += 3
            if budget > 0 and float(price or 0.0) <= budget:
                score += 2
            places, places_src = self._omni_extract_places_with_source(tmpl)
            if places is not None:
                if places > 0:
                    score += 2
                else:
                    score -= 3
            ranked.append((score, tmpl, price, places))

        ranked.sort(key=lambda x: x[0], reverse=True)
        top = ranked[:max(1, min(limit, 3))]
        currency = self.env.company.currency_id
        lines = ['RECOMMENDED_CAMPS:']
        for score, tmpl, price, places in top:
            line = '- %s | price: %s %s' % (tmpl.name, price, (tmpl.currency_id or currency).name or '')
            if places is not None:
                line += ' | places: %s' % places
            program, program_src = self._omni_extract_program_with_source(tmpl)
            if program:
                line += ' | program: %s' % program[:140].replace('\n', ' ')
            if tmpl.omni_chat_terms:
                line += ' | terms: %s' % (tmpl.omni_chat_terms[:200].replace('\n', ' '))
            if self._omni_debug_sources_enabled():
                line += ' | src(program=%s, places=%s)' % (program_src, places_src)
            line += ' | score: %s' % score
            lines.append(line)
        lines.append('Policy: offer at most 1-2 options first, ask one clarifying question if needed.')
        return '\n'.join(lines)

    @api.model
    def _omni_is_camp_product(self, tmpl):
        name = (tmpl.name or '').lower()
        cat = (tmpl.categ_id.name or '').lower() if tmpl.categ_id else ''
        terms = (tmpl.omni_chat_terms or '').lower()
        markers = ('таб', 'camp', 'obóz', 'kolonia', 'заїзд', 'turnus')
        return any(m in name or m in cat or m in terms for m in markers)

    @api.model
    def _omni_extract_program_with_source(self, tmpl):
        parts = []
        sources = []
        for field_name in ('omni_chat_terms', 'description_sale', 'website_description'):
            if field_name in tmpl._fields:
                val = getattr(tmpl, field_name, '') or ''
                txt = re.sub(r'\s+', ' ', str(val)).strip()
                if txt:
                    parts.append(txt)
                    sources.append(field_name)
        if not parts:
            return '', 'none'
        # Prefer explicit chatbot terms first, then supplement with short description.
        return ' | '.join(parts[:2]), '+'.join(sources[:2])

    @api.model
    def _omni_extract_places_with_source(self, tmpl):
        # Priority 1: dedicated camp/chat field in this module.
        if 'omni_places_remaining' in tmpl._fields and tmpl.omni_places_remaining is not False:
            try:
                return int(tmpl.omni_places_remaining), 'omni_places_remaining'
            except (TypeError, ValueError):
                pass
        # Priority 2: common event fields in custom Odoo builds.
        for fname in ('seats_available', 'seats_expected', 'seats_max'):
            if fname in tmpl._fields:
                try:
                    val = int(getattr(tmpl, fname))
                    return val, fname
                except (TypeError, ValueError):
                    continue
        # Priority 3: stock fallback for product variant.
        variant = tmpl.product_variant_id
        if variant and hasattr(variant, 'free_qty'):
            try:
                return int(variant.free_qty), 'product_variant.free_qty'
            except (TypeError, ValueError):
                pass
        if variant and hasattr(variant, 'qty_available'):
            try:
                return int(variant.qty_available), 'product_variant.qty_available'
            except (TypeError, ValueError):
                pass
        return None, 'none'

    @api.model
    def omni_partner_core_facts(self, partner):
        """Лише поля з БД — один рядок на факт."""
        if not partner:
            return _('partner_linked: no')
        p = partner.commercial_partner_id
        lines = [
            'crm_display_name: %s' % (p.name or ''),
            'email: %s' % (p.email or ''),
            'phone: %s' % (p.phone or ''),
            'mobile: %s' % (p.mobile or ''),
            'street: %s' % (p.street or ''),
            'city: %s' % (p.city or ''),
            'preferred_vocative: %s' % (p.omni_addressing_vocative or ''),
            'addressing_style: %s' % (p.omni_addressing_style or 'neutral'),
        ]
        return '\n'.join(lines)

    @api.model
    def omni_greeting_instruction_block(self, partner):
        """Інструкції для моделі: шаблон звернення або уточнити один раз."""
        Memory = self.env['omni.memory']
        if not partner:
            return _('GREETING: немає прив’язаного партнера.')
        p = partner.commercial_partner_id
        voc = (p.omni_addressing_vocative or '').strip()
        style = p.omni_addressing_style or 'neutral'
        if not voc:
            hint = Memory.omni_suggest_vocative_from_name(p.name)
            if hint:
                return (
                    'GREETING: у картці ім’я «%s». Можлива форма звертання «%s». '
                    'Якщо клієнт не підтвердив — один раз ввічливо запитайте, як зручно звертатися, '
                    'і після відповіді дані збережуться в CRM.'
                ) % (p.name, hint)
            return (
                'GREETING: один раз уточніть, як звертатися до клієнта (на ім’я чи офіційно), '
                'і поясніть що збережете для наступних розмов. Ім’я в CRM: %s.'
            ) % (p.name,)
        if style == 'formal_female':
            return (
                'GREETING_TEMPLATE_UK: Почніть з точної фрази: «Доброго дня, пані %(voc)s!» '
                '(не змінюйте зворот).'
            ) % {'voc': voc}
        if style == 'formal_male':
            return (
                'GREETING_TEMPLATE_UK: Почніть з точної фрази: «Доброго дня, пане %(voc)s!» '
                '(не змінюйте зворот).'
            ) % {'voc': voc}
        if style == 'informal':
            return (
                'GREETING_TEMPLATE_UK: Можна на ти. Почніть з «Привіт, %(voc)s!» '
                '(ім’я як у полі preferred_vocative).'
            ) % {'voc': voc}
        return (
            'GREETING: стиль neutral — ввічливо, без «пані/пане», поки клієнт не уточнив. '
            'Можна звернутися за іменем з картки якщо доречно: %s.'
        ) % (p.name,)

    @api.model
    def omni_channel_transcript_block(self, channel, limit=8):
        ICP = self.env['ir.config_parameter'].sudo()
        if str(ICP.get_param('omnichannel_bridge.llm_include_transcript', 'True')).lower() not in (
            '1',
            'true',
            'yes',
        ):
            return ''
        if not channel:
            return ''
        try:
            lim = int(ICP.get_param('omnichannel_bridge.llm_transcript_messages', '8'))
        except ValueError:
            lim = limit
        if self._omni_compact_mode():
            lim = min(lim, 4)
        Message = self.env['mail.message'].sudo()
        msgs = Message.search(
            [
                ('model', '=', 'discuss.channel'),
                ('res_id', '=', channel.id),
                ('message_type', '=', 'comment'),
            ],
            order='id desc',
            limit=max(1, min(lim, 30)),
        )
        lines = [
            _(
                'RECENT_THREAD (context only; not financial truth; may contain typos):'
            ),
        ]
        odoobot = self.env.ref('base.partner_root')
        customer = channel.omni_customer_partner_id
        for m in reversed(msgs):
            body = (html2plaintext(m.body or '') or '').strip()
            if not body:
                continue
            auth = m.author_id
            if customer and auth == customer:
                role = 'client'
            elif auth == odoobot:
                role = 'bot'
            else:
                role = 'staff'
            msg_len = 220 if self._omni_compact_mode() else 500
            lines.append('%s: %s' % (role, body[:msg_len]))
        return '\n'.join(lines)

    @api.model
    def omni_partner_orders_block(self, partner):
        """Замовлення клієнта: назва табору, extras, статус, сума."""
        if not partner:
            return ''
        p = partner.commercial_partner_id
        Order = self.env['sale.order'].sudo()
        orders = Order.search(
            [('partner_id', 'child_of', p.id)],
            order='date_order desc',
            limit=5,
        )
        if not orders:
            return _('CLIENT_ORDERS: немає замовлень у системі.')
        lines = ['CLIENT_ORDERS:']
        for order in orders:
            status = dict(order._fields['state'].selection).get(order.state, order.state)
            lines.append('  Замовлення %s | %s | %s %s' % (
                order.name,
                status,
                order.amount_total,
                order.currency_id.name or '',
            ))
            for line in order.order_line:
                product_name = line.product_id.display_name or line.name
                lines.append('    - %s × %s' % (line.product_uom_qty, product_name))
        return '\n'.join(lines)

    @api.model
    def _omni_interview_faq_sections(self):
        """Load interview FAQ and split into Q/A sections."""
        base_dir = os.path.dirname(os.path.dirname(__file__))  # addons/omnichannel_bridge
        faq_path = os.path.join(base_dir, 'data', 'knowledge', 'interview_faq_ua.md')
        if not os.path.exists(faq_path):
            return []
        try:
            with open(faq_path, 'r', encoding='utf-8') as fp:
                content = fp.read()
        except Exception:
            return []

        sections = []
        chunks = re.split(r'\n\*\*(.+?)\*\*\n', content)
        # chunks: [prefix, q1, a1, q2, a2, ...]
        if len(chunks) < 3:
            return []
        for idx in range(1, len(chunks) - 1, 2):
            question = (chunks[idx] or '').strip()
            answer = (chunks[idx + 1] or '').strip()
            if not question or not answer:
                continue
            sections.append((question, answer))
        return sections

    @api.model
    def omni_interview_faq_context(self, user_text, max_items=3):
        """
        Return top-matching interview FAQ snippets by simple keyword overlap.
        Keeps prompt compact while still grounding interview-style answers.
        """
        if self._omni_compact_mode():
            max_items = min(max_items, 1)
        sections = self._omni_interview_faq_sections()
        if not sections:
            return ''
        query = (user_text or '').lower().strip()
        if not query:
            return ''
        terms = {t for t in re.split(r'[^a-zA-Zа-яА-ЯіІїЇєЄ0-9]+', query) if len(t) >= 3}
        if not terms:
            return ''

        scored = []
        for q, a in sections:
            bag = (q + ' ' + a[:600]).lower()
            score = sum(1 for t in terms if t in bag)
            if score > 0:
                scored.append((score, q, a))
        if not scored:
            return ''
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:max(1, min(max_items, 5))]

        lines = [
            'INTERVIEW_FAQ_CONTEXT (UA, use only if relevant to client question):',
        ]
        for _, q, a in top:
            lines.append('- Q: %s' % q)
            ans_len = 260 if self._omni_compact_mode() else 900
            lines.append('  A: %s' % a[:ans_len].replace('\n', ' ').strip())
        lines.append(
            '- Policy: for prices/dates/availability always prioritize live ORM facts from catalog/orders/events.'
        )
        return '\n'.join(lines)

    @api.model
    def omni_camp_scope_block(self):
        return (
            'CAMP_SCOPE_POLICY:\n'
            '- Scope: only CampScout camp sales/support topics (programs, safety, logistics, payment, registration).\n'
            '- If question is outside scope, suggest manager handoff.\n'
            '- Reply language: Ukrainian or Polish according to client message.\n'
            '- Russian reply is disabled by policy.'
        )

    @api.model
    def omni_strict_grounding_bundle(self, channel, partner, user_text=''):
        """Єдиний блок фактів для LLM: ORM + умови каталогу + звернення + пам’ять + тред."""
        parts = [
            '=== FACTS_FROM_DATABASE (єдине джерело правди про ціни, місця, оплати, ПІБ) ===',
            self.omni_camp_scope_block(),
            '---',
            self.omni_partner_core_facts(partner),
            '---',
            self.omni_sales_discovery_block(partner),
            '---',
            self.omni_greeting_instruction_block(partner),
            '---',
            self.omni_partner_payment_summary(partner),
            '---',
            self.omni_partner_orders_block(partner),
            '---',
            self.omni_catalog_context_for_llm(partner),
            '---',
            self.omni_recommended_catalog_context(partner, limit=2),
        ]
        if partner and partner.omni_chat_memory:
            parts.append('---\nCLIENT_MEMORY_LINES:\n%s' % partner.omni_chat_memory.strip())
        transcript = self.omni_channel_transcript_block(channel)
        if transcript:
            parts.append('---\n%s' % transcript)
        faq_context = self.omni_interview_faq_context(user_text=user_text, max_items=3)
        if faq_context:
            parts.append('---\n%s' % faq_context)
        return '\n'.join(parts)

    @api.model
    def omni_sales_discovery_block(self, partner):
        """
        Sales flow helper for LLM:
        - keep dialog consultative
        - ask only missing qualification points
        - avoid repeating already known data from memory/CRM.
        """
        memory = (partner.omni_chat_memory or '').lower() if partner else ''
        has_age = bool(partner and partner.omni_child_age) or 'age:' in memory
        has_period = bool(partner and partner.omni_preferred_period) or 'period:' in memory
        has_budget = bool(partner and partner.omni_budget_amount) or 'budget:' in memory
        has_city = bool(partner and partner.omni_departure_city) or 'city:' in memory
        has_phone = bool(partner and (partner.phone or partner.mobile))
        has_email = bool(partner and partner.email)

        missing = []
        if not has_age:
            missing.append('вік дитини')
        if not has_period:
            missing.append('бажана зміна/дати')
        if not has_city:
            missing.append('місто виїзду/логістика')
        if not has_budget:
            missing.append('орієнтовний бюджет')
        if not has_phone and not has_email:
            missing.append('контакт для бронювання')

        profile_line = (
            'PROFILE_HINTS: age=%s; period=%s; city=%s; budget=%s %s; stage=%s'
            % (
                partner.omni_child_age if partner else '',
                (partner.omni_preferred_period or '') if partner else '',
                (partner.omni_departure_city or '') if partner else '',
                (partner.omni_budget_amount or '') if partner else '',
                (partner.omni_budget_currency or '') if partner else '',
                (partner.omni_sales_stage or '') if partner else '',
            )
        )

        return (
            'SALES_DISCOVERY_POLICY:\n'
            '- Працюй як консультант з продажу таборів: коротко, по суті, з емпатією.\n'
            '- Після першої відповіді веди кваліфікацію: вік, зміна, логістика, бюджет, контакт.\n'
            '- Став не більше 1-2 уточнень за повідомлення.\n'
            '- Не повторюй питання, якщо факт вже відомий з CRM або CLIENT_MEMORY_LINES.\n'
            '- %s.\n'
            '- Missing now: %s.\n'
            '- Коли даних достатньо: запропонуй 1-2 релевантні табори з ORM фактами і мʼякий наступний крок (бронь/менеджер).'
        ) % (
            profile_line,
            ', '.join(missing) if missing else 'дані для підбору вже зібрані',
        )
