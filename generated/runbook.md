# Runbook: payments-service Recurrence

## Alert
payments.checkout.p99 latency above 2s with elevated DB CPU and repeated product queries.

## Impact
Users may see elevated latency, failed requests, or degraded checkout completion.

## Diagnosis steps
1. Check p99 latency and error rate.
   ```bash
   kubectl top pods -n production
   ```
2. Inspect recent database query volume.
   ```sql
   SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY calls DESC LIMIT 10;
   ```
3. Compare the active deploy against the last known safe revision.

## Fix
1. Revert or patch the risky change.
2. Restore the prevention pattern: Restore eager loading, batch product lookups, add query-count regression coverage, and keep supporting indexes in place.
3. Deploy and watch latency plus database CPU.

## Verification
Confirm p99 latency, error rate, and saturation metrics return to baseline for 15 minutes.

## Escalation
Page the service owner and database on-call if the issue remains above threshold after rollback.
