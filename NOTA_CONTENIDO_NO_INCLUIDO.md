# Contenido del repositorio de trabajo que no se incluye en esta entrega

Esta carpeta lleva el código, las pruebas, los datos y la documentación de la práctica. El repositorio de trabajo tenía además lo que se detalla aquí, que se deja fuera para que la entrega pese poco y contenga solo lo evaluable. Los documentos de `docs/` citan algunos de estos elementos como historia; esta nota dice qué eran.

## 1. Entorno portátil de Windows (`entorno/`, ≈ 179 MB)

Un Python 3.7.5 de 64 bits embebido, con todo lo necesario para ejecutar la práctica con doble clic en `iniciar.bat`, sin instalar nada y sin permisos de administrador (el PC de la universidad no los da).

- El intérprete: `python.exe`, `pythonw.exe`, `python37.dll`, `python3.dll`, `python37.zip` (biblioteca estándar) y `python37._pth` (fija `Lib\site-packages` como única ruta de librerías y no mira el perfil del usuario).
- Los módulos compilados de la biblioteca estándar (`_socket.pyd`, `_ssl.pyd`, `_ctypes.pyd`, `_sqlite3.pyd`, `_decimal.pyd`, etc.), las DLL de OpenSSL (`libssl-1_1.dll`, `libcrypto-1_1.dll`) y de Visual C++ (`msvcp140.dll`, `vcruntime140.dll` y similares).
- `Lib\site-packages\`: `numpy` (47 MB), `scipy` (88 MB), `pybullet` (`pybullet.cp37-win_amd64.pyd`, 6 MB), `pybullet_planning`, `pkg_resources`, `typing_extensions.py` y `UR3e_rg2` (12 MB, el visualizador del enunciado en una copia adaptada a Python 3.7).

Para reconstruirlo hace falta Python 3.7.5 con esas librerías. Los obstáculos reales (la rueda de `pybullet` para Windows con Python 3.7 y la instalación de `UR3e_rg2` con `--no-deps`) están en `docs/depuración.md`, casos F1 y F3. La rueda de `UR3e_rg2` está en `recursos/`.

## 2. Kit de Linux (`linux/`, ≈ 255 MB)

Lo que usa `iniciar.sh` para montar un entorno en Linux sin internet ni `sudo` (decisión D28 en `docs/decisiones.md`):

| Archivo | Tamaño | Qué es |
|---|---|---|
| `cpython-3.11.17+20261013-x86_64-unknown-linux-gnu-install_only.tar.gz` | 49 MB | Python 3.11 independiente |
| `uv` | 44 MB | Binario del instalador `uv` |
| `wheels/pybullet-3.2.7-cp311-…-manylinux_2_17_x86_64.whl` | 98 MB | `pybullet` para Linux |
| `wheels/scipy-1.12.0-cp311-…-manylinux_2_17_x86_64.whl` | 37 MB | `scipy` |
| `wheels/numpy-1.26.4-cp311-…-manylinux_2_17_x86_64.whl` | 17 MB | `numpy` |
| `wheels/setuptools-80.10.2-py3-none-any.whl` | 1 MB | `setuptools` |
| `wheels/pybullet_planning-0.6.1-py2.py3-none-any.whl` | 0,1 MB | `pybullet_planning` |
| `wheels/typing_extensions-4.16.0-py3-none-any.whl` | < 0,1 MB | `typing_extensions` |

Sin esta carpeta, `iniciar.sh` usa el `uv` del sistema y descarga lo mismo de internet (`requirements-linux.txt` lista las dependencias).

## 3. Versiones de partida (`versiones/`, ≈ 100 KB)

Tres versiones anteriores de la práctica, archivadas como historia. De ellas salen los casos F1–F5 de `docs/depuración.md` y las decisiones D1–D5 de `docs/decisiones.md`.

| Versión | Contenido | Quién y cómo |
|---|---|---|
| `a_mano/` | `main.py` (1,5 KB) y una ficha de procedencia | El autor, sin IA, con el enunciado (2026-10-09). No imprime nada: lee la cabecera del subpaquete 0 pero no su cuerpo (F5) |
| `claude_1/` | 8 scripts (`ur_primary.py` con el hilo lector, `ejercicio1`–`ejercicio5`, `gemelo.py`, `simulador_ur.py`), un `README.md` y 6 documentos en `docs/` (contexto, arquitectura, pruebas, problemas, pendiente) | Claude Code, un solo prompt y sin el enunciado (2026-10-08). Probada con 2 URSim |
| `claude_2/` | `primaria.py`, `tiempo_real.py`, `varios_robots.py`, `ensenar_reproducir.py`, `robots.json` y `README.md` | Claude Code, con el enunciado (2026-10-09). Solo probada con robots falsos |

También se quita `pruebas/leer_claude2_robot_falso.py` (1 KB), que probaba `claude_2` y dependía de esa carpeta.

## 4. Documentos de trabajo retirados

| Documento | Tamaño | Qué era |
|---|---|---|
| `docs/memoria-borrador.md` | 10 KB | Borrador de la memoria, con marcadores sin resolver. La memoria de la práctica se entrega aparte |
| `docs/informe-desarrollo-claude-code.md` | 28 KB | Informe sobre el desarrollo de la práctica con Claude Code (línea de versiones, evolución del código y lecciones) |
| `docs/correo-profesor-borrador.md` | 26 líneas | Borrador de un correo al profesor. Ya se retiró del repositorio en el commit `03f2275` |

## 5. Otros

- El enunciado en PDF (una copia duplicada que había en la carpeta).
- Las cachés de Python (`__pycache__/`).
- La carpeta `.git` (ver abajo).

## 6. Control de versiones (git)

La práctica se desarrolló con git en un repositorio que abarca todas las asignaturas, rama `main`, un commit por cambio verificado y mensajes `p1: <qué cambia>`:

- **46 commits** tocan esta carpeta, del 2026-10-14 al 2026-10-22.
- **Etiquetas:** `p1-origen` (2026-10-14, estado inicial recibido) y `p1-defensa` (2026-10-20, tras la defensa con el UR3e).
- `docs/decisiones.md` y `docs/depuración.md` anotan en las decisiones (D1–D31) y en los fallos (F1–F31) el commit que las recoge (en los pocos casos hechos fuera del repositorio consta «—»), y `docs/pruebas.md` lleva la fecha de cada prueba, de modo que el historial se puede seguir desde esos documentos sin la carpeta `.git`.
