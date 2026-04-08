# DPIA Data Categories (Omnichannel Baseline)

This document defines baseline data categories for omnichannel processing.

## Categories

- Identity/contact: `name`, `email`, `phone`, messenger ids.
- Sales qualification: child age, preferred period, departure city, budget.
- Conversation metadata: provider, channel/thread ids, timestamps, tags.
- Commercial events: order/payment references and aggregate amounts.

## Minimization rules

- Keep only fields needed for camp selection, booking follow-up, and legal obligations.
- Child-sensitive fields are purged by retention policy (`retention_child_data_days`).
- Logs must mask direct PII where configured.

## Lawful handling baseline

- Consent snippets are channel-specific and legally approved.
- Right-to-erasure uses Odoo-side anonymization SOP.
- Provider platform retention/deletion limits are handled by separate legal workflow.
