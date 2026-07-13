# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para empaquetar Menu + Alcampo como un unico .exe (Fase 8).

Construye:  .venv/Scripts/pyinstaller menu-app.spec
Resultado:  dist/MenuAlcampo.exe  (onefile, arranca el servidor y abre el navegador)

Incluye config.yaml y el catalogo data/menu.db como recursos (se siembran en
%LOCALAPPDATA%/MenuAlcampo la primera vez, ver menu_app/lanzador.py).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []

# Paquetes con carga dinamica de submodulos / ficheros de datos.
# OJO 'pulp': incluye el BINARIO del solver CBC (cbc.exe) en pulp/solverdir; sin
# collect_all no se empaqueta y "Generar menú" falla con PulpSolverError.
# 'webview' (ventana nativa) y 'playwright' (carrito con Chrome/Edge del sistema).
for paquete in ("uvicorn", "fastapi", "starlette", "recipe_scrapers", "fpdf",
                "email_validator", "pulp", "webview", "playwright"):
    try:
        d, b, h = collect_all(paquete)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# Protocolos/loops que uvicorn importa por nombre en tiempo de ejecucion.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += [
    "anyio", "h11", "click", "yaml", "rapidfuzz", "pulp", "bs4",
    "menu_app.web.app", "menu_app.escritorio",
    # pywebview en Windows usa el backend EdgeChromium via pythonnet (clr).
    "webview", "webview.platforms.winforms", "clr",
]
hiddenimports += collect_submodules("webview")

# Recursos: config base y catalogo (si existe en el arbol de construccion).
raiz = Path(".").resolve()
datas += [("config.yaml", ".")]
if (raiz / "data" / "menu.db").exists():
    datas += [("data/menu.db", "data")]

a = Analysis(
    ["src/menu_app/escritorio.py"],  # programa de escritorio (ventana nativa)
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Fuera dependencias grandes que la app WEB no usa (IA opcional, plotting).
    excludes=["matplotlib", "tkinter", "google", "google_genai", "anthropic", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Sazon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,  # SIN consola: Sazon es un programa con ventana propia (no terminal)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icono.ico",  # icono de marca (Sazon)
)
