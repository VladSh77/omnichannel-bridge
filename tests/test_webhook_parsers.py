import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "addons/omnichannel_bridge/utils/webhook_parsers.py"
SPEC = importlib.util.spec_from_file_location("webhook_parsers", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
extract_meta_mid = MOD.extract_meta_mid
extract_telegram_update_id = MOD.extract_telegram_update_id
extract_whatsapp_message_id = MOD.extract_whatsapp_message_id
extract_viber_message_token = MOD.extract_viber_message_token


class WebhookParserTests(unittest.TestCase):
    def test_extract_telegram_update_id_ok(self):
        self.assertEqual(extract_telegram_update_id({"update_id": 12345}), "12345")

    def test_extract_telegram_update_id_missing(self):
        self.assertEqual(extract_telegram_update_id({}), "")

    def test_extract_meta_mid_first_match(self):
        payload = {
            "entry": [
                {
                    "messaging": [
                        {"message": {"mid": "m_1"}},
                        {"message": {"mid": "m_2"}},
                    ]
                },
            ]
        }
        self.assertEqual(extract_meta_mid(payload), "m_1")

    def test_extract_meta_mid_missing(self):
        payload = {"entry": [{"messaging": [{"message": {}}, {}]}]}
        self.assertEqual(extract_meta_mid(payload), "")

    def test_extract_whatsapp_message_id_ok(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [{"id": "wamid.HBgMTEST"}],
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(extract_whatsapp_message_id(payload), "wamid.HBgMTEST")

    def test_extract_whatsapp_message_id_missing(self):
        payload = {"entry": [{"changes": [{"value": {}}]}]}
        self.assertEqual(extract_whatsapp_message_id(payload), "")

    def test_extract_viber_message_token_ok(self):
        payload = {"event": "message", "message_token": 123456789}
        self.assertEqual(extract_viber_message_token(payload), "123456789")

    def test_extract_viber_message_token_missing(self):
        self.assertEqual(extract_viber_message_token({"event": "seen"}), "")

    # Non-text / media message scenarios

    def test_extract_meta_mid_with_image_attachment(self):
        """Messenger first-message-is-image scenario."""
        payload = {
            "entry": [
                {
                    "messaging": [
                        {
                            "message": {
                                "mid": "img_msg_123",
                                "attachments": [
                                    {"type": "image", "payload": {"url": "https://..."}}
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(extract_meta_mid(payload), "img_msg_123")

    def test_extract_meta_mid_with_sticker_and_text(self):
        """Messenger sticker with optional text."""
        payload = {
            "entry": [
                {
                    "messaging": [
                        {
                            "message": {
                                "mid": "sticker_msg_456",
                                "sticker_url": "https://platform-lookaside.fbsbx.com/platform/stickers...",
                                "text": "Found a sticker!",
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(extract_meta_mid(payload), "sticker_msg_456")

    def test_extract_telegram_update_id_with_photo(self):
        """Telegram photo message."""
        payload = {
            "update_id": 987654321,
            "message": {
                "message_id": 555,
                "photo": [{"file_id": "AgAD...", "width": 800, "height": 600}],
                "caption": "Nice pic!",
            },
        }
        self.assertEqual(extract_telegram_update_id(payload), "987654321")

    def test_extract_telegram_update_id_with_voice(self):
        """Telegram voice message (media-first)."""
        payload = {
            "update_id": 111222333,
            "message": {
                "message_id": 777,
                "voice": {"file_id": "AwAD...", "duration": 5},
                "caption": "Voice note",
            },
        }
        self.assertEqual(extract_telegram_update_id(payload), "111222333")

    def test_extract_telegram_update_id_with_video(self):
        """Telegram video message."""
        payload = {
            "update_id": 444555666,
            "message": {
                "message_id": 888,
                "video": {"file_id": "BgAD...", "width": 1280, "height": 720},
            },
        }
        self.assertEqual(extract_telegram_update_id(payload), "444555666")

    def test_extract_telegram_update_id_with_document(self):
        """Telegram file document."""
        payload = {
            "update_id": 777888999,
            "message": {
                "message_id": 999,
                "document": {"file_id": "CgAD...", "file_name": "invoice.pdf"},
                "caption": "Please review",
            },
        }
        self.assertEqual(extract_telegram_update_id(payload), "777888999")

    def test_extract_whatsapp_message_id_with_button_reply(self):
        """WhatsApp button reply message (interactive)."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.button_reply_789",
                                        "type": "button",
                                        "button": {"text": "Yes"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(extract_whatsapp_message_id(payload), "wamid.button_reply_789")

    def test_extract_whatsapp_message_id_with_interactive_list_reply(self):
        """WhatsApp interactive list selection."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.interactive_list_234",
                                        "type": "interactive",
                                        "interactive": {
                                            "type": "list_reply",
                                            "list_reply": {
                                                "title": "Option A",
                                                "id": "opt_a",
                                            },
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(
            extract_whatsapp_message_id(payload), "wamid.interactive_list_234"
        )


if __name__ == "__main__":
    unittest.main()
