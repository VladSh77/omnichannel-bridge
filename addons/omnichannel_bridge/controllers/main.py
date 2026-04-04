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
        if provider != 'meta':
            return request.make_response('Method Not Allowed', status=405)
        mode = request.params.get('hub.mode')
        token = request.params.get('hub.verify_token')
        challenge = request.params.get('hub.challenge')
        expected = (
            request.env['ir.config_parameter']
            .sudo()
            .get_param('omnichannel_bridge.meta_verify_token', '')
        )
        if mode == 'subscribe' and token and challenge and expected and token == expected:
            return request.make_response(challenge, headers=[('Content-Type', 'text/plain')])
        return request.make_response('Forbidden', status=403)
