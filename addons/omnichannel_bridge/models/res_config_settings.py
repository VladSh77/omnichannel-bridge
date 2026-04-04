# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    omnichannel_new_contact_as_lead = fields.Boolean(
        string='Create CRM opportunity for new chat contacts',
        config_parameter='omnichannel_bridge.new_contact_as_lead',
    )
    omnichannel_telegram_bot_token = fields.Char(
        string='Telegram bot token (fallback if not in Integrations)',
        config_parameter='omnichannel_bridge.telegram_bot_token',
    )
    omnichannel_telegram_webhook_secret = fields.Char(
        config_parameter='omnichannel_bridge.telegram_webhook_secret',
    )
    omnichannel_meta_page_access_token = fields.Char(
        string='Meta page access token (fallback)',
        config_parameter='omnichannel_bridge.meta_page_access_token',
    )
    omnichannel_meta_app_secret = fields.Char(
        string='Meta app secret (webhook X-Hub-Signature-256)',
        config_parameter='omnichannel_bridge.meta_app_secret',
    )
    omnichannel_meta_verify_token = fields.Char(
        string='Meta webhook verify token',
        config_parameter='omnichannel_bridge.meta_verify_token',
    )
    omnichannel_bot_reply_mode = fields.Selection(
        selection=[
            ('always', 'Always (instant replies whenever LLM is on)'),
            ('outside_manager_hours', 'Only outside manager working hours'),
            ('never', 'Never (manual only)'),
        ],
        string='Bot reply schedule',
        default='outside_manager_hours',
        config_parameter='omnichannel_bridge.bot_reply_mode',
    )
    omnichannel_manager_hour_start = fields.Char(
        string='Manager hours start (HH:MM, company timezone)',
        default='09:00',
        config_parameter='omnichannel_bridge.manager_hour_start',
    )
    omnichannel_manager_hour_end = fields.Char(
        string='Manager hours end (HH:MM, company timezone)',
        default='18:00',
        config_parameter='omnichannel_bridge.manager_hour_end',
    )
    omnichannel_llm_enabled = fields.Boolean(
        string='Enable LLM autoreplies',
        config_parameter='omnichannel_bridge.llm_enabled',
    )
    omnichannel_llm_backend = fields.Selection(
        selection=[
            ('ollama', 'Ollama (local, open weights)'),
            ('openai', 'OpenAI API (proprietary cloud)'),
        ],
        string='LLM backend',
        default='ollama',
        config_parameter='omnichannel_bridge.llm_backend',
    )
    omnichannel_ollama_base_url = fields.Char(
        string='Ollama base URL',
        default='http://127.0.0.1:11434',
        config_parameter='omnichannel_bridge.ollama_base_url',
    )
    omnichannel_ollama_model = fields.Char(
        string='Ollama model name',
        default='llama3.2',
        config_parameter='omnichannel_bridge.ollama_model',
    )
    omnichannel_llm_strict_grounding = fields.Boolean(
        string='Strict grounding (only FACTS_FROM_DATABASE)',
        default=True,
        config_parameter='omnichannel_bridge.llm_strict_grounding',
    )
    omnichannel_llm_include_transcript = fields.Boolean(
        string='Include recent thread in context',
        default=True,
        config_parameter='omnichannel_bridge.llm_include_transcript',
    )
    omnichannel_llm_transcript_messages = fields.Char(
        string='Transcript message count',
        default='8',
        config_parameter='omnichannel_bridge.llm_transcript_messages',
    )
    omnichannel_openai_enabled = fields.Boolean(
        string='Legacy: OpenAI toggle (same as LLM if backend=openai)',
        config_parameter='omnichannel_bridge.openai_enabled',
    )
    omnichannel_openai_api_key = fields.Char(
        config_parameter='omnichannel_bridge.openai_api_key',
    )
    omnichannel_openai_model = fields.Char(
        string='OpenAI model',
        default='gpt-4o-mini',
        config_parameter='omnichannel_bridge.openai_model',
    )
    omnichannel_openai_system_prompt = fields.Text(
        config_parameter='omnichannel_bridge.openai_system_prompt',
    )

    # --- Internal Telegram notifications ---
    omnichannel_internal_tg_bot_token = fields.Char(
        string='Internal Telegram bot token (manager notifications)',
        config_parameter='omnichannel_bridge.internal_tg_bot_token',
    )
    omnichannel_internal_tg_chat_id = fields.Char(
        string='Internal Telegram chat/group/channel ID',
        config_parameter='omnichannel_bridge.internal_tg_chat_id',
    )
    omnichannel_internal_notify_new = fields.Boolean(
        string='Notify on new thread',
        config_parameter='omnichannel_bridge.internal_notify_new',
    )
    omnichannel_internal_notify_escalate = fields.Boolean(
        string='Notify on escalation',
        config_parameter='omnichannel_bridge.internal_notify_escalate',
    )
    omnichannel_internal_notify_problem = fields.Boolean(
        string='Notify on problematic flag',
        config_parameter='omnichannel_bridge.internal_notify_problem',
    )
