# Postmortem: Product Catalog — Cache Stampede on Deploy — 2025-08-05

**Severity:** SEV-3  
**Duration:** 11 minutes (11:02 – 11:13 UTC)  
**Incident Commander:** Sofia Ramirez

## Summary

A rolling deploy of product-catalog-service caused all Redis cache keys to expire simultaneously (thundering herd). Every pod restarted with a fresh cache, leading to a flood of cache misses that hit the upstream Postgres database directly and briefly overwhelmed it.

## Timeline

- 11:00 — Deploy of product-catalog-service v3.8.2 begins (rolling restart)
- 11:02 — Datadog: `postgres.query_latency.p99 > 800ms`; Redis `cache_miss_rate` jumps to 98%
- 11:06 — On-call identifies all 12 pods restarted within 90 seconds, flushing local + Redis cache
- 11:08 — Cache warming script triggered manually
- 11:13 — Cache hit rate recovers to 94%; Postgres latency returns to normal

## Root Cause

The deploy used `kubectl rollout restart` which restarted all pods within ~90 seconds. Each pod initialized with a cold cache. All pods simultaneously tried to populate the same cache keys from Postgres, causing a stampede of ~800 concurrent identical queries.

## Fix

1. Implemented probabilistic early expiration (PER) to prevent synchronized expiry
2. Added cache lock (Redis `SET NX`) so only one pod regenerates a cache key; others wait
3. Switched deploy strategy to max-surge=1, max-unavailable=0 with 30s inter-pod delay

## Prevention

- Deploy runbook updated: cache warm-up job must complete before traffic is routed to new pods
- Added `cache_miss_rate` alert at 50% sustained for 2+ minutes

## Impact

- 11 minutes of elevated latency (p99 ~900ms vs normal ~80ms)
- No errors surfaced to users; retries absorbed the spike
