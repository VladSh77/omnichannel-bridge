# -*- coding: utf-8 -*-
import json

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
    omnichannel_viber_bot_token = fields.Char(
        string='Viber bot token (fallback)',
        config_parameter='omnichannel_bridge.viber_bot_token',
    )
    omnichannel_viber_webhook_secret = fields.Char(
        string='Viber webhook secret (X-Viber-Content-Signature)',
        config_parameter='omnichannel_bridge.viber_webhook_secret',
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
    omnichannel_webhook_rate_limit_per_minute = fields.Integer(
        string='Webhook per-IP rate limit (req/min, 0=off)',
        default=0,
        config_parameter='omnichannel_bridge.webhook_rate_limit_per_minute',
        help='Best-effort app-layer limit for /omni/webhook/*; prefer infra-level rate limit in production.',
    )
    omnichannel_sla_no_human_seconds = fields.Integer(
        string='SLA wait before bot reply (seconds)',
        default=180,
        config_parameter='omnichannel_bridge.sla_no_human_seconds',
        help='If no human manager reply appears in channel within this window, bot may reply.',
    )
    omnichannel_sla_scope = fields.Selection(
        selection=[
            ('manager_hours', 'Measure only during manager hours'),
            ('always', 'Measure 24x7'),
        ],
        string='SLA scope',
        default='manager_hours',
        config_parameter='omnichannel_bridge.sla_scope',
    )
    omnichannel_manager_session_timeout_minutes = fields.Integer(
        string='Manager session lock timeout (minutes)',
        default=30,
        config_parameter='omnichannel_bridge.manager_session_timeout_minutes',
        help='After manager message bot stays paused for this window in messenger channels.',
    )
    omnichannel_outbound_conflict_guard_seconds = fields.Integer(
        string='Outbound conflict/duplicate guard (seconds)',
        default=20,
        config_parameter='omnichannel_bridge.outbound_conflict_guard_seconds',
        help='Suppress bot outbound right after manager reply and skip duplicate outbound text in this window.',
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
    omnichannel_llm_prompt_version = fields.Char(
        string='Prompt version tag',
        config_parameter='omnichannel_bridge.llm_prompt_version',
        default='v1',
    )
    omnichannel_llm_experiment_tag = fields.Char(
        string='Prompt experiment tag',
        config_parameter='omnichannel_bridge.llm_experiment_tag',
        help='Optional A/B label for runtime prompt experiments.',
    )
    omnichannel_llm_assistant_profile = fields.Selection(
        selection=[
            ('default', 'Default'),
            ('sales_closer', 'Sales closer'),
            ('support_safe', 'Support safe'),
        ],
        string='Assistant profile',
        default='default',
        config_parameter='omnichannel_bridge.llm_assistant_profile',
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
    omnichannel_pain_script = fields.Text(
        string='Pain discovery script',
        config_parameter='omnichannel_bridge.pain_script',
    )
    omnichannel_upsell_script = fields.Text(
        string='Upsell script',
        config_parameter='omnichannel_bridge.upsell_script',
    )
    omnichannel_style_warm_policy = fields.Text(
        string='Warm style policy',
        config_parameter='omnichannel_bridge.style_warm_policy',
    )
    omnichannel_fomo_internal_notify = fields.Boolean(
        string='Notify managers on FOMO low availability hints',
        config_parameter='omnichannel_bridge.fomo_internal_notify',
        default=True,
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
    omnichannel_legal_terms_url = fields.Char(
        string='Legal terms URL',
        config_parameter='omnichannel_bridge.legal_terms_url',
        default='https://campscout.eu/terms',
    )
    omnichannel_legal_privacy_url = fields.Char(
        string='Legal privacy URL',
        config_parameter='omnichannel_bridge.legal_privacy_url',
        default='https://campscout.eu/privacy-policy',
    )
    omnichannel_legal_cookie_url = fields.Char(
        string='Legal cookie URL',
        config_parameter='omnichannel_bridge.legal_cookie_url',
        default='https://campscout.eu/cookie-policy',
    )
    omnichannel_legal_child_protection_url = fields.Char(
        string='Legal child protection URL',
        config_parameter='omnichannel_bridge.legal_child_protection_url',
        default='https://campscout.eu/child-protection',
    )
    omnichannel_legal_short_offer_text = fields.Text(
        string='Approved short offer wording',
        config_parameter='omnichannel_bridge.legal_short_offer_text',
    )
    omnichannel_legal_short_rodo_text = fields.Text(
        string='Approved short RODO wording',
        config_parameter='omnichannel_bridge.legal_short_rodo_text',
    )
    omnichannel_legal_short_child_text = fields.Text(
        string='Approved short child-data wording',
        config_parameter='omnichannel_bridge.legal_short_child_text',
    )
    omnichannel_legal_approved_owner = fields.Char(
        string='Legal approvals owner',
        config_parameter='omnichannel_bridge.legal_approved_owner',
        help='Process owner who approves legal auto-wording in bot context.',
    )
    omnichannel_consent_meta_text = fields.Text(
        string='Consent text: Meta/Instagram',
        config_parameter='omnichannel_bridge.consent_meta_text',
    )
    omnichannel_consent_telegram_text = fields.Text(
        string='Consent text: Telegram',
        config_parameter='omnichannel_bridge.consent_telegram_text',
    )
    omnichannel_consent_whatsapp_text = fields.Text(
        string='Consent text: WhatsApp',
        config_parameter='omnichannel_bridge.consent_whatsapp_text',
    )
    omnichannel_consent_site_text = fields.Text(
        string='Consent text: Website livechat',
        config_parameter='omnichannel_bridge.consent_site_text',
    )
    omnichannel_release_odoo_version = fields.Char(
        string='Release fingerprint: Odoo version',
        config_parameter='omnichannel_bridge.release_odoo_version',
    )
    omnichannel_release_custom_hash = fields.Char(
        string='Release fingerprint: custom repo hash',
        config_parameter='omnichannel_bridge.release_custom_hash',
    )
    omnichannel_release_ollama_model_version = fields.Char(
        string='Release fingerprint: Ollama model',
        config_parameter='omnichannel_bridge.release_ollama_model_version',
    )
    omnichannel_token_rotation_owner = fields.Char(
        string='Token rotation owner',
        config_parameter='omnichannel_bridge.token_rotation_owner',
    )
    omnichannel_token_rotation_next_date = fields.Date(
        string='Token rotation next date',
        config_parameter='omnichannel_bridge.token_rotation_next_date',
    )
    omnichannel_coupon_allowed_categ_ids = fields.Many2many(
        'product.category',
        string='Coupon allowed product categories',
        help='If set, coupon applies only to camp lines inside these categories (including subcategories).',
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
    omnichannel_internal_tg_api_base = fields.Char(
        string='Internal Telegram API base URL',
        config_parameter='omnichannel_bridge.internal_tg_api_base',
        default='https://api.telegram.org',
    )
    omnichannel_internal_tg_allowed_user_ids = fields.Char(
        string='Internal TG allowed user IDs (comma-separated)',
        config_parameter='omnichannel_bridge.internal_tg_allowed_user_ids',
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
    omnichannel_internal_notify_priority_keywords = fields.Char(
        string='Priority keyword override (comma-separated)',
        config_parameter='omnichannel_bridge.internal_notify_priority_keywords',
    )
    omnichannel_default_manager_user_id = fields.Many2one(
        'res.users',
        string='Default manager user (handoff owner)',
        config_parameter='omnichannel_bridge.default_manager_user_id',
    )
    omnichannel_internal_notify_email_manager = fields.Boolean(
        string='Also send manager email on escalation/priority',
        config_parameter='omnichannel_bridge.internal_notify_email_manager',
        default=False,
    )
    omnichannel_purchase_dedup_minutes = fields.Integer(
        string='Purchase event dedup window (minutes)',
        config_parameter='omnichannel_bridge.purchase_dedup_minutes',
        default=20,
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
    omnichannel_window_last_call_hours_before_close = fields.Float(
        string='Last-call trigger hours before window close',
        config_parameter='omnichannel_bridge.window_last_call_hours_before_close',
        default=2.0,
    )
    omnichannel_window_last_call_text = fields.Text(
        string='Last-call reminder text',
        config_parameter='omnichannel_bridge.window_last_call_text',
    )
    omnichannel_window_reminder_text = fields.Text(
        string='24h reminder text',
        config_parameter='omnichannel_bridge.window_reminder_text',
    )
    omnichannel_cooldown_reminder_minutes = fields.Integer(
        string='Cooldown: reminder (minutes)',
        config_parameter='omnichannel_bridge.cooldown_reminder_minutes',
        default=180,
    )
    omnichannel_cooldown_fomo_minutes = fields.Integer(
        string='Cooldown: FOMO hint (minutes)',
        config_parameter='omnichannel_bridge.cooldown_fomo_minutes',
        default=180,
    )
    omnichannel_cooldown_last_call_minutes = fields.Integer(
        string='Cooldown: last-call (minutes)',
        config_parameter='omnichannel_bridge.cooldown_last_call_minutes',
        default=180,
    )
    omnichannel_cooldown_global_minutes = fields.Integer(
        string='Cooldown: global marketing touch (minutes)',
        config_parameter='omnichannel_bridge.cooldown_global_minutes',
        default=60,
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
    omnichannel_retention_child_data_days = fields.Integer(
        string='Retention: child-sensitive profile fields (days)',
        config_parameter='omnichannel_bridge.retention_child_data_days',
        default=365,
        help='After this period, child age/preference fields can be auto-minimized by cron.',
    )
    omnichannel_log_pii_masking = fields.Boolean(
        string='Mask emails/phones in bridge logs',
        config_parameter='omnichannel_bridge.log_pii_masking',
        default=True,
    )
    omnichannel_moderation_keywords = fields.Text(
        string='Moderation keywords (comma-separated)',
        config_parameter='omnichannel_bridge.moderation_keywords',
        help='Additional risk keywords to trigger policy action.',
    )
    omnichannel_vocative_map_extra = fields.Text(
        string='Vocative map extra (name:vocative, comma-separated)',
        config_parameter='omnichannel_bridge.vocative_map_extra',
        help='Example: олена:Олено, віра:Віро',
    )
    omnichannel_moderation_action = fields.Selection(
        selection=[
            ('escalate', 'Escalate to manager'),
            ('escalate_pause', 'Escalate and pause bot'),
            ('note_only', 'Internal note only'),
        ],
        string='Moderation action',
        config_parameter='omnichannel_bridge.moderation_action',
        default='escalate',
    )

    def get_values(self):
        res = super().get_values()
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param('omnichannel_bridge.coupon_allowed_categ_ids', '[]')
        try:
            categ_ids = [int(x) for x in json.loads(raw or '[]') if int(x) > 0]
        except Exception:
            categ_ids = []
        res.update({
            'omnichannel_coupon_allowed_categ_ids': [(6, 0, categ_ids)],
        })
        return res

    def set_values(self):
        tracked_keys = [
            'omnichannel_bridge.openai_system_prompt',
            'omnichannel_bridge.llm_prompt_version',
            'omnichannel_bridge.llm_experiment_tag',
            'omnichannel_bridge.legal_short_offer_text',
            'omnichannel_bridge.legal_short_rodo_text',
            'omnichannel_bridge.legal_short_child_text',
            'omnichannel_bridge.consent_meta_text',
            'omnichannel_bridge.consent_telegram_text',
            'omnichannel_bridge.consent_whatsapp_text',
            'omnichannel_bridge.consent_site_text',
        ]
        icp = self.env['ir.config_parameter'].sudo()
        before = {k: (icp.get_param(k, '') or '') for k in tracked_keys}
        super().set_values()
        for settings in self:
            ids_payload = json.dumps(settings.omnichannel_coupon_allowed_categ_ids.ids or [])
            icp.set_param('omnichannel_bridge.coupon_allowed_categ_ids', ids_payload)
        after = {k: (icp.get_param(k, '') or '') for k in tracked_keys}
        Audit = self.env['omni.prompt.audit'].sudo()
        for key in tracked_keys:
            if before.get(key) == after.get(key):
                continue
            Audit.create({
                'changed_by': self.env.user.id,
                'key_name': key,
                'old_value': before.get(key, ''),
                'new_value': after.get(key, ''),
                'note': 'Updated via res.config.settings',
            })
