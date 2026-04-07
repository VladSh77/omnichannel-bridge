# Technical Passport — `omnichannel_bridge`

## Module Identity

- Name: `omnichannel_bridge`
- Platform: Odoo 17
- Language: Python 3.10+
- License: LGPL-3
- Runtime role: Omnichannel ingest, routing, AI reply orchestration

## Scope

- Aggregates inbound messages from supported channels into Odoo Discuss.
- Maps customer identity to `res.partner`.
- Builds strict database-grounded context for AI replies.
- Sends outbound replies back to provider channels.

## Current Channel Support

- Production-ready:
  - Meta (Facebook Messenger + Instagram Direct)
  - Telegram Bot API
- Stub-only:
  - WhatsApp
  - Viber

## Core Components

- `omni.bridge`:
  - Webhook ingestion and provider routing.
  - Partner/channel resolution.
  - Inbound delivery pipeline.
- `omni.ai`:
  - LLM backend dispatch (`ollama` or `openai`).
  - Strict grounding policy injection.
  - Fallback reply strategy when LLM is unavailable.
- `omni.knowledge`:
  - Facts bundle builder from ORM data only.
  - Catalog, payments, orders, greeting style, thread transcript.

## Integration Contracts

- Inbound endpoint contracts:
  - `GET/POST /omni/webhook/meta`
  - `POST /omni/webhook/telegram`
- AI backend contracts:
  - Ollama OpenAI-compatible API: `/v1/chat/completions`
  - Ollama native API: `/api/chat`
  - OpenAI API: `/v1/chat/completions`

## Data and Safety Principles

- Source of truth for commercial facts is Odoo ORM, not model free text.
- AI is used as a response engine, not as a fact authority.
- Sensitive child-related data must be minimized in prompt context.
- Legal statements must be restricted to approved legal facts pack.

## Non-Functional Requirements (Target)

- Idempotent webhook processing.
- Async LLM processing to avoid webhook timeout coupling.
- Bot/human race prevention.
- Traceability of bot decision path per thread.

## Environment Strategy

- Development: local only.
- Staging: mandatory parity with production `addons_path` and custom modules.
- Production: deploy only from reviewed, versioned git commits.

## Change Control Policy

- Work sequence is strict:
  1. Local implementation and validation.
  2. Git commit/push.
  3. Server delivery only after explicit approval.
