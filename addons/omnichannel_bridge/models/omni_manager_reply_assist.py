# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OmniManagerReplyAssist(models.TransientModel):
    _name = 'omni.manager.reply.assist'
    _description = 'Manager reply quality assistant'

    partner_id = fields.Many2one('res.partner')
    source_text = fields.Text(required=True)
    improved_text = fields.Text(readonly=True)

    def action_suggest(self):
        for wizard in self:
            partner = wizard.partner_id.sudo() if wizard.partner_id else self.env['res.partner']
            profile = (
                self.env['ir.config_parameter'].sudo().get_param(
                    'omnichannel_bridge.llm_assistant_profile',
                    'default',
                ) or 'default'
            ).strip()
            prompt = (
                'You are assistant_profile=%s. Rewrite manager reply with clear, polite, premium tone. '
                'Keep factual meaning, remove pressure, keep concise. '
                'Do not add new facts. Return only rewritten text.'
            ) % profile
            ai = self.env['omni.ai'].sudo()
            icp = self.env['ir.config_parameter'].sudo()
            backend = (icp.get_param('omnichannel_bridge.llm_backend') or 'ollama').strip()
            improved = ai._llm_complete(backend, icp, prompt, wizard.source_text or '')
            wizard.improved_text = (improved or wizard.source_text or '').strip()
            if partner:
                partner.omni_recompute_lead_score(reason='manager_reply_assist')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'omni.manager.reply.assist',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
