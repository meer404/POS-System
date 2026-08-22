"""Default admin seeding and optional demo data."""
import sqlite3
from datetime import date, timedelta

from backend.auth import hash_password

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def ensure_default_admin(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if count > 0:
        return
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, force_password_change) "
            "VALUES (?, ?, 'admin', 1)",
            (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD)),
        )


def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Opt-in demo data: a cashier user, ~8 products with varied batches,
    and a spread of historical sales so reports/charts have data to show.
    Never called automatically -- only via `python main.py --seed`.
    """
    existing = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if existing > 0:
        return

    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, force_password_change) "
            "VALUES ('cashier', ?, 'cashier', 0)",
            (hash_password("cashier123"),),
        )
        cashier_id = conn.execute(
            "SELECT id FROM users WHERE username = 'cashier'"
        ).fetchone()["id"]

        today = date.today()
        products = [
            # name, category, sale_price, unit, min_stock, purchase_price, qty, expiry_offset_days
            ("برنجی باسمەتی", "خواردنی وشک", 2500, "کیلۆ", 10, 1800, 50, None),
            ("ڕۆنی خۆراک", "خواردنی وشک", 4000, "لیتر", 5, 3200, 30, 400),
            ("شەکر", "خواردنی وشک", 1500, "کیلۆ", 10, 1100, 40, None),
            ("شیری تازە", "شیر و بەرهەمەکانی", 1000, "دانە", 15, 700, 25, 5),
            ("پەنیر", "شیر و بەرهەمەکانی", 3000, "کیلۆ", 5, 2200, 12, 10),
            ("نان", "نانەوایی", 250, "دانە", 20, 150, 60, 2),
            ("سیب", "میوە و سەوزە", 1500, "کیلۆ", 10, 1000, 35, 14),
            ("پەتاتە", "میوە و سەوزە", 750, "کیلۆ", 15, 500, 45, 30),
        ]
        product_ids = []
        for name, category, sale_price, unit, min_stock, purchase_price, qty, exp_offset in products:
            cur = conn.execute(
                "INSERT INTO products (name, category, sale_price, unit, min_stock) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, category, sale_price, unit, min_stock),
            )
            product_id = cur.lastrowid
            product_ids.append((product_id, sale_price, purchase_price))
            expiry = (today + timedelta(days=exp_offset)).isoformat() if exp_offset is not None else None
            conn.execute(
                "INSERT INTO stock_batches (product_id, purchase_price, quantity, expiry_date, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                (product_id, purchase_price, qty, expiry),
            )

        # A few historical sales spread over the last 2 weeks for report/chart data.
        import random

        random.seed(42)
        for days_ago in range(14, -1, -1):
            if random.random() < 0.35:
                continue  # skip some days so the chart isn't perfectly uniform
            sale_created = (today - timedelta(days=days_ago)).isoformat()
            num_items = random.randint(1, 4)
            chosen = random.sample(product_ids, k=min(num_items, len(product_ids)))
            total_amount = 0
            lines = []
            for product_id, sale_price, purchase_price in chosen:
                qty = random.randint(1, 3)
                line_total = sale_price * qty
                total_amount += line_total
                lines.append((product_id, qty, sale_price, line_total, purchase_price))
            discount = 0
            final_amount = total_amount - discount
            cur = conn.execute(
                "INSERT INTO sales (total_amount, discount, final_amount, cashier_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (total_amount, discount, final_amount, cashier_id, sale_created),
            )
            sale_id = cur.lastrowid
            for product_id, qty, unit_price, line_total, purchase_price in lines:
                batch = conn.execute(
                    "SELECT id, quantity FROM stock_batches WHERE product_id = ? AND status='active' "
                    "AND quantity > 0 ORDER BY id LIMIT 1",
                    (product_id,),
                ).fetchone()
                if batch is None:
                    continue
                take = min(qty, batch["quantity"])
                if take <= 0:
                    continue
                conn.execute(
                    "UPDATE stock_batches SET quantity = quantity - ? WHERE id = ?",
                    (take, batch["id"]),
                )
                conn.execute(
                    "INSERT INTO sale_items (sale_id, product_id, batch_id, quantity, unit_price, total_price) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (sale_id, product_id, batch["id"], take, unit_price, unit_price * take),
                )
