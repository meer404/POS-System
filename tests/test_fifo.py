from datetime import date, timedelta

import pytest

from backend import products, sales


def make_product(conn, name="Test Product", sale_price=1000):
    cur = conn.execute(
        "INSERT INTO products (name, barcode, sale_price, unit, min_stock) VALUES (?, ?, ?, 'دانە', 0)",
        (name, f"barcode-{name}", sale_price),
    )
    return cur.lastrowid


def make_batch(conn, product_id, purchase_price, quantity, expiry_date=None, received_offset_days=0):
    received_at = (date.today() - timedelta(days=received_offset_days)).isoformat() + " 00:00:00"
    cur = conn.execute(
        "INSERT INTO stock_batches (product_id, purchase_price, quantity, expiry_date, received_at, status) "
        "VALUES (?, ?, ?, ?, ?, 'active')",
        (product_id, purchase_price, quantity, expiry_date, received_at),
    )
    return cur.lastrowid


def test_fifo_consumes_nearest_expiry_first(conn):
    product_id = make_product(conn)
    batch_soon = make_batch(conn, product_id, 500, 3, expiry_date=(date.today() + timedelta(days=2)).isoformat())
    batch_later = make_batch(conn, product_id, 600, 10, expiry_date=(date.today() + timedelta(days=30)).isoformat())

    plan = sales.consume_fifo(conn, product_id, 5)

    assert plan[0][0] == batch_soon
    assert plan[0][1] == 3
    assert plan[1][0] == batch_later
    assert plan[1][1] == 2


def test_fifo_null_expiry_falls_back_to_received_at(conn):
    product_id = make_product(conn)
    older = make_batch(conn, product_id, 500, 2, expiry_date=None, received_offset_days=10)
    newer = make_batch(conn, product_id, 600, 5, expiry_date=None, received_offset_days=1)

    plan = sales.consume_fifo(conn, product_id, 4)

    assert plan[0][0] == older
    assert plan[0][1] == 2
    assert plan[1][0] == newer
    assert plan[1][1] == 2


def test_fifo_null_expiry_is_consumed_after_dated_batches(conn):
    product_id = make_product(conn)
    dated = make_batch(conn, product_id, 500, 2, expiry_date=(date.today() + timedelta(days=5)).isoformat())
    undated = make_batch(conn, product_id, 600, 5, expiry_date=None)

    plan = sales.consume_fifo(conn, product_id, 3)

    assert plan[0][0] == dated
    assert plan[1][0] == undated


def test_fifo_raises_on_insufficient_stock(conn):
    product_id = make_product(conn)
    make_batch(conn, product_id, 500, 2)

    with pytest.raises(sales.InsufficientStockError):
        sales.consume_fifo(conn, product_id, 5)


def test_complete_sale_splits_across_batches_and_updates_quantities(conn):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('c', 'x', 'cashier')"
    )
    cashier_id = cur.lastrowid
    product_id = make_product(conn, sale_price=1000)
    batch_a = make_batch(conn, product_id, 700, 3, expiry_date=(date.today() + timedelta(days=1)).isoformat())
    batch_b = make_batch(conn, product_id, 800, 10, expiry_date=(date.today() + timedelta(days=30)).isoformat())

    receipt = sales.complete_sale(
        conn,
        cashier_id=cashier_id,
        items=[{"product_id": product_id, "quantity": 5}],
        discount_mode="flat",
        discount_value=0,
    )

    assert receipt["total_amount"] == 5000
    assert receipt["final_amount"] == 5000

    qty_a = conn.execute("SELECT quantity FROM stock_batches WHERE id = ?", (batch_a,)).fetchone()["quantity"]
    qty_b = conn.execute("SELECT quantity FROM stock_batches WHERE id = ?", (batch_b,)).fetchone()["quantity"]
    assert qty_a == 0
    assert qty_b == 8

    sale_items = conn.execute(
        "SELECT * FROM sale_items WHERE product_id = ?", (product_id,)
    ).fetchall()
    assert len(sale_items) == 2

    # profit check: (1000-700)*3 + (1000-800)*2 = 900 + 400 = 1300
    from backend import reports

    today = date.today().isoformat()
    profit = reports.total_profit(conn, today, today)
    assert profit == 1300


def test_complete_sale_percent_discount(conn):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('c', 'x', 'cashier')"
    )
    cashier_id = cur.lastrowid
    product_id = make_product(conn, sale_price=1000)
    make_batch(conn, product_id, 500, 10)

    receipt = sales.complete_sale(
        conn,
        cashier_id=cashier_id,
        items=[{"product_id": product_id, "quantity": 4}],
        discount_mode="percent",
        discount_value=10,
    )

    assert receipt["total_amount"] == 4000
    assert receipt["discount"] == 400
    assert receipt["final_amount"] == 3600
