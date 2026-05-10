# Postmortem: Search Service — Index Drift Causing Stale Results — 2025-06-01

**Severity:** SEV-3  
**Duration:** ~18 hours (undetected overnight); resolved 2025-06-01 11:00 UTC  
**Incident Commander:** Aisha Thompson

## Summary

The search-service Elasticsearch index fell out of sync with the primary Postgres database after the indexing pipeline worker crashed silently at 17:00 UTC on 2025-05-31. Users saw stale product listings (items out of stock shown as available, prices from the previous day) for ~18 hours.

## Timeline

- 2025-05-31 17:00 — `search-indexer` worker pod crashes (OOM, unreported); dead-letter queue begins accumulating
- 2025-06-01 09:00 — Customer support reports multiple complaints about incorrect prices
- 09:20 — Search team identifies Elasticsearch index is 16 hours behind
- 09:35 — Manual full re-index triggered (took 90 minutes for 2.4M products)
- 11:00 — Index fully synced; stale results resolved

## Root Cause

The `search-indexer` pod ran without a liveness probe and crashed OOM at 17:00. The Kafka consumer group it managed stopped consuming update events. No alert existed for consumer group lag on the `product-updates` topic. The dead-letter queue silently grew overnight.

## Fix

1. Added liveness probe to `search-indexer` pod (restarts on failure)
2. Added Datadog alert: `kafka.consumer_group.lag > 1000 for 5 minutes`
3. Added hourly staleness check: if Elasticsearch `_max` document timestamp lags Postgres by >10 minutes, alert fires

## Prevention

- Kafka consumer lag monitoring added for all critical topics
- Search result spot-check added to synthetic monitoring suite (runs every 5 minutes, compares ES vs Postgres for 5 random products)

## Impact

- ~18 hours of stale search results for all users
- Unknown revenue impact (customers may have abandoned carts on seeing incorrect prices/stock)
