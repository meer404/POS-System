"""Database connection, schema creation, and path resolution."""
import sqlite3
import sys
from pathlib import Path

SCHEMA_VERSION = 2

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('admin', 'cashier')),
        force_password_change INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        barcode TEXT UNIQUE,
        category TEXT,
        sale_price INTEGER NOT NULL,
        unit TEXT,
        min_stock INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id),
        purchase_price INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        expiry_date DATE,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'disposed'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_amount INTEGER NOT NULL,
        discount INTEGER NOT NULL DEFAULT 0,
        final_amount INTEGER NOT NULL,
        cashier_id INTEGER NOT NULL REFERENCES users(id),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL REFERENCES sales(id),
        product_id INTEGER NOT NULL REFERENCES products(id),
        batch_id INTEGER NOT NULL REFERENCES stock_batches(id),
        quantity INTEGER NOT NULL,
        unit_price INTEGER NOT NULL,
        total_price INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_item_id INTEGER REFERENCES sale_items(id),
        batch_id INTEGER REFERENCES stock_batches(id),
        quantity INTEGER NOT NULL,
        reason TEXT NOT NULL CHECK (reason IN ('expired', 'supplier_return', 'customer_return')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS counters (
        name TEXT PRIMARY KEY,
        value INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_stock_batches_product ON stock_batches(product_id, status, expiry_date)",
    "CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id)",
    "CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_sale_items_batch ON sale_items(batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_returns_batch ON returns(batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_returns_sale_item ON returns(sale_item_id)",
]

# Columns added after the initial `returns` table shipped. `CREATE TABLE IF
# NOT EXISTS` is a no-op on a database that already has the table, so these
# need an explicit ALTER TABLE migration to reach existing store.db files.
RETURNS_TABLE_MIGRATIONS = [
    ("product_id", "ALTER TABLE returns ADD COLUMN product_id INTEGER REFERENCES products(id)"),
    ("refund_amount", "ALTER TABLE returns ADD COLUMN refund_amount INTEGER"),
]


def _migrate_returns_table(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(returns)")}
    for column_name, alter_statement in RETURNS_TABLE_MIGRATIONS:
        if column_name not in existing_columns:
            conn.execute(alter_statement)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_returns_product ON returns(product_id)")


def resolve_db_path() -> Path:
    """Resolve the SQLite file location for both dev and frozen (PyInstaller) runs.

    In a frozen onedir build, the writable data folder must live next to the
    executable, not inside the read-only/ephemeral bundle directory.
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "store.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path if db_path is not None else resolve_db_path()
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def supports_returning(conn: sqlite3.Connection) -> bool:
    return sqlite3.sqlite_version_info >= (3, 35, 0)


def init_db(conn: sqlite3.Connection) -> None:
    with conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        _migrate_returns_table(conn)
        row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_version (id, version) VALUES (1, ?)", (SCHEMA_VERSION,)
            )
        existing = conn.execute(
            "SELECT 1 FROM counters WHERE name = 'local_barcode'"
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO counters (name, value) VALUES ('local_barcode', 0)"
            )
