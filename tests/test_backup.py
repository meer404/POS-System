import sqlite3

import pytest

from backend import backup, db


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A file-based DB at tmp_path/store.db, with db.resolve_db_path patched
    so backups_dir() and restore_backup() both resolve under tmp_path."""
    db_path = tmp_path / "store.db"
    monkeypatch.setattr(db, "resolve_db_path", lambda: db_path)
    conn = db.get_connection(db_path=db_path)
    db.init_db(conn)
    yield conn, tmp_path
    try:
        conn.close()
    except sqlite3.Error:
        pass


def _add_product(conn, name):
    with conn:
        conn.execute(
            "INSERT INTO products (name, sale_price) VALUES (?, 100)", (name,)
        )


def test_create_backup_writes_consistent_snapshot(store):
    conn, tmp_path = store
    _add_product(conn, "A")

    result = backup.create_backup(conn)

    archive = tmp_path / "backups" / result["filename"]
    assert archive.is_file()
    assert result["exported_to"] is None
    assert result["size"] > 0

    snap = sqlite3.connect(str(archive))
    try:
        names = {r[0] for r in snap.execute("SELECT name FROM products")}
    finally:
        snap.close()
    assert names == {"A"}


def test_create_backup_export_copy(store, tmp_path):
    conn, _ = store
    export = tmp_path / "usb" / "mybackup.db"
    export.parent.mkdir()

    result = backup.create_backup(conn, export_path=str(export))

    assert export.is_file()
    assert result["exported_to"] == str(export)
    assert export.stat().st_size == result["size"]


def test_list_backups_newest_first(store):
    conn, _ = store
    first = backup.create_backup(conn)["filename"]
    # filenames carry a second-resolution timestamp; force a distinct name
    second_path = backup.backups_dir() / "pos-backup-99999999-999999.db"
    second_path.write_bytes((backup.backups_dir() / first).read_bytes())

    listing = backup.list_backups()
    assert [b["filename"] for b in listing][0] == "pos-backup-99999999-999999.db"
    assert all({"filename", "size", "created_at"} <= set(b) for b in listing)


def test_validate_rejects_non_sqlite(tmp_path):
    junk = tmp_path / "notadb.db"
    junk.write_text("this is not a database")
    with pytest.raises(ValueError):
        backup.validate_backup_file(str(junk))


def test_validate_rejects_missing_file(tmp_path):
    with pytest.raises(ValueError):
        backup.validate_backup_file(str(tmp_path / "nope.db"))


def test_validate_rejects_sqlite_without_pos_tables(tmp_path):
    other = tmp_path / "other.db"
    c = sqlite3.connect(str(other))
    with c:
        c.execute("CREATE TABLE foo (id INTEGER)")
    c.close()
    with pytest.raises(ValueError):
        backup.validate_backup_file(str(other))


def test_validate_accepts_real_backup(store):
    conn, _ = store
    result = backup.create_backup(conn)
    backup.validate_backup_file(result["path"])  # must not raise


def test_restore_round_trip(store):
    conn, tmp_path = store
    _add_product(conn, "A")
    archive = backup.create_backup(conn)["path"]
    _add_product(conn, "B")

    new_conn = backup.restore_backup(conn, archive)

    names = {r[0] for r in new_conn.execute("SELECT name FROM products")}
    assert names == {"A"}
    assert any(p.name.startswith("pre-restore-") for p in (tmp_path / "backups").glob("*.db"))
    new_conn.close()
