# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An offline-only desktop POS (cashier) system for a small market: Python + SQLite backend, vanilla HTML/CSS/JS frontend (Kurdish Sorani, RTL), running inside a pywebview desktop window. No server, no network calls at runtime — all third-party assets (font, icons, Chart.js) are vendored locally under `frontend/assets/` and `frontend/js/vendor/`. Currency is Iraqi Dinar (IQD): amounts are always whole integers, never floats, throughout the DB, backend, and UI.

## Commands

```
# setup
python -m venv venv
venv\Scripts\pip install -r requirements-dev.txt   # includes pytest + pyinstaller; requirements.txt alone is enough to just run the app

# run
venv\Scripts\python main.py                # normal run
venv\Scripts\python main.py --seed         # also seed demo products/sales/cashier user (only if products table is empty)
venv\Scripts\python main.py --debug        # opens with pywebview/devtools debug logging

# tests
venv\Scripts\python -m pytest tests/ -v
venv\Scripts\python -m pytest tests/test_fifo.py::test_fifo_consumes_nearest_expiry_first -v   # single test

# package to .exe (onedir, not onefile — see Packaging below)
venv\Scripts\pyinstaller build.spec --noconfirm
# output: dist/POS-System/  — must ship the WHOLE folder, not just the .exe
```

Default login after first run: `admin` / `admin123` (forces a password change on first login, via `users.force_password_change`). `--seed` additionally creates `cashier` / `cashier123`.

## Architecture

### Backend/frontend boundary

The entire frontend talks to Python through exactly one object: `backend/api.py`'s `JSApi` class, bound as pywebview's `js_api`. Every method returns a consistent envelope — `{"ok": true, "data": ...}` or `{"ok": false, "error": CODE, "message": "..."}` — and `frontend/js/api.js`'s `Api.call()` unwraps that envelope, throwing a JS `Error` on failure so page code can just `try/await`. When adding a new backend capability, it always goes: business logic function in the relevant `backend/*.py` module → thin wrapper method on `JSApi` → call site in a `frontend/js/pages/*.js` file. Don't call business-logic modules directly from the frontend; always go through `JSApi`.

### Role enforcement is server-side only, via one decorator

`backend/session.py` holds `_current_user` as a module-level singleton (safe because pywebview is a single-user desktop process, not a multi-client server) and defines `require_role(*roles)`. Every `JSApi` method except `login`, `logout`, `get_current_user`, `change_password`, `force_change_password` must carry `@require_role(...)`. `tests/test_roles.py::test_every_public_method_is_role_guarded_except_exempt` enforces this by introspection — if you add a new `JSApi` method without a role decorator (or without adding it to that test's `EXEMPT_METHODS`), the test fails on purpose. The frontend's sidebar/menu filtering (`frontend/js/router.js`'s `MENU` array) is UX convenience only; never trust it for security, and never add a permission check that exists only in JS.

One method, `update_product`, has a second, finer-grained check inside the method body: cashiers may create/edit products but not change `sale_price`, so `JSApi.update_product` inspects the payload for a `sale_price` key and rejects it for non-admins even though the method itself is `@require_role("admin", "cashier")`.

### Stock model: products vs. stock_batches, and FIFO consumption

`products` holds catalog data (name, barcode, sale_price, category, unit, min_stock) but never purchase price, quantity, or expiry — those live per-batch in `stock_batches`, because the same product can be restocked at different prices/expiry dates over time. Scanning a barcode that already exists never overwrites the old `purchase_price`; it inserts a new batch (`backend/products.py::add_stock_batch`).

Selling consumes stock via `backend/sales.py::consume_fifo`, which orders active batches (`status='active' AND quantity>0`) by nearest `expiry_date` first, falling back to oldest `received_at` for batches with no expiry date (`ORDER BY (expiry_date IS NULL), expiry_date ASC, received_at ASC`). A single cart line can therefore produce multiple `sale_items` rows (one per batch it drew from) — this is intentional and is how profit-per-batch (`unit_price - stock_batches.purchase_price`) stays accurate in `backend/reports.py`. A batch depleted to 0 by a sale stays `status='active'` (just filtered out by `quantity>0` in future queries); only `backend/expiry.py`'s loss/return flows actually flip `status` to `'disposed'`.

`complete_sale` re-fetches `sale_price` from the DB server-side and re-validates stock inside one transaction — client-supplied prices/quantities in the cart are never trusted, only used to decide *what* to attempt.

### Local barcode generation

`backend/products.py::generate_local_barcode` uses a single-row counter table (`counters`, name=`'local_barcode'`) incremented via `UPDATE ... RETURNING` (falls back to `UPDATE` + `SELECT` if the SQLite build lacks `RETURNING`, i.e. < 3.35). Format is `"9" + zero-padded 12 digits` (13 chars total), so generated barcodes can never collide with a real EAN/UPC barcode a scanner would read.

### Path resolution: two different "base directories"

There are two independent path-resolution concerns that must not be conflated:
- `backend/db.py::resolve_db_path` — the **writable** `data/store.db` location. In a frozen build this must be next to the `.exe` (`Path(sys.executable).parent`), *not* inside PyInstaller's bundle, because the bundle contents aren't guaranteed writable/persistent.
- `main.py`'s `ASSETS_DIR` / `frontend_path()` — the **read-only** `frontend/` static assets. In a frozen build these live inside the PyInstaller bundle at `sys._MEIPASS`, which is a *different* directory than `sys.executable`'s parent (PyInstaller 6.x onedir layout puts bundled data under `_internal/`, not directly beside the exe).

If you change how either is packaged/bundled, check both functions — they intentionally use different base paths and that's not a bug.

### Frontend structure

`frontend/index.html` is the only HTML document pywebview ever loads. It's a shell (sidebar + `#app` mount point) plus an inline login screen (`#login-screen`) — there is no separate `login.html` top-level document, specifically to avoid pywebview's `js_api` re-binding across a full page navigation. `frontend/js/router.js` is a hash router (`#/pos`, `#/products`, ...) that `fetch()`es an HTML fragment from `frontend/pages/*.html` into `#app` and then calls `init()`/`destroy()` on the matching module in `frontend/js/pages/*.js`. Each page module is an IIFE returning `{init, destroy}`; `destroy()` is responsible for tearing down anything page-specific (e.g. `ScannerFocus.unbind()`, a Chart.js instance).

`frontend/js/scanner-focus.js` keeps a barcode `<input>` focused for USB-HID scanner input without fighting the user: it refocuses on blur only if focus didn't deliberately move to another interactive element, and exposes `pause()`/`resume()` so `Modal.open()`/`Modal.close()` (in `toast.js`) can stop it from stealing focus out of modal form fields.

`frontend/js/format.js` (`formatMoney`, `formatNumber`, `formatDate`) is the only place money/number formatting should happen — always integer IQD, `en-US` grouping (renders left-to-right digit grouping correctly inside RTL text).

### Testing

`tests/conftest.py` provides a `conn` fixture: a fresh in-memory SQLite DB (`db.get_connection(":memory:")` + `db.init_db`) per test — no fixtures touch the real `data/store.db`. Business logic in `backend/*.py` takes a `conn` as its first argument specifically so it's testable without pywebview or the `JSApi`/session layer at all; `tests/test_roles.py` is the one place that exercises `JSApi` directly (to test the decorator behavior), constructing a bare `sqlite3.Connection` and calling `session.set_current_user(...)` manually rather than going through `auth.login`.

### Known, deliberate scope limits

Not gaps — see `README.md`'s "Known limitations" for the full list: no sale voiding, no user deactivation/deletion (would break `sales.cashier_id` FK), no customer-return UI (the schema and `backend/expiry.py::record_customer_return` support it but nothing calls it — it's there for a possible future page).

## Available imports

A Codex config (`~/.codex/config.toml`) and Gemini CLI settings (`~/.gemini/settings.json`) exist on this machine but haven't been imported into Claude Code. Run `/import` to see what's importable (MCP servers, slash commands, instructions), then `/import --yes=<digest>` to apply it.
