# [TICKET] Prevent recurrence: N+1 query guard for payments-service ORM changes

**Priority:** P1  
**Component:** payments-service / database  
**Labels:** reliability, database, orm, regression-prevention  
**Linked incident:** SEV-2 — 2025-11-03 (47 min, $34K impact)  
**Owner:** TBD  
**Sprint:** Next available

---

## Problem

On 2025-11-03, a PR that migrated the order serializer removed `eager_load(:products)` from the Order model. This caused one SQL query per order line item during checkout (N+1 pattern), driving RDS CPU to 94% and p99 latency to 4.8s for 47 minutes.

The root issue is structural: **there is no automated guard that catches N+1 query regressions before they reach production.** The fix was a one-line ORM change, but it required a live incident to detect.

---

## Root Cause Reference

> ORM migration in PR #4412 removed eager_load annotation. The serializer then lazy-loaded each product individually, producing N+1 queries at checkout.

---

## Acceptance Criteria

- [ ] **CI query count test**: A regression test runs in CI that asserts checkout produces ≤ 3 DB queries for any order size. Uses `db-query-matchers` or a custom counter. Fails the build if exceeded.
- [ ] **Bullet gem integration**: `bullet` gem enabled in test + staging environments. Build fails if Bullet detects an N+1 query in any request spec under `spec/requests/checkout_spec.rb`.
- [ ] **PR checklist item**: The payments-service PR template includes: `- [ ] Checked for N+1 queries? (run tests with BULLET=true or check query count assertions)`
- [ ] **Scope test**: A unit test asserts `Order.with_products` uses `eager_load` (not `joins`). Guards against future scope rewrites.
- [ ] **Monitor deployed**: `PaymentsCheckoutLatencyCritical` and `PaymentsRDSCpuCritical` Prometheus rules deployed to production monitoring namespace.
- [ ] **Runbook linked**: Alert annotations include runbook URL pointing to the checkout latency runbook.

---

## Implementation Notes

**Query count test (RSpec + db-query-matchers):**
```ruby
it "fetches checkout order in at most 3 queries" do
  order = create(:order, :with_products, product_count: 50)
  expect {
    get "/checkout/#{order.id}"
  }.to make_database_queries(count: 1..3)
end
```

**Bullet configuration (config/environments/test.rb):**
```ruby
config.after_initialize do
  Bullet.enable = true
  Bullet.raise = true  # raise error on N+1 detection
  Bullet.add_footer = false
end
```

---

## Definition of Done

- All 5 acceptance criteria checked off
- CI is green with the new tests
- No existing specs broken by Bullet integration
- Monitor YAML merged to infrastructure repo and alerts visible in Datadog/Grafana
