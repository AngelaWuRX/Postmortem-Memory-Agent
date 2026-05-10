"""
Regression tests for: payments-service N+1 query on order lookup (SEV-2, 2025-11-03)

Root cause: ORM migration removed eager_load(:products), causing one SQL query
per order line item instead of a single batched query. Triggered 4.8s p99 latency
and 94% RDS CPU during checkout.

These tests assert:
  1. Checkout does not issue more than a bounded number of DB queries per request
  2. The order serializer uses eager-loaded products, not lazy per-item SELECTs
"""

import pytest
from unittest.mock import MagicMock, patch, call
from collections import Counter


# ── helpers ───────────────────────────────────────────────────────────────────

class QueryCounter:
    """Context manager that counts SQL queries executed."""
    def __init__(self):
        self.count = 0
        self.queries = []

    def record(self, sql: str):
        self.count += 1
        self.queries.append(sql)

    def assert_max(self, limit: int, msg: str = ""):
        assert self.count <= limit, (
            f"Expected at most {limit} queries, got {self.count}.\n"
            f"Queries executed:\n" + "\n".join(f"  {q}" for q in self.queries)
            + (f"\n{msg}" if msg else "")
        )


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def order_with_items():
    """An order with 10 line items — enough to trigger N+1 if it exists."""
    order = MagicMock()
    order.id = 42
    order.user_id = 7
    order.total_price = 199.99

    products = [
        MagicMock(id=i, name=f"Product {i}", price=round(19.99 + i, 2))
        for i in range(1, 11)
    ]
    items = [
        MagicMock(product_id=p.id, price=p.price, product=p)
        for p in products
    ]
    order.order_items = items
    order.products = products  # eager-loaded association
    return order, products, items


@pytest.fixture
def large_order():
    """200-item order to stress-test query count scaling."""
    order = MagicMock()
    order.id = 99
    order.user_id = 1
    products = [MagicMock(id=i, name=f"P{i}", price=9.99) for i in range(200)]
    items = [MagicMock(product_id=p.id, price=p.price, product=p) for p in products]
    order.order_items = items
    order.products = products
    order.total_price = sum(p.price for p in products)
    return order


# ── N+1 regression tests ──────────────────────────────────────────────────────

class TestCheckoutQueryCount:
    """Ensure checkout serialization does not produce N+1 queries."""

    def test_serializer_uses_eager_loaded_products(self, order_with_items):
        """
        The serializer must access order.products (eager-loaded association),
        NOT call Product.find(id) for each item individually.
        """
        order, products, items = order_with_items
        product_find_calls = []

        with patch("app.models.Product") as MockProduct:
            MockProduct.find.side_effect = lambda id: next(
                (p for p in products if p.id == id), None
            )

            # Import here to pick up the patch
            from app.serializers.order_serializer import OrderSerializer
            result = OrderSerializer().serialize(order)

            # The serializer must NOT call Product.find at all — it should
            # use the eager-loaded order.products association
            assert MockProduct.find.call_count == 0, (
                f"OrderSerializer called Product.find {MockProduct.find.call_count} times. "
                "This is an N+1 query — use eager_load(:products) instead."
            )

        assert len(result["products"]) == len(products)

    def test_checkout_query_count_bounded(self, order_with_items):
        """
        Checkout for an order with N items must issue at most 3 queries,
        regardless of item count (1 for order, 1 for items, 1 for products batch).
        """
        order, _, _ = order_with_items
        counter = QueryCounter()

        with patch("app.models.Order") as MockOrder:
            MockOrder.with_products.return_value.find.return_value = order

            # Simulate a DB query counter via the connection
            with patch("app.db.connection.execute", side_effect=lambda sql, *a: counter.record(sql)):
                from app.controllers.checkout_controller import CheckoutController
                ctrl = CheckoutController()
                ctrl.params = {"id": order.id}
                ctrl.show()

        counter.assert_max(
            3,
            "Checkout must use at most 3 queries: 1 for order, 1 for order_items, 1 for products IN (...)"
        )

    def test_query_count_does_not_scale_with_item_count(self, large_order):
        """
        Query count must be O(1) with respect to number of order items.
        This test catches any regression where queries grow linearly with items.
        """
        query_counts = []

        for item_count in [1, 10, 50, 200]:
            order = MagicMock()
            products = [MagicMock(id=i, name=f"P{i}", price=9.99) for i in range(item_count)]
            order.order_items = [MagicMock(product_id=p.id, product=p) for p in products]
            order.products = products
            order.total_price = item_count * 9.99

            counter = QueryCounter()
            with patch("app.db.connection.execute", side_effect=lambda sql, *a: counter.record(sql)):
                from app.serializers.order_serializer import OrderSerializer
                OrderSerializer().serialize(order)
            query_counts.append(counter.count)

        # All counts must be equal (O(1)) — not growing with item count
        assert len(set(query_counts)) == 1, (
            f"Query count scales with item count: {dict(zip([1,10,50,200], query_counts))}. "
            "This is an N+1 query pattern."
        )


class TestEagerLoadScope:
    """Verify the with_products scope applies eager loading."""

    def test_with_products_scope_uses_eager_load(self):
        """Order.with_products must include eager_load(:products)."""
        from app.models.order import Order

        # Inspect the scope's eager_load_values
        scope = Order.with_products
        assert hasattr(scope, "eager_load_values"), "Scope missing eager_load support"
        assert "products" in scope.eager_load_values or "order_items" in scope.eager_load_values, (
            "Order.with_products scope does not eager-load products. "
            "Add: scope :with_products, -> { eager_load(:order_items).eager_load(:products) }"
        )

    def test_with_products_scope_not_using_lazy_joins(self):
        """with_products must not use plain joins() which still lazy-loads associations."""
        from app.models.order import Order
        import inspect

        # Check the scope definition doesn't use bare joins without eager loading
        scope_source = inspect.getsource(Order.with_products.fget if hasattr(Order.with_products, 'fget') else Order.with_products)
        assert "eager_load" in scope_source or "includes" in scope_source, (
            "with_products uses joins() without eager loading. "
            "Replace with eager_load(:products) to prevent N+1 queries."
        )
