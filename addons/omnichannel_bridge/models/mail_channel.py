# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MailChannel(models.Model):
    _inherit = 'discuss.channel'

    omni_provider = fields.Selection(
        selection=lambda self: self.env['omni.integration']._selection_providers(),
        index=True,
    )
    omni_external_thread_id = fields.Char(index=True)
    omni_customer_partner_id = fields.Many2one('res.partner', index=True, ondelete='set null')
    omni_bot_paused = fields.Boolean(default=False, index=True)
    omni_bot_pause_reason = fields.Char()
    omni_last_human_reply_at = fields.Datetime()
    omni_last_bot_reply_at = fields.Datetime()

    _sql_constraints = [
        (
            'omni_thread_unique',
            'unique(omni_provider, omni_external_thread_id)',
            'A Discuss thread for this messenger conversation already exists.',
        ),
    ]

    def action_omni_pause_bot(self):
        self.sudo().write({
            'omni_bot_paused': True,
            'omni_bot_pause_reason': 'manual_manager_takeover',
        })
        return True

    def action_omni_resume_bot(self):
        self.sudo().write({
            'omni_bot_paused': False,
            'omni_bot_pause_reason': False,
        })
        return True

    def _omni_thread_key_parts(self):
        self.ensure_one()
        return self.omni_provider, self.omni_external_thread_id

    def _omni_is_website_livechat_channel(self):
        self.ensure_one()
        if self.omni_provider == 'site_livechat':
            return True
        if 'livechat_channel_id' in self._fields and self.livechat_channel_id:
            return True
        return self.channel_type == 'livechat'

    def _omni_is_internal_author(self, partner):
        if not partner:
            return False
        return bool(partner.user_ids.filtered(lambda u: u.has_group('base.group_user')))

    def _omni_client_requests_human(self, text):
        lowered = (text or '').lower()
        keys = (
            'менеджер',
            'оператор',
            'людина',
            'з\'єднайте з менеджером',
            'покличте менеджера',
            'human',
            'manager',
            'operator',
        )
        return any(k in lowered for k in keys)

    @api.model
    def omni_get_or_create_thread(self, provider, external_thread_id, partner, label):
        existing = self.sudo().search([
            ('omni_provider', '=', provider),
            ('omni_external_thread_id', '=', str(external_thread_id)),
        ], limit=1)
        if existing:
            existing.sudo().omni_thread_align_customer(partner)
            return existing, False
        odoobot = self.env.ref('base.partner_root')
        channel = self.sudo().create({
            'name': label or _('[%(provider)s] %(name)s') % {
                'provider': provider,
                'name': partner.display_name,
            },
            'channel_type': 'group',
            'omni_provider': provider,
            'omni_external_thread_id': str(external_thread_id),
            'omni_customer_partner_id': partner.id,
        })
        if hasattr(channel, 'add_members'):
            channel.add_members(partner_ids=[partner.id, odoobot.id])
        else:
            channel.channel_partner_ids = [(6, 0, [partner.id, odoobot.id])]
        return channel, True

    def omni_thread_align_customer(self, partner):
        self.ensure_one()
        if not partner:
            return
        self.sudo().write({'omni_customer_partner_id': partner.id})
        member_partner_ids = self.channel_partner_ids.ids if 'channel_partner_ids' in self._fields else []
        if partner.id not in member_partner_ids:
            if hasattr(self, 'add_members'):
                self.add_members(partner_ids=[partner.id])
            else:
                self.channel_partner_ids = [(4, partner.id)]

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        odoobot = self.env.ref('base.partner_root')
        for channel in self:
            if message.author_id == odoobot:
                channel.sudo().write({'omni_last_bot_reply_at': fields.Datetime.now()})
            elif channel.omni_customer_partner_id and message.author_id != channel.omni_customer_partner_id:
                channel.sudo().write({'omni_last_human_reply_at': fields.Datetime.now()})
            channel._omni_handle_website_livechat_inbound(message)
            channel._omni_route_operator_reply_to_messenger(message)
        return message

    def _omni_handle_website_livechat_inbound(self, message):
        self.ensure_one()
        if self.omni_provider:
            # Messenger channels are handled by webhook ingest flow.
            return
        if not self._omni_is_website_livechat_channel():
            return
        icp = self.env['ir.config_parameter'].sudo()
        if str(icp.get_param('omnichannel_bridge.site_livechat_enabled', 'True')).lower() not in (
            '1', 'true', 'yes',
        ):
            return
        body = (message.body or '').strip()
        if not body:
            return
        if message.subtype_id and getattr(message.subtype_id, 'internal', False):
            return
        author = message.author_id
        odoobot = self.env.ref('base.partner_root')
        if not author or author == odoobot:
            return
        if self._omni_is_internal_author(author):
            # Manager joined the dialog -> stop bot until explicit resume.
            self.sudo().write({
                'omni_last_human_reply_at': fields.Datetime.now(),
                'omni_bot_paused': True,
                'omni_bot_pause_reason': 'manager_joined_livechat',
            })
            return
        if self._omni_client_requests_human(body):
            self.sudo().write({
                'omni_bot_paused': True,
                'omni_bot_pause_reason': 'client_requested_human',
            })
            self.message_post(
                body=_('Передаю діалог менеджеру. Будь ласка, зачекайте трохи.'),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=odoobot.id,
            )
            self.env['omni.notify'].sudo().notify_escalation(
                channel=self,
                partner=author,
                reason='🧑‍💼 Клієнт попросив менеджера у live chat',
            )
            return
        # Website visitor message -> same AI queue and sales/memory pipeline.
        self.sudo().write({'omni_customer_partner_id': author.id})
        self.env['omni.sales.intel'].sudo().omni_apply_inbound_triggers(
            channel=self,
            partner=author,
            text=body,
            provider='site_livechat',
        )
        self.env['omni.memory'].sudo().omni_apply_inbound_learning(author, body)
        self.env['omni.ai.job'].sudo().omni_enqueue_autoreply(
            channel=self,
            partner=author,
            text=body,
            provider='site_livechat',
            # Bot-first for website chat: respond immediately.
            delay_seconds=0,
        )

    def _omni_route_operator_reply_to_messenger(self, message):
        self.ensure_one()
        if not self.omni_provider or not self.omni_external_thread_id:
            return
        author = message.author_id
        if not author or author == self.omni_customer_partner_id:
            return
        if message.subtype_id and getattr(message.subtype_id, 'internal', False):
            return
        body = message.body
        if not body:
            return
        try:
            self.env['omni.bridge'].sudo().omni_send_outbound(
                self.omni_provider,
                self.omni_external_thread_id,
                self.omni_customer_partner_id,
                body,
            )
        except Exception:
            _logger.exception('Omnichannel outbound failed for channel %s', self.id)
