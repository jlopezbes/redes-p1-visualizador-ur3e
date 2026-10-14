# 03 – Arquitectura del código

Todo el código está en `c:\Users\Estudiante\Josu\Redes\practica 1\`. Compatible con **Python 3.7** (no usar walrus, `list[float]`, `match`, etc.). Comentarios y mensajes en español, estilo del código antiguo del usuario.

```
ur_primary.py  <── usado por ──  ejercicio1, ejercicio2, ejercicio3, ejercicio4
gemelo.py      <── usado por ──  ejercicio1, ejercicio2 (solo con --gemelo; import perezoso)
simulador_ur.py                  independiente (herramienta de prueba)
```

## `ur_primary.py` – núcleo de comunicación

| Elemento | Qué hace |
|---|---|
| `recv_exact(sock, n)` | Lee exactamente `n` bytes; lanza `ConnectionError` si el robot cierra |
| `leer_paquete(sock)` | Lee cabecera + cuerpo; devuelve `(tipo, cuerpo)`; `ValueError` si tamaño < 5 |
| `separar_subpaquetes(cuerpo)` | `{subtipo: datos}` recorriendo el cuerpo en memoria |
| `parsear_modo_robot(datos)` | dict con los 13 campos del subpaquete 0 |
| `parsear_joints(datos)` | dict de listas (6 valores por variable) del subpaquete 1 |
| `parsear_cartesiano(datos)` | lista `[x,y,z,rx,ry,rz]` del subpaquete 4 |
| `parsear_estado(cuerpo)` | combina lo anterior: `{"modo":…, "joints":…, "tcp":…}` (solo las claves presentes) |
| `parsear_robot("ip[:puerto]")` | devuelve `(ip, puerto)`; puerto por defecto 30001 |
| `class LectorUR(Thread)` | hilo `daemon` que conecta, lee en bucle y guarda el **último estado**; reconecta cada 2 s si hay error (`OSError`, `ValueError`, `struct.error`); `timeout` de socket 5 s. Métodos: `ultimo_estado()` (con lock), `parar()` |
| `formatear_estado(nombre, estado)` | una línea: joints (rad), TCP, modo |
| `MODOS_ROBOT` | mapa `robotMode` → texto |

Patrón de diseño clave: **los hilos solo escriben el último estado; el hilo principal lee y dibuja/imprime/manda órdenes.** El año pasado se llamaba al visualizador PyBullet desde varios hilos (no es seguro).

Salida típica de `formatear_estado`:
```
[UR1] joints (rad): [ -1.601,  -1.508,  -1.936,  -1.294,   1.596,  -0.031] | TCP: [-0.137, -0.267,  0.237, -0.001,  3.116,  0.039] | modo: running
```

## `gemelo.py` – visualizador 3D (opcional)

`class Gemelo(separacion=1.0)`:
- `__init__`: importa `UR3e_rg2.dynamic_ur3e.UR3eRG2` (abre la ventana PyBullet).
- `añadir_robot(nombre)`: el primero es el id 0 del visualizador; los siguientes se colocan con `spawn_robot([x,0,0,0,0,0])` con `x = separacion × n_robots_existentes`.
- `mover(nombre, joints)`: `visualizacion.move_robot(id, lista_de_6)`.

El import es perezoso para que el resto funcione sin PyBullet.

## `ejercicio1_leer_un_robot.py`

```
python ejercicio1_leer_un_robot.py [--robot IP[:PUERTO]] [--hz 2] [--completo] [--gemelo]
```
- `--robot` por defecto `127.0.0.1`. `--hz` = prints por segundo. `--completo` imprime además `modo` y `joints` (todas las variables). `--gemelo` abre el visualizador.
- Detalle cosmético conocido: la primera línea suele ser `sin datos todavia`.

## `ejercicio2_varios_robots.py`

```
python ejercicio2_varios_robots.py --robots IP1[:P1] IP2[:P2] ... [--hz 10] [--imprimir-cada 1.0] [--gemelo]
```
- Un `LectorUR` por robot, nombres `UR1`, `UR2`, ...
- Con `--gemelo` crea un robot 3D por cada lector.
- Los mensajes de "conectado" de los hilos se mezclan con los prints del hilo principal (cosmético).

## `ejercicio3_mover.py`

```
python ejercicio3_mover.py --robots IP1[:P1] [IP2[:P2] ...]
       [--pose home|pose1 | --joints q1 q2 q3 q4 q5 q6]
       [--metodo socket|rtde] [--a 0.2] [--v 0.2]
       [--arrancar] [--dashboard-puertos P1 P2 ...]
```
- `POSES`: `home = [0, -π/2, 0, -π/2, 0, 0]`; `pose1 = [π/4, -π/4, -1.57, -1.57, 2.57, 0]` (la del año pasado).
- Flujo: arranca un lector por robot → (opcional) `--arrancar` por dashboard → imprime estado "(antes)" → envía el movimiento a cada robot → `esperar_llegada` (tolerancia 0.01 rad en todos los joints, timeout 60 s) → imprime "(llego al destino)" o "(NO llego al destino)".
- `mover_socket`: `movej` por TCP a `ip:puerto` del robot y cierra.
- `mover_rtde`: `rtde_control.RTDEControlInterface(ip).moveJ(q, v, a)` — **ojo al orden `(q, velocidad, aceleración)` de ur_rtde**; luego `stopScript()`.
- `dashboard(ip, comando, puerto=29999)`; `arrancar_robot(ip, puerto_dashboard=29999)` hace `power on`, espera 2 s, `brake release`, espera 5 s.
- Con varios robots el movimiento se envía **secuencialmente** (casi simultáneo, no sincronizado) y la espera de llegada es también secuencial.

## `ejercicio4_espejo.py`

```
python ejercicio4_espejo.py --origen IP[:P] --destino IP[:P]
       [--metodo speed|socket|rtde] [--periodo 0.1] [--hz 50]
```
- Lee el origen y el destino con dos `LectorUR`; en bucle calcula la diferencia máxima entre `q_actual` y mueve el destino hacia el origen.
- **`speed` (defecto)**: `velocidad_i = clip(GANANCIA·(q_origen_i − q_destino_i), ±1.5)` con `GANANCIA = 4.0` y `speedj(vel, a=3.0, t=2·periodo)` cada `periodo`; conexión TCP **persistente** al destino (`enviar_script`, reconecta si falla); `stopj(2.0)` al terminar (en el `finally`).
- `socket`: `movej([q_origen], a=1.0, v=1.0, t=periodo)` solo si la diferencia > `UMBRAL = 0.005` rad. Arranca y frena en cada orden → **retraso de 0.6–0.8 rad** en las pruebas.
- `rtde`: `servoJ(q_origen, 0, 0, dt=1/hz, 0.1, 300)`; `servoStop()` + `stopScript()` al salir. **No probado.**
- Imprime cada ~1 s ORIGEN, DESTINO y "diferencia máxima".
- No tiene opción `--gemelo`.

## `ejercicio5_bidireccional.py`

```
python ejercicio5_bidireccional.py --primario IP[:P] --secundario IP[:P] [--vmax 1.0] [--periodo 0.1]
```
- Espejo en los dos sentidos. Clase `Robot` (lector + conexión TCP persistente + velocidad medida con las posiciones en ventanas de 0.3 s).
- Máquina de estados: **reposo** (nadie lidera, no se manda nada) → un robot supera `UMBRAL_VEL = 0.03 rad/s` → es el **líder** y el otro recibe `speedj` proporcional (`GANANCIA = 5`, saturado a `--vmax`) → el líder lleva `ESPERA_QUIETO = 0.5 s` quieto y el error < `0.01 rad` (o `MAX_QUIETO = 3 s`) → `stopj` y vuelta a reposo con `ENFRIAMIENTO = 1 s` (el seguidor aún frena y no debe detectarse como líder).
- Si ambos se mueven a la vez en reposo, gana el primario. Mientras hay líder se ignora lo que haga el seguidor.
- Al arrancar **no mueve nada** hasta que alguno se mueva. **No probado contra robots** (solo `ast.parse` y `--help`).

## `simulador_ur.py` – robot falso

```
python simulador_ur.py 30001 30011
```
Un robot por puerto. Emite (a 10 Hz) un paquete tipo 20 falso y un tipo 16 con subpaquetes 0 (modo "running"), 1 (joints) y 4 (TCP **siempre ceros**). Acepta líneas `movej([...])` (regex `movej\(\[([^\]]+)\]`) y mueve el robot falso a 0.5 rad/s. **No entiende `speedj` ni `stopj`.** Posición inicial `[0, -1.57, 0, -1.57, 0, 0]`. Es la herramienta con la que se verificaron los ejercicios 1–3 antes de que el usuario tuviera URSim.

## Estilo / convenciones

- Nombres y mensajes en español; identificadores con tilde permitidos solo donde ya estaban (`tamaño`, `añadir_robot`).
- Una función = una responsabilidad; `argparse` en cada ejercicio con `formatter_class=RawDescriptionHelpFormatter` y el docstring del módulo como ayuda.
- Imports pesados (`rtde_control`, `gemelo`) **perezosos**, para no exigir dependencias que no se usan.
