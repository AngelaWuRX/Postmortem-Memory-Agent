# Runbook: Payments Checkout Latency Spike (N+1 Query Pattern)

**Alert:** `PaymentsCheckoutLatencyCritical` — p99 > 2s  
**Component:** payments-service  
**Severity:** SEV-2  
**Last incident:** 2025-11-03 (47 min, $34K revenue impact)

---

## Alert

```
FIRING: PaymentsCheckoutLatencyCritical
  payments-service checkout p99 > 2.0s for 1m
  RDS CPU: 91%   Checkout error rate: 10%
```

---

## Impact

- Checkout failures for ~10–15% of users
- Revenue impact: ~$700/min based on 2025-11-03 baseline
- Downstream: order confirmation emails delayed; inventory holds may not release

---

## Diagnosis Steps

**1. Confirm the alert is real (not a deploy artifact)**

```bash
kubectl rollout status deployment/payments-service -n payments
# If a deploy just finished, wait 2 min and check if metrics recover naturally
```

**2. Check RDS Performance Insights for the query pattern**

```sql
-- In RDS Performance Insights, filter last 15 minutes
-- Look for: repeated single-row SELECTs on products table
SELECT sql_text, calls, mean_exec_time_ms
FROM pg_stat_statements
WHERE sql_text ILIKE '%products%WHERE id%'
ORDER BY calls DESC
LIMIT 20;
```

If you see `SELECT * FROM products WHERE id = $1` called hundreds of times per minute — this is the N+1 pattern.

**3. Check recent deployments to payments-service**

```bash
kubectl rollout history deployment/payments-service -n payments
# Note the last 2 image tags

# Check what changed
git log --oneline payments-service/app/serializers/ payments-service/app/models/order.rb
```

**4. Verify eager loading is in place**

```bash
# In a Rails console pod
kubectl exec -it deploy/payments-service -n payments -- rails console
```

```ruby
# Should produce 1-3 queries (order + items + products batch)
# NOT 1 + N queries
ActiveSupport::Notifications.subscribed(
  lambda { |*args| puts args[4][:sql] },
  "sql.active_record"
) { Order.with_products.find(Order.last.id).products.map(&:name) }
```

---

## Fix

**If N+1 confirmed:**

**Option A — Hotfix (fastest, deploy in <5 min)**

```ruby
# app/models/order.rb
scope :with_products, -> { eager_load(:order_items).eager_load(:products) }
```

```bash
git checkout -b hotfix/payments-n1-eager-load
# apply change, commit
git push origin hotfix/payments-n1-eager-load
# Fast-track through CI, deploy
kubectl set image deployment/payments-service \
  app=payments-service:hotfix-$(git rev-parse --short HEAD) -n payments
```

**Option B — Immediate mitigation (while fix deploys)**

Scale up RDS temporarily to absorb the extra query load:

```bash
aws rds modify-db-instance \
  --db-instance-identifier payments-db-prod \
  --db-instance-class db.r6g.4xlarge \
  --apply-immediately
```

---

## Verification

```bash
# Watch p99 recover (should drop below 200ms within 2 minutes of deploy)
watch -n 5 'kubectl exec -n payments deploy/payments-service -- \
  curl -s localhost:9090/metrics | grep checkout_p99'

# Confirm query count in console
# Should be exactly 3 queries for any order size
```

---

## Escalation

| Time without recovery | Action |
|---|---|
| +10 min | Page payments team lead |
| +20 min | Page DB on-call; consider RDS scale-up |
| +30 min | Incident bridge; consider feature flag to disable checkout |
