# Postmortem: API Gateway — Database Connection Pool Exhaustion — 2025-10-22

**Severity:** SEV-2  
**Duration:** 28 minutes (03:14 – 03:42 UTC)  
**Incident Commander:** James Park

## Summary

The api-gateway service became unresponsive during a traffic spike. All 200 database connections in the pool were held open by slow queries caused by a missing index on a recently-added `user_events` table. New requests queued waiting for a connection until timeouts cascaded.

## Timeline

- 03:14 — PagerDuty: `api-gateway.error_rate > 5%`; simultaneously `rds.DatabaseConnections = 200` (at pool max)
- 03:19 — On-call confirms RDS CPU at 78%, `SHOW PROCESSLIST` shows hundreds of threads waiting on `user_events` table scans
- 03:28 — Migration to add index on `user_events.user_id` + `user_events.created_at` deployed
- 03:35 — Connections drain; error rate returns to baseline
- 03:42 — All-clear

## Root Cause

PR #5801 added a `user_events` table and a nightly aggregation query. The query did a full table scan (`WHERE user_id = ? AND created_at > ?`) because neither column was indexed. During a traffic spike, concurrent aggregation jobs saturated the connection pool within 4 minutes.

## Fix

1. Added composite index: `CREATE INDEX idx_user_events_user_created ON user_events(user_id, created_at)`
2. Increased connection pool size from 200 to 350 as a short-term buffer
3. Added query timeout of 5s to prevent individual slow queries from holding connections

## Prevention

- `sqlcheck` added to CI to warn on queries that hit tables without indexes on the WHERE columns
- Connection pool utilization added to Datadog dashboard with alert at 80%

## Impact

- 28-minute degradation; ~15% of API requests failed with 503
- No data loss
