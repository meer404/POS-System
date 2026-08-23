"""Aggregate report queries: items sold, revenue, profit, top products, daily chart."""
import sqlite3
from datetime import date, timedelta

from backend.utils import rows_to_list


def _returns_totals(conn: sqlite3.Connection, start_date: str, end_date: str) -> sqlite3.Row:
    return conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(refund_amount), 0) AS amount
        FROM returns
        WHERE reason = 'customer_return' AND date(created_at) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()


def total_returns(conn: sqlite3.Connection, start_date: str, end_date: str) -> dict:
    row = _returns_totals(conn, start_date, end_date)
    return {"quantity": row["quantity"], "amount": row["amount"]}


def total_items_sold(conn: sqlite3.Connection, start_date: str, end_date: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(si.quantity), 0) AS total
        FROM sale_items si JOIN sales s ON s.id = si.sale_id
        WHERE date(s.created_at) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()
    returned = _returns_totals(conn, start_date, end_date)["quantity"]
    return row["total"] - returned


def total_revenue(conn: sqlite3.Connection, start_date: str, end_date: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(final_amount), 0) AS total FROM sales
        WHERE date(created_at) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()
    refunded = _returns_totals(conn, start_date, end_date)["amount"]
    return row["total"] - refunded


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
    refunded = _returns_totals(conn, start_date, end_date)["amount"]
    return row["total"] - refunded


def top_selling_products(conn: sqlite3.Connection, start_date: str, end_date: str, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            p.id,
            p.name,
            SUM(si.quantity) AS gross_qty_sold,
            SUM(si.total_price) AS gross_revenue,
            COALESCE(r.returned_qty, 0) AS returned_qty,
            COALESCE(r.returned_amount, 0) AS returned_amount
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN products p ON p.id = si.product_id
        LEFT JOIN (
            SELECT product_id, SUM(quantity) AS returned_qty, SUM(refund_amount) AS returned_amount
            FROM returns
            WHERE reason = 'customer_return' AND date(created_at) BETWEEN ? AND ?
            GROUP BY product_id
        ) r ON r.product_id = p.id
        WHERE date(s.created_at) BETWEEN ? AND ?
        GROUP BY p.id
        ORDER BY (gross_qty_sold - returned_qty) DESC
        LIMIT ?
        """,
        (start_date, end_date, start_date, end_date, limit),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "qty_sold": r["gross_qty_sold"] - r["returned_qty"],
            "revenue": r["gross_revenue"] - r["returned_amount"],
        }
        for r in rows
    ]


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
        "returns": total_returns(conn, start_date, end_date),
    }
