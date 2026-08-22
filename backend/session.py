"""Single-user desktop session state and role-enforcement decorator.

pywebview runs one desktop process with exactly one logged-in user at a
time, so session state is a simple module-level singleton rather than a
cookie/token scheme. This is the ONLY place role checks are enforced on
the backend -- the frontend's role-based menu filtering is UX only.
"""
import functools

_current_user: dict | None = None


def set_current_user(user: dict) -> None:
    global _current_user
    _current_user = user


def clear_current_user() -> None:
    global _current_user
    _current_user = None


def get_current_user() -> dict | None:
    return _current_user


def is_logged_in() -> bool:
    return _current_user is not None


def require_role(*allowed_roles: str):
    """Decorator for JSApi methods: enforces that a user is logged in and
    holds one of the allowed roles before the wrapped method runs.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            user = get_current_user()
            if user is None:
                return {"ok": False, "error": "NOT_AUTHENTICATED", "message": "پێویستە بچیتە ژوورەوە"}
            if user["role"] not in allowed_roles:
                return {"ok": False, "error": "FORBIDDEN", "message": "ڕێگەت پێنەدراوە"}
            return fn(self, *args, **kwargs)

        wrapper._role_guarded = True
        wrapper._allowed_roles = allowed_roles
        return wrapper

    return decorator
