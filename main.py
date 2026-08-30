"""Entry point: initializes the database, seeds default data, and opens
the pywebview desktop window bound to the JSApi backend."""
import sys
from pathlib import Path

import webview

from backend import db, seed
from backend.api import JSApi

# Static assets (frontend/) are read-only and ship inside the PyInstaller
# bundle (sys._MEIPASS), which differs from the writable data/ location
# next to the .exe that backend/db.py resolves independently.
if getattr(sys, "frozen", False):
    ASSETS_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    ASSETS_DIR = Path(__file__).resolve().parent


def frontend_path(*parts: str) -> str:
    return str(ASSETS_DIR / "frontend" / Path(*parts))


def main() -> None:
    conn = db.get_connection()
    db.init_db(conn)
    seed.ensure_default_admin(conn)

    if "--seed" in sys.argv:
        seed.seed_demo_data(conn)

    api = JSApi(conn)

    debug = "--debug" in sys.argv
    window = webview.create_window(
        "سیستەمی فرۆشتن",
        url=frontend_path("index.html"),
        js_api=api,
        width=1366,
        height=800,
        min_size=(1024, 700),
    )
    api._window = window  # enables native Save/Open dialogs for backup & restore
    webview.start(debug=debug)


if __name__ == "__main__":
    main()
