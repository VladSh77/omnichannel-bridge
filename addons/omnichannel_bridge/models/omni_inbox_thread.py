# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models
from odoo.tools import html2plaintext

from .omni_action_utils import ensure_act_window_views, merge_act_window_context

OPERATOR_STATUS_SELECTION = [
    ('needaction', 'Потребує уваги'),
    ('client_waiting', 'Клієнт очікує відповіді'),
    ('bot_on', 'Бот активний'),
    ('manager', 'Менеджер у діалозі'),
    ('idle', 'Без нещодавньої активності'),
]


def _plain_preview(body, limit=240):
    plain = (html2plaintext(body or '') or '').strip()
    if len(plain) > limit:
        plain = plain[:limit] + '…'
    return plain or '—'


def _operator_status_for_channel(channel):
    if channel.message_needaction_counter:
        return 'needaction'
    if channel.omni_bot_paused:
        return 'manager'
    if channel.omni_last_customer_inbound_at and (
        not channel.omni_last_bot_reply_at
        or channel.omni_last_customer_inbound_at > channel.omni_last_bot_reply_at
    ):
        return 'client_waiting'
    if channel.omni_last_bot_reply_at:
        return 'bot_on'
    return 'idle'


def _is_guest_partner(partner):
    if not partner:
        return True
    if partner.email or partner.phone or partner.mobile:
        return False
    name = (partner.name or '').strip().lower()
    if not name:
        return True
    return (
        name.startswith('@')
        or name.startswith('tg_')
        or name.startswith('wa:')
        or name.startswith('meta:')
        or name.startswith('viber:')
        or name.startswith('tiktok:')
        or name.startswith('line:')
    )


class OmniInboxThread(models.Model):
    _name = 'omni.inbox.thread'
    _description = 'Omnichannel operator inbox (mirror of messenger Discuss threads)'
    _order = 'last_message_at desc nulls last, id desc'

    channel_id = fields.Many2one(
        'discuss.channel',
        string='Discuss thread',
        required=True,
        ondelete='cascade',
        index=True,
    )
    thread_name = fields.Char(string='Тред', index=True)
    provider = fields.Selection(
        selection=lambda self: self.env['omni.integration']._selection_providers(),
        string='Канал',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Клієнт',
        index=True,
        ondelete='set null',
        help='Клієнт Odoo, до якого привʼязано поточну розмову.',
    )
    external_thread_id = fields.Char(
        string='Зовнішній ID',
        index=True,
        help='Зовнішній ідентифікатор контакту/треду в каналі провайдера.',
    )
    last_message_preview = fields.Char(string='Останнє повідомлення')
    last_message_at = fields.Datetime(string='Час останнього', index=True)
    operator_status = fields.Selection(
        selection=OPERATOR_STATUS_SELECTION,
        string='Статус',
        index=True,
    )
    needaction_counter = fields.Integer(string='Need action')
    conversation_stage = fields.Selection(
        selection=[
            ('new', 'Новий'),
            ('in_progress', 'В роботі'),
            ('new_message', 'Нове повідомлення'),
            ('close', 'Закрито'),
        ],
        string='Стадія',
        compute='_compute_conversation_stage',
    )
    social_username = fields.Char(
        string='Username',
        compute='_compute_panel_profile',
        help="Ім'я користувача або посилання на профіль у соцмережах.",
    )
    social_profile_url = fields.Char(
        string='URL профілю',
        compute='_compute_panel_profile',
        help='Пряме посилання на профіль клієнта в каналі.',
    )
    bot_name = fields.Char(
        string='Бот',
        compute='_compute_panel_profile',
        help='Назва бота/каналу, через який прийшов цей тред.',
    )
    sp_child_name = fields.Char(
        string="Ім'я дитини",
        help='Значення, зібране ботом під час діалогу.',
    )
    sp_booking_email = fields.Char(
        string='Email бронювання',
        help='Email, який клієнт назвав для бронювання.',
    )
    language_code = fields.Char(
        string='Мова',
        help='Код мови профілю клієнта (можна уточнити вручну).',
    )
    subscription_status_label = fields.Char(
        string='Статус підписки',
        compute='_compute_panel_profile',
        help='Статус/бейдж підписки з профілю каналу.',
    )
    partner_email = fields.Char(
        string='Email (клієнт)',
        compute='_compute_panel_profile',
        help='Email з картки клієнта Odoo.',
    )
    partner_phone = fields.Char(
        string='Телефон (клієнт)',
        compute='_compute_panel_profile',
        help='Телефон з картки клієнта Odoo.',
    )
    message_ids = fields.One2many(
        'mail.message',
        related='channel_id.message_ids',
        string='Повідомлення',
        readonly=True,
    )
    operator_user_ids = fields.Many2many(
        'res.users',
        string='Оператори',
        compute='_compute_operator_user_ids',
        inverse='_inverse_operator_user_ids',
    )
    card_header_html = fields.Html(
        string='Header card',
        compute='_compute_conversation_card_html',
        sanitize=False,
    )
    card_contact_html = fields.Html(
        string='Contact card',
        compute='_compute_conversation_card_html',
        sanitize=False,
    )
    card_channel_profile_html = fields.Html(
        string='Channel profile card',
        compute='_compute_conversation_card_html',
        sanitize=False,
    )
    card_odoo_client_html = fields.Html(
        string='Odoo client card',
        compute='_compute_conversation_card_html',
        sanitize=False,
    )
    card_thread_html = fields.Html(
        string='Thread card',
        compute='_compute_conversation_card_html',
        sanitize=False,
    )

    _sql_constraints = [
        ('omni_inbox_thread_channel_unique', 'unique(channel_id)', 'One inbox row per Discuss thread.'),
    ]

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('omni_inbox_sync_from_channel'):
            return res
        if 'partner_id' in vals:
            Channel = self.env['discuss.channel'].sudo()
            for rec in self:
                ch = rec.channel_id
                if not ch or not ch.exists() or not ch.omni_provider:
                    continue
                if rec.partner_id:
                    Channel.omni_bind_partner_to_channel(ch.id, rec.partner_id.id)
                else:
                    ch.write({'omni_customer_partner_id': False})
        if 'sp_child_name' in vals or 'sp_booking_email' in vals:
            Identity = self.env['omni.partner.identity'].sudo()
            for rec in self:
                ch = rec.channel_id
                if not ch or not ch.exists() or not ch.omni_provider:
                    continue
                ext = (ch.omni_external_thread_id or '').strip()
                if not ext:
                    continue
                identity = Identity.search(
                    [('provider', '=', ch.omni_provider), ('external_id', '=', ext)],
                    limit=1,
                )
                if not identity:
                    continue
                try:
                    meta = json.loads(identity.metadata_json or '{}') or {}
                except Exception:
                    meta = {}
                if not isinstance(meta, dict):
                    meta = {}
                telegram = meta.get('telegram') if isinstance(meta.get('telegram'), dict) else {}
                if 'sp_child_name' in vals:
                    telegram['child_name'] = rec.sp_child_name or ''
                if 'sp_booking_email' in vals:
                    meta['booking_email'] = rec.sp_booking_email or ''
                    telegram['booking_email'] = rec.sp_booking_email or ''
                if telegram:
                    meta['telegram'] = telegram
                identity.write({'metadata_json': json.dumps(meta, ensure_ascii=False)})
        if 'language_code' in vals:
            Identity = self.env['omni.partner.identity'].sudo()
            for rec in self:
                ch = rec.channel_id
                if not ch or not ch.exists() or not ch.omni_provider:
                    continue
                ext = (ch.omni_external_thread_id or '').strip()
                if not ext:
                    continue
                identity = Identity.search(
                    [('provider', '=', ch.omni_provider), ('external_id', '=', ext)],
                    limit=1,
                )
                if not identity:
                    continue
                try:
                    meta = json.loads(identity.metadata_json or '{}') or {}
                except Exception:
                    meta = {}
                if not isinstance(meta, dict):
                    meta = {}
                telegram = meta.get('telegram') if isinstance(meta.get('telegram'), dict) else {}
                telegram['language_code'] = rec.language_code or ''
                meta['telegram'] = telegram
                identity.write({'metadata_json': json.dumps(meta, ensure_ascii=False)})
        return res

    @api.depends('channel_id.active', 'partner_id', 'needaction_counter', 'operator_status')
    def _compute_conversation_stage(self):
        for rec in self:
            if rec.channel_id and not rec.channel_id.active:
                rec.conversation_stage = 'close'
            elif rec.needaction_counter:
                rec.conversation_stage = 'new_message'
            elif not rec.partner_id:
                rec.conversation_stage = 'new'
            else:
                rec.conversation_stage = 'in_progress'

    @api.depends('channel_id', 'partner_id')
    def _compute_panel_profile(self):
        Channel = self.env['discuss.channel'].sudo()
        for rec in self:
            rec.social_username = ''
            rec.social_profile_url = ''
            rec.bot_name = ''
            rec.subscription_status_label = ''
            rec.partner_email = ''
            rec.partner_phone = ''
            channel = rec.channel_id
            if not channel:
                continue
            card = Channel.omni_get_client_info_for_channel(channel.id) or {}
            ident = card.get('identity') or {}
            profile = card.get('channel_profile') or {}
            telegram = card.get('telegram') or {}
            partner = card.get('partner') or {}
            rec.social_username = ident.get('username') or ident.get('external_id') or ''
            rec.social_profile_url = ident.get('profile_url') or ''
            rec.bot_name = (profile.get('bot_name') or telegram.get('bot_name') or '').strip()
            badges = profile.get('badges') if isinstance(profile.get('badges'), list) else []
            rec.subscription_status_label = ', '.join(
                b.get('label', '').strip() for b in badges if isinstance(b, dict) and b.get('label')
            )
            rec.partner_email = (partner.get('email') or '').strip()
            rec.partner_phone = (partner.get('phone') or '').strip()

    @api.depends(
        'channel_id',
        'partner_id',
        'provider',
        'social_username',
        'social_profile_url',
        'bot_name',
        'language_code',
        'external_thread_id',
        'thread_name',
    )
    def _compute_conversation_card_html(self):
        Channel = self.env['discuss.channel'].sudo()
        provider_emoji_map = {
            'telegram': '✈️',
            'meta': '📘',
            'whatsapp': '🟢',
            'twilio_whatsapp': '🟢',
            'viber': '💜',
            'site_livechat': '🌐',
        }
        for rec in self:
            rec.card_header_html = ''
            rec.card_contact_html = ''
            rec.card_channel_profile_html = ''
            rec.card_odoo_client_html = ''
            rec.card_thread_html = ''
            channel = rec.channel_id
            if not channel:
                continue
            card = Channel.omni_get_client_info_for_channel(channel.id) or {}
            ident = card.get('identity') or {}
            partner = card.get('partner') or {}
            profile = card.get('channel_profile') or {}
            telegram = card.get('telegram') or {}
            badges = profile.get('badges') if isinstance(profile.get('badges'), list) else []
            badge_labels = [
                (b.get('label') or '').strip()
                for b in badges
                if isinstance(b, dict) and b.get('label')
            ]
            provider = rec.provider or ''
            provider_emoji = provider_emoji_map.get(provider, '')
            provider_label = card.get('provider_label') or provider or 'Omnichannel'
            display_name = (
                (partner.get('name') or '').strip()
                or (ident.get('display_name') or '').strip()
                or 'Клієнт'
            )
            username = (
                (ident.get('username') or '').strip()
                or (ident.get('external_id') or '').strip()
            )
            profile_url = (ident.get('profile_url') or '').strip()
            language_code = (ident.get('language_code') or rec.language_code or '').strip()
            booking_email = (
                (ident.get('booking_email') or '').strip()
                or (telegram.get('booking_email') or '').strip()
            )
            header_lines = [
                "<div class='oe_title'>",
                f"<h2>{display_name}</h2>",
                f"<div>{provider_emoji} {provider_label}</div>",
            ]
            if badge_labels:
                header_lines.append(
                    "<div>%s</div>" % " | ".join(badge_labels[:4])
                )
            header_lines.append("</div>")
            rec.card_header_html = "".join(header_lines)

            contact_lines = ["<div><strong>Контакт</strong></div>"]
            if username and profile_url:
                contact_lines.append(
                    "<div><a href='%s' target='_blank'>%s</a></div>"
                    % (profile_url, username)
                )
            elif username:
                contact_lines.append("<div>%s</div>" % username)
            if partner.get('email'):
                contact_lines.append("<div>Email: %s</div>" % partner.get('email'))
            if partner.get('phone'):
                contact_lines.append("<div>Телефон: %s</div>" % partner.get('phone'))
            if language_code:
                contact_lines.append("<div>Мова: %s</div>" % language_code)
            rec.card_contact_html = "".join(contact_lines)

            section = profile.get('section') if isinstance(profile.get('section'), dict) else {}
            section_title = (section.get('title') or 'Профіль каналу').strip()
            section_rows = section.get('rows') if isinstance(section.get('rows'), list) else []
            profile_lines = ["<div><strong>%s</strong></div>" % section_title]
            for row in section_rows[:8]:
                if not isinstance(row, dict):
                    continue
                if row.get('kind') == 'link' and row.get('href') and row.get('text'):
                    profile_lines.append(
                        "<div><a href='%s' target='_blank'>%s</a></div>"
                        % (row['href'], row['text'])
                    )
                elif row.get('text'):
                    profile_lines.append("<div>%s</div>" % row['text'])
            if rec.bot_name:
                profile_lines.append("<div>Бот: %s</div>" % rec.bot_name)
            if booking_email:
                profile_lines.append("<div>Email бронювання: %s</div>" % booking_email)
            rec.card_channel_profile_html = "".join(profile_lines)

            odoo_lines = ["<div><strong>Клієнт Odoo</strong></div>"]
            if rec.partner_id:
                odoo_lines.append("<div>%s</div>" % (rec.partner_id.display_name or '—'))
                if rec.partner_email:
                    odoo_lines.append("<div>Email: %s</div>" % rec.partner_email)
                if rec.partner_phone:
                    odoo_lines.append("<div>Телефон: %s</div>" % rec.partner_phone)
            else:
                odoo_lines.append("<div>Не ідентифіковано</div>")
            rec.card_odoo_client_html = "".join(odoo_lines)

            thread_lines = [
                "<div><strong>Тред</strong></div>",
                "<div>%s</div>" % ((rec.thread_name or '').strip() or '—'),
                "<div><code>%s</code></div>" % ((rec.external_thread_id or '').strip() or '—'),
            ]
            if profile.get('thread_user_id'):
                caption = profile.get('thread_user_caption') or 'Messenger user id'
                thread_lines.append(
                    "<div>%s: <code>%s</code></div>" % (caption, profile.get('thread_user_id'))
                )
            rec.card_thread_html = "".join(thread_lines)

    @api.depends('channel_id')
    def _compute_operator_user_ids(self):
        for rec in self:
            users = self.env['res.users']
            channel = rec.channel_id
            if channel:
                partners = channel.sudo().channel_member_ids.partner_id
                users = partners.user_ids.filtered(
                    lambda u: not u.share and u.active and not u._is_public()
                )
            rec.operator_user_ids = users

    def _inverse_operator_user_ids(self):
        for rec in self:
            channel = rec.channel_id.sudo()
            if not channel:
                continue
            partner_ids = rec.operator_user_ids.mapped('partner_id').ids
            if partner_ids:
                channel.add_members(partner_ids=partner_ids)
            current_user_partners = channel.channel_member_ids.partner_id.user_ids.filtered(
                lambda u: not u.share and u.active and not u._is_public()
            ).mapped('partner_id').ids
            remove_partner_ids = [pid for pid in current_user_partners if pid not in partner_ids]
            if remove_partner_ids:
                channel.channel_member_ids.filtered(
                    lambda m: m.partner_id.id in remove_partner_ids
                ).unlink()

    def action_open_identify_wizard(self):
        self.ensure_one()
        raw = self.env['ir.actions.act_window']._for_xml_id(
            'omnichannel_bridge.action_omni_conversation_identity_wizard'
        )
        act = merge_act_window_context(dict(raw), {'default_channel_id': self.channel_id.id})
        return ensure_act_window_views(act)

    def action_open_quick_bind_wizard(self):
        self.ensure_one()
        raw = self.env['ir.actions.act_window']._for_xml_id(
            'omnichannel_bridge.action_omni_partner_bind_wizard'
        )
        act = merge_act_window_context(dict(raw), {'default_channel_id': self.channel_id.id})
        return ensure_act_window_views(act)

    def action_open_partner_form(self):
        self.ensure_one()
        if not self.partner_id:
            return False
        act = {
            'type': 'ir.actions.act_window',
            'name': _('Картка клієнта'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }
        return ensure_act_window_views(act)

    @api.model
    def _sync_from_discuss_channels(self, channels):
        """Upsert dashboard rows from discuss.channel records (omnichannel only)."""
        Channel = self.env['discuss.channel'].sudo()
        channels = Channel.browse(channels.ids).exists().filtered('omni_provider')
        if not channels:
            return self.browse()

        rows = {}
        if channels.ids:
            self.env.cr.execute(
                """
                SELECT DISTINCT ON (res_id) res_id, body, date
                FROM mail_message
                WHERE model = 'discuss.channel'
                  AND message_type = 'comment'
                  AND res_id = ANY(%s)
                ORDER BY res_id, id DESC
                """,
                (list(channels.ids),),
            )
            for res_id, body, mdate in self.env.cr.fetchall():
                rows[res_id] = (body, mdate)

        existing = {
            r.channel_id.id: r
            for r in self.sudo().search([('channel_id', 'in', channels.ids)])
        }

        for channel in channels:
            tpl = rows.get(channel.id)
            if tpl:
                body, mdate = tpl
                preview = _plain_preview(body)
                last_at = mdate
            else:
                preview = '—'
                last_at = False

            card = Channel.omni_get_client_info_for_channel(channel.id) or {}
            ident = card.get('identity') or {}
            profile = card.get('channel_profile') or {}
            telegram = card.get('telegram') or {}
            extracted_child = (
                profile.get('child_name')
                or telegram.get('child_name')
                or ''
            )
            extracted_booking = (
                ident.get('booking_email')
                or telegram.get('booking_email')
                or ''
            )
            channel_partner = channel.omni_customer_partner_id
            if _is_guest_partner(channel_partner):
                channel_partner = self.env.ref('base.public_partner', raise_if_not_found=False)
            vals = {
                'thread_name': channel.name or '',
                'provider': channel.omni_provider,
                'partner_id': channel_partner.id if channel_partner else False,
                'external_thread_id': channel.omni_external_thread_id or False,
                'last_message_preview': preview,
                'last_message_at': last_at,
                'operator_status': _operator_status_for_channel(channel),
                'needaction_counter': channel.message_needaction_counter or 0,
            }
            row = existing.get(channel.id)
            if row:
                vals['sp_child_name'] = row.sp_child_name or extracted_child
                vals['sp_booking_email'] = row.sp_booking_email or extracted_booking
                vals['language_code'] = row.language_code or (ident.get('language_code') or '').strip()
                row.sudo().with_context(omni_inbox_sync_from_channel=True).write(vals)
            else:
                self.sudo().create(
                    dict(
                        vals,
                        channel_id=channel.id,
                        sp_child_name=extracted_child,
                        sp_booking_email=extracted_booking,
                        language_code=(ident.get('language_code') or '').strip(),
                    )
                )

        return self.search([('channel_id', 'in', channels.ids)])

    def action_open_in_discuss(self):
        self.ensure_one()
        channel = self.channel_id
        if not channel or not channel.exists():
            return False
        base = (
            self.env['ir.config_parameter']
            .sudo()
            .get_param('web.base.url', '')
            .rstrip('/')
        )
        if not base:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': '%s/web#action=mail.action_discuss&active_id=discuss.channel_%s'
            % (base, channel.id),
            'target': 'self',
        }

    def action_refresh_profile(self):
        self.ensure_one()
        if self.channel_id:
            self.env['discuss.channel'].sudo().omni_refresh_client_info_for_channel(self.channel_id.id)
            self._sync_from_discuss_channels(self.channel_id)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }

    def action_close_conversation(self):
        self.ensure_one()
        if self.channel_id:
            self.channel_id.sudo().write({'active': False})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_reopen_conversation(self):
        self.ensure_one()
        if self.channel_id:
            self.channel_id.sudo().write({'active': True})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_sync_all_from_threads(self):
        channels = self.env['discuss.channel'].sudo().search([('omni_provider', '!=', False)])
        self._sync_from_discuss_channels(channels)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Інбокс',
                'message': 'Оновлено рядки з Discuss-тредів (%s).' % len(channels),
                'type': 'success',
                'sticky': False,
            },
        }
