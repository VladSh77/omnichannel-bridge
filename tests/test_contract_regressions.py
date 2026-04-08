import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ContractRegressionTests(unittest.TestCase):
    def test_webhook_controller_has_payload_limit(self):
        content = (ROOT / 'addons/omnichannel_bridge/controllers/main.py').read_text()
        self.assertIn('webhook_max_body_bytes', content)
        self.assertIn('payload_too_large', content)

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
        self.assertIn('_omni_whatsapp_send_to_wa_id', content)
        self.assertIn('extract_whatsapp_message_id', parsers)

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

    def test_fsm_and_race_markers_present(self):
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        memory = (ROOT / 'addons/omnichannel_bridge/models/omni_memory.py').read_text()
        self.assertIn('_OMNI_STAGE_TRANSITIONS', partner)
        self.assertIn('omni_set_sales_stage', partner)
        self.assertIn('omni.stage.event', partner)
        self.assertTrue((ROOT / 'addons/omnichannel_bridge/models/omni_stage_event.py').exists())
        self.assertIn("source='omni_memory'", memory)
        self.assertIn('omni_set_sales_stage(', memory)
        self.assertIn('manager_session_active', channel)
        self.assertIn('omni_manager_session_active_now', channel)

    def test_retention_and_erasure_markers_present(self):
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        webhook = (ROOT / 'addons/omnichannel_bridge/models/omni_webhook_event.py').read_text()
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        self.assertIn('omni_cron_purge_old_messages', channel)
        self.assertIn('omni_cron_purge_old_events', webhook)
        self.assertIn('action_omni_right_to_erasure', partner)

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
        self.assertIn('omni_detected_lang', channel)

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
