"""Run this script on the CUSTOMER'S computer to get their machine fingerprint.

   python tools/get_machine_id.py

Copy the printed fingerprint and paste it into:
   backend/license.py  →  ALLOWED_FINGERPRINT = "paste-here"

Then rebuild the .exe.
"""
import sys
import os

# Allow running from the project root or from tools/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.license import get_machine_fingerprint

fp = get_machine_fingerprint()
print("=" * 60)
print("  فینگەرپرینتی ئەم کۆمپیوتەرە:")
print()
print(f"  {fp}")
print("=" * 60)
print()
print("ئەم کۆدە کۆپی بکە و لە backend/license.py دابنێ.")
print()
input("پرێس Enter بکە دابخەیت...")
