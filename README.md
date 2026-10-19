# Práctica 1 – Visualizador de un UR3e por TCP/IP

Lee el estado de un UR3e (real o URSim) por sockets TCP y lo reproduce en el visualizador PyBullet `UR3e_rg2`.

## 1. Enunciado

Fuente: [fuentes/enunciados/Práctica guiada visualizador de un UR3e por TCP IP.pdf](../../fuentes/enunciados/Pr%C3%A1ctica%20guiada%20visualizador%20de%20un%20UR3e%20por%20TCP%20IP.pdf) (apartados 10 a 12 leídos por la Pi el 2026-10-17 con `pdftotext`). Manuales: [fuentes/manuales/](../../fuentes/manuales/). Librería del visualizador: [fuentes/librerias/](../../fuentes/librerias/).

Programa en Python que lee el estado de un UR3e (real o URSim) por TCP/IP y lo reproduce en el visualizador PyBullet `UR3e_rg2`. Todo el código de comunicación lo escriben ellos. Desarrollo en el aula (red 10.172.18.x, URSim en VirtualBox en modo puente); validación y defensa con los UR3e del laboratorio de robótica (10.172.21.x: .203, .204, .205 y .206), con el profesor presente.

Evaluación **incremental y binaria**: cada nivel se supera entero o no.

| Nivel | Nota | Requisitos (todos obligatorios) |
|---|---|---|
| Aprobado | 5 | **Dos scripts separados:** `primaria.py` (puerto 30001) y `tiempo_real.py` (30003). Cada uno obtiene los 6 `q_actual` de un robot y mueve con ellos el UR3e de PyBullet; ambos usan buffer y delimitan los mensajes por su longitud. En la defensa: se mueve el robot en URSim y el simulado le sigue; **se reinicia URSim y el programa no se cuelga** |
| Notable | 7 | Todo lo anterior, más **un único script** que visualiza varios robots (≥ 2) en la misma ventana, cada uno en su posición; los robots se configuran sin tocar el código; un robot que se desconecta no detiene a los demás |
| Sobresaliente | 10 | Todo lo anterior, más el envío de órdenes y la mini-aplicación **Enseñar y reproducir**: enseñar ≥ 4 puntos (también con deslizadores de PyBullet, opcional), previsualizar, ejecutar con `movej` sin enviar el siguiente hasta confirmar el anterior (`isProgramRunning` falso y `q_actual` a menos de 0,01 rad), y supervisar (un mensaje de error tipo 20 subtipo 6 o 10, o `isProtectiveStopped`, detiene la secuencia, muestra el motivo y espera reanudar o cancelar); guardar y cargar la secuencia. Funcionando contra URSim y validada en un UR3e real con el profesor |

Límites obligatorios en el robot real: **0,3 rad/s y 0,5 rad/s²**, secuencia probada antes en URSim y profesor con la seta al alcance. Ninguna orden de movimiento a un robot real sin autorización expresa del profesor.

**Entrega:** código de cada nivel alcanzado y un README con cómo ejecutarlos y configurar las IP; **memoria breve de máximo 6 páginas** (explicación del código, estructura y estrategias de lectura, y las respuestas del apartado 12: 1 a 6 obligatorias, 7 y 8 para el notable, 9 y 10 para el sobresaliente); defensa en el aula contra URSim y después en el laboratorio con un UR3e. Cualquier miembro del grupo debe poder explicar cualquier línea; si no, el nivel no se considera superado. Fecha de entrega: no consta. Guía con las preguntas y su respuesta guía: [docs/desde-pi/defensa-p1.md](../../docs/desde-pi/defensa-p1.md).

## 2. Requisitos y estado

| Requisito (enunciado) | Script | Estado |
|---|---|---|
| Aprobado: un robot por la interfaz primaria (30001) → PyBullet | `src/primaria.py` | ✅ URSim (10 estados/s, reconectó solo tras una caída), 2026-10-19; lo que se ve en la ventana lo mira Josu |
| Aprobado: un robot por la interfaz de tiempo real (30003) → PyBullet | `src/tiempo_real.py` | ✅ URSim (≈ 420 estados/s), 2026-10-19 |
| Notable: varios robots en la misma ventana, un hilo por robot, sin tocar el código | `primaria.py` o `tiempo_real.py` y respuesta «2» (robots en `datos/robots.json`) | ✅ 2 URSim a la vez (tiempo real); el caso «uno se cae» solo con robots falsos |
| Sobresaliente: enseñar, previsualizar, ejecutar con `movej` y supervisar errores | `src/ensenar.py` (consola) | ⚠️ URSim robot1: cargar, ejecutar, cancelar (`stopj`) y secuencia completa; **sin probar** el error del robot / parada de protección con URSim y el UR3e |

✅/⚠️ = 181 pruebas automáticas (Python 3.7.5 en Windows, con el Python del PC y con el portable), los scripts contra robots falsos y contra URSim el 2026-10-19; ❌ UR3e real. Detalle en [docs/pruebas.md](docs/pruebas.md).

## 3. Cómo ejecutar

**En Windows, en cualquier PC (portable, D26):** doble clic en [iniciar.bat](iniciar.bat). Menú: 1 `primaria`, 2 `tiempo_real`, 3 `ensenar` (pide confirmación: envía `movej`), 4 abre `datos\robots.json` para cambiar las IP, 5 salir. También `iniciar.bat primaria|tiempo_real|ensenar` sin menú. Usa el Python de la carpeta `entorno\` (nada que instalar); si no existe, usa el `python` del PC. El entorno se crea con `powershell -ExecutionPolicy Bypass -File herramientas\crear_entorno.ps1` (raíz del repo; ver [docs/entorno.md](../../docs/entorno.md)) y para entregar se comprime esta carpeta entera con `entorno\` dentro.

**En Linux (D28, sin probar):** `./iniciar.sh` (misma interfaz: menú o `./iniciar.sh primaria|tiempo_real|ensenar`). La primera vez crea un `venv` en `entorno/` e instala [requirements-linux.txt](requirements-linux.txt) (necesita `python3` ≥ 3.9 con `venv` e internet); la rueda de `UR3e_rg2` viaja en `recursos/`. Si no es ejecutable: `chmod +x iniciar.sh`.

**Con el Python del PC** (desarrollo). Entorno (Python 3.7.5, URSim, puertos): [docs/entorno.md](../../docs/entorno.md). Desde la raíz del repo, en PowerShell 5.1. Los scripts no tienen argumentos y funcionan lancen desde donde se lancen (las rutas son relativas al script):

```powershell
python -u 2_practicas\Practica1_visualizador_UR3e\src\primaria.py      # interfaz primaria (30001); pregunta cuántos robots (Intro = 1)
python -u 2_practicas\Practica1_visualizador_UR3e\src\tiempo_real.py   # interfaz de tiempo real (30003); igual
python -u 2_practicas\Practica1_visualizador_UR3e\src\ensenar.py       # ¡ENVIA movej al robot! Se maneja con comandos
```

Los robots (nombre e IP) están **solo en `datos\robots.json`** (D23): cambiar de robot es editar ese fichero. `ensenar.py` usa el primero. Parar con Ctrl+C.

`ensenar.py` se maneja escribiendo comandos en la consola: `g` guardar punto, `v` previsualizar (mueve **solo el robot de la ventana** por los puntos guardados, sin enviar nada al robot real; luego vuelve a la pose real), `e` ejecutar, `c` cancelar, `r` reanudar, `s`/`l [nombre]` guardar/cargar en `datos\secuencias\`, `b` borrar, `ajustar <v rad/s> <a rad/s²>`, `q` salir. **Antes de `e`:** el robot encendido con frenos liberados (`robotMode = 7`) y, en URSim/PolyScope 5, *Ajustes → Sistema → Control remoto* en **Remoto**; velocidades bajas (por defecto 0,1 rad/s y 0,2 rad/s²) y zona despejada en un robot real. `movej` se niega a enviar más de 0,3 rad/s o 0,5 rad/s².

**Pruebas** (no necesitan robot ni URSim; las de PyBullet real sí necesitan la librería):

```powershell
python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas -v          # 181 pruebas, ≈ 40 s
python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_pybullet.py                   # Simulador con la librería real (ventana ≈ 2 s)
python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_extremo_a_extremo.py          # los 3 scripts con ventana real
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
| `versiones/a_mano/` | Hecha a mano por Josu (su propio `main.py`). Contra el robot falso no imprime nada: no lee el cuerpo del subpaquete 0 (la Pi, 2026-10-13). | sí |
| `versiones/claude_1/` | Claude, un prompt, 5 ejercicios, hilo lector y robot falso. Probada con URSim el 2026-10-08. | no |
| `versiones/claude_2/` | Claude, con enunciado: buffer validado, varios robots, enseñar y reproducir. Solo probada con robot falso. | sí |

Comparación: [docs/desde-pi/comparacion-versiones-p1.md](../../docs/desde-pi/comparacion-versiones-p1.md).

## 5. Estado y siguiente paso

**Historia (2026-10-14/16):** fase 1 (código de la IA a partir de `claude_2`, en módulos), revisión de robustez (cuatro capas, F7–F21) y limpieza por capas (D17–D21, `src/` de 1176 a 817 líneas); D22: el robot sale de `robots.json`. La versión con `main.py` se enseñó al profesor con URSim.

**Reorganización por niveles (2026-10-17, D23–D25; la web de control se retiró el 2026-10-19, D27):** un script por entregable (`primaria.py`, `tiempo_real.py`, `ensenar.py`) y las clases en `src/librerias/` (`red`, `ur`, `simulador`, `secuencia`); sin `argparse` ni `tareas.py`; rutas relativas a la carpeta de la práctica (`datos/robots.json`, `datos/secuencias/`). Prototipo de la Pi aplicado en la rama `prototipo-17-10` el 2026-10-19 (T14–T16 en [pruebas](docs/pruebas.md)). El código de las clases no cambió salvo lo imprescindible (`leer_robots`, `elegir_robots`, `visualizar`, `ajustar`).

**Portable y URSim (2026-10-19, D26):** `iniciar.bat` + `entorno\` (Python 3.7.5 embebido con las librerías, creado por `herramientas/crear_entorno.ps1`). 223 pruebas OK en Windows con el Python del PC y con el portable; humos con PyBullet real `OK`; `primaria`, `tiempo_real` y `ensenar` probados contra URSim (T17–T20). Fallos documentados: F27 (el servidor web no leía el cuerpo del `POST`; hoy sin web, queda como lección) y F28 (pruebas con tiempos justos para Windows).

**Web retirada y Linux (2026-10-19, D27 y D28):** Josu probó `iniciar.bat` y no entendió para qué servía «previsualizar» en la web ni veía que hiciera nada; para la defensa prefiere guardar puntos por consola. Se quitaron `hmi.py`, `hmi.html`, `_estado` y la cola de avisos con hora (`avisar` vuelve a ser `print`); `ensenar` avisa al previsualizar. Se añadió `iniciar.sh` para Linux.

**Siguiente:** (1) Josu lee el código nuevo (orden: `red.py` → `ur.py` → `simulador.py` → `secuencia.py` → `primaria.py` → `ensenar.py`) y decide las dudas abiertas: ¿`Lock` en `HiloLectorUR`? (el enunciado lo recomienda), ¿`varios.py` aparte por si el profesor lee «un único script» literalmente?, ¿`Secuencia`, el parámetro `visualizador` de `Simulador`?; (2) mirar a ojo la ventana de PyBullet contra URSim (postura y convenio de ángulos) y comprobar que el robot 2 sigue al suyo (era la carrera de F29, ya arreglada); (3) probar el error del robot / parada de protección con URSim y después el UR3e (velocidad 0,1 rad/s, zona despejada, primero solo lectura); (4) pedir la defensa oficial (Josu: el martes 2026-10-20 por la mañana) y ensayar los cambios en caliente sin IA; (5) memoria de máximo 6 páginas: borrador en `docs/memoria-borrador.md` y guía de defensa de la Pi en `docs/desde-pi/defensa-p1.md` (raíz del repo); (6) opcional: gráfico en `primaria.py`/`tiempo_real.py`, trayectoria suave entre puntos (ver «Mejoras posibles» en [arquitectura](docs/arquitectura.md)).

## Documentación de la práctica

[arquitectura](docs/arquitectura.md) · [decisiones](docs/decisiones.md) · [depuración](docs/depuración.md) · [pruebas](docs/pruebas.md) · [memoria (borrador)](docs/memoria-borrador.md) · desde la Pi: [defensa](../../docs/desde-pi/defensa-p1.md)

Protocolo del UR: [docs/ur-referencia.md](../../docs/ur-referencia.md) (raíz del repo).
