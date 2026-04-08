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


if __name__ == '__main__':
    unittest.main()
