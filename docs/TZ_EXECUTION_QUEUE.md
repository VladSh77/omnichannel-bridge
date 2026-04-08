# TZ Execution Queue (Phase 1)

## 1) Baseline Freeze + Definition of Done

Status: in progress

Baseline:

- Branch: `main`
- Baseline commit: `e695d03`
- Deployment baseline on server before new wave: documented in `docs/IMPLEMENTATION_LOG.md`

Purpose:

- Lock a stable checkpoint before the next TZ implementation waves.
- Define objective acceptance criteria so each next item is closed by tests, not by interpretation.

DoD per major block:

1. Channels (Meta/Telegram/WhatsApp/Viber)
   - Inbound and outbound smoke pass on staging.
   - Idempotency verified for replayed webhook payload.
   - No duplicate customer messages in Discuss.

2. Livechat entry UX (§2.2)
   - Chosen UX path implemented (pre-chat or buttons+composer).
   - Contact capture mapped to `res.partner`/`crm.lead`.
   - Composer remains available in target scenarios.

3. FSM + race semantics
   - Stage transitions enforced by explicit transition guard.
   - Manager lock prevents bot replies during active manager session.
   - Contract tests cover race markers and transition guards.

4. Camp seats/reserve/coupon
   - Seats mapping validated against production custom modules.
   - Sold-out path routes to reserve/handoff flow.
   - Coupon validation and redemption accounting active in `sale.order`.

5. Compliance/operations
   - Retention cron jobs active.
   - PII masking enabled for bridge error logs.
   - Right-to-erasure action available on partner card.

6. Quality gate (CI)
   - Compile checks pass for addon and tests.
   - Unit+contract tests pass in CI on push/PR.
   - No new linter errors in changed files.

Exit criteria for item 1:

- Baseline commit is documented.
- DoD matrix exists and is linked from README.
- Implementation log contains baseline freeze entry.
