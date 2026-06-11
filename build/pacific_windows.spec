# -*- mode: python ; coding: utf-8 -*-
"""
PACIFIC CLI — PyInstaller spec for Windows Store (MSIX) build.

This spec includes the WinRT Store billing modules so the built exe
can call Windows.Services.Store APIs when running as an MSIX package.

Usage:
    pyinstaller build/pacific_windows.spec --distpath dist/ --clean --noconfirm

Output:
    dist/pacific.exe
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Hidden imports ───────────────────────────────────────────────────

# All pacific submodules
hidden_imports = collect_submodules('pacific')

# Data & networking packages
hidden_imports += collect_submodules('yfinance')
hidden_imports += collect_submodules('rich')
hidden_imports += collect_submodules('mplfinance')

# WinRT — Microsoft Store billing (Windows only)
try:
    hidden_imports += collect_submodules('winrt')
    hidden_imports += [
        'winrt.windows.services.store',
        'winrt.windows.applicationmodel',
        'winrt.windows.foundation',
    ]
except Exception:
    pass  # Not on Windows — skip

hidden_imports += [
    # --- CLI framework ---
    'click',
    # --- HTTP / networking ---
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    # --- yfinance dependencies ---
    'multitasking',
    'platformdirs',
    'peewee',
    'beautifulsoup4',
    'bs4',
    'bs4.builder',
    'bs4.builder._htmlparser',
    'curl_cffi',
    'curl_cffi.requests',
    'protobuf',
    'google.protobuf',
    'google.protobuf.descriptor',
    'google.protobuf.message',
    'google.protobuf.reflection',
    'google.protobuf.symbol_database',
    'websockets',
    'frozendict',
    'pytz',
    'html5lib',
    'lxml',
    'soupsieve',
    # --- Data / numerics ---
    'pandas',
    'pandas.io.formats.style',
    'numpy',
    'dateutil',
    'six',
    # --- Charting ---
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends',
    'matplotlib.backends.backend_agg',
    'openpyxl',
    # --- PDF ---
    'fpdf',
    # --- JSON ---
    'json',
    # --- Windows-specific ---
    'ctypes',
    'asyncio',
]

# ── Data files ───────────────────────────────────────────────────────

datas = collect_data_files('certifi')
try:
    datas += collect_data_files('curl_cffi', include_py_files=True)
except Exception:
    pass

# ── Analysis ─────────────────────────────────────────────────────────

# Check for obfuscated staging directory (build pipeline uses this)
_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_staging = os.path.join(_spec_dir, 'obfuscated_staging')
if os.path.isdir(_staging):
    _entry = os.path.join(_staging, 'pacific_app.py')
    _pathex = [_staging, _spec_dir]
    print(f"[SPEC] Using OBFUSCATED source from {_staging}")
else:
    _entry = os.path.join(_spec_dir, '..', 'pacific_app.py')
    _pathex = [_spec_dir]
    print(f"[SPEC] Using plain source (no obfuscated_staging found)")

a = Analysis(
    [_entry],
    pathex=_pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'xmlrpc',
        'doctest',
        'torch',
        'tensorflow',
        'sklearn',
        'scipy',
        'sympy',
        'IPython',
        'jupyter',
        'notebook',
        'PIL.ImageTk',
        'cv2',
        'transformers',
        'torchaudio',
        'torchvision',
        'nltk',
        'spacy',
        'boto3',
        'botocore',
        'google.cloud',
        'google.auth',
        'google.api_core',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pacific',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,           # No argv emulation on Windows
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\pacific.ico' if os.path.exists('assets\\pacific.ico') else None,
    version_info=None,
)
