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
        self.assertIn('omni_coupon_code', content)
        self.assertIn('_omni_apply_public_coupon', content)
        self.assertIn('_omni_register_coupon_redemption', content)
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
        self.assertIn('_OMNI_STAGE_TRANSITIONS', partner)
        self.assertIn('omni_set_sales_stage', partner)
        self.assertIn('omni.stage.event', partner)
        self.assertTrue((ROOT / 'addons/omnichannel_bridge/models/omni_stage_event.py').exists())
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


if __name__ == '__main__':
    unittest.main()
