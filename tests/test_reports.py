from datetime import date

from backend import reports, sales


def setup_sale(conn, product_sale_price=1000, purchase_price=600, qty=3, discount=0):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('c', 'x', 'cashier')"
    )
    cashier_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO products (name, barcode, sale_price) VALUES ('p', 'bc1', ?)",
        (product_sale_price,),
    )
    product_id = cur.lastrowid
    conn.execute(
        "INSERT INTO stock_batches (product_id, purchase_price, quantity, status) VALUES (?, ?, ?, 'active')",
        (product_id, purchase_price, 100),
    )
    receipt = sales.complete_sale(
        conn,
        cashier_id=cashier_id,
        items=[{"product_id": product_id, "quantity": qty}],
        discount_mode="flat",
        discount_value=discount,
    )
    return product_id, receipt


def test_totals_match_hand_calculation(conn):
    product_id, receipt = setup_sale(conn, product_sale_price=1000, purchase_price=600, qty=3, discount=500)
    today = date.today().isoformat()

    assert reports.total_items_sold(conn, today, today) == 3
    assert reports.total_revenue(conn, today, today) == receipt["final_amount"] == 2500
    # profit = (1000-600)*3 = 1200
    assert reports.total_profit(conn, today, today) == 1200


def test_top_selling_products(conn):
    product_id, _ = setup_sale(conn, qty=5)
    today = date.today().isoformat()
    top = reports.top_selling_products(conn, today, today, limit=5)
    assert len(top) == 1
    assert top[0]["id"] == product_id
    assert top[0]["qty_sold"] == 5


def test_daily_chart_has_n_entries_with_zero_fill(conn):
    setup_sale(conn, qty=2)
    chart = reports.daily_sales_last_n_days(conn, n=7)
    assert len(chart) == 7
    today = date.today().isoformat()
    today_entry = next(d for d in chart if d["day"] == today)
    assert today_entry["revenue"] > 0
    zero_days = [d for d in chart if d["day"] != today]
    assert all(d["revenue"] == 0 for d in zero_days)


def test_out_of_range_dates_excluded(conn):
    setup_sale(conn, qty=2)
    assert reports.total_revenue(conn, "2000-01-01", "2000-01-02") == 0
    assert reports.total_items_sold(conn, "2000-01-01", "2000-01-02") == 0
