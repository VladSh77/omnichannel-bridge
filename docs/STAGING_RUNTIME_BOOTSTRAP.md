# Staging Runtime Bootstrap

Goal: keep staging aligned with production custom modules and integration behavior.

## Required baseline

- same `addons_path` custom repositories as production;
- same `omnichannel_bridge` branch/commit policy;
- same external integration settings structure (with staging tokens/secrets).

## Bootstrap steps

1. Clone custom addons repos used in production.
2. Restore sanitized production DB copy + filestore.
3. Configure staging Odoo with matching `addons_path`.
4. Upgrade `omnichannel_bridge`.
5. Run runtime smoke (`scripts/odoo_runtime_smoke.py`).

## Exit criteria

- module installed and all required omnichannel models present;
- cron jobs active;
- webhook endpoints reachable in staging;
- smoke report saved for release ticket.
