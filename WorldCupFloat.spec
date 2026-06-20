# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files


project_dir = Path(SPECPATH)


a = Analysis(
    ["worldcup_float.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        ("localization_zh.json", "."),
        ("assets/app_icons", "assets/app_icons"),
        *collect_data_files("opencc"),
    ],
    hiddenimports=[
        "pyttsx3.drivers",
        "pyttsx3.drivers.sapi5",
        "winrt.windows.foundation",
        "winrt.windows.foundation.collections",
        "winrt.windows.media.core",
        "winrt.windows.media.playback",
        "winrt.windows.media.speechsynthesis",
        "winrt.windows.storage.streams",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WorldCupFloat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=str(project_dir / "assets" / "worldcup_float.ico"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
