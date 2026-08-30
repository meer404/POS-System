# سیستەمی فرۆشتن (Local POS / Cashier System)

سیستەمێکی فرۆشتنی ناوخۆیی بۆ دووکان و بازاڕە بچووک و ناوەندییەکان، بە زمانی کوردی سۆرانی (RTL)، بەبێ پێویستی بە ئینتەرنێت.

A fully offline, local point-of-sale (cashier) system for small/medium markets, with a Kurdish Sorani (RTL) UI. Currency is Iraqi Dinar (IQD), always whole integers.

---

## پێویستییەکان / Prerequisites

- Windows 10/11
- Python 3.11+ (تاقیکراوەتەوە لەسەر Python 3.14 / tested on Python 3.14)
- WebView2 Runtime (لە زۆربەی سیستەمەکانی Windows 11 پێشوەخت دامەزراوە / preinstalled on most Windows 11 machines; if missing, install the free [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/))

## دامەزراندن / Installation

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

بۆ گەشەپێدان (تاقیکردنەوە و پاکەجکردن) / For development (tests + packaging):

```
venv\Scripts\pip install -r requirements-dev.txt
```

## ڕاکردن / Running

```
venv\Scripts\python main.py
```

بۆ زیادکردنی داتای نموونەیی (کاڵا، فرۆشتن، بەکارهێنەری فرۆشیار) لە یەکەم جار:
To load demo/sample data (products, sales, a cashier user) on first run:

```
venv\Scripts\python main.py --seed
```

بۆ کردنەوەی دیڤتووڵزی وێبکراوم (بۆ گەشەپێدان):
For opening browser devtools during development:

```
venv\Scripts\python main.py --debug
```

## هەژماری بنەڕەتی بەڕێوەبەر / Default admin account

- **ناوی بەکارهێنەر / Username:** `admin`
- **وشەی نهێنی / Password:** `admin123`

یەکەم جار کە بچیتە ژوورەوە، سیستەمەکە داوات لێدەکات وشەی نهێنی بگۆڕیت.
On first login, you will be required to change this password.

If you seed demo data, an additional cashier account is created: username `cashier`, password `cashier123`.

## تاقیکردنەوەکان / Running tests

```
venv\Scripts\python -m pytest tests/ -v
```

Covers: FIFO/nearest-expiry stock consumption, local barcode generation, report aggregation math, role-based access enforcement, and database backup/restore.

## باکاپ و گەڕاندنەوە / Backup & restore

بەڕێوەبەر لە پەڕەی **باکاپ** دەتوانێت وێنەیەکی تەواوی داتابەیس دروست بکات. هەموو
باکاپێک بە شێوەی خۆکار لە `data\backups\` (تەنیشت فایلی `.exe`) پاشەکەوت دەکرێت،
هەروەها دەکرێت وێنەیەک بۆ فلاش یان دیسکی دەرەکی هەڵبژێردرێت. گەڕاندنەوە داوای
وشەی نهێنی بەڕێوەبەر دەکات، پێش گۆڕین وێنەیەک لە داتای ئێستا (`pre-restore-*.db`)
پاشەکەوت دەکات، و دواتر داوا دەکات دووبارە بچیتەوە ژوورەوە.

The admin-only **Backup** page snapshots the whole database via SQLite's online
backup API (WAL-safe). Every backup is auto-kept in `data\backups\` next to the
`.exe`; a native Save dialog can also drop a copy on a USB/external drive.
Restore requires the admin's password, writes a `pre-restore-*.db` safety copy of
the current data first, then swaps the file in and forces a re-login.

## پاکەجکردن بۆ .exe / Packaging to .exe

```
venv\Scripts\pyinstaller build.spec
```

دەرئەنجامەکە لە `dist\POS-System\` دەبێت — هەموو فۆڵدەرەکە پێویستە بگوازرێتەوە پێکەوە (onedir build, not onefile).
Output lands in `dist\POS-System\` — copy the **whole folder**, not just the .exe (this is a onedir build so the writable `data\store.db` lives alongside it and survives relaunches/updates).

## سنووردارییە زانراوەکان / Known limitations

- No sale voiding/cancellation.
- No user deactivation/deletion (only role changes and password resets), to avoid breaking historical sales' foreign-key references.

## پێکهاتەی پڕۆژە / Project structure

```
backend/    Python business logic + SQLite (db.py, products.py, sales.py, reports.py, expiry.py, users.py, auth.py, api.py)
frontend/   HTML/CSS/JS UI (RTL, Kurdish), loaded into a pywebview desktop window
tests/      pytest unit tests for the backend
main.py     Entry point
```
