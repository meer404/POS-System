"""Database backup and restore for the offline POS.

A backup is a single-file SQLite snapshot produced via sqlite3's online
backup API (`Connection.backup`): it is WAL-safe and always internally
consistent, unlike a raw copy of `store.db` which can miss data still in the
`-wal` sidecar. Restore validates the incoming file, takes a safety snapshot
of the current database, then atomically swaps the file in for
`data/store.db` and hands back a fresh connection.
"""
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from backend import db

# Tables that must be present for a file to be accepted as a POS backup.
REQUIRED_TABLES = {
    "users",
    "products",
    "stock_batches",
    "sales",
    "sale_items",
    "returns",
    "counters",
    "schema_version",
}


def backups_dir() -> Path:
    """`data/backups/` next to the live database file (created on demand)."""
    d = db.resolve_db_path().parent / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def suggested_filename() -> str:
    return f"pos-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"


def _snapshot(conn: sqlite3.Connection, dest_path: Path) -> None:
    """Write a consistent copy of `conn`'s database to `dest_path`."""
    conn.execute("PRAGMA wal_checkpoint(FULL)")
    dest = sqlite3.connect(str(dest_path))
    try:
        with dest:
            conn.backup(dest)
    finally:
        dest.close()


def create_backup(conn: sqlite3.Connection, export_path: str | None = None) -> dict:
    """Snapshot the database into `data/backups/`, and optionally also copy
    that snapshot to `export_path` (e.g. a USB drive the user picked).
    """
    archive = backups_dir() / suggested_filename()
    _snapshot(conn, archive)
    exported_to = None
    if export_path:
        shutil.copyfile(str(archive), export_path)
        exported_to = export_path
    return {
        "filename": archive.name,
        "path": str(archive),
        "exported_to": exported_to,
        "size": archive.stat().st_size,
    }


def list_backups() -> list[dict]:
    """Local backup files, newest first."""
    out = []
    for p in sorted(backups_dir().glob("*.db"), key=lambda p: p.name, reverse=True):
        st = p.stat()
        out.append(
            {
                "filename": p.name,
                "size": st.st_size,
                "created_at": datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )
    return out


def validate_backup_file(path: str) -> None:
    """Raise ``ValueError`` (with a Sorani message) if `path` is not a usable
    POS backup: missing, not a SQLite database, corrupt, or missing tables.
    """
    p = Path(path)
    if not p.is_file():
        raise ValueError("فایلی باکاپ نەدۆزرایەوە")
    try:
        probe = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        raise ValueError("فایلەکە داتابەیسی دروست نییە")
    try:
        try:
            integrity = probe.execute("PRAGMA integrity_check").fetchone()
            names = {
                r[0]
                for r in probe.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        except sqlite3.DatabaseError:
            raise ValueError("فایلەکە داتابەیسی دروست نییە")
        if not integrity or integrity[0] != "ok":
            raise ValueError("فایلی باکاپ تێکچووە")
        if not REQUIRED_TABLES.issubset(names):
            raise ValueError("فایلەکە باکاپی ئەم سیستەمە نییە")
    finally:
        probe.close()


def restore_backup(conn: sqlite3.Connection, source_path: str) -> sqlite3.Connection:
    """Replace the live database with `source_path` and return a NEW connection.

    A safety snapshot of the current database is written to
    ``data/backups/pre-restore-<ts>.db`` first. The caller (``JSApi``) is
    responsible for rebinding ``self.conn`` to the returned connection and
    clearing the session.
    """
    validate_backup_file(source_path)
    live = db.resolve_db_path()

    _snapshot(conn, backups_dir() / f"pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")

    conn.close()
    for sidecar in (
        live.with_name(live.name + "-wal"),
        live.with_name(live.name + "-shm"),
    ):
        if sidecar.exists():
            sidecar.unlink()

    tmp = live.with_name(live.name + ".incoming")
    shutil.copyfile(source_path, tmp)
    os.replace(tmp, live)

    new_conn = db.get_connection()
    db.init_db(new_conn)  # idempotent; applies migrations if the backup is older
    return new_conn
