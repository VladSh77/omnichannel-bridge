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
