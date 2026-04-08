# Right to Erasure SOP

Operational SOP for handling user deletion requests in omnichannel flows.

## Scope

- Odoo-side omnichannel profile fields.
- Messenger identity mappings stored in `omni.partner.identity`.
- Internal references in Discuss/CRM needed for operational traceability.

## Procedure

1. Verify requestor identity using approved business process.
2. Open the partner card in Odoo.
3. Run `action_omni_right_to_erasure`.
4. Confirm:
   - contact fields are cleared,
   - omnichannel profile fields are anonymized,
   - identity display metadata is marked as erased.
5. Log ticket id / operator / timestamp in internal compliance log.

## Platform limitations

- Meta/Telegram-side message retention is governed by provider policies and cannot be retroactively hard-deleted from provider infrastructure by this action alone.
- If legal request requires provider-side follow-up, execute platform-specific support/legal workflow in parallel.

## Evidence checklist

- partner id,
- execution timestamp,
- operator name,
- request reference id.
