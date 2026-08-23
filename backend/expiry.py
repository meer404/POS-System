"""Expired / near-expiry batch queries, Mark as Loss, and supplier returns."""
import sqlite3

from backend.utils import as_int, row_to_dict, rows_to_list


def list_expired(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT sb.*, p.name AS product_name, p.unit
        FROM stock_batches sb JOIN products p ON p.id = sb.product_id
        WHERE sb.status = 'active' AND sb.quantity > 0
          AND sb.expiry_date IS NOT NULL AND sb.expiry_date < date('now')
        ORDER BY sb.expiry_date ASC
        """
    ).fetchall()
    return rows_to_list(rows)


def list_near_expiry(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    rows = conn.execute(
        """
        SELECT sb.*, p.name AS product_name, p.unit
        FROM stock_batches sb JOIN products p ON p.id = sb.product_id
        WHERE sb.status = 'active' AND sb.quantity > 0
          AND sb.expiry_date IS NOT NULL
          AND sb.expiry_date BETWEEN date('now') AND date('now', ?)
        ORDER BY sb.expiry_date ASC
        """,
        (f"+{days} days",),
    ).fetchall()
    return rows_to_list(rows)


def _adjust_batch(conn: sqlite3.Connection, batch_id: int, quantity: int, reason: str) -> dict:
    if quantity <= 0:
        raise ValueError("بڕ نابێت لە سفر کەمتر بێت")
    batch = conn.execute("SELECT * FROM stock_batches WHERE id = ?", (batch_id,)).fetchone()
    if batch is None:
        raise ValueError("بەچ نەدۆزرایەوە")
    if quantity > batch["quantity"]:
        raise ValueError("بڕ زیاترە لەوەی لە کۆگا هەیە")

    new_qty = batch["quantity"] - quantity
    with conn:
        if new_qty == 0:
            conn.execute(
                "UPDATE stock_batches SET quantity = 0, status = 'disposed' WHERE id = ?",
                (batch_id,),
            )
        else:
            conn.execute(
                "UPDATE stock_batches SET quantity = ? WHERE id = ?", (new_qty, batch_id)
            )
        conn.execute(
            "INSERT INTO returns (batch_id, quantity, reason) VALUES (?, ?, ?)",
            (batch_id, quantity, reason),
        )

    return row_to_dict(conn.execute("SELECT * FROM stock_batches WHERE id = ?", (batch_id,)).fetchone())


def mark_as_loss(conn: sqlite3.Connection, batch_id: int, quantity: int) -> dict:
    return _adjust_batch(conn, batch_id, quantity, "expired")


def return_to_supplier(conn: sqlite3.Connection, batch_id: int, quantity: int) -> dict:
    return _adjust_batch(conn, batch_id, quantity, "supplier_return")


def _restore_stock_for_return(conn: sqlite3.Connection, product_id: int, quantity: int) -> int:
    """Add `quantity` to the product's most recent active batch, or create a
    new one (priced at the product's last known purchase price) if it has
    none. Returns the batch_id that received the stock."""
    batch = conn.execute(
        """
        SELECT id FROM stock_batches
        WHERE product_id = ? AND status = 'active'
        ORDER BY received_at DESC LIMIT 1
        """,
        (product_id,),
    ).fetchone()
    if batch is not None:
        conn.execute(
            "UPDATE stock_batches SET quantity = quantity + ? WHERE id = ?",
            (quantity, batch["id"]),
        )
        return batch["id"]

    last_price_row = conn.execute(
        "SELECT purchase_price FROM stock_batches WHERE product_id = ? ORDER BY received_at DESC LIMIT 1",
        (product_id,),
    ).fetchone()
    purchase_price = last_price_row["purchase_price"] if last_price_row is not None else 0
    cur = conn.execute(
        "INSERT INTO stock_batches (product_id, purchase_price, quantity, status) VALUES (?, ?, ?, 'active')",
        (product_id, purchase_price, quantity),
    )
    return cur.lastrowid


def create_customer_return(conn: sqlite3.Connection, items: list[dict]) -> dict:
    """Barcode-driven customer return: no receipt/sale_item lookup, so each
    item only carries a product_id. Restores stock and records one `returns`
    row per item, all in a single transaction, and returns a receipt-shaped
    dict for the frontend's return slip.
    """
    if not items:
        raise ValueError("لیستی گەڕاندنەوە بەتاڵە")

    parsed_items = []
    for entry in items:
        product_id = as_int(entry.get("product_id"), "product_id")
        quantity = as_int(entry.get("quantity"), "quantity")
        refund_amount = as_int(entry.get("refund_amount"), "refund_amount")
        if quantity <= 0:
            raise ValueError("بڕ نابێت لە سفر کەمتر بێت")
        if refund_amount < 0:
            raise ValueError("بڕی گەڕاندنەوە نابێت لە سفر کەمتر بێت")
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            raise ValueError("کاڵا نەدۆزرایەوە")
        parsed_items.append((product, quantity, refund_amount))

    receipt_items = []
    total_refund = 0
    last_return_id = None
    with conn:
        for product, quantity, refund_amount in parsed_items:
            batch_id = _restore_stock_for_return(conn, product["id"], quantity)
            cur = conn.execute(
                """
                INSERT INTO returns (product_id, batch_id, quantity, refund_amount, reason)
                VALUES (?, ?, ?, ?, 'customer_return')
                """,
                (product["id"], batch_id, quantity, refund_amount),
            )
            last_return_id = cur.lastrowid
            receipt_items.append(
                {
                    "product_id": product["id"],
                    "name": product["name"],
                    "quantity": quantity,
                    "refund_amount": refund_amount,
                }
            )
            total_refund += refund_amount

        created_at = conn.execute(
            "SELECT created_at FROM returns WHERE id = ?", (last_return_id,)
        ).fetchone()["created_at"]

    return {"items": receipt_items, "total_refund": total_refund, "created_at": created_at}


def record_customer_return(conn: sqlite3.Connection, sale_item_id: int, quantity: int) -> dict:
    """Backend-only helper: restores `quantity` back to the batch a sold
    item was originally drawn from. Not wired to any frontend page -- the
    spec's module list has no dedicated customer-return screen, but the
    schema (returns.reason='customer_return') supports it for future use.
    """
    if quantity <= 0:
        raise ValueError("بڕ نابێت لە سفر کەمتر بێت")
    sale_item = conn.execute(
        "SELECT * FROM sale_items WHERE id = ?", (sale_item_id,)
    ).fetchone()
    if sale_item is None:
        raise ValueError("ئایتمی فرۆشتن نەدۆزرایەوە")
    if quantity > sale_item["quantity"]:
        raise ValueError("بڕ زیاترە لەوەی فرۆشراوە")

    batch_id = sale_item["batch_id"]
    with conn:
        conn.execute(
            "UPDATE stock_batches SET quantity = quantity + ?, status = 'active' WHERE id = ?",
            (quantity, batch_id),
        )
        conn.execute(
            "INSERT INTO returns (sale_item_id, quantity, reason) VALUES (?, ?, 'customer_return')",
            (sale_item_id, quantity),
        )

    return row_to_dict(conn.execute("SELECT * FROM stock_batches WHERE id = ?", (batch_id,)).fetchone())
