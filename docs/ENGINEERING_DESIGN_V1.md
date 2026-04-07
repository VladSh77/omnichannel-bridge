# Engineering Design v1 — Idempotency and Async Queue

## Objective

Define the first production-grade technical increment:

1. webhook idempotency,
2. asynchronous AI processing,
3. bot/human race guard.

## Part 1: Webhook Idempotency

## Problem

Providers may redeliver the same webhook event. Without deduplication, duplicate messages and duplicate AI actions can occur.

## Proposed Model

- New model: `omni.webhook.event`
- Suggested fields:
  - `provider` (char/selection),
  - `external_event_id` (char, indexed),
  - `payload_hash` (char, indexed),
  - `state` (`received`, `processed`, `failed`),
  - `received_at`,
  - `processed_at`,
  - `error_message`.

## Key Rule

- Unique constraint on `(provider, external_event_id)` when event id exists.
- Fallback unique path: `(provider, payload_hash)` for providers/events without stable ids.

## Processing Flow

1. Parse inbound payload and derive idempotency key.
2. Attempt create idempotency record.
3. If duplicate key:
  - return success response to provider,
  - skip business processing.
4. If new key:
  - continue inbound delivery flow.
5. Mark as processed/failed with timestamp.

## Part 2: Asynchronous AI Queue

## Problem

LLM requests can exceed safe webhook timing windows and create retry storms.

## Proposed Model

- New model: `omni.ai.job`
- Suggested fields:
  - `channel_id`,
  - `partner_id`,
  - `provider`,
  - `user_text`,
  - `state` (`queued`, `running`, `done`, `failed`, `cancelled`),
  - `attempt_count`,
  - `next_attempt_at`,
  - `last_error`.

## Execution Strategy

- Webhook path:
  - enqueue AI job, return quickly.
- Worker path:
  - cron job processes queued jobs in bounded batches.
  - retry with backoff on transient failures.

## Delivery Guarantees

- At-least-once queue execution with idempotent message posting guard.
- Safe retry policy:
  - max attempts configurable,
  - fallback message when retries exhausted.

## Part 3: Bot/Human Race Guard

## Problem

Manager and bot can reply almost simultaneously, reducing trust.

## Proposed Channel Controls

- Add fields on `mail.channel`:
  - `omni_bot_paused` (bool),
  - `omni_bot_pause_reason` (char),
  - `omni_last_human_reply_at` (datetime),
  - `omni_last_bot_reply_at` (datetime).

## Guard Rules

- If human reply detected recently, AI job is cancelled or deferred.
- If explicit pause flag is set, AI job is skipped.
- If client explicitly requests human, pause bot and notify manager.

## MVP Sequencing

1. Implement idempotency model and guards.
2. Implement AI job queue + cron worker.
3. Add bot/human lock fields and decision gate.
4. Add observability counters and structured logs.

## Acceptance Criteria

- Duplicate provider events do not create duplicate inbound messages.
- Webhook endpoints return quickly while AI replies still execute.
- No bot reply is sent after recent human manager reply in guarded window.
