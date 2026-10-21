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
| Sobresaliente: enseñar, previsualizar, ejecutar con `movej` y supervisar errores | `src/ensenar.py` (consola) | ⚠️ URSim robot1: cargar, ejecutar, cancelar (`stopj`) y secuencia completa (2026-10-19); **UR3e del laboratorio en la defensa (2026-10-20)**, con el rechazo C210 corregido (F31, D31; datos de Josu, sin log); **sin probar** el error del robot / parada de protección con URSim |
| Defensa (pedido en directo por el profesor, 2026-10-20): grabar puntos en un robot y ejecutarlos en otro | `src/copiar.py` (consola, D30) | ⚠️ **funcionó a la primera con los UR3e** (dato de Josu, sin log); sus 17 pruebas con robots falsos están en `pruebas/test_copiar.py` (T31) |

✅/⚠️ = 201 pruebas automáticas (Python 3.7.5 en Windows, con el Python del PC y con el portable; T28), los scripts contra robots falsos y contra URSim el 2026-10-19, y `ensenar.py`/`copiar.py` con los UR3e el 2026-10-20 (T29, T30). Las pruebas escritas durante la defensa (F31, `copiar.py`) ya están en el repo: 201 en total (T31). Detalle en [docs/pruebas.md](docs/pruebas.md).

## 3. Cómo ejecutar

**En Windows, en cualquier PC (portable, D26):** doble clic en [iniciar.bat](iniciar.bat). Menú: 1 `primaria`, 2 `tiempo_real`, 3 `ensenar` (pide confirmación: envía `movej`), 4 abre `datos\robots.json` para cambiar las IP, 5 salir, 6 `copiar` (pide confirmación: envía `movej` al ejecutor). También `iniciar.bat primaria|tiempo_real|ensenar|copiar [grabador ejecutor]` sin menú. Usa el Python de la carpeta `entorno\` (nada que instalar); si no existe, usa el `python` del PC. El entorno se crea con `powershell -ExecutionPolicy Bypass -File herramientas\crear_entorno.ps1` (raíz del repo; ver [docs/entorno.md](../../docs/entorno.md)) y para entregar se comprime esta carpeta entera con `entorno\` dentro.

**En Linux (D28, probado por Josu en un Ubuntu el 2026-10-19):** desde una terminal, `bash iniciar.sh` (misma interfaz: menú o `bash iniciar.sh primaria|tiempo_real|ensenar|copiar [grabador ejecutor]`). La primera vez monta `entorno-linux/` con el kit de la carpeta `linux/` (`uv`, un Python 3.11 y las ruedas de [requirements-linux.txt](requirements-linux.txt); **sin internet ni `sudo`**). `linux/` se genera en Windows con `powershell -ExecutionPolicy Bypass -File herramientas\preparar_linux.ps1` (≈ 240 MB, no se versiona) y viaja con la carpeta al pendrive; hay que copiar la carpeta al disco del PC antes de ejecutar (un pendrive FAT no deja ejecutar). Sin `linux/`, necesita `uv` e internet.

**Con el Python del PC** (desarrollo). Entorno (Python 3.7.5, URSim, puertos): [docs/entorno.md](../../docs/entorno.md). Desde la raíz del repo, en PowerShell 5.1. Los scripts no tienen argumentos y funcionan lancen desde donde se lancen (las rutas son relativas al script):

```powershell
python -u 2_practicas\Practica1_visualizador_UR3e\src\primaria.py      # interfaz primaria (30001); pregunta cuántos robots (Intro = 1)
python -u 2_practicas\Practica1_visualizador_UR3e\src\tiempo_real.py   # interfaz de tiempo real (30003); igual
python -u 2_practicas\Practica1_visualizador_UR3e\src\ensenar.py       # ¡ENVIA movej al robot! Se maneja con comandos
python -u 2_practicas\Practica1_visualizador_UR3e\src\copiar.py        # graba en el 2o robot y ¡ENVIA movej al 1o! (o: copiar.py robot1 robot2)
```

Los robots (nombre e IP) están **solo en `datos\robots.json`** (D23): cambiar de robot es editar ese fichero. `ensenar.py` usa el primero. Parar con Ctrl+C. **Desde la defensa (2026-10-20) el fichero lleva las IP del laboratorio** (`robot1` = `10.172.21.205`, `robot2` = `10.172.21.206`); para URSim en el aula hay que volver a `10.172.18.74` y `10.172.18.131`.

`ensenar.py` se maneja escribiendo comandos en la consola: `g` guardar punto, `v` previsualizar (mueve **solo el robot de la ventana** por los puntos guardados, sin enviar nada al robot real; luego vuelve a la pose real), `e` ejecutar, `c` cancelar, `r` reanudar, `s`/`l [nombre]` guardar/cargar en `datos\secuencias\`, `b` borrar, `ajustar <v rad/s> <a rad/s²>`, `q` salir. **Antes de `e`:** el robot encendido con frenos liberados (`robotMode = 7`) y, en URSim/PolyScope 5, *Ajustes → Sistema → Control remoto* en **Remoto**; velocidades bajas (por defecto 0,1 rad/s y 0,2 rad/s²) y zona despejada en un robot real. `movej` se niega a enviar más de 0,3 rad/s o 0,5 rad/s². **Control remoto antes de arrancar:** si el robot rechaza la orden (error C210: la conexión se abrió en Local), el programa lo dice, no manda `stopj`, reconecta y se continúa con `r` (F31, D31).

`copiar.py` es `ensenar.py` con dos robots: `g` guarda la posición del **grabador** (2.º de `robots.json`, solo se lee: nunca recibe órdenes) y `e` la ejecuta en el **ejecutor** (1.º, el mismo que mueve `ensenar.py`). Mismos comandos y ficheros. Con `copiar.py <grabador> <ejecutor>` se eligen por nombre (D30).

**Pruebas** (no necesitan robot ni URSim; las de PyBullet real sí necesitan la librería):

```powershell
python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas -v          # 201 pruebas, ≈ 49 s (T31)
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

**Reorganización por niveles (2026-10-17, D23–D25; la web de control se retiró el 2026-10-19, D27):** un script por entregable (`primaria.py`, `tiempo_real.py`, `ensenar.py`) y las clases en `src/librerias/` (`red`, `ur`, `simulador`, `secuencia`); sin `argparse` ni `tareas.py`; rutas relativas a la carpeta de la práctica (`datos/robots.json`, `datos/secuencias/`). Prototipo de la Pi aplicado el 2026-10-19 (rama `prototipo-17-10`, ya fusionada en `main`) (T14–T16 en [pruebas](docs/pruebas.md)). El código de las clases no cambió salvo lo imprescindible (`leer_robots`, `elegir_robots`, `visualizar`, `ajustar`).

**Portable y URSim (2026-10-19, D26):** `iniciar.bat` + `entorno\` (Python 3.7.5 embebido con las librerías, creado por `herramientas/crear_entorno.ps1`). 223 pruebas OK en Windows con el Python del PC y con el portable; humos con PyBullet real `OK`; `primaria`, `tiempo_real` y `ensenar` probados contra URSim (T17–T20). Fallos documentados: F27 (el servidor web no leía el cuerpo del `POST`; hoy sin web, queda como lección) y F28 (pruebas con tiempos justos para Windows).

**Web retirada y Linux (2026-10-19, D27 y D28):** Josu probó `iniciar.bat` y no entendió para qué servía «previsualizar» en la web ni veía que hiciera nada; para la defensa prefiere guardar puntos por consola. Se quitaron `hmi.py`, `hmi.html`, `_estado` y la cola de avisos con hora (`avisar` vuelve a ser `print`); `ensenar` avisa al previsualizar. Se añadió `iniciar.sh` para Linux.

**`Lock` y mediciones (2026-10-19, D29, T25–T27):** `HiloLectorUR` vuelve a tener `Lock` (`cerrojo`) sobre `q`, que el hilo lector escribe y `visualizar` lee (181 pruebas OK). Medidas para la memoria: bytes por `recv()` (pregunta 1) y retraso entre URSim y el robot simulado (pregunta 7; primaria ≈ 51 ms desde que llega un `q` hasta que se dibuja y tiempo real ≈ 1,6 ms, relativos al flujo de tiempo real; con un movimiento autorizado de ±0,2 rad en `robot1` de URSim). La pregunta 6 (cable fuera) no se ha medido. Josu empezó el repaso del código por `ur.py` con preguntas sueltas (sin marcar nada en la guía de la Pi).

**Defensa con los UR3e (2026-10-20, F31, D30, D31):** Josu defendió la práctica con el profesor y los UR3e del laboratorio. Salieron **un fallo** y **una petición nueva**, ambos resueltos en el momento con Claude Code. (1) *Fallo F31:* con el robot real, `e` daba el error 210 (el robot rechaza órdenes de una conexión abierta en modo Local aunque luego se pase a remoto), el texto del error se leía mal y el `stopj` rechazado producía un «Robot detenido» falso. Ahora se explica, no se manda `stopj`, se reconecta y se sigue con `r`; además `red.py` hace `shutdown()` antes de `close()` (Linux). (2) *Petición del profesor, D30:* `copiar.py`, que graba puntos en un robot (solo lectura) y los ejecuta en otro; funcionó a la primera. También se cambiaron `datos/robots.json` (IP del laboratorio) y los menús de `iniciar.bat`/`iniciar.sh` (opción 6). El 2026-10-20 se fusionó la copia hecha en el otro PC con este repo (la cronología de ese día lo cuenta). Las pruebas escritas allí (3 de F31 y `test_copiar.py`) se trajeron después: 201 en verde (T31).

**Siguiente:** (1) hecho: pruebas del otro PC traídas y ejecutadas, 201 OK (T31); (2) cerrar la memoria con la Pi (`docs/memoria-borrador.md`, máximo 6 páginas) y el correo breve al profesor con el fallo, el arreglo y `copiar.py`; (3) subir la carpeta a Drive con `empaquetar.bat` y dar la práctica por cerrada; (4) pendientes menores de antes de la defensa: medir la pregunta 6 (cable fuera 5 s), probar el error del robot / parada de protección con URSim, mirar a ojo la ventana de PyBullet (postura y convenio de ángulos); (5) opcional: evitar el primer fallo C210 reconectando antes de la primera ejecución (D31), gráfico en `primaria.py`/`tiempo_real.py`, trayectoria suave entre puntos (ver «Mejoras posibles» en [arquitectura](docs/arquitectura.md)).

## Documentación de la práctica

[arquitectura](docs/arquitectura.md) · [decisiones](docs/decisiones.md) · [depuración](docs/depuración.md) · [pruebas](docs/pruebas.md) · [memoria (borrador)](docs/memoria-borrador.md) · [informe de desarrollo con Claude Code](docs/informe-desarrollo-claude-code.md) (evidencia de la [guía común](../../docs/guia-programar-con-ia.md)) · desde la Pi: [defensa](../../docs/desde-pi/defensa-p1.md)

Protocolo del UR: [docs/ur-referencia.md](../../docs/ur-referencia.md) (raíz del repo).
