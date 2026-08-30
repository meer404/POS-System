import inspect

import pytest

from backend import session
from backend.api import JSApi

EXEMPT_METHODS = {"login", "logout", "get_current_user", "change_password", "force_change_password"}


def test_every_public_method_is_role_guarded_except_exempt():
    for name, fn in inspect.getmembers(JSApi, predicate=inspect.isfunction):
        if name.startswith("_") or name in EXEMPT_METHODS:
            continue
        assert getattr(fn, "_role_guarded", False), (
            f"JSApi.{name} is not wrapped in @require_role and is not in EXEMPT_METHODS"
        )


def test_cashier_forbidden_from_admin_only_methods(conn):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('cashier1', 'x', 'cashier')"
    )
    session.set_current_user({"id": cur.lastrowid, "username": "cashier1", "role": "cashier"})
    api = JSApi(conn)

    assert api.get_report_summary(preset="today")["error"] == "FORBIDDEN"
    assert api.list_expired_batches()["error"] == "FORBIDDEN"
    assert api.list_users()["error"] == "FORBIDDEN"
    assert api.delete_user(1)["error"] == "FORBIDDEN"
    assert api.list_backups()["error"] == "FORBIDDEN"
    assert api.create_backup()["error"] == "FORBIDDEN"
    assert api.restore_backup("x")["error"] == "FORBIDDEN"
    session.clear_current_user()


def test_cashier_allowed_shared_methods(conn):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('cashier2', 'x', 'cashier')"
    )
    session.set_current_user({"id": cur.lastrowid, "username": "cashier2", "role": "cashier"})
    api = JSApi(conn)

    assert api.list_products()["ok"] is True
    session.clear_current_user()


def test_cashier_cannot_change_sale_price_but_admin_can(conn):
    conn.execute(
        "INSERT INTO products (name, barcode, sale_price) VALUES ('p', 'b1', 1000)"
    )
    product_id = conn.execute("SELECT id FROM products WHERE barcode='b1'").fetchone()["id"]

    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('cashier3', 'x', 'cashier')"
    )
    session.set_current_user({"id": cur.lastrowid, "username": "cashier3", "role": "cashier"})
    api = JSApi(conn)
    result = api.update_product(product_id, {"sale_price": 2000})
    assert result["error"] == "FORBIDDEN"

    cur2 = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('admin2', 'x', 'admin')"
    )
    session.set_current_user({"id": cur2.lastrowid, "username": "admin2", "role": "admin"})
    result2 = api.update_product(product_id, {"sale_price": 2000})
    assert result2["ok"] is True
    session.clear_current_user()


def test_unauthenticated_requests_rejected(conn):
    session.clear_current_user()
    api = JSApi(conn)
    result = api.list_products()
    assert result["error"] == "NOT_AUTHENTICATED"
