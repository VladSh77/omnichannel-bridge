# Child Data Retention Policy

Baseline minimization policy for child-sensitive fields in omnichannel profile.

## Covered fields

- `res.partner.omni_child_age`

## Runtime controls

- Setting: `omnichannel_bridge.retention_child_data_days`
- Daily cron: `omni_cron_purge_child_sensitive_fields`

When retention window is exceeded, child age is removed from profile card automatically.

## Operational notes

- Keep only minimum child data needed for camp selection and sales follow-up.
- For legal/medical specifics, handoff to manager and avoid long-term storage in free-form memory.
- If stricter legal requirement applies, reduce retention days accordingly.
