# -*- coding: utf-8 -*-
import hashlib
import json

from odoo import fields, models


class OmniWebhookEvent(models.Model):
    _name = 'omni.webhook.event'
    _description = 'Omnichannel webhook idempotency registry'
    _order = 'id desc'

    provider = fields.Selection(
        selection=lambda self: self.env['omni.integration']._selection_providers(),
        required=True,
        index=True,
    )
    external_event_id = fields.Char(index=True)
    payload_hash = fields.Char(required=True, index=True)
    state = fields.Selection(
        selection=[
            ('received', 'Received'),
            ('processed', 'Processed'),
            ('failed', 'Failed'),
        ],
        default='received',
        required=True,
        index=True,
    )
    error_message = fields.Text()
    received_at = fields.Datetime(default=fields.Datetime.now, required=True)
    processed_at = fields.Datetime()

    _sql_constraints = [
        (
            'omni_webhook_event_unique_provider_external',
            'unique(provider, external_event_id)',
            'Webhook event with this provider and external id already exists.',
        ),
        (
            'omni_webhook_event_unique_provider_hash',
            'unique(provider, payload_hash)',
            'Webhook event with this provider and payload hash already exists.',
        ),
    ]

    @staticmethod
    def omni_payload_hash(payload):
        if isinstance(payload, (bytes, bytearray)):
            raw = bytes(payload)
        elif isinstance(payload, str):
            raw = payload.encode('utf-8')
        else:
            raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()
