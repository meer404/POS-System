"""Product + stock batch business logic, including local barcode generation."""
import sqlite3

from backend.utils import row_to_dict, rows_to_list

LOCAL_BARCODE_PREFIX = "9"
LOCAL_BARCODE_DIGITS = 12  # total length = 1 (prefix) + 12 = 13


def _format_local_barcode(counter_value: int) -> str:
    return LOCAL_BARCODE_PREFIX + str(counter_value).zfill(LOCAL_BARCODE_DIGITS)


def generate_local_barcode(conn: sqlite3.Connection) -> str:
    """Generate a unique 13-digit local barcode prefixed with '9', backed by
    an auto-incrementing counter. Defensively re-checks for collisions.
    """
    for _ in range(5):
        with conn:
            try:
                cur = conn.execute(
                    "UPDATE counters SET value = value + 1 WHERE name = 'local_barcode' RETURNING value"
                )
                value = cur.fetchone()["value"]
            except sqlite3.OperationalError:
                # Older SQLite without RETURNING support (pre-3.35).
                conn.execute(
                    "UPDATE counters SET value = value + 1 WHERE name = 'local_barcode'"
                )
                value = conn.execute(
                    "SELECT value FROM counters WHERE name = 'local_barcode'"
                ).fetchone()["value"]
        barcode = _format_local_barcode(value)
        exists = conn.execute(
            "SELECT 1 FROM products WHERE barcode = ?", (barcode,)
        ).fetchone()
        if exists is None:
            return barcode
    raise RuntimeError("Failed to generate a unique local barcode after 5 attempts")


def find_product_by_barcode(conn: sqlite3.Connection, barcode: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM products WHERE barcode = ?", (barcode,)
    ).fetchone()
    return row_to_dict(row)


def search_products(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    like = f"%{query}%"
    rows = conn.execute(
        """
        SELECT p.*, COALESCE(SUM(CASE WHEN sb.status = 'active' THEN sb.quantity ELSE 0 END), 0) AS stock_qty
        FROM products p
        LEFT JOIN stock_batches sb ON sb.product_id = p.id
        WHERE p.name LIKE ? OR p.barcode LIKE ?
        GROUP BY p.id
        ORDER BY p.name
        LIMIT ?
        """,
        (like, like, limit),
    ).fetchall()
    return rows_to_list(rows)


def list_products(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.*, COALESCE(SUM(CASE WHEN sb.status = 'active' THEN sb.quantity ELSE 0 END), 0) AS stock_qty
        FROM products p
        LEFT JOIN stock_batches sb ON sb.product_id = p.id
        GROUP BY p.id
        ORDER BY p.name
        """
    ).fetchall()
    return rows_to_list(rows)


def get_product_with_batches(conn: sqlite3.Connection, product_id: int) -> dict | None:
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        return None
    batches = conn.execute(
        """
        SELECT * FROM stock_batches
        WHERE product_id = ? AND status = 'active' AND quantity > 0
        ORDER BY (expiry_date IS NULL), expiry_date ASC, received_at ASC
        """,
        (product_id,),
    ).fetchall()
    result = row_to_dict(product)
    result["batches"] = rows_to_list(batches)
    return result


def create_product(
    conn: sqlite3.Connection,
    *,
    name: str,
    barcode: str | None,
    category: str | None,
    sale_price: int,
    unit: str | None,
    min_stock: int,
    purchase_price: int,
    quantity: int,
    expiry_date: str | None,
) -> dict:
    if not name or not name.strip():
        raise ValueError("ناوی کاڵا پێویستە")
    if sale_price < 0 or purchase_price < 0 or quantity < 0 or min_stock < 0:
        raise ValueError("بەها و بڕ نابێت لە سفر کەمتر بێت")

    with conn:
        if not barcode or not barcode.strip():
            barcode = generate_local_barcode(conn)
        else:
            existing = conn.execute(
                "SELECT 1 FROM products WHERE barcode = ?", (barcode,)
            ).fetchone()
            if existing is not None:
                raise ValueError("ئەم بارکۆدە پێشتر تۆمارکراوە")

        cur = conn.execute(
            "INSERT INTO products (name, barcode, category, sale_price, unit, min_stock) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name.strip(), barcode, category, sale_price, unit, min_stock),
        )
        product_id = cur.lastrowid
        conn.execute(
            "INSERT INTO stock_batches (product_id, purchase_price, quantity, expiry_date, status) "
            "VALUES (?, ?, ?, ?, 'active')",
            (product_id, purchase_price, quantity, expiry_date),
        )

    return get_product_with_batches(conn, product_id)


def add_stock_batch(
    conn: sqlite3.Connection,
    *,
    product_id: int,
    purchase_price: int,
    quantity: int,
    expiry_date: str | None,
) -> dict:
    if purchase_price < 0 or quantity < 0:
        raise ValueError("بەها و بڕ نابێت لە سفر کەمتر بێت")
    product = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        raise ValueError("کاڵاکە نەدۆزرایەوە")

    with conn:
        conn.execute(
            "INSERT INTO stock_batches (product_id, purchase_price, quantity, expiry_date, status) "
            "VALUES (?, ?, ?, ?, 'active')",
            (product_id, purchase_price, quantity, expiry_date),
        )

    return get_product_with_batches(conn, product_id)


def update_product(
    conn: sqlite3.Connection,
    product_id: int,
    *,
    name: str | None = None,
    barcode: str | None = None,
    category: str | None = None,
    sale_price: int | None = None,
    unit: str | None = None,
    min_stock: int | None = None,
) -> dict:
    existing = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if existing is None:
        raise ValueError("کاڵاکە نەدۆزرایەوە")

    fields = []
    values = []
    if name is not None:
        if not name.strip():
            raise ValueError("ناوی کاڵا نابێت بەتاڵ بێت")
        fields.append("name = ?")
        values.append(name.strip())
    if barcode is not None:
        if barcode != existing["barcode"]:
            clash = conn.execute(
                "SELECT 1 FROM products WHERE barcode = ? AND id != ?", (barcode, product_id)
            ).fetchone()
            if clash is not None:
                raise ValueError("ئەم بارکۆدە پێشتر تۆمارکراوە")
        fields.append("barcode = ?")
        values.append(barcode)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if sale_price is not None:
        if sale_price < 0:
            raise ValueError("نرخی فرۆشتن نابێت لە سفر کەمتر بێت")
        fields.append("sale_price = ?")
        values.append(sale_price)
    if unit is not None:
        fields.append("unit = ?")
        values.append(unit)
    if min_stock is not None:
        if min_stock < 0:
            raise ValueError("کەمترین بڕ نابێت لە سفر کەمتر بێت")
        fields.append("min_stock = ?")
        values.append(min_stock)

    if fields:
        values.append(product_id)
        with conn:
            conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", values)

    return get_product_with_batches(conn, product_id)
