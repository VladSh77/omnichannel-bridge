#!/usr/bin/env python3
"""
Lightweight runtime smoke checks for omnichannel_bridge.
Run inside `odoo shell` context: `python < this_file` is not required;
copy/paste the `run(env)` body or import from custom tooling.
"""

# Every ModelsModel / TransientModel _name in addons/omnichannel_bridge/models/.
# If any is missing in env, menus/RPC fail with KeyError — usually stale code or no -u.
_REQUIRED_OMNI_MODELS = (
    'omni.ai',
    'omni.ai.job',
    'omni.bridge',
    'omni.coupon.redemption',
    'omni.crm.analytics.wizard',
    'omni.crm.analytics.wizard.line',
    'omni.insurance.package',
    'omni.integration',
    'omni.inbox.thread',
    'omni.knowledge',
    'omni.knowledge.article',
    'omni.legal.document',
    'omni.manager.reply.assist',
    'omni.manager.reply.template',
    'omni.memory',
    'omni.moderation.rule',
    'omni.notify',
    'omni.objection.policy',
    'omni.outbound.log',
    'omni.partner.identity',
    'omni.payment.event',
    'omni.prompt.audit',
    'omni.promo',
    'omni.reserve.entry',
    'omni.sales.intel',
    'omni.stage.event',
    'omni.stage.transition',
    'omni.tg.broadcast.wizard',
    'omni.webhook.event',
)


def run(env):
    mod = env['ir.module.module'].search([('name', '=', 'omnichannel_bridge')], limit=1)
    assert mod and mod.state == 'installed', 'Module not installed'
    for name in _REQUIRED_OMNI_MODELS:
        assert name in env, f'{name} missing in registry (upgrade omnichannel_bridge, check startup ImportError)'
    assert 'omni_purchase_confirmed_at' in env['res.partner']._fields, 'Partner payment field missing'
    crons = env['ir.cron'].search([('code', 'ilike', 'omni_cron_')], limit=200)
    assert bool(crons), 'No omnichannel crons found'
    return {
        'module_state': mod.state,
        'cron_count': len(crons),
        'omni_models_checked': len(_REQUIRED_OMNI_MODELS),
    }
