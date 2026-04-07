# Security and RODO Baseline — `omnichannel_bridge`

## Security Principles

- Secrets are never stored in git.
- No secret values in logs, chat transcripts, or docs.
- Provider tokens are stored only in approved secure settings paths.

## Prompt Data Minimization

- Child-sensitive data must not be injected into LLM context unless required.
- Avoid passing full personal identifiers by default.
- Keep legal and commercial facts structured and explicit.

## Logging Policy

- Mask personal and credential-like values in debug/error logs.
- Log event identifiers and technical status, not raw sensitive payloads.
- Keep audit trail for configuration and prompt policy changes.

## RODO/GDPR Guardrails

- Lawful basis and consent boundaries must be reflected in bot behavior.
- Marketing communication must honor explicit consent records.
- Child-protection escalation must always route to human manager.

## Access and Environments

- Local and staging environments must use non-production tokens.
- Production changes require review and explicit approval.
- Staging must mirror production module topology for reliable validation.

## Mandatory Controls (Implementation Backlog)

- Idempotency key storage for webhook deduplication.
- Async queue to decouple webhook response from LLM latency.
- Bot/human lock to prevent conflicting replies.
- Redaction utility for log-safe output.
