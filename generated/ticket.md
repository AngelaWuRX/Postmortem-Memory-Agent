# [TICKET] Prevent recurrence: payments-service
**Priority:** P1
**Component:** payments-service
**Labels:** payments, database, orm, n-plus-one, latency

## Problem
An ORM migration removed eager loading, causing checkout serialization to lazy-load products one item at a time.

## Root cause reference
Incident date: 2025-11-03  
Severity: SEV-2

## Acceptance criteria
- [ ] Add regression coverage for the failure mode.
- [ ] Add or tune monitoring for: payments.checkout.p99 latency above 2s with elevated DB CPU and repeated product queries.
- [ ] Document the response path in the service runbook.
- [ ] Validate the fix in staging before release.

## Implementation notes
Restore eager loading, batch product lookups, add query-count regression coverage, and keep supporting indexes in place.

## Definition of done
The recurring risk is covered by CI, monitored in production, and documented for on-call response.
