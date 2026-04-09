# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import html2plaintext

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
    partner_id = fields.Many2one('res.partner', string='Клієнт', index=True, ondelete='set null')
    external_thread_id = fields.Char(string='Зовнішній ID', index=True)
    last_message_preview = fields.Char(string='Останнє повідомлення')
    last_message_at = fields.Datetime(string='Час останнього', index=True)
    operator_status = fields.Selection(
        selection=OPERATOR_STATUS_SELECTION,
        string='Статус',
        index=True,
    )
    needaction_counter = fields.Integer(string='Need action')

    _sql_constraints = [
        ('omni_inbox_thread_channel_unique', 'unique(channel_id)', 'One inbox row per Discuss thread.'),
    ]

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

            vals = {
                'thread_name': channel.name or '',
                'provider': channel.omni_provider,
                'partner_id': channel.omni_customer_partner_id.id
                if channel.omni_customer_partner_id
                else False,
                'external_thread_id': channel.omni_external_thread_id or False,
                'last_message_preview': preview,
                'last_message_at': last_at,
                'operator_status': _operator_status_for_channel(channel),
                'needaction_counter': channel.message_needaction_counter or 0,
            }
            row = existing.get(channel.id)
            if row:
                row.sudo().write(vals)
            else:
                self.sudo().create(dict(vals, channel_id=channel.id))

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
