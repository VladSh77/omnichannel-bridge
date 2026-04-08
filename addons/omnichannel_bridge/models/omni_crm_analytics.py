# -*- coding: utf-8 -*-
import re
from collections import Counter
from datetime import datetime, time, timedelta

from odoo import api, fields, models


_OBJECTION_RE = re.compile(r'objection_detected:\s*([a-z_]+)', re.IGNORECASE)


class OmniCrmAnalyticsWizard(models.TransientModel):
    _name = 'omni.crm.analytics.wizard'
    _description = 'Omnichannel CRM analytics'

    date_from = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self) - timedelta(days=30),
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    total_threads = fields.Integer(readonly=True)
    total_leads = fields.Integer(readonly=True)
    handoff_threads = fields.Integer(readonly=True)
    avg_response_seconds = fields.Float(readonly=True, digits=(16, 2))
    objection_events = fields.Integer(readonly=True)
    purchase_intent_events = fields.Integer(readonly=True)
    bot_reply_threads = fields.Integer(readonly=True)
    human_reply_threads = fields.Integer(readonly=True)
    mixed_reply_threads = fields.Integer(readonly=True)
    tg_new_contacts = fields.Integer(readonly=True)
    coupon_redemptions_count = fields.Integer(readonly=True)
    coupon_discount_total = fields.Float(readonly=True, digits=(16, 2))
    coupon_orders_revenue = fields.Float(readonly=True, digits=(16, 2))
    ad_spend_amount = fields.Float(digits=(16, 2))
    romi_percent = fields.Float(readonly=True, digits=(16, 2))
    line_ids = fields.One2many(
        'omni.crm.analytics.wizard.line',
        'wizard_id',
        readonly=True,
    )

    def _dt_start_end(self):
        self.ensure_one()
        start_dt = datetime.combine(self.date_from, time.min)
        end_dt = datetime.combine(self.date_to, time.max)
        return fields.Datetime.to_string(start_dt), fields.Datetime.to_string(end_dt)

    def action_refresh(self):
        for wizard in self:
            wizard._compute_metrics()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'omni.crm.analytics.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _compute_metrics(self):
        self.ensure_one()
        date_start, date_end = self._dt_start_end()

        channel_domain = [
            ('omni_provider', '!=', False),
            ('create_date', '>=', date_start),
            ('create_date', '<=', date_end),
        ]
        channels = self.env['discuss.channel'].sudo().search(channel_domain)
        self.total_threads = len(channels)

        provider_counts = Counter(channels.mapped('omni_provider'))
        partner_stage_counts = Counter(
            channels.mapped('omni_customer_partner_id').filtered(lambda p: p).mapped('omni_sales_stage')
        )

        self.handoff_threads = sum(1 for ch in channels if ch.omni_customer_partner_id.omni_sales_stage == 'handoff')

        lead_domain = [
            ('create_date', '>=', date_start),
            ('create_date', '<=', date_end),
            ('partner_id', '!=', False),
        ]
        leads = self.env['crm.lead'].sudo().search(lead_domain)
        omni_partner_ids = set(channels.mapped('omni_customer_partner_id').ids)
        self.total_leads = sum(1 for lead in leads if lead.partner_id.id in omni_partner_ids)

        # Response time proxy: manager reply timestamp after last inbound on thread.
        deltas = []
        for channel in channels:
            if (
                channel.omni_last_customer_inbound_at
                and channel.omni_last_human_reply_at
                and channel.omni_last_human_reply_at >= channel.omni_last_customer_inbound_at
            ):
                delta = channel.omni_last_human_reply_at - channel.omni_last_customer_inbound_at
                deltas.append(delta.total_seconds())
        self.avg_response_seconds = (sum(deltas) / len(deltas)) if deltas else 0.0
        bot_threads = 0
        human_threads = 0
        mixed_threads = 0
        for channel in channels:
            has_bot = bool(channel.omni_last_bot_reply_at)
            has_human = bool(channel.omni_last_human_reply_at)
            if has_bot and has_human:
                mixed_threads += 1
            elif has_bot:
                bot_threads += 1
            elif has_human:
                human_threads += 1
        self.bot_reply_threads = bot_threads
        self.human_reply_threads = human_threads
        self.mixed_reply_threads = mixed_threads

        message_domain = [
            ('model', '=', 'discuss.channel'),
            ('res_id', 'in', channels.ids or [0]),
            ('create_date', '>=', date_start),
            ('create_date', '<=', date_end),
        ]
        messages = self.env['mail.message'].sudo().search(message_domain)
        objection_counter = Counter()
        purchase_intent = 0
        for msg in messages:
            body = (msg.body or '')
            match = _OBJECTION_RE.search(body)
            if match:
                objection_counter[match.group(1)] += 1
            if 'purchase_intent_detected' in body:
                purchase_intent += 1
        self.objection_events = sum(objection_counter.values())
        self.purchase_intent_events = purchase_intent

        tg_identities = self.env['omni.partner.identity'].sudo().search([
            ('provider', '=', 'telegram'),
            ('create_date', '>=', date_start),
            ('create_date', '<=', date_end),
        ])
        self.tg_new_contacts = len(tg_identities)

        redemptions = self.env['omni.coupon.redemption'].sudo().search([
            ('redeemed_at', '>=', date_start),
            ('redeemed_at', '<=', date_end),
        ])
        self.coupon_redemptions_count = len(redemptions)
        self.coupon_discount_total = sum(redemptions.mapped('discount_amount'))
        self.coupon_orders_revenue = sum(redemptions.mapped('order_id.amount_total'))
        spend = float(self.ad_spend_amount or 0.0)
        if spend > 0:
            self.romi_percent = ((self.coupon_orders_revenue - spend) / spend) * 100.0
        else:
            self.romi_percent = 0.0

        line_vals = []
        for provider, count in sorted(provider_counts.items()):
            line_vals.append((0, 0, {
                'section': 'provider',
                'key': provider,
                'label': provider,
                'count': count,
            }))
        for stage, count in sorted(partner_stage_counts.items()):
            line_vals.append((0, 0, {
                'section': 'stage',
                'key': stage,
                'label': stage,
                'count': count,
            }))
        for reason, count in sorted(objection_counter.items()):
            line_vals.append((0, 0, {
                'section': 'objection',
                'key': reason,
                'label': reason,
                'count': count,
            }))
        line_vals.append((0, 0, {
            'section': 'campaign',
            'key': 'telegram_new_contacts',
            'label': 'Telegram new contacts',
            'count': self.tg_new_contacts,
        }))
        line_vals.append((0, 0, {
            'section': 'campaign',
            'key': 'coupon_redemptions',
            'label': 'Coupon redemptions',
            'count': self.coupon_redemptions_count,
        }))
        line_vals.append((0, 0, {
            'section': 'reply_owner',
            'key': 'bot_only_threads',
            'label': 'Bot-only replied threads',
            'count': self.bot_reply_threads,
        }))
        line_vals.append((0, 0, {
            'section': 'reply_owner',
            'key': 'human_only_threads',
            'label': 'Manager-only replied threads',
            'count': self.human_reply_threads,
        }))
        line_vals.append((0, 0, {
            'section': 'reply_owner',
            'key': 'mixed_threads',
            'label': 'Mixed bot+manager replied threads',
            'count': self.mixed_reply_threads,
        }))
        self.line_ids.unlink()
        if line_vals:
            self.write({'line_ids': line_vals})

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._compute_metrics()
        return rec


class OmniCrmAnalyticsWizardLine(models.TransientModel):
    _name = 'omni.crm.analytics.wizard.line'
    _description = 'Omnichannel CRM analytics line'

    wizard_id = fields.Many2one('omni.crm.analytics.wizard', required=True, ondelete='cascade')
    section = fields.Selection(
        selection=[
            ('provider', 'By Provider'),
            ('stage', 'By Sales Stage'),
            ('objection', 'By Objection Type'),
            ('campaign', 'Campaign Metrics'),
            ('reply_owner', 'By Reply Owner'),
        ],
        required=True,
    )
    key = fields.Char(required=True)
    label = fields.Char(required=True)
    count = fields.Integer(required=True)
