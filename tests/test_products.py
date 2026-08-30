import pytest

from backend import products, session
from backend.api import JSApi


def _make_product(conn, name="کاڵا", barcode="b-del", quantity=5):
    return products.create_product(
        conn,
        name=name,
        barcode=barcode,
        category=None,
        sale_price=1000,
        unit=None,
        min_stock=0,
        purchase_price=600,
        quantity=quantity,
        expiry_date=None,
    )


def test_delete_product_removes_product_and_batches(conn):
    p = _make_product(conn)
    products.delete_product(conn, p["id"])
    assert conn.execute("SELECT 1 FROM products WHERE id = ?", (p["id"],)).fetchone() is None
    assert (
        conn.execute("SELECT 1 FROM stock_batches WHERE product_id = ?", (p["id"],)).fetchone()
        is None
    )


def test_delete_product_missing_raises(conn):
    with pytest.raises(ValueError):
        products.delete_product(conn, 999999)


def test_delete_product_blocked_when_it_has_sales(conn):
    p = _make_product(conn)
    batch_id = conn.execute(
        "SELECT id FROM stock_batches WHERE product_id = ?", (p["id"],)
    ).fetchone()["id"]
    cashier_id = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('c1', 'x', 'cashier')"
    ).lastrowid
    sale_id = conn.execute(
        "INSERT INTO sales (total_amount, discount, final_amount, cashier_id) VALUES (1000, 0, 1000, ?)",
        (cashier_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO sale_items (sale_id, product_id, batch_id, quantity, unit_price, total_price) "
        "VALUES (?, ?, ?, 1, 1000, 1000)",
        (sale_id, p["id"], batch_id),
    )
    with pytest.raises(ValueError):
        products.delete_product(conn, p["id"])
    assert conn.execute("SELECT 1 FROM products WHERE id = ?", (p["id"],)).fetchone() is not None


def test_delete_product_blocked_when_it_has_returns(conn):
    p = _make_product(conn)
    conn.execute(
        "INSERT INTO returns (product_id, quantity, reason, refund_amount) "
        "VALUES (?, 1, 'customer_return', 1000)",
        (p["id"],),
    )
    with pytest.raises(ValueError):
        products.delete_product(conn, p["id"])


def test_jsapi_delete_product_admin_only(conn):
    p = _make_product(conn)
    cashier_id = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('c2', 'x', 'cashier')"
    ).lastrowid
    session.set_current_user({"id": cashier_id, "username": "c2", "role": "cashier"})
    api = JSApi(conn)
    assert api.delete_product(p["id"])["error"] == "FORBIDDEN"

    admin_id = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('a2', 'x', 'admin')"
    ).lastrowid
    session.set_current_user({"id": admin_id, "username": "a2", "role": "admin"})
    assert api.delete_product(p["id"])["ok"] is True
    assert api.delete_product(p["id"])["error"] == "VALIDATION_ERROR"  # already gone
    session.clear_current_user()
