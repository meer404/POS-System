import pytest

from backend import session, users
from backend.api import JSApi
from backend.seed import DEFAULT_ADMIN_USERNAME


def _add_user(conn, username, role="admin"):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, 'x', ?)",
        (username, role),
    )
    return cur.lastrowid


def test_list_users_flags_default_admin_as_protected(conn):
    _add_user(conn, DEFAULT_ADMIN_USERNAME)
    _add_user(conn, "admin2")
    _add_user(conn, "cashier1", role="cashier")

    by_name = {u["username"]: u for u in users.list_users(conn)}
    assert by_name[DEFAULT_ADMIN_USERNAME]["protected"] is True
    assert by_name["admin2"]["protected"] is False
    assert by_name["cashier1"]["protected"] is False


def test_is_protected_user(conn):
    protected_id = _add_user(conn, DEFAULT_ADMIN_USERNAME)
    other_id = _add_user(conn, "admin2")
    assert users.is_protected_user(conn, protected_id) is True
    assert users.is_protected_user(conn, other_id) is False
    assert users.is_protected_user(conn, 99999) is False


def test_set_user_role_blocked_for_protected_admin(conn):
    protected_id = _add_user(conn, DEFAULT_ADMIN_USERNAME)
    with pytest.raises(ValueError):
        users.set_user_role(conn, protected_id, "cashier")
    assert conn.execute(
        "SELECT role FROM users WHERE id = ?", (protected_id,)
    ).fetchone()["role"] == "admin"


def test_set_user_role_allowed_for_other_admin(conn):
    other_id = _add_user(conn, "admin2")
    users.set_user_role(conn, other_id, "cashier")
    assert conn.execute(
        "SELECT role FROM users WHERE id = ?", (other_id,)
    ).fetchone()["role"] == "cashier"


def test_reset_password_blocked_for_protected_admin(conn):
    protected_id = _add_user(conn, DEFAULT_ADMIN_USERNAME)
    with pytest.raises(ValueError):
        users.reset_user_password(conn, protected_id, "newpass")


def test_reset_password_allowed_for_other_user(conn):
    other_id = _add_user(conn, "cashier1", role="cashier")
    assert users.reset_user_password(conn, other_id, "newpass") == {"ok": True}


def test_jsapi_rejects_changes_to_protected_admin(conn):
    protected_id = _add_user(conn, DEFAULT_ADMIN_USERNAME)
    acting_admin_id = _add_user(conn, "admin2")
    session.set_current_user({"id": acting_admin_id, "username": "admin2", "role": "admin"})
    api = JSApi(conn)

    assert api.set_user_role(protected_id, "cashier")["error"] == "VALIDATION_ERROR"
    assert api.reset_user_password(protected_id, "newpass")["error"] == "VALIDATION_ERROR"
    session.clear_current_user()
