# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.fields import Datetime

_logger = logging.getLogger(__name__)


class OmniAiJob(models.Model):
    _name = 'omni.ai.job'
    _description = 'Asynchronous AI reply job'
    _order = 'id desc'

    channel_id = fields.Many2one('discuss.channel', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', ondelete='set null', index=True)
    provider = fields.Selection(
        selection=lambda self: self.env['omni.integration']._selection_providers(),
        required=True,
        index=True,
    )
    user_text = fields.Text(required=True)
    state = fields.Selection(
        selection=[
            ('queued', 'Queued'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='queued',
        required=True,
        index=True,
    )
    attempt_count = fields.Integer(default=0, required=True)
    max_attempts = fields.Integer(default=3, required=True)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, index=True)
    last_error = fields.Text()

    @api.model
    def omni_enqueue_autoreply(self, channel, partner, text, provider, delay_seconds=0):
        if not channel or not text:
            return False
        # Keep only the freshest pending request per thread/provider to avoid
        # backlog floods after temporary outages of LLM/backend.
        stale = self.sudo().search([
            ('channel_id', '=', channel.id),
            ('provider', '=', provider),
            ('state', '=', 'queued'),
        ])
        if stale:
            stale.write({
                'state': 'cancelled',
                'last_error': 'superseded_by_new_inbound',
            })
        next_at = fields.Datetime.now()
        if delay_seconds and delay_seconds > 0:
            next_at = Datetime.now() + timedelta(seconds=int(delay_seconds))
        return self.sudo().create({
            'channel_id': channel.id,
            'partner_id': partner.id if partner else False,
            'provider': provider,
            'user_text': text,
            'next_attempt_at': next_at,
        })

    def action_retry(self):
        for job in self.sudo():
            if job.state in ('failed', 'cancelled'):
                job.write({
                    'state': 'queued',
                    'next_attempt_at': fields.Datetime.now(),
                    'last_error': False,
                })
        return True

    def action_cancel(self):
        self.sudo().write({'state': 'cancelled'})
        return True

    @api.model
    def omni_cron_process_jobs(self, limit=30):
        now = fields.Datetime.now()
        jobs = self.sudo().search(
            [
                ('state', '=', 'queued'),
                ('next_attempt_at', '<=', now),
            ],
            order='id asc',
            limit=max(1, int(limit)),
        )
        for job in jobs:
            job._omni_run_single()

    def _omni_run_single(self):
        self.ensure_one()
        if self.state != 'queued':
            return

        channel = self.channel_id.sudo()
        partner = self.partner_id.sudo() if self.partner_id else False

        if channel.omni_bot_paused:
            self.sudo().write({
                'state': 'cancelled',
                'last_error': 'bot_paused_on_channel',
            })
            return

        # Do not let bot race with recent human answer in messenger threads.
        # Website livechat is bot-first and should reply immediately.
        if self.provider != 'site_livechat' and channel.omni_last_human_reply_at:
            icp = self.env['ir.config_parameter'].sudo()
            try:
                guard_seconds = int(icp.get_param('omnichannel_bridge.sla_no_human_seconds', '180'))
            except ValueError:
                guard_seconds = 180
            guard_seconds = max(30, guard_seconds)
            now = Datetime.now()
            delta = now - channel.omni_last_human_reply_at
            if delta < timedelta(seconds=guard_seconds):
                self.sudo().write({
                    'state': 'cancelled',
                    'last_error': 'recent_human_reply',
                })
                return

        current_attempt = self.attempt_count + 1
        self.sudo().write({
            'state': 'running',
            'attempt_count': current_attempt,
            'last_error': False,
        })
        try:
            self.env['omni.ai'].sudo().omni_maybe_autoreply(
                channel=channel,
                partner=partner,
                text=self.user_text,
                provider=self.provider,
            )
            self.sudo().write({
                'state': 'done',
            })
        except Exception as err:
            _logger.exception('AI job failed id=%s', self.id)
            if current_attempt >= self.max_attempts:
                self.sudo().write({
                    'state': 'failed',
                    'last_error': str(err),
                })
                # Fallback final customer message if AI failed repeatedly.
                self.env['omni.ai'].sudo()._omni_send_fallback(
                    channel=channel,
                    partner=partner,
                    icp=self.env['ir.config_parameter'].sudo(),
                )
                return
            next_try = Datetime.now() + timedelta(seconds=30 * current_attempt)
            self.sudo().write({
                'state': 'queued',
                'next_attempt_at': next_try,
                'last_error': str(err),
            })
