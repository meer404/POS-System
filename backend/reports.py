"""Aggregate report queries: items sold, revenue, profit, top products, daily chart."""
import sqlite3
from datetime import date, timedelta

from backend.utils import rows_to_list


def total_items_sold(conn: sqlite3.Connection, start_date: str, end_date: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(si.quantity), 0) AS total
        FROM sale_items si JOIN sales s ON s.id = si.sale_id
        WHERE date(s.created_at) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()
    return row["total"]


def total_revenue(conn: sqlite3.Connection, start_date: str, end_date: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(final_amount), 0) AS total FROM sales
        WHERE date(created_at) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()
    return row["total"]


def total_profit(conn: sqlite3.Connection, start_date: str, end_date: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM((si.unit_price - sb.purchase_price) * si.quantity), 0) AS total
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN stock_batches sb ON sb.id = si.batch_id
        WHERE date(s.created_at) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()
    return row["total"]


def top_selling_products(conn: sqlite3.Connection, start_date: str, end_date: str, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.id, p.name, SUM(si.quantity) AS qty_sold, SUM(si.total_price) AS revenue
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN products p ON p.id = si.product_id
        WHERE date(s.created_at) BETWEEN ? AND ?
        GROUP BY p.id
        ORDER BY qty_sold DESC
        LIMIT ?
        """,
        (start_date, end_date, limit),
    ).fetchall()
    return rows_to_list(rows)


def daily_sales_last_n_days(conn: sqlite3.Connection, n: int = 7) -> list[dict]:
    rows = conn.execute(
        """
        SELECT date(created_at) AS day, COALESCE(SUM(final_amount), 0) AS revenue
        FROM sales
        WHERE date(created_at) >= date('now', ?)
        GROUP BY day
        ORDER BY day
        """,
        (f"-{n - 1} days",),
    ).fetchall()
    by_day = {r["day"]: r["revenue"] for r in rows}

    today = date.today()
    result = []
    for i in range(n - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        result.append({"day": day, "revenue": by_day.get(day, 0)})
    return result


def get_summary(conn: sqlite3.Connection, start_date: str, end_date: str) -> dict:
    return {
        "items_sold": total_items_sold(conn, start_date, end_date),
        "revenue": total_revenue(conn, start_date, end_date),
        "profit": total_profit(conn, start_date, end_date),
        "top_products": top_selling_products(conn, start_date, end_date, limit=5),
        "daily_chart": daily_sales_last_n_days(conn, n=7),
    }
