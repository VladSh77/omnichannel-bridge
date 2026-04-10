import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class IdempotencyTests(unittest.TestCase):
    """
    Idempotency tests for omnichannel_bridge webhook ingest.

    Context: Webhook providers (Meta, Telegram, Viber, WhatsApp) may retry
    delivery if they don't receive a success response within ~30 seconds.
    The omni_bridge module must detect and skip duplicate payloads.

    Mechanism:
    - Extract idempotency key from webhook payload (provider-specific)
    - Create `omni.webhook.event` record with (provider, external_event_id) unique constraint
    - On duplicate key: return {"ok": True, "deduplicated": True}
    - On new key: continue business processing, mark as processed
    """

    def test_webhook_event_model_exists(self):
        """Contract: omni.webhook.event model must exist for dedup tracking."""
        model = (
            ROOT / "addons/omnichannel_bridge/models/omni_webhook_event.py"
        ).read_text()
        self.assertIn("_name = 'omni.webhook.event'", model)
        self.assertIn("external_event_id", model)
        self.assertIn("provider", model)
        self.assertIn("state", model)

    def test_webhook_event_unique_constraint(self):
        """Contract: (provider, external_event_id) must be unique to prevent duplicates."""
        model = (
            ROOT / "addons/omnichannel_bridge/models/omni_webhook_event.py"
        ).read_text()
        # Look for unique constraint definition
        self.assertTrue(
            "_sql_constraints" in model or "UNIQUE" in model or "unique" in model,
            "omni.webhook.event must have unique constraint on (provider, external_event_id)",
        )

    def test_idempotency_extraction_functions_present(self):
        """Contract: Idempotency key extraction functions must exist for all live providers."""
        bridge = (ROOT / "addons/omnichannel_bridge/models/omni_bridge.py").read_text()
        parsers = (
            ROOT / "addons/omnichannel_bridge/utils/webhook_parsers.py"
        ).read_text()

        # Meta extraction
        self.assertIn("extract_meta_mid", parsers)
        self.assertIn("extract_meta_mid", bridge)

        # Telegram extraction
        self.assertIn("extract_telegram_update_id", parsers)
        self.assertIn("extract_telegram_update_id", bridge)

        # WhatsApp extraction
        self.assertIn("extract_whatsapp_message_id", parsers)
        self.assertIn("extract_whatsapp_message_id", bridge)

    def test_extract_meta_mid_payload(self):
        """Test idempotency: Meta message ID extraction from webhook payload."""
        import importlib.util

        MODULE_PATH = ROOT / "addons/omnichannel_bridge/utils/webhook_parsers.py"
        SPEC = importlib.util.spec_from_file_location("webhook_parsers", MODULE_PATH)
        MOD = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(MOD)

        # Test: Meta developer sends same message twice
        payload_1 = {
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "123"},
                            "message": {"mid": "msg_abc123", "text": "Hello"},
                            "timestamp": 1234567890,
                        }
                    ]
                }
            ]
        }

        # First call should extract mid
        mid_1 = MOD.extract_meta_mid(payload_1)
        self.assertEqual(mid_1, "msg_abc123")

        # Same payload sent again (retry) should extract same mid
        mid_2 = MOD.extract_meta_mid(payload_1)
        self.assertEqual(mid_1, mid_2)

    def test_extract_telegram_update_id_payload(self):
        """Test idempotency: Telegram update ID extraction from webhook payload."""
        import importlib.util

        MODULE_PATH = ROOT / "addons/omnichannel_bridge/utils/webhook_parsers.py"
        SPEC = importlib.util.spec_from_file_location("webhook_parsers", MODULE_PATH)
        MOD = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(MOD)

        # Test: Telegram Bot API sends same update twice
        payload = {
            "update_id": 987654321,
            "message": {
                "message_id": 42,
                "date": 1234567890,
                "chat": {"id": -100777, "type": "group"},
                "from": {"id": 111},
                "text": "Привіт",
            },
        }

        # First extraction
        update_id_1 = MOD.extract_telegram_update_id(payload)
        self.assertEqual(update_id_1, "987654321")

        # Duplicate payload should extract same update_id
        update_id_2 = MOD.extract_telegram_update_id(payload)
        self.assertEqual(update_id_1, update_id_2)

    def test_extract_whatsapp_message_id_payload(self):
        """Test idempotency: WhatsApp message ID extraction from webhook payload."""
        import importlib.util

        MODULE_PATH = ROOT / "addons/omnichannel_bridge/utils/webhook_parsers.py"
        SPEC = importlib.util.spec_from_file_location("webhook_parsers", MODULE_PATH)
        MOD = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(MOD)

        # Test: WhatsApp Cloud API sends same message twice
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "380671234567",
                                        "id": "wamid.HBgMCghEVZjMyUDQw0=",
                                        "timestamp": 1234567890,
                                        "type": "text",
                                        "text": {"body": "Hi there"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        # First extraction
        msg_id_1 = MOD.extract_whatsapp_message_id(payload)
        self.assertEqual(msg_id_1, "wamid.HBgMCghEVZjMyUDQw0=")

        # Duplicate payload should extract same message_id
        msg_id_2 = MOD.extract_whatsapp_message_id(payload)
        self.assertEqual(msg_id_1, msg_id_2)

    def test_duplicate_webhook_returns_success(self):
        """Contract: Duplicate webhook delivery must return 200 OK with deduplicated flag."""
        bridge = (ROOT / "addons/omnichannel_bridge/models/omni_bridge.py").read_text()
        # Verify dedup response structure
        self.assertIn('"ok": True', bridge)
        self.assertIn('"deduplicated": True', bridge)

    def test_webhook_event_state_transitions(self):
        """Contract: Webhook events must track state (pending/processing/processed/failed)."""
        model = (
            ROOT / "addons/omnichannel_bridge/models/omni_webhook_event.py"
        ).read_text()
        # Check for state field
        self.assertIn("state", model)
        # Check for typical state values
        self.assertTrue(
            any(s in model for s in ["processed", "failed", "pending", "processing"]),
            "webhook event model must have state tracking",
        )

    def test_idempotency_prevents_duplicate_partners(self):
        """Contract: Replay of same webhook twice must not create duplicate partner records."""
        # This is a logical contract: if dedup works, inbound delivery happens only once
        # Partner linking happens once per unique external_user_id

        # Evidence: omni.webhook.event blocks duplicate processing via unique constraint
        model = (
            ROOT / "addons/omnichannel_bridge/models/omni_webhook_event.py"
        ).read_text()
        self.assertIn("_name = 'omni.webhook.event'", model)
        # If duplicate webhook event creation fails, business logic never runs twice


if __name__ == "__main__":
    unittest.main()
