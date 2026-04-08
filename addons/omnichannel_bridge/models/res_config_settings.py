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
    omnichannel_whatsapp_verify_token = fields.Char(
        string='WhatsApp webhook verify token',
        config_parameter='omnichannel_bridge.whatsapp_verify_token',
    )
    omnichannel_whatsapp_phone_number_id = fields.Char(
        string='WhatsApp Cloud phone number ID',
        config_parameter='omnichannel_bridge.whatsapp_phone_number_id',
    )
    omnichannel_whatsapp_app_secret = fields.Char(
        string='WhatsApp app secret (signature)',
        config_parameter='omnichannel_bridge.whatsapp_app_secret',
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
    omnichannel_bot_inside_hours_if_manager_quiet = fields.Boolean(
        string='During manager hours: bot after quiet period (SLA)',
        default=True,
        config_parameter='omnichannel_bridge.bot_inside_hours_if_manager_quiet',
        help='If enabled, Meta/Telegram AI jobs wait SLA seconds during manager hours so the manager can reply first; '
        'then the bot may reply if still no human message. Website live chat is unchanged (immediate).',
    )
    omnichannel_night_bot_enabled = fields.Boolean(
        string='Night / early window: bot always allowed',
        default=False,
        config_parameter='omnichannel_bridge.night_bot_enabled',
        help='Optional extra local-time window (e.g. 22:00–07:00) where bot may reply even if it overlaps manager hours.',
    )
    omnichannel_night_bot_start = fields.Char(
        string='Night window start (HH:MM)',
        default='22:00',
        config_parameter='omnichannel_bridge.night_bot_start',
    )
    omnichannel_night_bot_end = fields.Char(
        string='Night window end (HH:MM)',
        default='07:00',
        config_parameter='omnichannel_bridge.night_bot_end',
    )
    omnichannel_webhook_max_body_bytes = fields.Integer(
        string='Webhook max body size (bytes)',
        default=1048576,
        config_parameter='omnichannel_bridge.webhook_max_body_bytes',
        help='Reject larger POST bodies on /omni/webhook/* with 413 (TZ §14.5).',
    )
    omnichannel_sla_no_human_seconds = fields.Integer(
        string='SLA wait before bot reply (seconds)',
        default=180,
        config_parameter='omnichannel_bridge.sla_no_human_seconds',
        help='If no human manager reply appears in channel within this window, bot may reply.',
    )
    omnichannel_manager_session_timeout_minutes = fields.Integer(
        string='Manager session lock timeout (minutes)',
        default=30,
        config_parameter='omnichannel_bridge.manager_session_timeout_minutes',
        help='After manager message bot stays paused for this window in messenger channels.',
    )
    omnichannel_llm_enabled = fields.Boolean(
        string='Enable LLM autoreplies',
        config_parameter='omnichannel_bridge.llm_enabled',
    )
    omnichannel_site_livechat_enabled = fields.Boolean(
        string='Enable AI on website live chat',
        config_parameter='omnichannel_bridge.site_livechat_enabled',
        default=True,
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
        default='http://77.42.20.195:11434',
        config_parameter='omnichannel_bridge.ollama_base_url',
    )
    omnichannel_ollama_model = fields.Char(
        string='Ollama model name',
        default='qwen2.5:7b',
        config_parameter='omnichannel_bridge.ollama_model',
    )
    omnichannel_fallback_message = fields.Text(
        string='Fallback message when LLM is unavailable',
        config_parameter='omnichannel_bridge.fallback_message',
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
    omnichannel_llm_debug_data_sources = fields.Boolean(
        string='Debug: show fact data sources in context',
        config_parameter='omnichannel_bridge.llm_debug_data_sources',
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
    omnichannel_objection_playbook_price = fields.Text(
        string='Objection playbook: price',
        config_parameter='omnichannel_bridge.objection_playbook_price',
    )
    omnichannel_objection_playbook_timing = fields.Text(
        string='Objection playbook: timing',
        config_parameter='omnichannel_bridge.objection_playbook_timing',
    )
    omnichannel_objection_playbook_trust = fields.Text(
        string='Objection playbook: trust',
        config_parameter='omnichannel_bridge.objection_playbook_trust',
    )
    omnichannel_objection_playbook_need_to_think = fields.Text(
        string='Objection playbook: need_to_think',
        config_parameter='omnichannel_bridge.objection_playbook_need_to_think',
    )
    omnichannel_objection_playbook_competitor = fields.Text(
        string='Objection playbook: competitor',
        config_parameter='omnichannel_bridge.objection_playbook_competitor',
    )
    omnichannel_objection_playbook_not_decision_maker = fields.Text(
        string='Objection playbook: not_decision_maker',
        config_parameter='omnichannel_bridge.objection_playbook_not_decision_maker',
    )
    omnichannel_coupon_public_channel_url = fields.Char(
        string='Public Telegram channel for coupon',
        config_parameter='omnichannel_bridge.coupon_public_channel_url',
        default='https://t.me/campscouting',
        help='Clients open this public Telegram channel and take the current promo code from pinned/latest post.',
    )
    omnichannel_coupon_public_code = fields.Char(
        string='Public coupon code (from Telegram channel)',
        config_parameter='omnichannel_bridge.coupon_public_code',
    )
    omnichannel_coupon_discount_percent = fields.Float(
        string='Public coupon discount percent',
        config_parameter='omnichannel_bridge.coupon_discount_percent',
        default=5.0,
    )

    # --- Bot kill switch via Telegram ---
    omnichannel_admin_tg_user_ids = fields.Char(
        string='Admin Telegram user IDs (comma-separated, for /stop_bot /start_bot)',
        config_parameter='omnichannel_bridge.admin_tg_user_ids',
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
    omnichannel_internal_tg_priority_chat_id = fields.Char(
        string='Priority Telegram chat/group/channel ID (optional)',
        config_parameter='omnichannel_bridge.internal_tg_priority_chat_id',
        help='If set, urgent/problematic notifications are sent to this channel; otherwise they go to the default internal chat with PRIORITY tag.',
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
    omnichannel_window_reminder_enabled = fields.Boolean(
        string='Enable 24h window reminder automation',
        config_parameter='omnichannel_bridge.window_reminder_enabled',
        default=False,
    )
    omnichannel_window_reminder_trigger_hours = fields.Float(
        string='Reminder trigger hours after last inbound',
        config_parameter='omnichannel_bridge.window_reminder_trigger_hours',
        default=20.0,
    )
    omnichannel_window_message_window_hours = fields.Float(
        string='Max platform window hours',
        config_parameter='omnichannel_bridge.window_message_window_hours',
        default=24.0,
    )
    omnichannel_window_reminder_text = fields.Text(
        string='24h reminder text',
        config_parameter='omnichannel_bridge.window_reminder_text',
    )
    omnichannel_retention_message_days = fields.Integer(
        string='Retention: omni chat messages (days)',
        config_parameter='omnichannel_bridge.retention_message_days',
        default=180,
    )
    omnichannel_retention_webhook_days = fields.Integer(
        string='Retention: webhook event records (days)',
        config_parameter='omnichannel_bridge.retention_webhook_days',
        default=30,
    )
    omnichannel_log_pii_masking = fields.Boolean(
        string='Mask emails/phones in bridge logs',
        config_parameter='omnichannel_bridge.log_pii_masking',
        default=True,
    )
