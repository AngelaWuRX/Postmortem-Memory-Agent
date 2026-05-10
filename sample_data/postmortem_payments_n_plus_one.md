# Postmortem: Payments Service Latency Spike — 2025-11-03

**Severity:** SEV-2  
**Duration:** 47 minutes (14:22 – 15:09 UTC)  
**Incident Commander:** Maya Chen

## Summary

The payments-service experienced a p99 latency spike from 120ms to 4.8s, causing checkout failures for 12% of users. Root cause was an N+1 query introduced in a recent ORM migration that fired one SQL query per order line item instead of batching.

## Timeline

- 14:22 — Datadog alert: `payments.checkout.p99 > 2s` fires
- 14:28 — On-call engineer pages DB team; RDS CPU at 94%
- 14:35 — Query analysis shows `SELECT * FROM products WHERE id = ?` called 80–200× per request
- 14:51 — Hotfix deployed: replaced loop queries with single `SELECT ... WHERE id IN (...)`
- 15:02 — DB CPU drops to 18%, p99 recovers to 130ms
- 15:09 — Incident closed

## Root Cause

ORM migration in PR #4412 removed an eager-loading annotation (`include: :products`) from the order serializer. The serializer then lazy-loaded each product individually, producing N+1 queries at checkout.

## Fix

1. Re-added `eager_load(:products)` to the order query scope
2. Added a DB index on `order_items.product_id` (was missing)
3. Added integration test asserting max 3 DB queries per checkout request

## Prevention

- PR checklist now includes "did you check for N+1 queries with Bullet gem?"
- Query count regression test added to CI

## Impact

- 12% checkout failure rate for 47 minutes
- ~$34,000 estimated revenue impact
