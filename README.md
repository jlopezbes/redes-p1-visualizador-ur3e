# Práctica 1 – Visualizador de un UR3e por TCP/IP

Lee el estado de un UR3e (real o URSim) por sockets TCP y lo reproduce en el visualizador PyBullet `UR3e_rg2`.

## 1. Enunciado

Fuente: [fuentes/enunciados/Práctica guiada visualizador de un UR3e por TCP IP.pdf](../../fuentes/enunciados/Pr%C3%A1ctica%20guiada%20visualizador%20de%20un%20UR3e%20por%20TCP%20IP.pdf). Manuales: [fuentes/manuales/](../../fuentes/manuales/). Librería del visualizador: [fuentes/librerias/](../../fuentes/librerias/).

> ⚠️ **Resumen de segunda mano.** No se ha podido leer el PDF en este PC (falta `pdftoppm`). Lo de abajo sale del README de la versión Claude 2 (que sí tenía el enunciado) y de `docs/desde-pi/comparacion-versiones-p1.md`. Hay que contrastarlo con el PDF (consulta abierta en [docs/para-pi.md](../../docs/para-pi.md)).

Niveles según Claude 2:

- **Aprobado:** un robot por la interfaz primaria (puerto 30001) y otro por la de tiempo real (30003), reproducidos en PyBullet.
- **Notable:** varios robots en la misma ventana, un hilo por robot.
- **Sobresaliente:** enseñar puntos, previsualizarlos, ejecutarlos con `movej` y supervisar errores del robot.

Entrega y fecha: no constan.

## 2. Requisitos y estado

| Requisito | Archivo | Estado |
|---|---|---|
| Un robot por interfaz primaria (30001) → PyBullet | `src/main.py primaria` → `tareas.visualizar` con `ClienteUR` | ⚠️ robot falso, no URSim |
| Un robot por interfaz de tiempo real (30003) → PyBullet | `src/main.py tiempo-real` → `tareas.visualizar` con `ClienteUR(tiempo_real=True)` | ⚠️ robot falso, no URSim |
| Varios robots en la misma ventana (un hilo por robot) | `src/main.py varios` → `tareas.visualizar` + `src/robots.json` (nombre e IP) | ⚠️ 2 robots falsos, no URSim |
| Enseñar, previsualizar y reproducir con `movej`; supervisar errores | `src/main.py ensenar` → `tareas.ensenar_reproducir` + `src/secuencia.py` | ⚠️ robot falso, no URSim |

⚠️ = probado con pruebas automáticas y con `main.py` entero contra un robot falso (ventana real de PyBullet); ❌ contra URSim o un UR3e. Detalle en [docs/pruebas.md](docs/pruebas.md).

## 3. Cómo ejecutar

Entorno (Python 3.7.5, URSim, puertos): [docs/entorno.md](../../docs/entorno.md). Desde la raíz del repo, en PowerShell 5.1:

```powershell
python -u 2_practicas\Practica1_visualizador_UR3e\src\main.py primaria                   # URSim 1 por NAT: 127.0.0.1:30001
python -u 2_practicas\Practica1_visualizador_UR3e\src\main.py primaria --ip 10.172.21.203  # un robot del laboratorio
python -u 2_practicas\Practica1_visualizador_UR3e\src\main.py tiempo-real                # 127.0.0.1:30003
python -u 2_practicas\Practica1_visualizador_UR3e\src\main.py varios                     # robots de src\robots.json
python -u 2_practicas\Practica1_visualizador_UR3e\src\main.py ensenar --v 0.1 --a 0.2    # ¡ENVIA movej al robot!
```

Parar con Ctrl+C. `ensenar` pide comandos en la consola: `g` guardar punto, `v` previsualizar, `e` ejecutar, `c` cancelar, `r` reanudar, `s`/`l [fichero]` guardar/cargar, `b` borrar, `q` salir. **Antes de `e`:** el robot encendido con frenos liberados (`robotMode = 7`) y, en URSim/PolyScope 5, *Ajustes → Sistema → Control remoto* en **Remoto**; velocidades bajas y zona despejada en un robot real. `movej` se niega a enviar más de 0,3 rad/s o 0,5 rad/s².

**Pruebas** (no necesitan robot ni URSim):

```powershell
python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas -v          # 122 pruebas, ≈ 32 s
python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_pybullet.py                   # Simulador con la librería real (ventana ≈ 2 s)
python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_extremo_a_extremo.py          # main.py entero con ventana real
```

Para probar las versiones archivadas sin robot, con el robot falso de Claude 1 (solo lectura; **no lanzarlo con URSim abierto**: comparten puertos):

```powershell
# terminal 1: robot falso en el puerto 31001
python -B -u 2_practicas\Practica1_visualizador_UR3e\versiones\claude_1\simulador_ur.py 31001

# terminal 2: Claude 1 (parar con Ctrl+C) o Claude 2 (se para solo a los 3 estados)
python -B -u 2_practicas\Practica1_visualizador_UR3e\versiones\claude_1\ejercicio1_leer_un_robot.py --robot 127.0.0.1:31001
python -B -u 2_practicas\Practica1_visualizador_UR3e\pruebas\leer_claude2_robot_falso.py
```

## 4. Versiones de partida

Se conservan tal cual como historia, sin editar (salvo los duplicados quitados, ver cada `ORIGEN.md`).

| Carpeta | Qué es | Enunciado |
|---|---|---|
| `versiones/a_mano/` | Hecha a mano por Josu (`main.py`). Contra el robot falso no imprime nada: no lee el cuerpo del subpaquete 0 (la Pi, 2026-10-13). | sí |
| `versiones/claude_1/` | Claude, un prompt, 5 ejercicios, hilo lector y robot falso. Probada con URSim el 2026-10-08. | no |
| `versiones/claude_2/` | Claude, con enunciado: buffer validado, varios robots, enseñar y reproducir. Solo probada con robot falso. | sí |

Comparación: [docs/desde-pi/comparacion-versiones-p1.md](../../docs/desde-pi/comparacion-versiones-p1.md).

## 5. Estado y siguiente paso

**Fase 1 hecha (2026-10-14):** código escrito por la IA a partir de `claude_2`, en módulos, y probado de extremo a extremo contra un robot falso.

**Revisión de robustez hecha (2026-10-14, cuatro capas):** excepciones propias, parada si el robot falla, códigos de salida 0/1/2. Casos F7–F21 en [depuración](docs/depuración.md). El código creció a 1176 líneas y Josu lo veía excesivo.

**Limpieza por capas hecha (2026-10-15/16, D17–D21):** `src/` baja a 817 líneas (−31 %). Una sola clase `ClienteUR` para la primaria y la de tiempo real, que entrega los mensajes ya decodificados; una sola excepción de comunicación (`ErrorRed`); una sola función `visualizar`; sin «estado fresco»; robots colocados en fila por el simulador y `robots.json` solo con nombre e IP. Ver [arquitectura](docs/arquitectura.md) (módulos, flujo, errores, constantes). 122 pruebas, `humo_pybullet.py` y `humo_extremo_a_extremo.py` en verde con la ventana real y robots falsos (T10–T12 en [pruebas](docs/pruebas.md)); F22–F24 en [depuración](docs/depuración.md).

**Siguiente:** (1) Josu termina de leer el código final (orden sugerido: `red.py` → `ur.py` → `simulador.py` → `secuencia.py` → `tareas.py` → `main.py`) y decide las dudas abiertas: ¿se quita `Secuencia` (lista con `guardar`/`cargar`) y se llevan sus ficheros a `_comando`?, ¿el parámetro `visualizador` de `Simulador`, que solo usan los tests?, ¿`cargar_robots` dentro de `main`?; (2) probar con URSim y después con el UR3e (avisar antes de enviar `movej`; `--v 0.1 --a 0.2`, zona despejada y primero solo lectura con `primaria`); (3) comprobar a ojo la ventana de PyBullet (postura y convenio de ángulos, apartado 9 del enunciado); (4) simplificar el parser de `main.py` (Josu: algo más sencillo, p. ej. con `input`); (5) HMI con pygame para la consola de `ensenar`; (6) opcional: trayectoria suave entre puntos, ver «Mejoras posibles» en [arquitectura](docs/arquitectura.md). `src/robots.json` lo edita Josu (IP de robots del laboratorio): `varios` sin `--config` se conectará a ellos.

## Documentación de la práctica

[arquitectura](docs/arquitectura.md) · [decisiones](docs/decisiones.md) · [depuración](docs/depuración.md) · [pruebas](docs/pruebas.md)

Protocolo del UR: [docs/ur-referencia.md](../../docs/ur-referencia.md) (raíz del repo).
