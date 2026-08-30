"""JSApi: the single object exposed to the frontend via pywebview's js_api.

Every method returns a consistent envelope: {"ok": True, "data": ...} or
{"ok": False, "error": CODE, "message": "..."}. Every method except `login`
is wrapped in `require_role`, which is the sole server-side enforcement
point for admin/cashier permissions -- the frontend's sidebar filtering is
UX only and must never be trusted for security.
"""
import sqlite3

from backend import auth, backup, expiry, products, reports, session, users
from backend.sales import InsufficientStockError
from backend.sales import complete_sale as _complete_sale
from backend.sales import get_cart_item_snapshot as _get_cart_item_snapshot
from backend.sales import get_receipt as _get_receipt
from backend.session import require_role
from backend.utils import date_range_for_preset


def _ok(data=None):
    return {"ok": True, "data": data}


def _err(code: str, message: str = ""):
    return {"ok": False, "error": code, "message": message or code}


class JSApi:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        # Underscore-prefixed so pywebview's js_api introspection ignores it
        # (a public attr here makes pywebview try to serialize the whole
        # native window object and blow the recursion limit).
        self._window = None  # set from main.py; used for native file dialogs

    # ---------------- Auth ----------------

    def login(self, username: str, password: str) -> dict:
        return auth.login(self.conn, username, password)

    def logout(self) -> dict:
        return auth.logout()

    def get_current_user(self) -> dict:
        return _ok(session.get_current_user())

    def change_password(self, old_password: str, new_password: str) -> dict:
        user = session.get_current_user()
        if user is None:
            return _err("NOT_AUTHENTICATED")
        try:
            return auth.change_password(self.conn, user["id"], old_password, new_password)
        except ValueError as e:
            return _err("VALIDATION_ERROR", str(e))

    def force_change_password(self, new_password: str) -> dict:
        user = session.get_current_user()
        if user is None:
            return _err("NOT_AUTHENTICATED")
        try:
            return auth.force_change_password(self.conn, user["id"], new_password)
        except ValueError as e:
            return _err("VALIDATION_ERROR", str(e))

    # ---------------- Products ----------------

    @require_role("admin", "cashier")
    def find_product_by_barcode(self, barcode: str) -> dict:
        return _ok(products.find_product_by_barcode(self.conn, barcode))

    @require_role("admin", "cashier")
    def search_products(self, query: str) -> dict:
        return _ok(products.search_products(self.conn, query))

    @require_role("admin", "cashier")
    def list_products(self) -> dict:
        return _ok(products.list_products(self.conn))

    @require_role("admin", "cashier")
    def generate_barcode(self) -> dict:
        return _ok(products.generate_local_barcode(self.conn))

    @require_role("admin", "cashier")
    def create_product(self, payload: dict) -> dict:
        try:
            result = products.create_product(
                self.conn,
                name=payload.get("name"),
                barcode=payload.get("barcode"),
                category=payload.get("category"),
                sale_price=int(payload.get("sale_price", 0)),
                unit=payload.get("unit"),
                min_stock=int(payload.get("min_stock", 0)),
                purchase_price=int(payload.get("purchase_price", 0)),
                quantity=int(payload.get("quantity", 0)),
                expiry_date=payload.get("expiry_date") or None,
            )
            return _ok(result)
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    @require_role("admin", "cashier")
    def add_stock_batch(self, product_id: int, purchase_price: int, quantity: int, expiry_date: str | None) -> dict:
        try:
            result = products.add_stock_batch(
                self.conn,
                product_id=int(product_id),
                purchase_price=int(purchase_price),
                quantity=int(quantity),
                expiry_date=expiry_date or None,
            )
            return _ok(result)
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    @require_role("admin", "cashier")
    def get_product_detail(self, product_id: int) -> dict:
        result = products.get_product_with_batches(self.conn, int(product_id))
        if result is None:
            return _err("NOT_FOUND", "کاڵاکە نەدۆزرایەوە")
        return _ok(result)

    @require_role("admin", "cashier")
    def update_product(self, product_id: int, payload: dict) -> dict:
        user = session.get_current_user()
        payload = dict(payload)
        if "sale_price" in payload and user["role"] != "admin":
            return _err("FORBIDDEN", "تەنها بەڕێوەبەر دەتوانێت نرخی فرۆشتن بگۆڕێت")
        try:
            result = products.update_product(
                self.conn,
                int(product_id),
                name=payload.get("name"),
                barcode=payload.get("barcode"),
                category=payload.get("category"),
                sale_price=int(payload["sale_price"]) if "sale_price" in payload else None,
                unit=payload.get("unit"),
                min_stock=int(payload["min_stock"]) if "min_stock" in payload else None,
            )
            return _ok(result)
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    # ---------------- Sales ----------------

    @require_role("admin", "cashier")
    def get_cart_item_snapshot(self, product_id: int) -> dict:
        result = _get_cart_item_snapshot(self.conn, int(product_id))
        if result is None:
            return _err("NOT_FOUND")
        return _ok(result)

    @require_role("admin", "cashier")
    def complete_sale(self, items: list, discount_mode: str, discount_value: int) -> dict:
        user = session.get_current_user()
        try:
            receipt = _complete_sale(
                self.conn,
                cashier_id=user["id"],
                items=items,
                discount_mode=discount_mode,
                discount_value=int(discount_value),
            )
            return _ok(receipt)
        except InsufficientStockError as e:
            return _err(
                "INSUFFICIENT_STOCK",
                f"بڕی پێویست بۆ '{e.product_name}' لە کۆگا نییە (بەردەست: {e.available}, داواکراو: {e.requested})",
            )
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    @require_role("admin", "cashier")
    def get_receipt(self, sale_id: int) -> dict:
        result = _get_receipt(self.conn, int(sale_id))
        if result is None:
            return _err("NOT_FOUND")
        return _ok(result)

    # ---------------- Reports (admin only) ----------------

    @require_role("admin")
    def get_report_summary(self, start_date: str = None, end_date: str = None, preset: str = None) -> dict:
        if preset:
            start_date, end_date = date_range_for_preset(preset)
        if not start_date or not end_date:
            return _err("VALIDATION_ERROR", "بەرواری دەستپێک و کۆتایی پێویستە")
        return _ok(reports.get_summary(self.conn, start_date, end_date))

    @require_role("admin")
    def get_daily_chart(self, days: int = 7) -> dict:
        return _ok(reports.daily_sales_last_n_days(self.conn, int(days)))

    # ---------------- Expiry (admin only) ----------------

    @require_role("admin")
    def list_expired_batches(self) -> dict:
        return _ok(expiry.list_expired(self.conn))

    @require_role("admin")
    def list_near_expiry_batches(self, days: int = 7) -> dict:
        return _ok(expiry.list_near_expiry(self.conn, int(days)))

    @require_role("admin")
    def mark_batch_as_loss(self, batch_id: int, quantity: int) -> dict:
        try:
            return _ok(expiry.mark_as_loss(self.conn, int(batch_id), int(quantity)))
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    @require_role("admin")
    def return_batch_to_supplier(self, batch_id: int, quantity: int) -> dict:
        try:
            return _ok(expiry.return_to_supplier(self.conn, int(batch_id), int(quantity)))
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    # ---------------- Customer returns ----------------

    @require_role("admin", "cashier")
    def create_customer_return(self, items: list) -> dict:
        try:
            return _ok(expiry.create_customer_return(self.conn, items))
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    # ---------------- Users (admin only) ----------------

    @require_role("admin")
    def list_users(self) -> dict:
        return _ok(users.list_users(self.conn))

    @require_role("admin")
    def create_user(self, username: str, password: str, role: str) -> dict:
        try:
            return _ok(users.create_user(self.conn, username, password, role))
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    @require_role("admin")
    def set_user_role(self, user_id: int, role: str) -> dict:
        try:
            return _ok(users.set_user_role(self.conn, int(user_id), role))
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    @require_role("admin")
    def reset_user_password(self, user_id: int, new_password: str) -> dict:
        try:
            return _ok(users.reset_user_password(self.conn, int(user_id), new_password))
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    @require_role("admin")
    def delete_user(self, user_id: int) -> dict:
        current = session.get_current_user()
        if current is not None and current["id"] == int(user_id):
            return _err("VALIDATION_ERROR", "ناتوانیت هەژماری خۆت بسڕیتەوە")
        try:
            return _ok(users.delete_user(self.conn, int(user_id)))
        except (ValueError, TypeError) as e:
            return _err("VALIDATION_ERROR", str(e))

    # ---------------- Backup / restore (admin only) ----------------

    @require_role("admin")
    def list_backups(self) -> dict:
        return _ok(backup.list_backups())

    @require_role("admin")
    def create_backup(self) -> dict:
        export_path = None
        if self._window is not None:
            import webview

            res = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=backup.suggested_filename(),
                file_types=("Backup fayl (*.db)",),
            )
            if res:
                export_path = res if isinstance(res, str) else res[0]
        try:
            return _ok(backup.create_backup(self.conn, export_path))
        except OSError as e:
            return _err("BACKUP_FAILED", str(e))

    @require_role("admin")
    def restore_backup(self, admin_password: str, archive_name: str | None = None) -> dict:
        user = session.get_current_user()
        row = self.conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        if row is None or not auth.verify_password(admin_password, row["password_hash"]):
            return _err("INVALID_CREDENTIALS", "وشەی نهێنی هەڵەیە")

        if archive_name:
            from pathlib import Path

            if archive_name != Path(archive_name).name:
                return _err("VALIDATION_ERROR", "ناوی فایل نادروستە")
            source = str(backup.backups_dir() / archive_name)
        elif self._window is not None:
            import webview

            res = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Backup fayl (*.db)",),
            )
            if not res:
                source = None
            else:
                source = res if isinstance(res, str) else res[0]
        else:
            source = None
        if not source:
            return _err("CANCELLED", "هیچ فایلێک هەڵنەبژێردرا")

        try:
            new_conn = backup.restore_backup(self.conn, source)
        except ValueError as e:
            return _err("INVALID_BACKUP", str(e))
        except OSError as e:
            return _err("RESTORE_FAILED", str(e))
        self.conn = new_conn
        session.clear_current_user()  # force re-login; users table changed
        return _ok({"restored": True})

    # ---------------- Misc ----------------

    @require_role("admin", "cashier")
    def open_external_url(self, url: str) -> dict:
        """Hand a whitelisted URL to the OS default browser (used by the
        footer credit link). The app itself makes no network call."""
        from urllib.parse import urlparse

        parsed = urlparse(url or "")
        host = parsed.hostname or ""
        if parsed.scheme != "https" or (host != "mir.codes" and not host.endswith(".mir.codes")):
            return _err("VALIDATION_ERROR", "بەستەرەکە ڕێگەپێدراو نییە")

        import webbrowser

        webbrowser.open(url)
        return _ok()
