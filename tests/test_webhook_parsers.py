import unittest
import importlib.util
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'addons/omnichannel_bridge/utils/webhook_parsers.py'
SPEC = importlib.util.spec_from_file_location('webhook_parsers', MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
extract_meta_mid = MOD.extract_meta_mid
extract_telegram_update_id = MOD.extract_telegram_update_id


class WebhookParserTests(unittest.TestCase):
    def test_extract_telegram_update_id_ok(self):
        self.assertEqual(extract_telegram_update_id({'update_id': 12345}), '12345')

    def test_extract_telegram_update_id_missing(self):
        self.assertEqual(extract_telegram_update_id({}), '')

    def test_extract_meta_mid_first_match(self):
        payload = {
            'entry': [
                {'messaging': [{'message': {'mid': 'm_1'}}, {'message': {'mid': 'm_2'}}]},
            ]
        }
        self.assertEqual(extract_meta_mid(payload), 'm_1')

    def test_extract_meta_mid_missing(self):
        payload = {'entry': [{'messaging': [{'message': {}}, {}]}]}
        self.assertEqual(extract_meta_mid(payload), '')


if __name__ == '__main__':
    unittest.main()
