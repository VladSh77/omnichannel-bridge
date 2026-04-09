# -*- coding: utf-8 -*-
"""
Реєстр каналів omnichannel: що вже приймає webhook у модулі, а що — лише заглушка.

Детальні схеми JSON і посилання на офіційні доки: docs/MESSENGER_WEBHOOK_IDENTITY_SCHEMA.md
"""

# Стан доставки в цьому репозиторії (не плутати з наявністю бізнес-акаунта у Meta/TikTok).
DELIVERY_LIVE = 'live'
DELIVERY_STUB = 'stub'

# provider -> 'live' | 'stub'
OMNI_PROVIDER_DELIVERY = {
    'telegram': DELIVERY_LIVE,
    'meta': DELIVERY_LIVE,
    'whatsapp': DELIVERY_LIVE,
    'twilio_whatsapp': DELIVERY_LIVE,
    'viber': DELIVERY_LIVE,
    'site_livechat': DELIVERY_LIVE,
    'tiktok': DELIVERY_STUB,
    'line': DELIVERY_STUB,
}

OMNI_STUB_PROVIDERS = frozenset(
    p for p, state in OMNI_PROVIDER_DELIVERY.items() if state == DELIVERY_STUB
)


def omni_is_stub_provider(provider):
    return (provider or '') in OMNI_STUB_PROVIDERS


def omni_provider_delivery_state(provider):
    return OMNI_PROVIDER_DELIVERY.get(provider or '', DELIVERY_STUB)
