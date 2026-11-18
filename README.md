# Práctica 1 – Visualizador de un UR3e por TCP/IP

Lee el estado de un UR3e (real o URSim) por sockets TCP (`socket`, `struct`, hilos) y lo reproduce en el visualizador PyBullet `UR3e_rg2`. Python 3.7.5.

**Nivel al que se opta: sobresaliente** (incluye aprobado y notable).

## Qué hay

| Script (`src/`) | Qué hace |
|---|---|
| `primaria.py` | Visualiza 1 o varios robots por la interfaz primaria (puerto 30001) |
| `tiempo_real.py` | Lo mismo por la interfaz de tiempo real (puerto 30003) |
| `ensenar.py` | Enseñar puntos, previsualizar, ejecutar con `movej` y supervisar; por consola |
| `copiar.py` | Como `ensenar.py`, pero graba los puntos en un robot (solo lectura) y los ejecuta en otro |

Las clases están en `src/librerias/` (`red`, `ur`, `simulador`, `secuencia`). Los datos, en `datos/`; las pruebas, en `pruebas/`.

## Configurar las IP

Los robots están **solo en `datos/robots.json`** (nombre e IP); no hay que tocar el código. Ahora lleva las IP del laboratorio (`robot1` = `10.172.21.205`, `robot2` = `10.172.21.206`); para URSim en el aula, las de las máquinas virtuales (`10.172.18.x`). `ensenar.py` usa el primero; en `copiar.py`, el primero es el ejecutor y el segundo el grabador.

## Cómo ejecutar

Requisitos: Python 3.7, `pybullet` y `UR3e_rg2` (la rueda está en `recursos/`; los problemas de instalación con Python 3.7 están en [docs/depuración.md](docs/depuración.md), F1 y F3). El Python portátil que usaba el repositorio de trabajo no se incluye (ver [NOTA_CONTENIDO_NO_INCLUIDO.md](NOTA_CONTENIDO_NO_INCLUIDO.md)).

Desde esta carpeta, en PowerShell (los scripts no llevan argumentos; se paran con Ctrl+C):

```powershell
python -u src\primaria.py       # pregunta cuántos robots (Intro = 1)
python -u src\tiempo_real.py    # igual
python -u src\ensenar.py        # ¡ENVÍA movej al robot!
python -u src\copiar.py         # ¡ENVÍA movej al ejecutor!  (o: copiar.py grabador ejecutor)
```

`iniciar.bat` (Windows) e `iniciar.sh` (Linux, `bash iniciar.sh`) ofrecen un menú con lo mismo y piden confirmación antes de enviar `movej`; usan el Python de `entorno\` o `entorno-linux\` si existe y, si no, el del sistema (en Linux hace falta `uv` e internet; dependencias en `requirements-linux.txt`).

Comandos de `ensenar.py`: `g` guardar punto, `v` previsualizar (solo mueve el robot de la ventana), `e` ejecutar, `c` cancelar, `r` reanudar, `s`/`l [nombre]` guardar/cargar en `datos/secuencias/`, `b` borrar, `ajustar <v rad/s> <a rad/s²>`, `q` salir.

**Robot real:** `movej` no envía más de 0,3 rad/s ni 0,5 rad/s² (por defecto 0,1 y 0,2). El robot debe estar encendido, con los frenos liberados y en control remoto *antes* de arrancar el programa; si no, rechaza la orden (error C210), el programa lo explica y se continúa con `r`.

## Pruebas

No necesitan robot ni URSim (robots falsos en `127.0.0.1`):

```powershell
python -B -m unittest discover -s pruebas -v
python -u pruebas\humo_pybullet.py              # simulador con la librería real
python -u pruebas\humo_extremo_a_extremo.py     # los tres scripts con ventana real
```

## Documentación

Los cuatro documentos de `docs/` son el registro de trabajo de la práctica y **están pensados para consumo de IA**: se mantuvieron para que un asistente de IA pudiera retomar el proyecto entre sesiones, por eso están redactados en tercera persona («el autor» es el autor de la práctica) y con detalle de proceso. No sustituyen a la memoria.

- [docs/arquitectura.md](docs/arquitectura.md): capas, hilos y flujo de datos.
- [docs/decisiones.md](docs/decisiones.md): decisiones de diseño y alternativas.
- [docs/depuración.md](docs/depuración.md): fallos reales y cómo se resolvieron.
- [docs/pruebas.md](docs/pruebas.md): qué se probó, con qué comando y con qué resultado (✅ ejecutado, ⚠️ con salvedad, ❌ no probado).
- [NOTA_CONTENIDO_NO_INCLUIDO.md](NOTA_CONTENIDO_NO_INCLUIDO.md): lo que tenía el repositorio de trabajo y no se incluye, y el resumen de cómo se usó git.

La memoria de la práctica se entrega aparte.
