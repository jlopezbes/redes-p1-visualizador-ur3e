# Arquitectura

Versión final en `src/` (fase 1: código escrito por la IA a partir de `claude_2`, pendiente de la revisión de Josu). Python 3.7.5, solo `socket`, `struct`, `threading` y la librería estándar, más `UR3e_rg2` (PyBullet) para dibujar.

## Módulos

| Archivo | Qué contiene | Responsabilidad |
|---|---|---|
| `src/main.py` | `main()`, `crear_parser()` | Punto de entrada: lee los argumentos (`primaria`, `tiempo-real`, `varios`, `ensenar`) y llama a la tarea. |
| `src/tareas.py` | `visualizar_primaria`, `visualizar_tiempo_real`, `visualizar_varios`, `ensenar_reproducir`, `cargar_robots` | Las cuatro tareas de la práctica como **funciones** que juntan los controladores. Aquí vive el bucle de dibujo y la consola de enseñar. |
| `src/ur.py` | clases `ClienteUR`, `UrPrimaria`, `UrTiempoReal`, `LectorUR` y las funciones de decodificación | **Habla con el UR** usando `ConexionTCP`: corta los bytes en mensajes, los decodifica y envía `movej`/`stopj`. Define `ErrorUR`: es lo único que sale de este módulo hacia arriba (D10). |
| `src/red.py` | clases `ConexionTCP`, `ErrorRed`, `ErrorRedTimeout` | **Red pura**: abrir, cerrar, enviar y recibir por TCP con timeouts. No conoce el protocolo del UR. Valida sus argumentos y **traduce todo fallo de socket a `ErrorRed`** (D10, D11): las capas de arriba no conocen `socket` ni `OSError`. |
| `src/simulador.py` | clase `Simulador` | Envuelve `UR3eRG2` (PyBullet): robots por nombre, posición de la base, `mover` y `previsualizar`. |
| `src/secuencia.py` | clases `Secuencia`, `Reproductor` | Enseñar y reproducir: la lista de puntos (JSON) y la máquina de estados que envía un `movej` por punto y vigila errores. |
| `src/robots.json` | datos | Robots de `visualizar_varios`: nombre, IP, puerto y posición de la base. |

## Flujo de datos

```
python src\main.py <orden>
        |
        v
   main.py ──> tareas.py  (funciones: visualizar_*, ensenar_reproducir)
                  │
     ┌────────────┼──────────────────────────┐
     v            v                          v
  ur.py        secuencia.py              simulador.py
  UrPrimaria   Secuencia, Reproductor    Simulador ──> UR3eRG2 ──> PyBullet (ventana)
  UrTiempoReal      │ usa UrPrimaria
  LectorUR  <───────┘
     │
     v
  red.py: ConexionTCP ──TCP──> robot UR (30001 primaria · 30003 tiempo real)
```

Un mensaje de estado: `ConexionTCP.recibir()` → buffer de `ClienteUR` → `extraer_mensaje` (corta por longitud) → `leer_estado` (decodifica `q`, `ejecutando`, `protegido`) → `Simulador.mover()`.

## Errores de red (contrato de `red.py`)

| Situación | Qué ocurre | Conexión |
|---|---|---|
| IP, puerto o timeouts no válidos al crear `ConexionTCP` | `ValueError` en español (no se toca la red) | — |
| `abrir()` rechazada, sin ruta o sin respuesta | `ErrorRed` (o `ErrorRedTimeout` si no contesta) con `ip:puerto` | sin abrir |
| `recibir()` sin datos en `timeout_lectura` s | `ErrorRedTimeout` | **sigue abierta** |
| `recibir()`: el otro lado cierra o hay un RST; `enviar()` falla | `ErrorRed` | se **cierra** (`abierta` pasa a `False`) |
| `enviar()`/`recibir()` con la conexión cerrada, también si la cerró otro hilo | `ErrorRed` | — |
| `recibir(maximo)` con `maximo` fuera de 1–1 048 576, `enviar()` con algo que no es `bytes` | `ValueError` / `TypeError` (error de programación) | no cambia |

`cerrar()` se puede llamar varias veces y desde otro hilo. Si el otro extremo cierra, el primer `enviar()` puede no fallar (TCP lo acepta): fallará el siguiente o el `recibir()`.

## Errores del robot (contrato de `ur.py`)

Una clase de excepción por capa (D10): `ErrorRed` sale de `red.py` y se queda en `ur.py`; `ErrorUR` sale de `ur.py` y es lo único que conocen `secuencia.py` y `tareas.py`. `ValueError`/`TypeError` solo significan «argumento mal puesto».

| Situación | Qué ocurre |
|---|---|
| Falla la red (`ErrorRed`), el buffer se desalinea (longitud imposible), un mensaje llega cortado o mal formado, el subpaquete de articulaciones no mide 251 B, o `q` no es finito o pasa de ±(2π + 0,2) rad | `ErrorUR` con el motivo en español (`raise ... from e`) |
| Pasan `PLAZO_ESTADO` s sin un estado válido, aunque lleguen otros bytes (robot mudo o que gotea) | `ErrorUR` desde `estados()`/`mensajes()` |
| `movej` sin estado válido de hace menos de `PLAZO_ESTADO` s | `ErrorUR` y **no se envía nada** (ante la duda, no mover) |
| `movej` con ángulos, velocidad o aceleración fuera de límites o de otro tipo; `enviar_script` con saltos de línea | `ValueError` |
| `stopj` con un valor no válido | frena igualmente con `ACELERACION_MAX`; `stopj` nunca exige estado fresco |
| Texto de un error del robot | solo ASCII imprimible y como mucho 300 caracteres |

**Estado fresco:** `ClienteUR.estado_fresco()` es la única definición (un estado válido recibido hace menos de `PLAZO_ESTADO` s, con `time.monotonic()`). La usan `LectorUR.ultimo_q()` (devuelve `None` si el q es viejo) y `UrPrimaria.movej()`. Un `ErrorUR` (también por falta de estados) hace que `LectorUR` y `ensenar_reproducir` cierren y reconecten; un `ErrorRedTimeout` suelto se trata igual.

**`LectorUR`:** `ultimo_q()` (copia o `None`), `vivo`, `ultimo_error` (texto o `None`), `parar()` (cierra el socket, el hilo sale enseguida) y `detener(timeout)` (`parar()` + `join`). El motivo de una desconexión se escribe una vez, no en cada reintento. Un bug dentro del hilo se anota en `ultimo_error` con su traceback y el hilo sigue reintentando.

**Para la capa de `main.py` (C4):** `ConexionTCP` lanza `ValueError` si la IP, el puerto o los timeouts no son válidos; por eso `main.py` debe validar `--ip`, `--puerto` y `robots.json` **antes** de abrir la ventana y de crear las conexiones, y mostrar el motivo en español.

## Hilos y concurrencia

| Tarea | Hilos | Qué comparten y cómo |
|---|---|---|
| `visualizar_*` | un `LectorUR` por robot + el hilo principal | Cada `LectorUR` guarda solo el **último `q`** bajo un `Lock`; el hilo principal lo pide con `ultimo_q()` y dibuja a `HZ_DIBUJO`. Si el robot se cae, `ultimo_q()` devuelve `None` y el robot simulado se queda quieto. |
| `ensenar_reproducir` | hilo principal + un hilo que lee la consola | El hilo de consola solo mete líneas en una `queue.Queue`; el principal lee los mensajes del robot, atiende los comandos y dibuja. |

**PyBullet se toca solo desde el hilo principal** (no es seguro entre hilos). Los hilos terminan con `parar()` (un `Event` y el cierre del socket; `detener(timeout)` añade el `join`) y son `daemon`: no impiden salir con Ctrl+C.

## Parámetros ajustables

| Dónde | Constante | Valor | Unidad | Para qué |
|---|---|---|---|---|
| `ur.py` | `VELOCIDAD_MAX` / `ACELERACION_MAX` | 0,3 / 0,5 | rad/s / rad/s² | Límite de `movej`: se niega a enviar más (robot real). |
| `ur.py` | `REINTENTO` | 2,0 | s | Espera entre reconexiones. |
| `ur.py` | `PLAZO_ESTADO` | 2,0 | s | Un `q` más viejo no es actual: `ultimo_q()` da `None`, `movej` se niega y el cliente lanza `ErrorUR`. |
| `ur.py` | `TAM_SUB_JOINTS`, `OFFSET_Q_ACTUAL` | 251, 252 | bytes | Formato esperado; con otro tamaño de subpaquete de articulaciones, `ErrorUR` (no hay movimiento). No verificado con un robot real. |
| `ur.py` | `LIMITE_Q_ENVIO` / `LIMITE_Q_LECTURA` | 2π / 2π + 0,2 | rad | Se envía hasta ±2π; se lee con un margen por si el robot está en el tope de una articulación. |
| `ur.py` | `MAX_TEXTO_ERROR` | 300 | caracteres | Texto de error del robot que se conserva. |
| `red.py` | `timeout_conexion` / `timeout_lectura` | 5,0 / 2,0 | s | Parámetros de `ConexionTCP`; deben cumplir `0 < t <= MAX_TIMEOUT`. |
| `red.py` | `MAX_TIMEOUT` | 3600 | s | Timeout máximo aceptado (un valor mayor, `None`, `nan` o `inf` es un error). |
| `red.py` | `MAX_RECIBIR` | 1 048 576 | bytes | Tope del argumento de `recibir(maximo)`. |
| `tareas.py` | `HZ_DIBUJO`, `PERIODO_INFO` | 30, 1,0 | Hz, s | Ritmo de dibujo y de las líneas de información. |
| `secuencia.py` | `TOLERANCIA`, `ESPERA_ARRANQUE` | 0,01, 2,0 | rad, s | Cuándo se da un punto por alcanzado y cuánto se espera a que arranque el programa. |
| `main.py` | `--v`, `--a` (solo `ensenar`) | 0,1 / 0,2 | rad/s / rad/s² | Velocidad y aceleración de cada `movej`. |
| `main.py` | `--ip`, `--puerto`, `--config` | `127.0.0.1`, 30001 / 30003, `robots.json` | | Robot y fichero de robots. |

## Mejoras posibles (ideas, nada implementado ni probado)

**Trayectoria suave entre puntos.** Hoy el robot se para en cada punto: `movej(q, a, v)` planifica un perfil trapezoidal que acaba con velocidad cero, y el `Reproductor` no envía el siguiente hasta que `isProgramRunning` baja. Fuente: el manual de URScript (`fuentes/manuales/scriptmanualG5_.pdf`, entrada de `movej`; el PDF no se ha podido leer en este PC, así que es de memoria y hay que contrastarlo).

| Opción | Cómo | Coste |
|---|---|---|
| Blend | `movej(q, a, v, 0, r)` con `r > 0` (en **metros**, aunque el movimiento sea articular): el robot redondea la esquina sin parar. Solo funciona entre movimientos del **mismo programa**: habría que enviar un bloque `def prog(): movej(...) movej(...) end`. | El robot ya no pasa exactamente por el punto, así que `TOLERANCIA` y el seguimiento punto a punto del `Reproductor` dejan de valer; hay que repensar la supervisión. Radios que se solapan dan error. |
| Interpolador propio | Calcular en Python la velocidad de cada articulación a partir del punto siguiente y enviar `speedj` a ritmo fijo (lo hizo `claude_1`, ejercicio 4: 0,04 rad de retraso frente a 0,6–0,8 rad con `movej` cortos). | Pasa a ser nuestro el límite de aceleración y la parada de emergencia. `speedj` con ganancia alta es agresivo en el robot físico. |
| `servoj` / RTDE | Streaming de posiciones a 125–500 Hz. | Sale del alcance de «sockets en crudo»; solo como alternativa declarada. |

Primero se probaría en URSim, nunca en el UR3e directamente.

## Limitaciones conocidas (sin resolver)

- Cualquier mensaje tipo 20 con subtipo 6 o 10 (error o excepción de programa) detiene la secuencia, **sin mirar `reportLevel`**: es lo más seguro, pero un aviso informativo del robot también pararía un movimiento. No se ha podido comprobar qué niveles emite un UR3e.
- El formato de 251 B del subpaquete de articulaciones y el offset 252 del tiempo real **no están verificados con un robot real**; si un robot manda otro tamaño, `ur.py` lanza `ErrorUR` en lugar de adivinar.
- `Simulador.previsualizar` bloquea el hilo principal unos segundos: durante ese tiempo los mensajes del robot se acumulan y, al terminar, se procesan de golpe (el robot simulado salta por posiciones atrasadas un instante). Es el comportamiento de `claude_2`; no se ha medido con un robot real.
- `UR3eRG2` abre siempre la ventana (`gui=True` fijo): no se puede ejecutar sin pantalla.
- Los formatos de tipo 20 (subtipos 6 y 10), los 251 B del subpaquete 1 y el offset 252 del tiempo real salen del enunciado a través de `claude_2` y **no están verificados** con un robot (ver [pruebas](pruebas.md)).
