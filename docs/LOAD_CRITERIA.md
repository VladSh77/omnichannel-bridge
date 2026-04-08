# Load Criteria (Baseline)

Baseline acceptance criteria for peak ad traffic windows.

## Targets

- Concurrent active threads: 100+
- Sustained inbound rate: 20 messages/minute
- P95 enqueue latency to AI job: under 5 seconds
- P95 outbound send latency (provider API acknowledged): under 8 seconds
- Error budget during peak window: under 2% failed outbound attempts (excluding provider hard outages)

## Mandatory Guards

- Webhook idempotency active (`omni.webhook.event`)
- Outbound conflict/duplicate guard active
- Fallback message active when LLM backend unavailable
- Manager-session lock active

## Verification Window

- Execute during staging/prod-copy load drill for at least 15 minutes sustained load.
- Capture logs and metrics snapshot in incident/release notes.
