# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime

from odoo import _, api, fields, models
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
    def _omni_is_camp_event_name(self, event_name):
        txt = (event_name or '').lower()
        if not txt:
            return False
        camp_markers = (
            'кемп', 'табір', 'camp', 'obóz', 'kolonia', 'turnus',
            'дослідники морів', 'долини карпа', 'пошумимо', 'вовчій стежці',
            'підкова', 'цивілізація', 'chill-camp',
        )
        non_camp_markers = (
            'зустріч', 'он лайн', 'курс', 'вебінар', 'meeting',
        )
        if any(k in txt for k in non_camp_markers):
            return False
        return any(k in txt for k in camp_markers)

    @api.model
    def omni_cron_refresh_camp_availability_snapshot(self):
        """
        Daily auto-monitoring of camp free places for bot grounding.
        Creates/updates one KB article with fresh seats + locations.
        """
        if 'event.event' not in self.env:
            return
        Event = self.env['event.event'].sudo()
        Registration = self.env['event.registration'].sudo() if 'event.registration' in self.env else False
        events = Event.search([('active', '=', True)], order='date_begin asc, id asc')
        camp_rows = []
        now = fields.Datetime.now()
        for event in events:
            name = (
                event.name.get('uk_UA')
                if isinstance(event.name, dict)
                else (event.name or '')
            ) or (
                event.name.get('en_US')
                if isinstance(event.name, dict)
                else ''
            ) or 'event'
            if not self._omni_is_camp_event_name(name):
                continue
            registered = 0
            if Registration:
                registered = Registration.search_count([
                    ('event_id', '=', event.id),
                    ('state', 'not in', ('cancel', 'cancelled', 'draft')),
                ])
            seats_max = int(event.seats_max or 0)
            seats_available = max(0, seats_max - registered) if seats_max else 0
            country = ''
            if event.country_id:
                country = event.country_id.name if isinstance(event.country_id.name, str) else ''
            location = country or event.address_id.city or (
                event.address_id.name if event.address_id else ''
            ) or '-'
            camp_rows.append({
                'name': name,
                'location': location,
                'seats_available': seats_available,
                'seats_max': seats_max,
                'registered': registered,
            })
        if not camp_rows:
            return

        lines = [
            'AUTO_DAILY_CAMP_AVAILABILITY',
            'updated_at: %s' % datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'source: event.event + event.registration',
            '',
            'Дані для бота (актуальна наявність місць):',
        ]
        for row in camp_rows:
            lines.append(
                '- %s | локація: %s | вільно місць: %s/%s'
                % (row['name'], row['location'], row['seats_available'], row['seats_max'])
            )
        body = '\n'.join(lines)

        Article = self.env['omni.knowledge.article'].sudo()
        article = Article.search([('source_ref', '=', 'daily_camp_availability_snapshot')], limit=1)
        vals = {
            'name': 'CampScout: щоденний моніторинг вільних місць (auto)',
            'category': 'faq',
            'channel_scope': 'all',
            'priority': 5,
            'body': body,
            'source_type': 'other',
            'source_ref': 'daily_camp_availability_snapshot',
            'source_timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'editorial_approved': True,
        }
        if article:
            article.write(vals)
        else:
            Article.create(vals)

        # Internal manager alert for low-seat camps.
        threshold_raw = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.camp_low_availability_threshold',
            '5',
        )
        try:
            threshold = max(1, int(threshold_raw))
        except Exception:
            threshold = 5
        self.env['omni.notify'].sudo().notify_low_availability(camp_rows, threshold=threshold)

    @api.model
    def _omni_debug_sources_enabled(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.llm_debug_data_sources',
            'False',
        )
        return str(val).lower() in ('1', 'true', 'yes')

    @api.model
    def _omni_pricelist_for_catalog(self, partner):
        """Company pricelist field name differs across sale/website stacks; avoid AttributeError."""
        if partner:
            return partner.property_product_pricelist
        company = self.env.company
        if 'property_product_pricelist_id' in company._fields:
            return company.property_product_pricelist_id
        c_partner = company.partner_id.sudo()
        if c_partner and 'property_product_pricelist' in c_partner._fields:
            return c_partner.property_product_pricelist
        return False

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
        if 'website_sale' in self.env and 'is_published' in Product._fields:
            domain.append(('is_published', '=', True))
        order = 'website_sequence, name' if 'website_sequence' in Product._fields else 'name'
        products = Product.search(domain, order=order, limit=max(limit * 3, 40))
        chunks = []
        pricelist = self._omni_pricelist_for_catalog(partner)
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
                if places <= 0:
                    line += ' | reserve: manager_waitlist_required'
            else:
                line += ' | places_left: unknown | reserve: manager_waitlist_required'
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
        if 'website_sale' in self.env and 'is_published' in Product._fields:
            domain.append(('is_published', '=', True))
        products = Product.search(domain, limit=80)
        if not products:
            return 'RECOMMENDED_CAMPS: no recommendations available.'
        products = [p for p in products if self._omni_is_camp_product(p)]
        if not products:
            return 'RECOMMENDED_CAMPS: no camp products matched.'

        period = ((partner.omni_preferred_period or '').strip().lower() if partner else '')
        budget = float(partner.omni_budget_amount or 0.0) if partner else 0.0

        pricelist = self._omni_pricelist_for_catalog(partner)

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
                if places <= 0:
                    line += ' | reserve: manager_waitlist_required'
            else:
                line += ' | places: unknown | reserve: manager_waitlist_required'
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
        code = (getattr(tmpl, 'default_code', None) or '').strip().upper()
        if code.startswith('CS-'):
            return True
        name = (tmpl.name or '').lower()
        cat = (tmpl.categ_id.name or '').lower() if tmpl.categ_id else ''
        terms = (tmpl.omni_chat_terms or '').lower()
        markers = ('таб', 'camp', 'obóz', 'kolonia', 'заїзд', 'turnus', 'poszum', 'пошум')
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
        def _event_truth_available(event):
            event = event.sudo()
            # Prefer explicit registration truth-sync when event.registration model is present.
            if 'event.registration' in self.env and 'seats_max' in event._fields:
                Registration = self.env['event.registration'].sudo()
                reg_domain = [
                    ('event_id', '=', event.id),
                    ('state', 'not in', ('cancel', 'cancelled', 'draft')),
                ]
                try:
                    reserved = Registration.search_count(reg_domain)
                    return max(0, int((event.seats_max or 0) - reserved)), 'event.registration.state_count'
                except Exception:
                    pass
            if 'seats_available' in event._fields:
                try:
                    return int(event.seats_available), 'event.seats_available'
                except (TypeError, ValueError):
                    pass
            return None, 'none'

        # Priority 0: CampScout custom helper method from campscout-management.
        if hasattr(tmpl, 'get_camp_availability'):
            try:
                val = tmpl.get_camp_availability()
                if val is not None:
                    return int(val), 'product_template.get_camp_availability'
            except Exception:
                pass
        # Priority 0.1: Bonsens custom event link on template.
        if 'bs_event_id' in tmpl._fields and tmpl.bs_event_id:
            places, src = _event_truth_available(tmpl.bs_event_id)
            if places is not None:
                return places, 'bs_event_id.%s' % src
        # Priority 0.2: Bonsens custom event link on variant.
        variant = tmpl.product_variant_id
        if variant and 'bs_event_id' in variant._fields and variant.bs_event_id:
            places, src = _event_truth_available(variant.bs_event_id)
            if places is not None:
                return places, 'product_variant.bs_event_id.%s' % src
        # Priority 0.3: event tickets -> future events seats_available sum.
        if tmpl.product_variant_ids:
            Ticket = self.env['event.event.ticket'].sudo()
            tickets = Ticket.search([('product_id', 'in', tmpl.product_variant_ids.ids)], limit=300)
            if tickets:
                now_dt = fields.Datetime.now()
                events = tickets.mapped('event_id').filtered(lambda e: not e.date_begin or e.date_begin >= now_dt)
                if events:
                    try:
                        total = 0
                        used_truth = False
                        for event in events:
                            ev_places, ev_src = _event_truth_available(event)
                            if ev_places is None:
                                continue
                            total += int(ev_places)
                            if ev_src == 'event.registration.state_count':
                                used_truth = True
                        if total >= 0:
                            if used_truth:
                                return total, 'event_ticket.future_events.event_registration_truth'
                            return total, 'event_ticket.future_events.seats_available'
                    except Exception:
                        pass
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
        channel = channel.sudo()
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
    def omni_legal_context_block(self):
        company = self.env.company.sudo()
        legal_name = (company.name or '').strip() or 'CampScout'
        icp = self.env['ir.config_parameter'].sudo()
        terms_url = (icp.get_param('omnichannel_bridge.legal_terms_url') or 'https://campscout.eu/terms').strip()
        privacy_url = (icp.get_param('omnichannel_bridge.legal_privacy_url') or 'https://campscout.eu/privacy-policy').strip()
        cookie_url = (icp.get_param('omnichannel_bridge.legal_cookie_url') or 'https://campscout.eu/cookie-policy').strip()
        child_url = (
            icp.get_param('omnichannel_bridge.legal_child_protection_url') or
            'https://campscout.eu/child-protection'
        ).strip()
        short_offer = (icp.get_param('omnichannel_bridge.legal_short_offer_text') or '').strip()
        short_rodo = (icp.get_param('omnichannel_bridge.legal_short_rodo_text') or '').strip()
        short_child = (icp.get_param('omnichannel_bridge.legal_short_child_text') or '').strip()
        approved_owner = (icp.get_param('omnichannel_bridge.legal_approved_owner') or '').strip()
        approved = [x for x in (short_offer, short_rodo, short_child) if x]
        approved_block = (
            '- Approved short legal wording (use as-is, no improvisation):\n'
            + '\n'.join('  • %s' % s[:260] for s in approved)
            if approved else
            '- Approved short legal wording: use legal URLs and neutral wording, no invented clauses.'
        )
        return (
            'LEGAL_CONTEXT:\n'
            '- Data controller / responsible legal entity: %s.\n'
            '- Use only these legal links (no invented legal text):\n'
            '  • %s\n'
            '  • %s\n'
            '  • %s\n'
            '  • %s\n'
            '%s\n'
            '- Legal auto-wording approval owner: %s.\n'
            '- For legal, insurance, child-safety disputes: mandatory human handoff.\n'
            '- Child data minimization: ask only what is needed for camp selection/booking.'
        ) % (legal_name, terms_url, privacy_url, cookie_url, child_url, approved_block, approved_owner or 'not set')

    @api.model
    def omni_channel_consent_policy_block(self):
        icp = self.env['ir.config_parameter'].sudo()
        meta = (icp.get_param('omnichannel_bridge.consent_meta_text') or '').strip()
        tg = (icp.get_param('omnichannel_bridge.consent_telegram_text') or '').strip()
        wa = (icp.get_param('omnichannel_bridge.consent_whatsapp_text') or '').strip()
        site = (icp.get_param('omnichannel_bridge.consent_site_text') or '').strip()
        return (
            'CHANNEL_CONSENT_POLICY:\n'
            '- meta_instagram: %s\n'
            '- telegram: %s\n'
            '- whatsapp: %s\n'
            '- site_livechat: %s\n'
            '- Policy: use channel-specific consent wording when discussing proactive messaging/marketing.'
        ) % (
            meta or 'Use approved consent wording configured by legal owner.',
            tg or 'Use approved consent wording configured by legal owner.',
            wa or 'Use approved consent wording configured by legal owner.',
            site or 'Use approved consent wording configured by legal owner.',
        )

    @api.model
    def omni_coupon_policy_block(self):
        ICP = self.env['ir.config_parameter'].sudo()
        channel_url = (ICP.get_param('omnichannel_bridge.coupon_public_channel_url') or '').strip()
        if not channel_url:
            channel_url = 'https://t.me/campscouting'
        return (
            'COUPON_POLICY:\n'
            '- -5%% coupon flow is public-channel based (no personal code generation by bot).\n'
            '- Client opens Telegram channel and copies current code from pinned/latest post.\n'
            '- Coupon channel URL: %s\n'
            '- Scope remains camp products only by business rule.'
        ) % channel_url

    @api.model
    def omni_reserve_policy_block(self):
        return (
            'RESERVE_POLICY:\n'
            '- If places_left/places is 0 for requested camp/event, do NOT claim availability.\n'
            '- If places_left/places is unknown, do NOT invent number; route to manager waitlist flow.\n'
            '- Mandatory next step: offer manager contact to add client to reserve/waitlist.\n'
            '- Ask one contact point (phone or email) and handoff to manager.'
        )

    @api.model
    def omni_payment_policy_block(self):
        return (
            'PAYMENT_POLICY:\n'
            '- Payment facts are allowed only from ORM statuses (sale.order/account.move/payment.transaction).\n'
            '- Never promise bank settlement timing or payment provider guarantees.\n'
            '- Do not claim "paid" unless status explicitly indicates paid/in_payment/done/authorized in ORM.\n'
            '- If status is unclear or missing, say so and offer manager/billing handoff.\n'
            '- For legal/payment dispute wording, keep neutral and route to manager.'
        )

    @api.model
    def omni_promo_context_block(self):
        today = fields.Date.context_today(self)
        promos = self.env['omni.promo'].sudo().search([('active', '=', True)], order='id desc', limit=8)
        lines = ['PROMOTIONS:']
        for p in promos:
            if p.date_start and p.date_start > today:
                continue
            if p.date_end and p.date_end < today:
                continue
            prod_names = ', '.join(p.product_tmpl_ids.mapped('name')[:5]) if p.product_tmpl_ids else 'all camp products'
            lines.append(
                '- %s | code:%s | discount:%s%% | channel:%s | products:%s | terms:%s'
                % (
                    p.name,
                    p.code or '—',
                    p.discount_percent or 0.0,
                    p.channel_scope or 'all',
                    prod_names,
                    (p.terms or '').strip()[:180] or '—',
                )
            )
        if len(lines) == 1:
            lines.append('- no active promotions')
        return '\n'.join(lines)

    @api.model
    def omni_insurance_context_block(self):
        packages = self.env['omni.insurance.package'].sudo().search([('active', '=', True)], order='id desc', limit=12)
        lines = ['INSURANCE_PACKAGES:']
        for pkg in packages:
            linked_product = pkg.product_tmpl_id.name if pkg.product_tmpl_id else '—'
            lines.append(
                '- %s | code:%s | channel:%s | product:%s | policy:%s | terms:%s'
                % (
                    pkg.name,
                    pkg.code or '—',
                    pkg.channel_scope or 'all',
                    linked_product,
                    pkg.policy_url or '—',
                    (pkg.short_terms or '').strip()[:180] or '—',
                )
            )
        if len(lines) == 1:
            lines.append('- no active insurance packages')
        return '\n'.join(lines)

    @api.model
    def omni_legal_documents_context_block(self):
        docs = self.env['omni.legal.document'].sudo().search(
            [('active', '=', True), ('allow_in_bot', '=', True)],
            order='id desc',
            limit=20,
        )
        lines = ['LEGAL_DOCUMENTS:']
        for doc in docs:
            lines.append(
                '- %s | type:%s | pdf:%s | url:%s | quote:%s'
                % (
                    doc.name,
                    doc.doc_type or 'other',
                    'yes' if doc.is_pdf else 'no',
                    doc.url,
                    (doc.short_quote or '').strip()[:180] or '—',
                )
            )
        if len(lines) == 1:
            lines.append('- no bot-approved legal docs configured')
        return '\n'.join(lines)

    @api.model
    def omni_prompt_versioning_block(self):
        icp = self.env['ir.config_parameter'].sudo()
        version = (icp.get_param('omnichannel_bridge.llm_prompt_version') or 'v1').strip()
        exp_tag = (icp.get_param('omnichannel_bridge.llm_experiment_tag') or '').strip()
        profile = (icp.get_param('omnichannel_bridge.llm_assistant_profile') or 'default').strip()
        return (
            'PROMPT_VERSIONING:\n'
            '- prompt_version: %s\n'
            '- experiment_tag: %s\n'
            '- assistant_profile: %s\n'
            '- Policy: keep answer behavior compliant with strict grounding regardless of experiment tag.'
        ) % (version, exp_tag or 'none', profile or 'default')

    @api.model
    def _omni_rag_hybrid_enabled(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.rag_hybrid_enabled',
            'True',
        )
        return str(val).lower() in ('1', 'true', 'yes')

    @api.model
    def _omni_rag_graph_enabled(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.rag_graph_enabled',
            'True',
        )
        return str(val).lower() in ('1', 'true', 'yes')

    @api.model
    def _omni_rag_rrf_k(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.rag_rrf_k',
            '60',
        )
        try:
            return max(1, min(int(raw), 200))
        except Exception:
            return 60

    @api.model
    def _omni_rag_top_k(self, max_items=4):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.rag_top_k',
            '8',
        )
        try:
            configured = max(1, min(int(raw), 20))
        except Exception:
            configured = 8
        # Context U-curve safeguard: keep small-mid context by default.
        if self._omni_compact_mode():
            configured = min(configured, 5)
        return max(1, min(max_items, configured))

    @api.model
    def _omni_rag_anchor_min_percent(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'omnichannel_bridge.rag_anchor_min_percent',
            '50',
        )
        try:
            return max(10, min(int(raw), 100))
        except Exception:
            return 50

    @api.model
    def _omni_term_set(self, text):
        txt = (text or '').lower().strip()
        if not txt:
            return set()
        return {t for t in re.split(r'[^a-zA-Zа-яА-ЯіІїЇєЄ0-9]+', txt) if len(t) >= 3}

    @api.model
    def _omni_phrase_overlap_score(self, query, candidate_text):
        q_terms = self._omni_term_set(query)
        c_terms = self._omni_term_set(candidate_text)
        if not q_terms or not c_terms:
            return 0.0
        shared = q_terms.intersection(c_terms)
        if not shared:
            return 0.0
        return float(len(shared)) / float(max(len(q_terms), 1))

    @api.model
    def _omni_cross_rerank_score(self, query, name, quote):
        # Lightweight cross-encoder approximation: token overlap + phrase hits + prefix bonus.
        base = self._omni_phrase_overlap_score(query, '%s %s' % (name or '', quote or ''))
        q = (query or '').strip().lower()
        n = (name or '').strip().lower()
        qt = (quote or '').strip().lower()
        phrase_bonus = 0.0
        if q and q in qt:
            phrase_bonus += 0.4
        if q and q in n:
            phrase_bonus += 0.2
        if q and n.startswith(q[: min(8, len(q))]):
            phrase_bonus += 0.1
        return base + phrase_bonus

    @api.model
    def _omni_build_hybrid_candidates(self):
        candidates = []
        for doc in self.env['omni.legal.document'].sudo().search([('active', '=', True), ('allow_in_bot', '=', True)], limit=80):
            candidates.append({
                'id': 'doc:%s' % doc.id,
                'kind': 'doc',
                'name': doc.name or '',
                'url': doc.url or '',
                'quote': doc.short_quote or '',
                'bag': ('%s %s %s' % (doc.name or '', doc.short_quote or '', doc.doc_type or '')).lower(),
                'graph_tag': 'legal',
            })
        for pkg in self.env['omni.insurance.package'].sudo().search([('active', '=', True)], limit=80):
            candidates.append({
                'id': 'insurance:%s' % pkg.id,
                'kind': 'insurance',
                'name': pkg.name or '',
                'url': pkg.policy_url or '',
                'quote': pkg.short_terms or '',
                'bag': ('%s %s %s' % (pkg.name or '', pkg.short_terms or '', pkg.code or '')).lower(),
                'graph_tag': 'insurance',
            })
        today = fields.Date.context_today(self)
        for art in self.env['omni.knowledge.article'].sudo().search([('active', '=', True)], order='priority asc, id desc', limit=120):
            if not getattr(art, 'editorial_approved', True):
                continue
            if getattr(art, 'fact_expires_on', False) and art.fact_expires_on < today:
                continue
            candidates.append({
                'id': 'knowledge:%s' % art.id,
                'kind': 'knowledge',
                'name': art.name or '',
                'url': art.source_url or '',
                'quote': art.body or '',
                'bag': ('%s %s %s' % (art.name or '', art.body or '', art.category or '')).lower(),
                'graph_tag': 'article:%s' % (art.category or 'other'),
                'priority': art.priority or 100,
            })
        return candidates

    @api.model
    def _omni_graph_expand_candidates(self, query_terms, lexical_ranked):
        if not lexical_ranked:
            return []
        # IFR-like graph expansion: pull neighbors by graph tag and shared key terms.
        anchors = lexical_ranked[: min(5, len(lexical_ranked))]
        tags = {c.get('graph_tag') for c in anchors if c.get('graph_tag')}
        seed_terms = set()
        for c in anchors:
            seed_terms.update(self._omni_term_set(c.get('name')))
            seed_terms.update(self._omni_term_set(c.get('quote')))
        seed_terms = {t for t in seed_terms if t in query_terms or len(t) >= 5}

        expanded = []
        for c in lexical_ranked:
            if c in anchors:
                continue
            match_tag = c.get('graph_tag') in tags if c.get('graph_tag') else False
            match_term = bool(seed_terms.intersection(self._omni_term_set(c.get('name'))))
            if match_tag or match_term:
                expanded.append(c)
        return expanded[:20]

    @api.model
    def omni_dynamic_rag_context(self, user_text, max_items=4):
        query = (user_text or '').lower().strip()
        if not query:
            return ''
        query_terms = self._omni_term_set(query)
        if not query_terms:
            return ''

        candidates = self._omni_build_hybrid_candidates()
        lexical = []
        for c in candidates:
            score = sum(1 for t in query_terms if t in (c.get('bag') or ''))
            if c.get('kind') == 'knowledge' and c.get('priority', 100) <= 30:
                score += 1
            if score > 0:
                lexical.append((score, c))
        if not lexical:
            return ''

        lexical.sort(key=lambda x: x[0], reverse=True)
        lexical_ranked = [c for _s, c in lexical]

        # If hybrid mode is disabled, keep legacy lexical path.
        if not self._omni_rag_hybrid_enabled():
            top = lexical_ranked[: self._omni_rag_top_k(max_items=max_items)]
            lines = ['RAG_CONTEXT:']
            for c in top:
                lines.append('- %s | %s | url:%s | quote:%s | score:%s' % (
                    c.get('kind') or '—',
                    c.get('name') or '—',
                    c.get('url') or '—',
                    (c.get('quote') or '').strip()[:180] or '—',
                    1,
                ))
            return '\n'.join(lines)

        graph_candidates = []
        if self._omni_rag_graph_enabled():
            graph_candidates = self._omni_graph_expand_candidates(query_terms, lexical_ranked)
        fused_pool = []
        seen = set()
        for c in lexical_ranked + graph_candidates:
            cid = c.get('id')
            if not cid or cid in seen:
                continue
            seen.add(cid)
            fused_pool.append(c)

        # RRF fusion between lexical rank and graph expansion rank.
        rrf_k = self._omni_rag_rrf_k()
        lexical_pos = {c.get('id'): idx for idx, c in enumerate(lexical_ranked)}
        graph_pos = {c.get('id'): idx for idx, c in enumerate(graph_candidates)}
        fused = []
        for c in fused_pool:
            cid = c.get('id')
            score = 0.0
            if cid in lexical_pos:
                score += 1.0 / float(rrf_k + lexical_pos[cid] + 1)
            if cid in graph_pos:
                score += 1.0 / float(rrf_k + graph_pos[cid] + 1)
            # Lightweight cross-rerank pass.
            score += self._omni_cross_rerank_score(query, c.get('name'), c.get('quote'))
            c_terms = self._omni_term_set('%s %s' % (c.get('name') or '', c.get('quote') or ''))
            anchor_ratio = float(len(query_terms.intersection(c_terms))) / float(max(len(query_terms), 1))
            # Anti-drift guard: penalize candidates that diverge from the original query.
            anchor_min = float(self._omni_rag_anchor_min_percent()) / 100.0
            if anchor_ratio < anchor_min:
                score -= 0.35
            fused.append((score, anchor_ratio, c))

        fused.sort(key=lambda x: x[0], reverse=True)
        top_k = self._omni_rag_top_k(max_items=max_items)
        anchor_min = float(self._omni_rag_anchor_min_percent()) / 100.0
        selected = []
        for score, anchor_ratio, c in fused:
            if len(selected) >= top_k:
                break
            if anchor_ratio < anchor_min and len(selected) > 0:
                continue
            selected.append((score, anchor_ratio, c))
        # Hard reset fallback: if anti-drift removes everything, use lexical anchors only.
        if not selected:
            for c in lexical_ranked[:top_k]:
                selected.append((1.0, 1.0, c))

        lines = ['RAG_CONTEXT:']
        lines.append('RAG_PIPELINE: hybrid_retrieval + rrf_fusion + cross_rerank + anti_drift')
        for score, anchor_ratio, c in selected:
            lines.append('- %s | %s | url:%s | quote:%s | score:%s' % (
                c.get('kind') or '—',
                c.get('name') or '—',
                c.get('url') or '—',
                (c.get('quote') or '').strip()[:180] or '—',
                round(score, 4),
            ))
            if self._omni_debug_sources_enabled():
                lines.append('  debug: anchor_ratio=%s id=%s tag=%s' % (
                    round(anchor_ratio, 3),
                    c.get('id') or '—',
                    c.get('graph_tag') or '—',
                ))
        return '\n'.join(lines)

    @api.model
    def omni_release_fingerprint_block(self):
        icp = self.env['ir.config_parameter'].sudo()
        return (
            'RELEASE_FINGERPRINT:\n'
            '- odoo_version: %s\n'
            '- custom_repo_hash: %s\n'
            '- ollama_model_version: %s'
        ) % (
            (icp.get_param('omnichannel_bridge.release_odoo_version') or '').strip() or 'not set',
            (icp.get_param('omnichannel_bridge.release_custom_hash') or '').strip() or 'not set',
            (icp.get_param('omnichannel_bridge.release_ollama_model_version') or '').strip() or 'not set',
        )

    @api.model
    def omni_strict_grounding_bundle(self, channel, partner, user_text=''):
        """Єдиний блок фактів для LLM: ORM + умови каталогу + звернення + пам’ять + тред."""
        if channel:
            channel = channel.sudo()
        if partner:
            partner = partner.sudo()
        parts = [
            '=== FACTS_FROM_DATABASE (єдине джерело правди про ціни, місця, оплати, ПІБ) ===',
            self.omni_camp_scope_block(),
            '---',
            self.omni_legal_context_block(),
            '---',
            self.omni_channel_consent_policy_block(),
            '---',
            self.omni_legal_documents_context_block(),
            '---',
            self.omni_coupon_policy_block(),
            '---',
            self.omni_promo_context_block(),
            '---',
            self.omni_insurance_context_block(),
            '---',
            self.omni_prompt_versioning_block(),
            '---',
            self.omni_release_fingerprint_block(),
            '---',
            self.omni_reserve_policy_block(),
            '---',
            self.omni_payment_policy_block(),
            '---',
            self.omni_partner_core_facts(partner),
            '---',
            self.omni_sales_discovery_block(partner, channel=channel, user_text=user_text or ''),
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
        rag_context = self.omni_dynamic_rag_context(user_text=user_text, max_items=4)
        if rag_context:
            parts.append('---\n%s' % rag_context)
        return '\n'.join(parts)

    @api.model
    def omni_sales_discovery_block(self, partner, channel=None, user_text=''):
        """
        Sales flow helper for LLM:
        - keep dialog consultative
        - ask only missing qualification points
        - avoid repeating already known data from memory/CRM.
        """
        omni_ai = self.env['omni.ai'].sudo()
        flags = omni_ai._omni_qualification_flags(
            partner, user_text=user_text or '', channel=channel,
        )
        has_age = flags['has_age']
        has_period = flags['has_period']
        has_budget = flags['has_budget']
        has_city = flags['has_city']
        has_contact = flags['has_contact']

        missing = []
        if not has_age:
            missing.append('вік дитини')
        if not has_period:
            missing.append('бажана зміна/дати')
        if not has_city:
            missing.append('місто виїзду/логістика')
        if not has_budget:
            missing.append('орієнтовний бюджет')
        if not has_contact:
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
        stage = (partner.omni_sales_stage or '') if partner else ''
        handoff_line = ''
        if stage == 'handoff':
            handoff_line = (
                '\n- STAGE_HANDOFF: не збирай поля з Missing і не починай кваліфікацію заново; '
                'коротко підтримай клієнта або підтвердь передачу менеджеру.'
            )

        return (
            'SALES_FUNNEL_CRM (внутрішній етап у stage=...):\n'
            '- new: перший контакт; одне тепле уточнення з Missing (не «продаж у лоб»).\n'
            '- qualifying: послідовно закривай Missing — одне питання за повідомлення.\n'
            '- proposal: 1–2 релевантні табори з фактами; без тиску на оплату в чаті; мʼякий крок (бронь/менеджер).\n'
            '- handoff: діалог передано людині — не розгортай нову воронку в чаті.\n'
            'SALES_DISCOVERY_POLICY:\n'
            '- Працюй як консультант з продажу таборів: коротко, по суті, з емпатією.\n'
            '- Після першої відповіді веди кваліфікацію: вік, зміна, логістика, бюджет, контакт.\n'
            '- Став не більше одного уточнювального питання за повідомлення.\n'
            '- Не повторюй питання, якщо факт уже в CRM, CLIENT_MEMORY_LINES або видно з THREAD_TRANSCRIPT вище.\n'
            '- Якщо вік дитини вже відомий — ніколи знову не питай про вік (ні в тексті, ні в уточненні).\n'
            '- %s.\n'
            '- Missing now: %s.%s\n'
            '- Коли даних достатньо: запропонуй 1-2 релевантні табори з ORM фактами і мʼякий наступний крок (бронь/менеджер).'
        ) % (
            profile_line,
            ', '.join(missing) if missing else 'дані для підбору вже зібрані',
            handoff_line,
        )
