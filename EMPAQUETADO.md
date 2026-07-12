# Empaquetado a .exe (Fase 8)

La aplicación es un servidor web local (FastAPI) que se abre en el navegador. Se
empaqueta a un **único ejecutable Windows** con PyInstaller, y opcionalmente se
envuelve en un **instalador** con Inno Setup.

## 1. Construir el ejecutable

```powershell
# desde la carpeta menu-app, con el entorno virtual
.venv\Scripts\pyinstaller --clean --noconfirm menu-app.spec
```

Resultado: **`dist\MenuAlcampo.exe`** (onefile, ~57 MB porque incluye el catálogo
`data/menu.db`). Al ejecutarlo:

1. Siembra `config.yaml` y `data/menu.db` en `%LOCALAPPDATA%\MenuAlcampo` la primera
   vez (carpeta escribible; el .exe es de solo lectura).
2. Arranca el servidor en el primer puerto libre (8137/8138/8139) y **abre el
   navegador** automáticamente.
3. Todo lo que el usuario genera (planes, `config.usuario.yaml`, catálogo
   actualizado, caché) se guarda en esa carpeta de datos, no dentro del .exe.

Cerrar la ventana de consola cierra la app.

### Qué incluye el `.spec`
- `collect_all` de uvicorn, fastapi, starlette, recipe_scrapers, fpdf (submódulos y
  datos que cargan dinámicamente).
- `config.yaml` y `data/menu.db` como recursos.
- **Excluye** matplotlib, tkinter, y los SDK de IA (google-genai, anthropic) porque
  la interfaz web no los usa → ejecutable más pequeño.

## 2. Crear el instalador (opcional)

Requiere [Inno Setup 6](https://jrsoftware.org/isinfo.php). Tras construir el .exe:

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Resultado: **`dist\MenuAlcampo-Setup.exe`**. Instala sin permisos de administrador
(en la carpeta del usuario), crea accesos directos en el menú Inicio y —opcional—
en el escritorio. Los datos del usuario en `%LOCALAPPDATA%\MenuAlcampo` se conservan
al desinstalar (configurable en `installer.iss`).

## Publicar una versión nueva (actualizaciones, Fase 11)

La distribución va por **GitHub Releases**. Con `.github/workflows/release.yml`, al
hacer *push* de un tag `vX.Y.Z` se construye el `.exe` + el instalador en un runner
Windows y se adjuntan a la Release automáticamente:

```powershell
# 1) sube la version en src/menu_app/version.py (p.ej. 0.2.0)
git tag v0.2.0
git push origin v0.2.0
```

La app comprueba `api.github.com/repos/<repo>/releases/latest` al arrancar (y desde
**Configuración → Buscar actualizaciones**) y muestra un **banner** con la descarga si
hay una versión nueva. Rellena el repo público de binarios en Configuración o en
`config.yaml` (`actualizaciones.repo: usuario/sazon-releases`). No instala nada solo:
enlaza la descarga.

## Notas
- El catálogo empaquetado es una foto del momento de construir. El usuario puede
  refrescar precios/ofertas/productos desde la pestaña **Catálogo** de la app.
- Para una app sin catálogo embebido (más ligera, ~40 MB), quita la línea de
  `data/menu.db` del `.spec`; en el primer arranque el usuario tendrá que pulsar
  "Descargar catálogo".
- Primer arranque de un .exe onefile es algo lento (descomprime a un temporal);
  los siguientes son más rápidos.
