# -*- coding: utf-8 -*-


def ensure_act_window_views(action):
    """
    Odoo 17 web client _preprocessAction expects action.views and calls .map on it.
    Some RPC paths return act_window dicts without views even after _for_xml_id.
    """
    if not isinstance(action, dict):
        return action
    if action.get('type') != 'ir.actions.act_window':
        return action
    if action.get('views'):
        return action
    vm = (action.get('view_mode') or 'form').strip()
    modes = [m.strip() for m in vm.split(',') if m.strip()]
    out_modes = ['list' if m == 'tree' else m for m in modes]
    return dict(action, views=[(False, m) for m in out_modes])
