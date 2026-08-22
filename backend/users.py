"""Admin-only user management (create, list, role change, password reset)."""
import sqlite3

from backend.auth import hash_password
from backend.utils import row_to_dict, rows_to_list


def list_users(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, username, role, force_password_change, created_at FROM users ORDER BY username"
    ).fetchall()
    return rows_to_list(rows)


def create_user(conn: sqlite3.Connection, username: str, password: str, role: str) -> dict:
    if not username or not username.strip():
        raise ValueError("ناوی بەکارهێنەر پێویستە")
    if role not in ("admin", "cashier"):
        raise ValueError("ڕۆڵ نادروستە")
    if len(password) < 4:
        raise ValueError("وشەی نهێنی زۆر کورتە")

    existing = conn.execute(
        "SELECT 1 FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    if existing is not None:
        raise ValueError("ئەم ناوە پێشتر بەکارهاتووە")

    with conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role, force_password_change) "
            "VALUES (?, ?, ?, 1)",
            (username.strip(), hash_password(password), role),
        )
        user_id = cur.lastrowid

    return row_to_dict(
        conn.execute(
            "SELECT id, username, role, force_password_change, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    )


def set_user_role(conn: sqlite3.Connection, user_id: int, role: str) -> dict:
    if role not in ("admin", "cashier"):
        raise ValueError("ڕۆڵ نادروستە")
    existing = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if existing is None:
        raise ValueError("بەکارهێنەر نەدۆزرایەوە")

    with conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    return row_to_dict(
        conn.execute(
            "SELECT id, username, role, force_password_change, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    )


def reset_user_password(conn: sqlite3.Connection, user_id: int, new_password: str) -> dict:
    if len(new_password) < 4:
        raise ValueError("وشەی نهێنی زۆر کورتە")
    existing = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if existing is None:
        raise ValueError("بەکارهێنەر نەدۆزرایەوە")

    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, force_password_change = 1 WHERE id = ?",
            (hash_password(new_password), user_id),
        )

    return {"ok": True}
