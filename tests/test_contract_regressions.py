import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ContractRegressionTests(unittest.TestCase):
    def test_webhook_controller_has_payload_limit(self):
        content = (ROOT / 'addons/omnichannel_bridge/controllers/main.py').read_text()
        self.assertIn('webhook_max_body_bytes', content)
        self.assertIn('payload_too_large', content)
        self.assertIn('webhook_rate_limit_per_minute', content)
        self.assertIn('rate_limited', content)

    def test_reserve_flow_markers_present(self):
        content = (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text()
        self.assertIn('_omni_apply_reserve_flow', content)
        self.assertIn('reserve_waitlist', content)

    def test_purchase_confirmed_hook_files_present(self):
        self.assertTrue((ROOT / 'addons/omnichannel_bridge/models/sale_order.py').exists())
        self.assertTrue((ROOT / 'addons/omnichannel_bridge/models/payment_transaction.py').exists())
        self.assertTrue((ROOT / 'addons/omnichannel_bridge/models/account_move.py').exists())

    def test_coupon_e2e_markers_present(self):
        content = (ROOT / 'addons/omnichannel_bridge/models/sale_order.py').read_text()
        promo = (ROOT / 'addons/omnichannel_bridge/models/omni_promo.py').read_text()
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        self.assertIn('omni_coupon_code', content)
        self.assertIn('_omni_apply_public_coupon', content)
        self.assertIn('_omni_register_coupon_redemption', content)
        self.assertIn('_omni_coupon_allowed_categories', content)
        self.assertIn('coupon_allowed_categ_ids', settings)
        self.assertIn('omni_find_active_by_code', promo)
        self.assertTrue((ROOT / 'addons/omnichannel_bridge/models/omni_coupon_redemption.py').exists())

    def test_whatsapp_runtime_markers_present(self):
        content = (ROOT / 'addons/omnichannel_bridge/models/omni_bridge.py').read_text()
        parsers = (ROOT / 'addons/omnichannel_bridge/utils/webhook_parsers.py').read_text()
        self.assertIn('_omni_process_whatsapp_stub', content)
        self.assertIn('whatsapp_cloud', content)
        self.assertIn('provider_stub', content)
        self.assertIn('_omni_process_twilio_whatsapp', content)
        self.assertIn('_omni_whatsapp_send_to_wa_id', content)
        self.assertIn('extract_whatsapp_message_id', parsers)
        self.assertIn('extract_twilio_whatsapp_message_id', parsers)

    def test_omni_integration_ensure_all_providers_marker(self):
        content = (ROOT / 'addons/omnichannel_bridge/models/omni_integration.py').read_text()
        defaults = (ROOT / 'addons/omnichannel_bridge/data/omni_defaults.xml').read_text()
        self.assertIn('def omni_ensure_all_provider_integration_rows', content)
        self.assertIn('omni_ensure_all_provider_integration_rows', defaults)

    def test_viber_runtime_markers_present(self):
        content = (ROOT / 'addons/omnichannel_bridge/models/omni_bridge.py').read_text()
        parsers = (ROOT / 'addons/omnichannel_bridge/utils/webhook_parsers.py').read_text()
        self.assertIn('_omni_process_viber_stub', content)
        self.assertIn('_omni_viber_send_to_user', content)
        self.assertIn('extract_viber_message_token', parsers)

    def test_livechat_entry_flow_markers_present(self):
        content = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        self.assertIn('_omni_handle_livechat_entry_flow', content)
        self.assertIn('omni_livechat_entry_state', content)
        self.assertIn('_omni_livechat_entry_menu_text', content)
        self.assertIn('_omni_livechat_prefers_polish', content)
        self.assertIn('manager_hours_now', content)
        self.assertIn('omni_livechat_contact_attempts', content)
        self.assertIn('_omni_livechat_contact_invalid_text', content)
        self.assertIn('_omni_refresh_livechat_channel_label', content)
        self.assertIn('_omni_refresh_livechat_contact_identity', content)

    def test_fsm_and_race_markers_present(self):
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        memory = (ROOT / 'addons/omnichannel_bridge/models/omni_memory.py').read_text()
        stage_views = (ROOT / 'addons/omnichannel_bridge/views/omni_stage_event_views.xml').read_text()
        self.assertIn('_OMNI_STAGE_TRANSITIONS', partner)
        self.assertIn('omni_set_sales_stage', partner)
        self.assertIn('omni.stage.event', partner)
        self.assertTrue((ROOT / 'addons/omnichannel_bridge/models/omni_stage_event.py').exists())
        self.assertIn('action_omni_stage_event', stage_views)
        self.assertIn('menu_omni_stage_events', (ROOT / 'addons/omnichannel_bridge/views/omni_ops_views.xml').read_text())
        self.assertIn("source='omni_memory'", memory)
        self.assertIn('omni_set_sales_stage(', memory)
        self.assertIn('manager_session_active', channel)
        self.assertIn('omni_manager_session_active_now', channel)
        self.assertIn('omni_merge_duplicates_by_rules', partner)

    def test_retention_and_erasure_markers_present(self):
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        webhook = (ROOT / 'addons/omnichannel_bridge/models/omni_webhook_event.py').read_text()
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        runbook = (ROOT / 'docs/OPERATIONS_RUNBOOK.md').read_text()
        self.assertIn('omni_cron_purge_old_messages', channel)
        self.assertIn('omni_cron_purge_old_events', webhook)
        self.assertIn('action_omni_right_to_erasure', partner)
        self.assertIn('omni_cron_purge_child_sensitive_fields', partner)
        self.assertIn('retention_child_data_days', settings)
        self.assertIn('RIGHT_TO_ERASURE_SOP.md', runbook)

    def test_crm_analytics_wizard_line_acl_allows_create_for_managers(self):
        csv_text = (ROOT / 'addons/omnichannel_bridge/security/ir.model.access.csv').read_text()
        for line in csv_text.splitlines():
            if line.startswith('access_omni_crm_analytics_wizard_line_manager,'):
                self.assertTrue(line.endswith(',1,1,1,1'), 'wizard.line needs create/write for CRM analytics')
                break
        else:
            self.fail('missing access_omni_crm_analytics_wizard_line_manager row')

    def test_crm_analytics_markers_present(self):
        analytics = (ROOT / 'addons/omnichannel_bridge/models/omni_crm_analytics.py').read_text()
        ops_views = (ROOT / 'addons/omnichannel_bridge/views/omni_ops_views.xml').read_text()
        self.assertIn('omni.crm.analytics.wizard', analytics)
        self.assertIn('avg_response_seconds', analytics)
        self.assertIn('bot_reply_threads', analytics)
        self.assertIn('mixed_reply_threads', analytics)
        self.assertIn('objection_to_intent_percent', analytics)
        self.assertIn('meta_goal_leads', analytics)
        self.assertIn('romi_percent', analytics)
        self.assertIn('coupon_redemptions_count', analytics)
        self.assertIn('menu_omni_crm_analytics', ops_views)

    def test_direct_manager_handoff_markers_present(self):
        notify = (ROOT / 'addons/omnichannel_bridge/models/omni_notify.py').read_text()
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        self.assertIn('_notify_manager_direct', notify)
        self.assertIn('mail.activity', notify)
        self.assertIn('omnichannel_bridge.default_manager_user_id', settings)
        self.assertIn('purchase_dedup_minutes', settings)
        self.assertIn('purchase_dedup_minutes', notify)

    def test_outbound_ordering_guard_markers_present(self):
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        self.assertIn('omni_last_outbound_hash', channel)
        self.assertIn('Skip bot outbound due manager recent reply', channel)
        self.assertIn('omnichannel_bridge.outbound_conflict_guard_seconds', settings)

    def test_coupon_meta_offer_markers_present(self):
        ai = (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text()
        self.assertIn('_omni_is_coupon_question', ai)
        self.assertIn('_omni_coupon_meta_offer_text', ai)
        self.assertIn('coupon_public_channel_url', ai)

    def test_language_policy_markers_present(self):
        ai = (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text()
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        self.assertIn('_omni_detect_and_store_channel_language', ai)
        self.assertIn('_omni_ru_language_policy_reply', ai)
        self.assertIn('uk_markers', ai)
        self.assertIn('omni_detected_lang', channel)

    def test_scope_confusion_and_priority_markers_present(self):
        ai = (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text()
        intel = (ROOT / 'addons/omnichannel_bridge/models/omni_sales_intel.py').read_text()
        notify = (ROOT / 'addons/omnichannel_bridge/models/omni_notify.py').read_text()
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('_omni_is_confusion_message', ai)
        self.assertIn('_omni_send_confusion_safe_reply', ai)
        self.assertIn('omni_objection_next_step_block', intel)
        self.assertIn('internal_notify_priority_keywords', settings)
        self.assertIn('internal_notify_priority_keywords', notify)
        self.assertIn("'website_sale' in self.env", knowledge)
        self.assertIn('time.sleep(2)', ai)
        self.assertIn('_pick_online_manager_user', notify)
        self.assertIn("final_body.startswith('🤖')", ai)
        self.assertIn('sla_scope', ai)
        self.assertIn('omni_pain_script_block', intel)
        self.assertIn('omni_upsell_script_block', intel)
        self.assertIn('_omni_warm_style_policy', ai)
        self.assertIn('fomo_internal_notify', settings)
        self.assertIn('moderation_keywords', settings)
        self.assertIn('_omni_moderation_policy_hit', ai)
        self.assertIn('cooldown_global_minutes', settings)
        self.assertIn('_omni_marketing_touch_allowed', (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text())

    def test_ci_lint_step_present(self):
        ci = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('ruff check', ci)

    def test_objection_policy_editor_markers_present(self):
        intel = (ROOT / 'addons/omnichannel_bridge/models/omni_sales_intel.py').read_text()
        model = (ROOT / 'addons/omnichannel_bridge/models/omni_objection_policy.py').read_text()
        views = (ROOT / 'addons/omnichannel_bridge/views/omni_objection_policy_views.xml').read_text()
        ops = (ROOT / 'addons/omnichannel_bridge/views/omni_ops_views.xml').read_text()
        moderation_model = (ROOT / 'addons/omnichannel_bridge/models/omni_moderation_rule.py').read_text()
        moderation_views = (ROOT / 'addons/omnichannel_bridge/views/omni_moderation_rule_views.xml').read_text()
        memory = (ROOT / 'addons/omnichannel_bridge/models/omni_memory.py').read_text()
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        self.assertIn('omni.objection.policy', model)
        self.assertIn('menu_omni_objection_policy', ops)
        self.assertIn('menu_omni_moderation_rules', ops)
        self.assertIn('action_omni_objection_policy', views)
        self.assertIn('action_omni_moderation_rule', moderation_views)
        self.assertIn('omni.moderation.rule', moderation_model)
        self.assertIn("self.env['omni.objection.policy']", intel)
        self.assertIn("self.env['omni.moderation.rule']", (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text())
        self.assertIn('tokens = [t for t in re.split', intel)
        self.assertIn('_omni_vocative_map', memory)
        self.assertIn('vocative_map_extra', settings)

    def test_knowledge_article_editor_markers_present(self):
        model = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge_article.py').read_text()
        views = (ROOT / 'addons/omnichannel_bridge/views/omni_knowledge_article_views.xml').read_text()
        ops = (ROOT / 'addons/omnichannel_bridge/views/omni_ops_views.xml').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('omni.knowledge.article', model)
        self.assertIn('action_omni_knowledge_article', views)
        self.assertIn('menu_omni_knowledge_articles', ops)
        self.assertIn("self.env['omni.knowledge.article']", knowledge)

    def test_stage_transition_and_payment_event_markers_present(self):
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        transition_model = (ROOT / 'addons/omnichannel_bridge/models/omni_stage_transition.py').read_text()
        payment_model = (ROOT / 'addons/omnichannel_bridge/models/omni_payment_event.py').read_text()
        payment_views = (ROOT / 'addons/omnichannel_bridge/views/omni_payment_event_views.xml').read_text()
        notify = (ROOT / 'addons/omnichannel_bridge/models/omni_notify.py').read_text()
        self.assertIn('omni.stage.transition', transition_model)
        self.assertIn("self.env['omni.stage.transition']", partner)
        self.assertIn('omni.payment.event', payment_model)
        self.assertIn('action_omni_payment_event', payment_views)
        self.assertIn('omni_purchase_confirmed_at', notify)

    def test_learning_and_dpia_docs_present(self):
        runbook = (ROOT / 'docs/OPERATIONS_RUNBOOK.md').read_text()
        self.assertIn('DPIA_DATA_CATEGORIES.md', runbook)
        self.assertIn('LEARNING_POLICY_NO_FINETUNE.md', runbook)
        self.assertIn('STAGING_RUNTIME_BOOTSTRAP.md', runbook)
        self.assertIn('PROD_LIVECHAT_SMOKE_2026-04-08.md', runbook)

    def test_camp_product_markers_include_cs_code_and_poszum(self):
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn("code.startswith('CS-')", knowledge)
        self.assertIn("'poszum'", knowledge)
        self.assertIn("'пошум'", knowledge)
        self.assertIn('_omni_pricelist_for_catalog', knowledge)

    def test_camp_knowledge_seed_data_linked_in_manifest(self):
        manifest = (ROOT / 'addons/omnichannel_bridge/__manifest__.py').read_text()
        data = (ROOT / 'addons/omnichannel_bridge/data/omni_camp_knowledge_articles.xml').read_text(
            encoding='utf-8'
        )
        self.assertIn('omni_camp_knowledge_articles.xml', manifest)
        self.assertIn('omni_kb_camp_schedule_day', data)
        self.assertIn('model="omni.knowledge.article"', data)

    def test_ukrainian_i18n_covers_main_omni_menus(self):
        po = (ROOT / 'addons/omnichannel_bridge/i18n/uk_UA.po').read_text(encoding='utf-8')
        self.assertIn('msgid "Integrations"', po)
        self.assertIn('msgstr "Інтеграції"', po)
        self.assertIn('msgid "Operations"', po)
        self.assertIn('msgstr "Операції"', po)
        self.assertIn('model:ir.ui.menu,name:omnichannel_bridge.menu_omni_ops_root', po)

    def test_res_config_settings_uses_char_not_text_for_config_parameter_fields(self):
        """Odoo res.config.settings only allows boolean/int/float/char/selection/many2one/datetime for ICP-backed fields."""
        py = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        self.assertNotIn('fields.Text(', py)
        self.assertIn('omnichannel_window_reminder_text = fields.Char(', py)

    def test_res_config_settings_fields_referenced_in_settings_xml_exist_in_python(self):
        """Avoid upgrade ParseError: field X does not exist on res.config.settings (XML ahead of models)."""
        py = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        xml = (ROOT / 'addons/omnichannel_bridge/views/res_config_settings_views.xml').read_text()
        self.assertIn('omnichannel_sla_scope', py)
        self.assertIn("config_parameter='omnichannel_bridge.sla_scope'", py)
        self.assertIn('name="omnichannel_sla_scope"', xml)

    def test_livechat_prechat_and_runtime_smoke_markers_present(self):
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        smoke = (ROOT / 'scripts/odoo_runtime_smoke.py').read_text()
        self.assertIn("('awaiting_name', 'Awaiting name')", channel)
        self.assertIn('_omni_livechat_name_prompt_text_lang', channel)
        self.assertIn('def run(env):', smoke)
        self.assertIn('_REQUIRED_OMNI_MODELS', smoke)
        self.assertIn('omni.stage.transition', smoke)
        self.assertIn('omni.objection.policy', smoke)

    def test_outbound_log_and_message_tags_markers_present(self):
        bridge = (ROOT / 'addons/omnichannel_bridge/models/omni_bridge.py').read_text()
        log_model = (ROOT / 'addons/omnichannel_bridge/models/omni_outbound_log.py').read_text()
        message = (ROOT / 'addons/omnichannel_bridge/models/mail_message.py').read_text()
        intel = (ROOT / 'addons/omnichannel_bridge/models/omni_sales_intel.py').read_text()
        ops = (ROOT / 'addons/omnichannel_bridge/views/omni_ops_views.xml').read_text()
        self.assertIn('_omni_log_outbound_delivery', bridge)
        self.assertIn('omni.outbound.log', log_model)
        self.assertIn('omni_attach_tags', message)
        self.assertIn('_omni_tag_latest_customer_message', intel)
        self.assertIn('menu_omni_outbound_log', ops)

    def test_res_company_omnichannel_tab_markers_present(self):
        rc = (ROOT / 'addons/omnichannel_bridge/models/res_company.py').read_text()
        v = (ROOT / 'addons/omnichannel_bridge/views/res_company_views.xml').read_text()
        oi = (ROOT / 'addons/omnichannel_bridge/models/omni_integration.py').read_text()
        self.assertIn('omni_integration_ids', rc)
        self.assertIn('action_omni_sync_messenger_channels', rc)
        self.assertIn('omni_ensure_integration_rows_for_company_ids', oi)
        self.assertIn('view_company_form_omnichannel', v)
        self.assertIn('base.view_company_form', v)
        self.assertIn('Додати всі канали з реєстру', v)

    def test_omni_inbox_thread_operator_dashboard_markers_present(self):
        inbox = (ROOT / 'addons/omnichannel_bridge/models/omni_inbox_thread.py').read_text()
        ch = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        v = (ROOT / 'addons/omnichannel_bridge/views/omni_inbox_thread_views.xml').read_text()
        menu = (ROOT / 'addons/omnichannel_bridge/views/omni_integration_views.xml').read_text()
        self.assertIn("_name = 'omni.inbox.thread'", inbox)
        self.assertIn('def _sync_from_discuss_channels', inbox)
        self.assertIn('def action_open_in_discuss', inbox)
        self.assertNotIn('omni_dashboard_last_message_preview', ch)
        self.assertIn('def _omni_sync_inbox_rows', ch)
        self.assertIn('action_omni_inbox_thread', v)
        self.assertIn('action_omni_inbox_thread', menu)
        self.assertIn('menu_omni_open_discuss', menu)
        self.assertIn('view_omni_inbox_thread_form_conversation', v)
        wiz = (ROOT / 'addons/omnichannel_bridge/models/omni_conversation_identity_wizard.py').read_text()
        wiz_xml = (ROOT / 'addons/omnichannel_bridge/views/omni_conversation_identity_wizard_views.xml').read_text()
        self.assertIn("_name = 'omni.conversation.identity.wizard'", wiz)
        self.assertIn('def action_link_partner', wiz)
        self.assertIn('name="search_done"', wiz_xml)
        self.assertIn('invisible="not search_done"', wiz_xml)

    def test_discuss_client_card_parity_markers_present(self):
        manifest = (ROOT / 'addons/omnichannel_bridge/__manifest__.py').read_text()
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        action_js = (ROOT / 'addons/omnichannel_bridge/static/src/omni_thread_actions.js').read_text()
        panel_js = (
            ROOT / 'addons/omnichannel_bridge/static/src/components/omni_client_info_panel/omni_client_info_panel.js'
        ).read_text()
        panel_xml = (
            ROOT / 'addons/omnichannel_bridge/static/src/components/omni_client_info_panel/omni_client_info_panel.xml'
        ).read_text()
        thread_patch = (ROOT / 'addons/omnichannel_bridge/static/src/thread_patch.js').read_text()
        integration_views = (
            ROOT / 'addons/omnichannel_bridge/views/omni_integration_views.xml'
        ).read_text()
        self.assertIn("'web'", manifest)
        self.assertIn('static/src/omni_thread_actions.js', manifest)
        self.assertIn('omni_get_client_info_for_channel', channel)
        self.assertIn('omni_refresh_client_info_for_channel', channel)
        self.assertIn('_omni_refresh_telegram_avatar', channel)
        self.assertIn('_to_store', channel)
        self.assertIn('omni-client-info', action_js)
        self.assertIn('OmniClientInfoPanel', panel_js)
        self.assertIn('omni_action_open_conversation_card_from_panel', channel)
        self.assertIn(
            'return self.omni_action_open_conversation_card_from_panel(channel_id)',
            channel,
        )
        self.assertIn('onOpenConversationCardClick', panel_js)
        self.assertIn('mail.action_discuss', integration_views)
        self.assertIn('Оновити профіль', panel_xml)
        self.assertIn('state.card.channel_profile', panel_xml)
        self.assertIn('getChat', channel)
        self.assertIn('channel_profile', channel)
        self.assertIn('omni_is_stub_provider', channel)
        self.assertIn('_omni_whatsapp_cloud_parts', channel)
        contracts = (
            ROOT / 'addons/omnichannel_bridge/utils/omni_provider_contracts.py'
        ).read_text()
        self.assertIn('OMNI_PROVIDER_DELIVERY', contracts)
        self.assertIn("'tiktok'", contracts)
        self.assertTrue((ROOT / 'docs/MESSENGER_WEBHOOK_IDENTITY_SCHEMA.md').is_file())
        self.assertIn('WhatsApp Cloud API', (ROOT / 'docs/MESSENGER_WEBHOOK_IDENTITY_SCHEMA.md').read_text())
        self.assertIn('omniProvider', thread_patch)

    def test_sendpulse_conversation_card_reference_doc_present(self):
        ref = ROOT / 'docs/SENDPULSE_CONVERSATION_CARD_REFERENCE.md'
        self.assertTrue(ref.is_file())
        body = ref.read_text()
        self.assertIn('sendpulse.connect', body)
        self.assertIn('view_sendpulse_connect_form', body)
        self.assertIn('SendpulseInfoPanel', body)
        chk = (ROOT / 'docs/TZ_CHECKLIST.md').read_text()
        self.assertIn('SENDPULSE_CONVERSATION_CARD_REFERENCE.md', chk)

    def test_telegram_getchat_ingest_marker_present(self):
        bridge = (ROOT / 'addons/omnichannel_bridge/models/omni_bridge.py').read_text()
        self.assertIn('def _omni_telegram_getchat_snapshot', bridge)
        self.assertIn('def _omni_merge_telegram_identity_metadata', (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text())

    def test_omni_get_client_info_identity_fallback_when_partner_unlinked(self):
        """Guest / not-yet-bound threads: identity is keyed by external_id, not partner_id."""
        py = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        self.assertIn('def _omni_identity_for_channel', py)
        self.assertIn("'external_id', '=', ext)", py)

    def test_anti_repeat_prefill_markers_present(self):
        ai = (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text()
        self.assertIn('_omni_prefill_partner_from_inbound_text', ai)
        self.assertIn('_omni_text_has_contact', ai)
        self.assertIn('profile_prefill_from_inbound', ai)

    def test_tg_marketing_consent_markers_present(self):
        bridge = (ROOT / 'addons/omnichannel_bridge/models/omni_bridge.py').read_text()
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        self.assertIn('_omni_is_tg_marketing_subscribe', bridge)
        self.assertIn('_omni_is_tg_marketing_unsubscribe', bridge)
        self.assertIn('omni_tg_marketing_opt_in', partner)

    def test_tg_broadcast_markers_present(self):
        broadcast = (ROOT / 'addons/omnichannel_bridge/models/omni_tg_broadcast.py').read_text()
        ops = (ROOT / 'addons/omnichannel_bridge/views/omni_ops_views.xml').read_text()
        self.assertIn('omni.tg.broadcast.wizard', broadcast)
        self.assertIn('only_opted_in', broadcast)
        self.assertIn('menu_omni_tg_broadcast', ops)

    def test_promo_entities_markers_present(self):
        promo = (ROOT / 'addons/omnichannel_bridge/models/omni_promo.py').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('omni.promo', promo)
        self.assertIn('omni_promo_context_block', knowledge)
        self.assertIn('PROMOTIONS:', knowledge)

    def test_insurance_entities_and_context_markers_present(self):
        insurance = (ROOT / 'addons/omnichannel_bridge/models/omni_insurance_package.py').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('omni.insurance.package', insurance)
        self.assertIn('omni_insurance_context_block', knowledge)
        self.assertIn('INSURANCE_PACKAGES:', knowledge)

    def test_legal_document_registry_markers_present(self):
        legal_doc = (ROOT / 'addons/omnichannel_bridge/models/omni_legal_document.py').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('omni.legal.document', legal_doc)
        self.assertIn('version_tag', legal_doc)
        self.assertIn('approved_by', legal_doc)
        self.assertIn('omni_legal_documents_context_block', knowledge)
        self.assertIn('LEGAL_DOCUMENTS:', knowledge)

    def test_event_registration_truth_sync_markers_present(self):
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('event.registration', knowledge)
        self.assertIn('event.registration.state_count', knowledge)
        self.assertIn('event_ticket.future_events.event_registration_truth', knowledge)

    def test_payment_policy_markers_present(self):
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('omni_payment_policy_block', knowledge)
        self.assertIn('PAYMENT_POLICY:', knowledge)

    def test_legal_pack_settings_markers_present(self):
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('legal_terms_url', settings)
        self.assertIn('legal_short_rodo_text', settings)
        self.assertIn('Approved short legal wording', knowledge)

    def test_prompt_versioning_markers_present(self):
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        self.assertIn('llm_prompt_version', settings)
        self.assertIn('llm_experiment_tag', settings)
        self.assertIn('PROMPT_VERSIONING:', knowledge)
        self.assertIn('RELEASE_FINGERPRINT:', knowledge)

    def test_channel_consent_policy_markers_present(self):
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        knowledge = (ROOT / 'addons/omnichannel_bridge/models/omni_knowledge.py').read_text()
        ai = (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text()
        self.assertIn('consent_meta_text', settings)
        self.assertIn('consent_site_text', settings)
        self.assertIn('CHANNEL_CONSENT_POLICY:', knowledge)
        self.assertIn('consent_site_text', ai)

    def test_prompt_audit_markers_present(self):
        audit = (ROOT / 'addons/omnichannel_bridge/models/omni_prompt_audit.py').read_text()
        settings = (ROOT / 'addons/omnichannel_bridge/models/res_config_settings.py').read_text()
        ops = (ROOT / 'addons/omnichannel_bridge/views/omni_ops_views.xml').read_text()
        self.assertIn('omni.prompt.audit', audit)
        self.assertIn('tracked_keys', settings)
        self.assertIn('menu_omni_prompt_audit', ops)

    def test_reserve_waitlist_model_markers_present(self):
        reserve = (ROOT / 'addons/omnichannel_bridge/models/omni_reserve_entry.py').read_text()
        ai = (ROOT / 'addons/omnichannel_bridge/models/omni_ai.py').read_text()
        self.assertIn('omni.reserve.entry', reserve)
        self.assertIn('_omni_create_or_get_reserve_entry', ai)
        self.assertIn('omni_reserve_entry_id', ai)


if __name__ == '__main__':
    unittest.main()
