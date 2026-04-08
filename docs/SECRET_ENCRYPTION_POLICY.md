# Secret Encryption Policy

Baseline policy for token/secret handling:

- Production secrets should use encrypted-at-rest storage available in target platform (Enterprise/custom vault).
- Access must be restricted to approved administrators only.
- Rotate Meta/Telegram secrets on schedule and on compromise suspicion.
- Never hardcode secrets in source code or commit history.

Current module stores integration values in settings parameters and relies on platform-level encryption policy enforcement.
