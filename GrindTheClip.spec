# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static'), ('cloudflared.exe', '.')],
    hiddenimports=['engineio.async_drivers.threading', 'flask_socketio', 'socketio', 'engineio', 'bidict', 'simple_websocket', 'wsproto', 'gevent', 'geventwebsocket'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'torch', 'transformers', 'tensorflow'],
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
    name='GrindTheClip',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
