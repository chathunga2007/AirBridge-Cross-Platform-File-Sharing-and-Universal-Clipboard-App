# -*- mode: python ; coding: utf-8 -*-
"""
AirBridge - PyInstaller Build Specification
Compiles AirBridge into a high-performance standalone Windows application
Created by Chathunga
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

BASE_DIR = Path.cwd()

# Data files to bundle: assets and mobile_ui
datas = [
    (str(BASE_DIR / 'assets'), 'assets'),
    (str(BASE_DIR / 'mobile_ui'), 'mobile_ui'),
]

# Collect any internal data from pillow_heif
try:
    datas += collect_data_files('pillow_heif')
except Exception:
    pass

# Hidden imports needed by dynamic ASGI / FastAPI / Uvicorn server & GUI hooks
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'fastapi',
    'fastapi.responses',
    'fastapi.middleware.cors',
    'fastapi.staticfiles',
    'starlette',
    'starlette.requests',
    'starlette.responses',
    'starlette.middleware',
    'websockets',
    'websockets.legacy',
    'websockets.legacy.server',
    'multipart',
    'python_multipart',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageOps',
    'pillow_heif',
    'pyperclip',
    'mss',
    'qrcode',
    'psutil',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'win32com',
    'win32com.client',
    'win32com.propsys',
    'win32com.propsys.propsys',
    'win32com.propsys.pscon',
]

a = Analysis(
    ['main.py'],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt5', 'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AirBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI application (no cmd terminal popup)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE_DIR / 'assets' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AirBridge',
)
