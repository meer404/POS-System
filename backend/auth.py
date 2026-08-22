"""Password hashing, login/logout, and self-service password change."""
import sqlite3

import bcrypt

from backend import session
from backend.utils import row_to_dict

BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def login(conn: sqlite3.Connection, username: str, password: str) -> dict:
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return {"ok": False, "error": "INVALID_CREDENTIALS", "message": "ناوی بەکارهێنەر یان وشەی نهێنی هەڵەیە"}

    user = row_to_dict(row)
    del user["password_hash"]
    session.set_current_user(user)
    return {"ok": True, "data": user}


def logout() -> dict:
    session.clear_current_user()
    return {"ok": True, "data": None}


def change_password(conn: sqlite3.Connection, user_id: int, old_password: str, new_password: str) -> dict:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return {"ok": False, "error": "NOT_FOUND", "message": "بەکارهێنەر نەدۆزرایەوە"}
    if not verify_password(old_password, row["password_hash"]):
        return {"ok": False, "error": "INVALID_CREDENTIALS", "message": "وشەی نهێنی کۆن هەڵەیە"}
    if len(new_password) < 4:
        return {"ok": False, "error": "WEAK_PASSWORD", "message": "وشەی نهێنی نوێ زۆر کورتە"}

    new_hash = hash_password(new_password)
    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, force_password_change = 0 WHERE id = ?",
            (new_hash, user_id),
        )

    current = session.get_current_user()
    if current and current["id"] == user_id:
        current["force_password_change"] = 0
        session.set_current_user(current)

    return {"ok": True, "data": None}


def force_change_password(conn: sqlite3.Connection, user_id: int, new_password: str) -> dict:
    """Used only for the mandatory first-login password change, where the
    user is authenticated but we don't ask them to re-type the (known
    default, or admin-assigned temporary) old password."""
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return {"ok": False, "error": "NOT_FOUND", "message": "بەکارهێنەر نەدۆزرایەوە"}
    if not row["force_password_change"]:
        return {"ok": False, "error": "NOT_REQUIRED", "message": "پێویست ناکات وشەی نهێنی بگۆڕدرێت"}
    if len(new_password) < 4:
        return {"ok": False, "error": "WEAK_PASSWORD", "message": "وشەی نهێنی نوێ زۆر کورتە"}

    new_hash = hash_password(new_password)
    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, force_password_change = 0 WHERE id = ?",
            (new_hash, user_id),
        )

    current = session.get_current_user()
    if current and current["id"] == user_id:
        current["force_password_change"] = 0
        session.set_current_user(current)

    return {"ok": True, "data": None}
