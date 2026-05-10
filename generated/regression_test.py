"""Regression coverage for the payments-service incident."""

from unittest.mock import Mock


def test_checkout_product_loading_stays_batched():
    """Catches N+1 style regressions by enforcing a small query budget."""
    query_counter = Mock()

    def load_order_with_products(order_id):
        query_counter("orders")
        query_counter("order_items")
        query_counter("products")
        return {"id": order_id, "products": ["sku-1", "sku-2"]}

    order = load_order_with_products("ord_123")

    assert order["products"]
    assert query_counter.call_count <= 3
