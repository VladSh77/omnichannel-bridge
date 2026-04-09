#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Probe how omnichannel_bridge resolves free places for camp products (odoo shell).

Usage on the Odoo host (adjust -c / -d):

  docker exec -it campscout_web odoo shell -c /etc/odoo/odoo.conf -d campscout --no-http \\
    < scripts/odoo_probe_camp_places.py

Or paste into an interactive odoo shell:

  from odoo.tools import config
  exec(open('/mnt/custom-addons/omnichannel_bridge_repo/addons/../scripts/odoo_probe_camp_places.py').read())
  run(env)

Default search: POSHUMIMO shift 1 (Polish/UA names + CS-PSH).
"""


def run(env, partner=None):
    Know = env['omni.knowledge'].sudo()
    Product = env['product.template'].sudo()
    or_block = [
        '|',
        '|',
        '|',
        ('default_code', 'ilike', 'CS-PSH'),
        ('name', 'ilike', 'poszum'),
        ('name', 'ilike', 'пошум'),
        ('name', 'ilike', 'POSHUMIMO'),
    ]
    domain = ['&', ('sale_ok', '=', True)] + or_block
    if 'is_published' in Product._fields:
        domain = ['&', ('is_published', '=', True)] + domain
    found = Product.search(domain, limit=30, order='id desc')
    lines = []
    lines.append('=== omni camp probe (product.template) ===')
    lines.append('matches: %s' % len(found))
    for tmpl in found:
        is_camp = Know._omni_is_camp_product(tmpl)
        places, src = Know._omni_extract_places_with_source(tmpl)
        lines.append(
            '- id=%s | default_code=%s | name=%s | is_camp=%s | places=%s | src=%s'
            % (
                tmpl.id,
                getattr(tmpl, 'default_code', None) or '',
                (tmpl.name or '')[:80],
                is_camp,
                places,
                src,
            )
        )
    lines.append('--- catalog snippet (same logic as LLM FACTS) ---')
    lines.append(Know.omni_catalog_context_for_llm(partner, limit=15))
    return '\n'.join(lines)


if __name__ == '__main__':
    raise SystemExit(
        'Import this file inside odoo shell and call run(env), '
        'or pipe into odoo shell stdin with a tiny wrapper that defines env.'
    )
