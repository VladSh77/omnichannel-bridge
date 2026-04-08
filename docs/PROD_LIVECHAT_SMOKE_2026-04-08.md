# Production Livechat Smoke (2026-04-08)

Validated after deploy on production runtime.

## Checks

- module `omnichannel_bridge` installed and upgraded successfully;
- website livechat channel path routes into omnichannel entry flow;
- entry flow now enforces structured pre-chat sequence:
  - name capture,
  - contact capture (phone/email),
  - CRM lead creation on contact;
- menu-driven topic routing remains available while free-text composer stays usable.

## Result

- smoke status: PASS
- follow-up: keep daily spot-check on livechat handoff and manager notification path.
