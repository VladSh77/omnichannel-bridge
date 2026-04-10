# LLM Fallback Smoke (20.9.1)

Date: 2026-04-10

Fallback chain:
- Primary: `ollama`
- Fallback: OpenAI-compatible endpoint (`gemini` via `openai_base_url`)

Configured controls:
- Fallback switch in Settings: enabled.
- Triggers:
  - timeout/read-timeout,
  - primary circuit-breaker open,
  - empty primary answer.
- Guardrails preserved in fallback path:
  - strict grounding,
  - no-russian policy,
  - sales-discovery flow,
  - anti-hallucination finalizers.
- Security:
  - API key only in `ir.config_parameter`,
  - no secret in git/code.
- Rate cap:
  - fallback requests per minute capped (`llm_fallback_rate_cap_per_minute`).
- Operational logs:
  - fallback start reason,
  - session duration,
  - restore event to primary backend.

Smoke scenario:
1. Simulate primary unavailable.
2. Validate fallback reply is returned.
3. Restore primary.
4. Validate session closed and duration logged.

Result:
- PASS (`primary down -> fallback reply -> primary restore`).
