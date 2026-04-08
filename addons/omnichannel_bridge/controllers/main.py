# -*- coding: utf-8 -*-
import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)
_WEBHOOK_IP_BUCKET = {}


class OmnichannelWebhookController(http.Controller):
    def _omni_rate_limit_allowed(self):
        ip = (
            request.httprequest.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            request.httprequest.remote_addr or
            'unknown'
        )
        icp = request.env['ir.config_parameter'].sudo()
        try:
            rpm = max(0, int(icp.get_param('omnichannel_bridge.webhook_rate_limit_per_minute', '0')))
        except (TypeError, ValueError):
            rpm = 0
        if rpm <= 0:
            return True
        now = int(time.time())
        win_start = now - 60
        bucket = [ts for ts in _WEBHOOK_IP_BUCKET.get(ip, []) if ts >= win_start]
        if len(bucket) >= rpm:
            _WEBHOOK_IP_BUCKET[ip] = bucket
            return False
        bucket.append(now)
        _WEBHOOK_IP_BUCKET[ip] = bucket
        return True

    @http.route(
        '/omni/webhook/<string:provider>',
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
    )
    def omnichannel_webhook(self, provider, **kwargs):
        if request.httprequest.method == 'GET':
            return self._omni_webhook_get(provider)
        payload = request.httprequest.get_data() or b'{}'
        max_bytes_raw = (
            request.env['ir.config_parameter']
            .sudo()
            .get_param('omnichannel_bridge.webhook_max_body_bytes', '1048576')
        )
        try:
            max_bytes = max(4096, int(max_bytes_raw))
        except (TypeError, ValueError):
            max_bytes = 1048576
        if len(payload) > max_bytes:
            _logger.warning(
                'Omnichannel webhook body too large: provider=%s size=%s max=%s',
                provider,
                len(payload),
                max_bytes,
            )
            return request.make_json_response(
                {'ok': False, 'error': 'payload_too_large'},
                status=413,
            )
        if not self._omni_rate_limit_allowed():
            return request.make_json_response(
                {'ok': False, 'error': 'rate_limited'},
                status=429,
            )
        headers = {k: v for k, v in request.httprequest.headers.items()}
        try:
            result = request.env['omni.bridge'].sudo().omni_process_webhook(
                provider,
                payload,
                headers,
            )
            return request.make_json_response(result)
        except Exception:
            _logger.exception('Omnichannel webhook failed (provider=%s)', provider)
            return request.make_json_response({'ok': False, 'error': 'server_error'}, status=500)

    def _omni_webhook_get(self, provider):
        if provider not in ('meta', 'whatsapp'):
            return request.make_response('Method Not Allowed', status=405)
        mode = request.params.get('hub.mode')
        token = request.params.get('hub.verify_token')
        challenge = request.params.get('hub.challenge')
        icp = request.env['ir.config_parameter'].sudo()
        if provider == 'whatsapp':
            expected = (
                icp.get_param('omnichannel_bridge.whatsapp_verify_token', '').strip() or
                icp.get_param('omnichannel_bridge.meta_verify_token', '').strip()
            )
        else:
            expected = icp.get_param('omnichannel_bridge.meta_verify_token', '').strip()
        if mode == 'subscribe' and token and challenge and expected and token == expected:
            return request.make_response(challenge, headers=[('Content-Type', 'text/plain')])
        return request.make_response('Forbidden', status=403)
