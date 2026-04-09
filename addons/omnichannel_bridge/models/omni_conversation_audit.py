# -*- coding: utf-8 -*-
import re
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from odoo import api, fields, models


def _normalize_text(text):
    txt = re.sub(r'<[^>]+>', ' ', text or '')
    txt = re.sub(r'\s+', ' ', txt).strip().lower()
    return txt


_BEHAVIOR_RULES = {
    'price_expensive': (
        r'\bдорог',
        r'\bзадорого',
        r'\bне потяг',
        r'\bбюджет',
        r'\bza drogo',
        r'\bdrogo',
        r'\btoo expensive',
    ),
    'think_later': (
        r'\bподума',
        r'\bпізніше',
        r'\bпотом',
        r'\blater',
        r'\bzastanow',
        r'\bдам знати',
    ),
    'self_followup': (
        r'\bя напишу',
        r'\bсам[а-яіїєґ]* напиш',
        r'\bпотім напиш',
        r'\bвідпиш',
        r'\bif anything.*write',
    ),
    'need_family_consult': (
        r'\bпорадит',
        r'\bчоловік',
        r'\bдружин',
        r'\bмама',
        r'\bтато',
        r'\bmusz[eę] zapyta',
        r'\bwith my husband',
        r'\bwith my wife',
    ),
    'ask_children_first': (
        r'\bскажу дит',
        r'\bзапитаю.*діт',
        r'\bдитина виріш',
        r'\bask.*child',
    ),
    'distance_far': (
        r'\bдалеко',
        r'\bдоїзд',
        r'\bдорога',
        r'\bтрансфер',
        r'\bdojazd',
        r'\btoo far',
    ),
    'silence_wording': (
        r'\bнеактуаль',
        r'\bне зараз',
        r'\bnot now',
        r'\bnie teraz',
    ),
}


class OmniConversationAudit(models.Model):
    _name = 'omni.conversation.audit'
    _description = 'Omnichannel weekly conversation audit'
    _order = 'run_at desc, id desc'

    name = fields.Char(required=True, readonly=True, default='Conversation Audit')
    date_from = fields.Date(required=True, readonly=True)
    date_to = fields.Date(required=True, readonly=True)
    run_at = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now)

    total_threads = fields.Integer(readonly=True)
    total_customer_messages = fields.Integer(readonly=True)
    behavior_hits = fields.Integer(readonly=True)
    client_silence_threads = fields.Integer(readonly=True)
    delayed_client_reply_threads = fields.Integer(readonly=True)
    manager_slow_reply_threads = fields.Integer(readonly=True)
    manager_missing_reply_threads = fields.Integer(readonly=True)

    note = fields.Text(readonly=True)
    line_ids = fields.One2many('omni.conversation.audit.line', 'audit_id', readonly=True)

    def action_refresh(self):
        for rec in self:
            rec._run_audit()
        return True

    def _is_internal_author(self, partner):
        if not partner:
            return False
        partner = partner.sudo()
        return bool(partner.user_ids.filtered(lambda u: u.has_group('base.group_user')))

    def _detect_behavior_tags(self, text):
        txt = _normalize_text(text)
        tags = []
        for key, patterns in _BEHAVIOR_RULES.items():
            if any(re.search(pat, txt) for pat in patterns):
                tags.append(key)
        return tags

    def _run_audit(self):
        self.ensure_one()
        dt_from = datetime.combine(self.date_from, time.min)
        dt_to = datetime.combine(self.date_to, time.max)
        dt_from_str = fields.Datetime.to_string(dt_from)
        dt_to_str = fields.Datetime.to_string(dt_to)

        channels = self.env['discuss.channel'].sudo().search([
            '|',
            ('omni_provider', '!=', False),
            ('channel_type', '=', 'livechat'),
        ])
        messages = self.env['mail.message'].sudo().search([
            ('model', '=', 'discuss.channel'),
            ('res_id', 'in', channels.ids or [0]),
            ('create_date', '>=', dt_from_str),
            ('create_date', '<=', dt_to_str),
            ('message_type', '!=', 'notification'),
        ], order='res_id asc, create_date asc, id asc')

        by_channel = defaultdict(list)
        for msg in messages:
            by_channel[msg.res_id].append(msg)

        behavior_counter = Counter()
        behavior_samples = {}
        client_silence = set()
        delayed_client = set()
        manager_slow = set()
        manager_missing = set()
        customer_messages = 0

        odoobot = self.env.ref('base.partner_root')
        slow_manager_threshold = timedelta(hours=2)
        missing_manager_threshold = timedelta(hours=24)
        client_silence_threshold = timedelta(hours=12)
        delayed_client_threshold = timedelta(hours=24)
        now = fields.Datetime.now()

        for channel in channels:
            thread = by_channel.get(channel.id, [])
            if not thread:
                continue

            # behavior tags by customer messages
            for msg in thread:
                if self._is_internal_author(msg.author_id) or msg.author_id == odoobot:
                    continue
                customer_messages += 1
                tags = self._detect_behavior_tags(msg.body or '')
                for tag in tags:
                    behavior_counter[tag] += 1
                    if tag not in behavior_samples:
                        behavior_samples[tag] = (channel, (msg.body or '')[:300])

            # manager reply quality around explicit handoff asks
            for i, msg in enumerate(thread):
                if self._is_internal_author(msg.author_id) or msg.author_id == odoobot:
                    continue
                txt = _normalize_text(msg.body or '')
                asked_manager = any(k in txt for k in ('менеджер', 'manager', 'operator', 'людина'))
                if not asked_manager:
                    continue
                manager_reply_at = None
                for nxt in thread[i + 1:]:
                    if self._is_internal_author(nxt.author_id):
                        manager_reply_at = nxt.create_date
                        break
                if not manager_reply_at:
                    if now - msg.create_date >= missing_manager_threshold:
                        manager_missing.add(channel.id)
                else:
                    if manager_reply_at - msg.create_date > slow_manager_threshold:
                        manager_slow.add(channel.id)

            # silence psychology signals from conversation rhythm
            for i, msg in enumerate(thread):
                is_bot_or_manager = bool(msg.author_id == odoobot or self._is_internal_author(msg.author_id))
                if not is_bot_or_manager:
                    continue
                next_customer_at = None
                for nxt in thread[i + 1:]:
                    if not self._is_internal_author(nxt.author_id) and nxt.author_id != odoobot:
                        next_customer_at = nxt.create_date
                        break
                if not next_customer_at:
                    if now - msg.create_date >= client_silence_threshold:
                        client_silence.add(channel.id)
                else:
                    if next_customer_at - msg.create_date >= delayed_client_threshold:
                        delayed_client.add(channel.id)

        self.line_ids.unlink()
        lines = []
        for tag, count in behavior_counter.most_common():
            sample_channel = behavior_samples[tag][0] if tag in behavior_samples else False
            sample_text = behavior_samples[tag][1] if tag in behavior_samples else ''
            lines.append((0, 0, {
                'section': 'behavior',
                'key': tag,
                'label': tag.replace('_', ' ').title(),
                'count': count,
                'sample_channel_id': sample_channel.id if sample_channel else False,
                'sample_text': sample_text,
            }))
        lines.extend([
            (0, 0, {
                'section': 'manager_error',
                'key': 'manager_slow_reply_threads',
                'label': 'Manager slow reply (>2h after manager ask)',
                'count': len(manager_slow),
            }),
            (0, 0, {
                'section': 'manager_error',
                'key': 'manager_missing_reply_threads',
                'label': 'Manager missing reply (>24h after manager ask)',
                'count': len(manager_missing),
            }),
            (0, 0, {
                'section': 'silence',
                'key': 'client_silence_threads',
                'label': 'Client silence after bot/manager (>=12h)',
                'count': len(client_silence),
            }),
            (0, 0, {
                'section': 'silence',
                'key': 'delayed_client_reply_threads',
                'label': 'Delayed client reply (>=24h)',
                'count': len(delayed_client),
            }),
        ])

        self.write({
            'total_threads': len(by_channel),
            'total_customer_messages': customer_messages,
            'behavior_hits': sum(behavior_counter.values()),
            'client_silence_threads': len(client_silence),
            'delayed_client_reply_threads': len(delayed_client),
            'manager_slow_reply_threads': len(manager_slow),
            'manager_missing_reply_threads': len(manager_missing),
            'note': (
                'Auto weekly sales psychology audit: behavior tags, client silence, and manager response errors.'
            ),
            'line_ids': lines,
        })

    @api.model
    def omni_cron_run_weekly_audit(self):
        today = fields.Date.context_today(self)
        date_to = today - timedelta(days=1)
        date_from = date_to - timedelta(days=6)
        rec = self.sudo().create({
            'name': 'Conversation Audit %s - %s' % (date_from, date_to),
            'date_from': date_from,
            'date_to': date_to,
        })
        rec._run_audit()
        return rec.id


class OmniConversationAuditLine(models.Model):
    _name = 'omni.conversation.audit.line'
    _description = 'Omnichannel conversation audit line'
    _order = 'section, count desc, id asc'

    audit_id = fields.Many2one('omni.conversation.audit', required=True, ondelete='cascade')
    section = fields.Selection(
        [
            ('behavior', 'Behavior'),
            ('silence', 'Silence'),
            ('manager_error', 'Manager Errors'),
        ],
        required=True,
    )
    key = fields.Char(required=True)
    label = fields.Char(required=True)
    count = fields.Integer(required=True, default=0)
    sample_channel_id = fields.Many2one('discuss.channel', string='Sample thread')
    sample_text = fields.Text()
