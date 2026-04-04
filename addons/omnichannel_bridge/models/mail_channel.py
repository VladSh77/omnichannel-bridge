# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MailChannel(models.Model):
    _inherit = 'mail.channel'

    omni_provider = fields.Selection(
        selection=lambda self: self.env['omni.integration']._selection_providers(),
        index=True,
    )
    omni_external_thread_id = fields.Char(index=True)
    omni_customer_partner_id = fields.Many2one('res.partner', index=True, ondelete='set null')

    _sql_constraints = [
        (
            'omni_thread_unique',
            'unique(omni_provider, omni_external_thread_id)',
            'A Discuss thread for this messenger conversation already exists.',
        ),
    ]

    def _omni_thread_key_parts(self):
        self.ensure_one()
        return self.omni_provider, self.omni_external_thread_id

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
        channel.channel_partner_ids = [(6, 0, [partner.id, odoobot.id])]
        return channel, True

    def omni_thread_align_customer(self, partner):
        self.ensure_one()
        if not partner:
            return
        self.sudo().write({'omni_customer_partner_id': partner.id})
        if partner.id not in self.channel_partner_ids.ids:
            self.channel_partner_ids = [(4, partner.id)]

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        for channel in self:
            channel._omni_route_operator_reply_to_messenger(message)
        return message

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
