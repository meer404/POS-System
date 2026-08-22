"""Small shared helpers: row->dict conversion, date helpers, validation."""
import sqlite3
from datetime import date, datetime, timedelta


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


def today_iso() -> str:
    return date.today().isoformat()


def date_range_for_preset(preset: str) -> tuple[str, str]:
    """Return (start_date, end_date) ISO strings, inclusive, for a quick preset."""
    today = date.today()
    if preset == "today":
        start = today
    elif preset == "week":
        start = today - timedelta(days=today.weekday())
    elif preset == "month":
        start = today.replace(day=1)
    else:
        raise ValueError(f"Unknown preset: {preset}")
    return start.isoformat(), today.isoformat()


def clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def as_int(value, field_name: str = "value") -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")
    return result
