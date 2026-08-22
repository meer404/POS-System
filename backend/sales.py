"""Cart checkout, FIFO/nearest-expiry stock consumption, discount resolution."""
import sqlite3

from backend.utils import row_to_dict, rows_to_list


class InsufficientStockError(Exception):
    def __init__(self, product_id: int, product_name: str, available: int, requested: int):
        self.product_id = product_id
        self.product_name = product_name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient stock for product {product_id}: available={available}, requested={requested}"
        )


def get_cart_item_snapshot(conn: sqlite3.Connection, product_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT p.id AS product_id, p.name, p.sale_price,
               COALESCE(SUM(CASE WHEN sb.status='active' THEN sb.quantity ELSE 0 END), 0) AS available_qty
        FROM products p
        LEFT JOIN stock_batches sb ON sb.product_id = p.id
        WHERE p.id = ?
        GROUP BY p.id
        """,
        (product_id,),
    ).fetchone()
    return row_to_dict(row)


def consume_fifo(conn: sqlite3.Connection, product_id: int, quantity: int) -> list[tuple[int, int, int]]:
    """Return a consumption plan: list of (batch_id, qty_from_batch, purchase_price),
    ordered nearest-expiry-first (NULL expiry batches fall back to FIFO by received_at).
    Raises InsufficientStockError if total active stock is short.
    """
    batches = conn.execute(
        """
        SELECT id, quantity, purchase_price
        FROM stock_batches
        WHERE product_id = ? AND status = 'active' AND quantity > 0
        ORDER BY (expiry_date IS NULL), expiry_date ASC, received_at ASC
        """,
        (product_id,),
    ).fetchall()

    remaining = quantity
    plan: list[tuple[int, int, int]] = []
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch["quantity"], remaining)
        if take > 0:
            plan.append((batch["id"], take, batch["purchase_price"]))
            remaining -= take

    if remaining > 0:
        product = conn.execute("SELECT name FROM products WHERE id = ?", (product_id,)).fetchone()
        product_name = product["name"] if product else "?"
        available = quantity - remaining
        raise InsufficientStockError(product_id, product_name, available, quantity)

    return plan


def resolve_discount(total_amount: int, discount_mode: str, discount_value: int) -> int:
    if discount_mode == "percent":
        amount = round(total_amount * discount_value / 100)
    elif discount_mode == "flat":
        amount = discount_value
    else:
        raise ValueError("discount_mode must be 'percent' or 'flat'")
    return max(0, min(total_amount, int(amount)))


def complete_sale(conn: sqlite3.Connection, *, cashier_id: int, items: list[dict], discount_mode: str, discount_value: int) -> dict:
    """items: [{'product_id': int, 'quantity': int}, ...]. Prices are never
    trusted from the client -- sale_price is re-fetched server-side.
    Raises InsufficientStockError or ValueError on invalid input; caller
    (JSApi) is responsible for turning that into a structured error response.
    """
    if not items:
        raise ValueError("سەبەتە بەتاڵە")

    with conn:
        total_amount = 0
        item_plans = []  # (product_id, unit_price, plan)
        for item in items:
            product_id = int(item["product_id"])
            qty = int(item["quantity"])
            if qty <= 0:
                raise ValueError("بڕ نابێت لە سفر کەمتر بێت")
            product = conn.execute(
                "SELECT id, name, sale_price FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if product is None:
                raise ValueError(f"کاڵا نەدۆزرایەوە: {product_id}")
            unit_price = product["sale_price"]
            plan = consume_fifo(conn, product_id, qty)
            total_amount += unit_price * qty
            item_plans.append((product_id, unit_price, plan))

        discount = resolve_discount(total_amount, discount_mode, discount_value)
        final_amount = total_amount - discount

        cur = conn.execute(
            "INSERT INTO sales (total_amount, discount, final_amount, cashier_id) VALUES (?, ?, ?, ?)",
            (total_amount, discount, final_amount, cashier_id),
        )
        sale_id = cur.lastrowid

        receipt_lines = []
        for product_id, unit_price, plan in item_plans:
            product_name = conn.execute(
                "SELECT name FROM products WHERE id = ?", (product_id,)
            ).fetchone()["name"]
            line_qty = 0
            for batch_id, take, _purchase_price in plan:
                conn.execute(
                    "UPDATE stock_batches SET quantity = quantity - ? WHERE id = ?",
                    (take, batch_id),
                )
                line_total = unit_price * take
                conn.execute(
                    "INSERT INTO sale_items (sale_id, product_id, batch_id, quantity, unit_price, total_price) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (sale_id, product_id, batch_id, take, unit_price, line_total),
                )
                line_qty += take
            receipt_lines.append(
                {
                    "product_id": product_id,
                    "name": product_name,
                    "quantity": line_qty,
                    "unit_price": unit_price,
                    "total_price": unit_price * line_qty,
                }
            )

        created_at = conn.execute(
            "SELECT created_at FROM sales WHERE id = ?", (sale_id,)
        ).fetchone()["created_at"]

    return {
        "sale_id": sale_id,
        "total_amount": total_amount,
        "discount": discount,
        "final_amount": final_amount,
        "items": receipt_lines,
        "created_at": created_at,
    }


def get_receipt(conn: sqlite3.Connection, sale_id: int) -> dict | None:
    sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if sale is None:
        return None
    rows = conn.execute(
        """
        SELECT si.product_id, p.name, si.quantity, si.unit_price, si.total_price
        FROM sale_items si JOIN products p ON p.id = si.product_id
        WHERE si.sale_id = ?
        """,
        (sale_id,),
    ).fetchall()
    # Merge rows for the same product (a sale can have multiple batch-split rows).
    merged: dict[int, dict] = {}
    for r in rows:
        pid = r["product_id"]
        if pid not in merged:
            merged[pid] = {
                "product_id": pid,
                "name": r["name"],
                "quantity": 0,
                "unit_price": r["unit_price"],
                "total_price": 0,
            }
        merged[pid]["quantity"] += r["quantity"]
        merged[pid]["total_price"] += r["total_price"]

    result = row_to_dict(sale)
    result["items"] = list(merged.values())
    return result
