"""Machine-lock license check.

How to use:
  1. Run  tools/get_machine_id.py  on the customer's computer.
  2. Copy the printed fingerprint into ALLOWED_FINGERPRINT below.
  3. Build the .exe — it will only start on that specific machine.

While ALLOWED_FINGERPRINT is the placeholder value, the check is skipped
(development / testing mode).
"""

import hashlib
import subprocess
import sys
import uuid

# ── Paste the customer's fingerprint here before building the .exe ──────────
ALLOWED_FINGERPRINT = "REPLACE_WITH_CUSTOMER_FINGERPRINT"
# ────────────────────────────────────────────────────────────────────────────

_SECRET_SALT = "POS-LOCK-2026"


def _disk_serial() -> str:
    """Return the first non-empty disk serial via wmic (Windows only)."""
    try:
        out = subprocess.run(
            ["wmic", "diskdrive", "get", "SerialNumber", "/value"],
            capture_output=True, text=True, timeout=6,
        ).stdout
        for line in out.splitlines():
            if line.startswith("SerialNumber="):
                val = line.split("=", 1)[1].strip()
                if val:
                    return val
    except Exception:
        pass
    return "NODISK"


def _mac_address() -> str:
    """Return the primary MAC address as a hex string."""
    mac = uuid.getnode()
    return ":".join(f"{(mac >> (i * 8)) & 0xFF:02x}" for i in range(5, -1, -1))


def get_machine_fingerprint() -> str:
    """Stable fingerprint for this machine (SHA-256 of disk serial + MAC + salt)."""
    raw = f"{_disk_serial()}|{_mac_address()}|{_SECRET_SALT}"
    return hashlib.sha256(raw.encode()).hexdigest()


def check_license() -> None:
    """Abort the process if this machine is not the licensed machine.

    Call this as the very first thing in main().
    """
    # Dev / build mode — no fingerprint configured yet
    if ALLOWED_FINGERPRINT == "REPLACE_WITH_CUSTOMER_FINGERPRINT":
        return

    if get_machine_fingerprint() == ALLOWED_FINGERPRINT:
        return  # licensed — carry on

    # ── Not licensed: show a Kurdish error dialog and quit ──────────────────
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "نەرمەکار پارێزراوە",
            "ئەم نەرمەکارە تەنها لەسەر کۆمپیوتەری تایبەتی خۆی کار دەکات.\n\n"
            "تکایە پەیوەندی بە فرۆشیار بکە."
        )
        root.destroy()
    except Exception:
        pass  # tkinter might not be available in some frozen builds

    sys.exit(1)
