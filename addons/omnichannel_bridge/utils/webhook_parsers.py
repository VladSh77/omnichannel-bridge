# -*- coding: utf-8 -*-
"""Pure webhook parser helpers for CI-friendly tests."""


def extract_telegram_update_id(data):
    update_id = (data or {}).get('update_id')
    return str(update_id) if update_id is not None else ''


def extract_meta_mid(data):
    for entry in (data or {}).get('entry', []):
        for event in entry.get('messaging', []):
            msg = event.get('message') or {}
            mid = msg.get('mid')
            if mid:
                return str(mid)
    return ''


def extract_whatsapp_message_id(data):
    for entry in (data or {}).get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value') or {}
            for msg in value.get('messages', []):
                msg_id = msg.get('id')
                if msg_id:
                    return str(msg_id)
    return ''


def extract_viber_message_token(data):
    token = (data or {}).get('message_token')
    return str(token) if token is not None else ''
