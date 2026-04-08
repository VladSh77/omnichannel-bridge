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

    def test_fsm_and_race_markers_present(self):
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        self.assertIn('_OMNI_STAGE_TRANSITIONS', partner)
        self.assertIn('omni_set_sales_stage', partner)
        self.assertIn('manager_session_active', channel)
        self.assertIn('omni_manager_session_active_now', channel)

    def test_retention_and_erasure_markers_present(self):
        channel = (ROOT / 'addons/omnichannel_bridge/models/mail_channel.py').read_text()
        webhook = (ROOT / 'addons/omnichannel_bridge/models/omni_webhook_event.py').read_text()
        partner = (ROOT / 'addons/omnichannel_bridge/models/res_partner.py').read_text()
        self.assertIn('omni_cron_purge_old_messages', channel)
        self.assertIn('omni_cron_purge_old_events', webhook)
        self.assertIn('action_omni_right_to_erasure', partner)


if __name__ == '__main__':
    unittest.main()
