# Backup and Restore Drill

Goal: validate DB + filestore recovery for omnichannel chat integrity.

## Drill Steps

1. Take backup snapshot (database + filestore).
2. Restore to isolated environment.
3. Validate:
   - `discuss.channel` omnichannel threads exist,
   - message history present,
   - webhook event idempotency records present,
   - partner identity links preserved.
4. Run smoke checks for inbound/outbound on restored copy.
5. Record RTO/RPO, operator, and issues.
