# Staging Meta Test Page Checklist

Minimum staging checklist for Meta test page before production release:

1. Connect Meta test page and webhook verify token.
2. Confirm signed POST webhook acceptance.
3. Send inbound DM and verify Discuss thread creation.
4. Verify outbound reply and dedupe/conflict guards.
5. Verify fallback path with LLM disabled.
6. Record staging run date, owner, and commit hash.
