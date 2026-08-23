import pytest

from backend import expiry, reports, sales


def make_product(conn, name="Test Product", sale_price=1000):
    cur = conn.execute(
        "INSERT INTO products (name, barcode, sale_price, unit, min_stock) VALUES (?, ?, ?, 'دانە', 0)",
        (name, f"barcode-{name}", sale_price),
    )
    return cur.lastrowid


def make_batch(conn, product_id, purchase_price, quantity):
    cur = conn.execute(
        "INSERT INTO stock_batches (product_id, purchase_price, quantity, status) VALUES (?, ?, ?, 'active')",
        (product_id, purchase_price, quantity),
    )
    return cur.lastrowid


def make_cashier(conn):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('c', 'x', 'cashier')"
    )
    return cur.lastrowid


def test_restores_existing_active_batch(conn):
    product_id = make_product(conn)
    batch_id = make_batch(conn, product_id, 600, 5)

    expiry.create_customer_return(
        conn, [{"product_id": product_id, "quantity": 2, "refund_amount": 2000}]
    )

    qty = conn.execute("SELECT quantity FROM stock_batches WHERE id = ?", (batch_id,)).fetchone()["quantity"]
    assert qty == 7


def test_creates_new_batch_with_last_known_price_when_none_active(conn):
    product_id = make_product(conn)
    batch_id = make_batch(conn, product_id, 700, 3)
    # deplete and dispose the only batch
    conn.execute("UPDATE stock_batches SET quantity = 0, status = 'disposed' WHERE id = ?", (batch_id,))

    expiry.create_customer_return(
        conn, [{"product_id": product_id, "quantity": 4, "refund_amount": 4000}]
    )

    new_batch = conn.execute(
        "SELECT * FROM stock_batches WHERE product_id = ? AND status = 'active'", (product_id,)
    ).fetchone()
    assert new_batch is not None
    assert new_batch["quantity"] == 4
    assert new_batch["purchase_price"] == 700


def test_multiple_products_in_one_call_restore_independently(conn):
    product_a = make_product(conn, name="A")
    product_b = make_product(conn, name="B")
    batch_a = make_batch(conn, product_a, 500, 5)
    batch_b = make_batch(conn, product_b, 300, 10)

    receipt = expiry.create_customer_return(
        conn,
        [
            {"product_id": product_a, "quantity": 1, "refund_amount": 1000},
            {"product_id": product_b, "quantity": 3, "refund_amount": 900},
        ],
    )

    assert conn.execute("SELECT quantity FROM stock_batches WHERE id = ?", (batch_a,)).fetchone()["quantity"] == 6
    assert conn.execute("SELECT quantity FROM stock_batches WHERE id = ?", (batch_b,)).fetchone()["quantity"] == 13
    assert receipt["total_refund"] == 1900
    assert len(receipt["items"]) == 2


def test_rejects_non_positive_quantity(conn):
    product_id = make_product(conn)
    make_batch(conn, product_id, 500, 5)
    with pytest.raises(ValueError):
        expiry.create_customer_return(
            conn, [{"product_id": product_id, "quantity": 0, "refund_amount": 0}]
        )


def test_rejects_negative_refund_amount(conn):
    product_id = make_product(conn)
    make_batch(conn, product_id, 500, 5)
    with pytest.raises(ValueError):
        expiry.create_customer_return(
            conn, [{"product_id": product_id, "quantity": 1, "refund_amount": -1}]
        )


def test_rejects_unknown_product(conn):
    with pytest.raises(ValueError):
        expiry.create_customer_return(
            conn, [{"product_id": 9999, "quantity": 1, "refund_amount": 100}]
        )


def test_rejects_empty_items(conn):
    with pytest.raises(ValueError):
        expiry.create_customer_return(conn, [])


def test_sell_then_return_restores_stock_to_original(conn):
    cashier_id = make_cashier(conn)
    product_id = make_product(conn, sale_price=1000)
    make_batch(conn, product_id, 600, 5)

    sales.complete_sale(
        conn,
        cashier_id=cashier_id,
        items=[{"product_id": product_id, "quantity": 1}],
        discount_mode="flat",
        discount_value=0,
    )
    stock_after_sale = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS q FROM stock_batches WHERE product_id = ? AND status = 'active'",
        (product_id,),
    ).fetchone()["q"]
    assert stock_after_sale == 4

    expiry.create_customer_return(
        conn, [{"product_id": product_id, "quantity": 1, "refund_amount": 1000}]
    )
    stock_after_return = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS q FROM stock_batches WHERE product_id = ? AND status = 'active'",
        (product_id,),
    ).fetchone()["q"]
    assert stock_after_return == 5


def test_reports_net_out_sale_and_return_on_same_day(conn):
    cashier_id = make_cashier(conn)
    product_id = make_product(conn, sale_price=1000)
    make_batch(conn, product_id, 600, 5)

    sales.complete_sale(
        conn,
        cashier_id=cashier_id,
        items=[{"product_id": product_id, "quantity": 2}],
        discount_mode="flat",
        discount_value=0,
    )
    expiry.create_customer_return(
        conn, [{"product_id": product_id, "quantity": 1, "refund_amount": 1000}]
    )

    today = conn.execute("SELECT date('now', 'localtime') AS d").fetchone()["d"]
    assert reports.total_items_sold(conn, today, today) == 1
    assert reports.total_revenue(conn, today, today) == 1000
    # gross profit = (1000-600)*2 = 800; minus full refund (1000) = -200
    assert reports.total_profit(conn, today, today) == -200
    returns_summary = reports.total_returns(conn, today, today)
    assert returns_summary == {"quantity": 1, "amount": 1000}

    # a different day's window is unaffected
    assert reports.total_items_sold(conn, "2000-01-01", "2000-01-02") == 0
