# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class OmnichannelWebhookController(http.Controller):
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
