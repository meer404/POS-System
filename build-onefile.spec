# -*- mode: python ; coding: utf-8 -*-
# Onefile build: produces a single POS-System.exe.
# Startup is slower (~5-15 s) because PyInstaller extracts assets to a
# temp folder on every launch.  The writable data/store.db is still created
# next to the .exe (backend/db.py uses sys.executable parent), so the
# database persists across runs correctly.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('frontend', 'frontend')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='POS-System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)
