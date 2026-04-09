#!/usr/bin/env python3
"""
Lightweight runtime smoke checks for omnichannel_bridge.
Run inside `odoo shell` context: `python < this_file` is not required;
copy/paste the `run(env)` body or import from custom tooling.
"""


def run(env):
    mod = env['ir.module.module'].search([('name', '=', 'omnichannel_bridge')], limit=1)
    assert mod and mod.state == 'installed', 'Module not installed'
    assert 'omni.legal.document' in env, 'Legal document model missing (upgrade omnichannel_bridge)'
    assert 'omni.insurance.package' in env, 'Insurance package model missing (upgrade omnichannel_bridge)'
    assert 'omni.prompt.audit' in env, 'Prompt audit model missing (upgrade omnichannel_bridge)'
    assert 'omni.knowledge.article' in env, 'Knowledge model missing'
    assert 'omni.stage.transition' in env, 'Stage transition model missing'
    assert 'omni.payment.event' in env, 'Payment event model missing'
    assert 'omni_purchase_confirmed_at' in env['res.partner']._fields, 'Partner payment field missing'
    crons = env['ir.cron'].search([('code', 'ilike', 'omni_cron_')], limit=200)
    assert bool(crons), 'No omnichannel crons found'
    return {
        'module_state': mod.state,
        'cron_count': len(crons),
    }
