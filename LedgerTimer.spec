# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for LedgerTimer.

Build:  python -m PyInstaller LedgerTimer.spec --noconfirm
Output: dist/LedgerTimer.exe — single file, no console window.

Do not run a raw `pyinstaller --onefile ...`; it regenerates this file and
loses the icon and data-file settings.

On macOS, change the `icon=` line below to 'ledgertimer/app_icon.icns'.
On Linux the `icon=` setting is silently ignored — that is expected.
"""

from PyInstaller.utils.hooks import collect_data_files

# CustomTkinter ships its themes and assets as data files.
datas = collect_data_files("customtkinter")

# gui.py looks for the window/taskbar icon at <bundle>/ledgertimer/app_icon.ico
datas += [("ledgertimer/app_icon.ico", "ledgertimer")]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
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
    name="LedgerTimer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="ledgertimer/app_icon.ico",
)
