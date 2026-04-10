# AI-only Launch Gate (20.9, 20.10)

Purpose: formal gate before enabling AI-only primary mode and before Phase 2 outbound.

## Phase 1 (chat-core only) checklist

- All channels pass parity matrix (`docs/CHANNEL_PARITY_E2E_CHECKLIST.md`).
- No blocking author/identity routing defects in Discuss.
- AI-only KPIs satisfied for 7 days:
  - relevancy >= 97%
  - critical hallucination <= 1%
  - automation resolution >= 95%
  - fallback-only <= 3%

## Knowledge base gate

- Only editorially approved facts are used in production responses.
- Expired/non-approved facts are excluded from RAG context.
- If fact is missing or unapproved: controlled response + manager handoff.

## Phase 2 unlock rule

- No new outbound features (email/sms/campaign automation) until:
  - Phase 1 formal sign-off is complete,
  - owner approval (`admin@campscout.eu`) is recorded,
  - stability report for last 7 days attached.

## Evidence package

- E2E test report
- RAG E2E metrics report
- incident log (0 blocking incidents)
- owner sign-off
