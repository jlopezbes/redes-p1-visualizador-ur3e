# Arquitectura

Versión final en `src/`: escrita por la IA a partir de `claude_2`, endurecida en la auditoría de robustez (2026-10-14) y **limpiada por capas** el 2026-10-15/16 (D17–D21; 1176 → 817 líneas), y el 2026-10-17 **reorganizada por niveles** (D23: un script por entregable, las clases en `src/librerias/`, sin `argparse` ni `tareas.py`) y una web de control para `ensenar` que se **retiró el 2026-10-19** (D24 sustituida por D27: nadie la defendería con el UR3e delante). Pendiente de la revisión final de Josu. Python 3.7.5, solo `socket`, `struct`, `threading` y la librería estándar, más `UR3e_rg2` (PyBullet) para dibujar.

## Módulos

**Scripts ejecutables** (`src/`, uno por nivel del enunciado; no tienen argumentos: la IP sale de `datos/robots.json` y lo demás son constantes):

| Archivo | Nivel | Qué hace |
|---|---|---|
| `src/primaria.py` | Aprobado | Visualiza 1 o varios robots por la interfaz primaria (30001). Pregunta con `input` cuántos (Intro = 1). |
| `src/tiempo_real.py` | Aprobado | Igual, por la interfaz de tiempo real (30003). |
| `src/ensenar.py` | Sobresaliente | Enseñar, previsualizar, ejecutar y supervisar con el primer robot del JSON. Lleva la consola (`_leer_consola`, `_comando`), y el bucle principal. |

Los dos primeros son casi idénticos a propósito: son los dos «scripts separados» que pide el enunciado y la única diferencia es `tiempo_real=True`. El notable (varios robots en una ventana) lo cubren con la respuesta «2» a la pregunta.

**Librerías** (`src/librerias/`, módulos planos: cada script añade esa carpeta al `sys.path` con su propia ruta, así que no importa desde dónde se lance):

| Archivo | Qué contiene | Responsabilidad |
|---|---|---|
| `ur.py` | clases `ClienteUR`, `HiloLectorUR`; funciones `es_punto_valido`, `leer_robots`, `elegir_robots` | **Portal entre la red y el robot** (D18): conecta, corta los bytes en paquetes, los decodifica y entrega diccionarios ya traducidos (`mensajes()`); envía `movej`/`stopj`. Una sola clase para la interfaz primaria y la de tiempo real. `HiloLectorUR` es el hilo aparte que lee un robot y guarda solo el último `q`. `leer_robots` lee `robots.json`; `elegir_robots` pregunta cuántos visualizar. |
| `red.py` | clases `ConexionTCP`, `ErrorRed`, `ErrorRedTimeout` | **Red pura**: conectar, desconectar, enviar y recibir por TCP con timeouts. No conoce el protocolo del UR. Valida IP y puerto y **traduce todo fallo de socket a `ErrorRed`** (D19). |
| `simulador.py` | clases `Simulador`, `ErrorSimulador`; función `visualizar` | Envuelve `UR3eRG2` (PyBullet): robots por nombre, colocados en fila a 1 m (D21), `mover`, `previsualizar` y `cerrar`. Convierte los fallos de la librería en `ErrorSimulador`. `visualizar(clientes)` es el bucle de `primaria.py` y `tiempo_real.py` (antes en `tareas.py`). |
| `secuencia.py` | clases `Secuencia`, `Reproductor`, `ErrorSecuencia`; | Enseñar y reproducir: `Secuencia` es una lista de puntos que se guarda y carga en JSON; `Reproductor` es la máquina de estados que envía un `movej` por punto, vigila errores y permite `ajustar` velocidad y aceleración. No deja escapar `ErrorRed`. |

**Datos** (`datos/`): `robots.json` (solo `nombre` e `ip`, D21; `primaria` y `tiempo_real` usan los primeros N que se pidan, `ensenar` el primero) y `secuencias/` (los puntos guardados). Todas las rutas se calculan a partir de la ubicación del script (`os.path.dirname(os.path.abspath(__file__))` y `..`), nunca absolutas: la práctica funciona igual en cualquier PC y desde cualquier carpeta.

## Flujo de datos

```
python src\primaria.py      python src\tiempo_real.py      python src\ensenar.py
        |                           |                            |
        v                           v                            v
  simulador.visualizar ──────────────┘                    consola (hilo aparte)
        │                                                        │ lineas de texto → queue.Queue
        │                                                        v
   ┌────┴─────────────┐                     ┌──────────────── hilo principal ────────────────┐
   v                  v                     v                  v                             v
ur.py            simulador.py            ur.py          secuencia.py                   simulador.py
HiloLectorUR     Simulador ──> UR3eRG2   ClienteUR      Reproductor (usa ClienteUR)    Simulador ──> UR3eRG2 ──> PyBullet
ClienteUR        ──> PyBullet (ventana)       │
   │                                          │
   v                                          v
red.py: ConexionTCP ──TCP──> robot UR (30001 primaria · 30003 tiempo real)
```

Un mensaje de estado: `ConexionTCP.recibir()` → buffer de `ClienteUR` → `_cortar` (corta por longitud) → `_decodificar` → diccionario (`q`, `ejecutando`, `protegido`, `emergencia`, `modo`) o `{"error": texto}` → `HiloLectorUR.q` o `Reproductor.procesar` → `Simulador.mover()`. Las capas de arriba no ven bytes ni tipos de mensaje.

**Primaria y tiempo real en una clase** (`ClienteUR(ip, puerto=None, tiempo_real=False)`): los dos paquetes empiezan por su longitud (`int32`), así que `_cortar` es el mismo; solo cambian el mínimo permitido y la decodificación. La primaria (30001, ≈ 10 Hz) trae articulaciones, modo del robot y errores; la de tiempo real (30003, ≈ 500 Hz) solo `q`. **`ensenar` usa siempre la primaria**: en tiempo real no llegan `ejecutando`, `protegido`, `emergencia` ni errores, y el `Reproductor` nunca vería una parada.

## Errores de red (contrato de `red.py`)

| Situación | Qué ocurre | Conexión |
|---|---|---|
| IP o puerto no válidos al crear `ConexionTCP` | `ValueError` en español (no se toca la red) | — |
| `conectar()` rechazada, sin ruta o sin respuesta | `ErrorRed` (o `ErrorRedTimeout` si no contesta en `TIMEOUT_CONEXION`) con `ip:puerto` y la causa probable | sin abrir |
| `recibir()` sin datos en `TIMEOUT_LECTURA` s | `ErrorRedTimeout` | **sigue abierta** |
| `recibir()`: el otro lado cierra o hay un RST; `enviar()` falla | `ErrorRed` | se **cierra** |
| `enviar()`/`recibir()` con la conexión cerrada, también si la cerró otro hilo | `ErrorRed` («no esta abierta») | — |

`desconectar()` se puede llamar varias veces y desde otro hilo (despierta a un `recibir()` bloqueado). Si el otro extremo cierra, el primer `enviar()` puede no fallar (TCP lo acepta): fallará el siguiente o el `recibir()`. En Windows rechazar una conexión a un puerto cerrado tarda 1–2 s.

## Errores del robot (contrato de `ur.py`)

Una sola excepción de comunicación, `ErrorRed` (D19): `ur.py` la deja pasar tal cual y la usa también para los fallos de protocolo. `ErrorSecuencia` y `ErrorSimulador` salen de sus módulos; `tareas.py` captura `ErrorRed` en el bucle de `ensenar` y `ErrorSecuencia` al guardar y cargar, y `main.py` convierte `ErrorRed` y `ErrorSimulador` en mensaje y código de salida. `ValueError` solo significa «argumento mal puesto».

| Situación | Qué ocurre |
|---|---|
| Falla la red, el buffer se desalinea (longitud imposible), un mensaje llega cortado o mal formado, o el subpaquete de articulaciones no mide 251 B | `ErrorRed` con el motivo en español (`mensajes()` termina; `HiloLectorUR` y `ensenar` reconectan) |
| Llegan más de `MAX_IGNORADOS` (100) paquetes seguidos sin ningún dato útil | `ErrorRed` «puerto o interfaz equivocados» (p. ej. cliente primaria contra el puerto 30003) |
| `movej` con ángulos fuera de ±2π, o velocidad o aceleración fuera de `[MINIMO, VELOCIDAD_MAX]` / `[MINIMO, ACELERACION_MAX]` | `ValueError` y **no se envía nada** |
| `stopj` | siempre se envía; `ErrorRed` si no hay conexión |
| Un mensaje del robot de tipo 20 con subtipo 6 o 10 | se entrega como `{"error": texto}` (`reportLevel` sin mirar) |

**No hay noción de «dato fresco»** (D20): si el robot calla, `recibir` da `ErrorRedTimeout` a los `TIMEOUT_LECTURA` s, el cliente reconecta y `HiloLectorUR.q` pasa a `None`; `movej` no depende del último estado porque lleva ángulos absolutos.

**`HiloLectorUR`:** atributos `q` (último `q`, 6 ángulos en rad, o `None` sin conexión), `ultimo_error` (texto o `None`) y `recibidos` (contador, para los estados por segundo); método `detener()` (cierra el socket y espera hasta 3 s). Un solo hilo los escribe y el resto solo los lee: no hace falta `Lock`. El motivo de una desconexión se escribe una vez, no en cada reintento.

## Errores de la secuencia y del simulador (contrato de `secuencia.py` y `simulador.py`)

| Situación | Qué ocurre |
|---|---|
| `Secuencia.cargar`: fichero ausente, ilegible, vacío, binario, JSON malo, o algo que no sea una lista de puntos de 6 ángulos en ±2π | `ErrorSecuencia` (qué fichero y por qué); la secuencia no cambia |
| `Secuencia.guardar` sin poder escribir | `ErrorSecuencia` |
| `Reproductor`: `stopj` que no sale | una línea en mayúsculas («NO SE HA PODIDO ENVIAR LA PARADA... PARALO CON EL BOTON DEL PENDANT»); `cancelar` deja el `Reproductor` en `LIBRE` igualmente |
| `Reproductor`: `protegido` o `emergencia` | no se ejecuta ni se reanuda; en movimiento, `stopj` y `PARADA`. El modo del robot solo se muestra |
| `Reproductor`: sin conexión al ejecutar o reanudar | `movej` falla con `ErrorRed`: `PARADA` con el motivo, sin excepción hacia arriba |
| `Simulador`: falta `UR3e_rg2`, ventana cerrada, `pybullet.error` | `ErrorSimulador` |

Fases del `Reproductor`: `LIBRE`, `ENVIADO` (se envió un `movej` y aún no se ve el programa en marcha), `MOVIENDO` (`isProgramRunning`) y `PARADA` (algo falló: se intentó `stopj` y se espera `r` o `c`). `ocupado` es `ENVIADO` o `MOVIENDO`.

**Configuración (los tres scripts):** `ur.leer_robots` lanza `ValueError` si `robots.json` no existe, está mal formado, está vacío o le falta `nombre` o `ip`; `ConexionTCP` lanza `ValueError` si la IP o el puerto no son válidos. Los clientes se crean **antes** que el `Simulador`, así que el error salta antes de abrir la ventana.

| Código de salida | Cuándo |
|---|---|
| 0 | Fin normal o Ctrl+C |
| 1 | `ValueError` (`robots.json` o una IP mal puestos) o `ErrorSimulador`: se escribe `Error: <motivo>` sin traceback; o un fallo inesperado del programa (Python imprime el traceback) |

(Antes había un código 2 para los argumentos mal puestos; sin `argparse` ya no existe, D23. Los fallos de la red no salen del programa: `HiloLectorUR` y `ensenar` reintentan.)

## Hilos y concurrencia

| Tarea | Hilos | Qué comparten y cómo |
|---|---|---|
| `primaria.py` / `tiempo_real.py` (`visualizar`) | un `HiloLectorUR` por robot + el hilo principal | Cada hilo guarda solo el **último `q`** en su atributo `q`; el hilo principal lo lee y dibuja 30 veces por segundo, sin bloquearse aunque un robot tarde en contestar. Si el robot se cae, `q` pasa a `None` y el robot simulado se queda quieto. |
| `ensenar.py` | hilo principal + un hilo que lee la consola | La consola solo mete líneas de texto en una `queue.Queue`; el principal lee los mensajes del robot, atiende los comandos y dibuja. No usa `HiloLectorUR`: necesita todos los mensajes (errores, `isProgramRunning`). |

**PyBullet se toca solo desde el hilo principal** (no es seguro entre hilos). Los hilos terminan con `detener()` y son `daemon`: no impiden salir con Ctrl+C. Al salir de `visualizar` y de `ensenar.main`, un `try/finally` frena el robot si hace falta, detiene los hilos y cierra la ventana, en ese orden.

## Parámetros ajustables

| Dónde | Constante | Valor | Unidad | Para qué |
|---|---|---|---|---|
| `ur.py` | `PUERTO_PRIMARIA` / `PUERTO_TIEMPO_REAL` | 30001 / 30003 | | Puertos del protocolo UR. |
| `ur.py` | `VELOCIDAD_MAX` / `ACELERACION_MAX` | 0,3 / 0,5 | rad/s / rad/s² | Límite de `movej`: se niega a enviar más (robot real). |
| `ur.py` | `MINIMO` | 0,001 | rad/s y rad/s² | Mínimo de `movej`: por debajo, Python escribiría `1e-05` y no se sabe si URScript lo admite. |
| `ur.py` | `REINTENTO` | 2,0 | s | Espera entre reconexiones. |
| `ur.py` | `TAM_SUB_JOINTS`, `OFFSET_Q_ACTUAL` | 251, 252 | bytes | Formato esperado; con otro tamaño de subpaquete de articulaciones, `ErrorRed`. No verificado con un robot real. |
| `ur.py` | `MAX_LONGITUD` | 65 536 | bytes | Un paquete más largo significa buffer desalineado. |
| `ur.py` | `MAX_IGNORADOS` | 100 | paquetes | Paquetes seguidos sin ningún dato útil antes de suponer puerto equivocado. |
| `red.py` | `TIMEOUT_CONEXION` / `TIMEOUT_LECTURA` | 5,0 / 2,0 | s | Tiempo máximo para conectar y para que llegue algo. |
| `secuencia.py` | `TOLERANCIA`, `ESPERA_ARRANQUE` | 0,01, 2,0 | rad, s | Cuándo se da un punto por alcanzado y cuánto se espera a que arranque el programa. |
| `simulador.py` | `MAX_PREVIEW`, `PASOS_TRAMO`, `DURACION_TRAMO` | 20,0, 20, 1,0 | s, pasos, s | Duración máxima de `previsualizar` (bloquea el hilo principal), pasos de interpolación y segundos por tramo. |
| `ensenar.py` | `VELOCIDAD`, `ACELERACION` | 0,1 / 0,2 | rad/s / rad/s² | Velocidad y aceleración iniciales de cada `movej`; se cambian con `ajustar` dentro de los límites de `ur.py`. |
| `ensenar.py` | `ROBOTS`, `SECUENCIAS` | `datos/robots.json`, `datos/secuencias/` | | Rutas relativas al script. |

## Mejoras posibles (ideas, nada implementado ni probado)

**Gráfico y estado en `primaria.py` y `tiempo_real.py`.** `visualizar` podría guardar el último `q` de cada `HiloLectorUR` y mostrar las dos interfaces comparadas (pregunta 7 del enunciado: retraso entre URSim y el simulador). No implementado.

**Registro de órdenes en fichero.** Anotar con hora cada `movej` y `stopj` enviados en `datos/registro.txt` (unas 3 líneas en `Reproductor`). El enunciado no lo pide; no se ha añadido.

**Trayectoria suave entre puntos.** Hoy el robot se para en cada punto: `movej(q, a, v)` planifica un perfil trapezoidal que acaba con velocidad cero, y el `Reproductor` no envía el siguiente hasta que `isProgramRunning` baja. Fuente: el manual de URScript (`fuentes/manuales/scriptmanualG5_.pdf`, entrada de `movej`; no contrastado en el PDF).

| Opción | Cómo | Coste |
|---|---|---|
| Blend | `movej(q, a, v, 0, r)` con `r > 0` (en **metros**, aunque el movimiento sea articular): el robot redondea la esquina sin parar. Solo funciona entre movimientos del **mismo programa**: habría que enviar un bloque `def prog(): movej(...) movej(...) end`. | El robot ya no pasa exactamente por el punto, así que `TOLERANCIA` y el seguimiento punto a punto del `Reproductor` dejan de valer; hay que repensar la supervisión. Radios que se solapan dan error. |
| Interpolador propio | Calcular en Python la velocidad de cada articulación a partir del punto siguiente y enviar `speedj` a ritmo fijo (lo hizo `claude_1`, ejercicio 4: 0,04 rad de retraso frente a 0,6–0,8 rad con `movej` cortos). | Pasa a ser nuestro el límite de aceleración y la parada de emergencia. `speedj` con ganancia alta es agresivo en el robot físico. |
| `servoj` / RTDE | Streaming de posiciones a 125–500 Hz. | Sale del alcance de «sockets en crudo»; solo como alternativa declarada. |

Primero se probaría en URSim, nunca en el UR3e directamente.

## Limitaciones conocidas (sin resolver)

- Cualquier mensaje tipo 20 con subtipo 6 o 10 (error o excepción de programa) detiene la secuencia, **sin mirar `reportLevel`**: es lo más seguro, pero un aviso informativo del robot también pararía un movimiento. No se ha podido comprobar qué niveles emite un UR3e.
- El formato de 251 B del subpaquete de articulaciones y el offset 252 del tiempo real **no están verificados con un robot real**; si un robot manda otro tamaño, `ur.py` lanza `ErrorRed` en lugar de adivinar.
- **Datos viejos tras una vista previa (D20, aceptado por Josu):** `Simulador.previsualizar` bloquea el hilo principal hasta `MAX_PREVIEW` s; mientras tanto los mensajes del robot se acumulan en el socket y, al terminar, se procesan de golpe. Un `g` pulsado justo después de `v` podría guardar una posición vieja. Con el robot en movimiento no ocurre: `previsualizar` solo se acepta con el `Reproductor` en `LIBRE`.
- Un mensaje del robot mal formado ya no se descarta (como en la auditoría): `ensenar` lo trata como conexión perdida y reconecta (≈ 2 s); con un movimiento en curso, `stopj` y `PARADA`, igual que antes.
- `Reproductor` en `MOVIENDO` no tiene vigilante de tiempo: si `isProgramRunning` no baja nunca (programa pausado en el pendant), espera hasta que el usuario cancele con `c`. No se avisa por duración (D14).
- Una lista anidada 5000 niveles en un fichero de secuencia ya no se captura (`RecursionError`): se quitó como validación absurda (D17).
- El modo del robot (`robotMode`) no bloquea ningún movimiento porque su decodificación no está verificada con un robot real.
- `UR3eRG2` abre siempre la ventana (`gui=True` fijo): no se puede ejecutar sin pantalla.
- Los formatos de tipo 20 (subtipos 6 y 10), los 251 B del subpaquete 1 y el offset 252 del tiempo real salen del enunciado a través de `claude_2` y **no están verificados** con un robot (ver [pruebas](pruebas.md)).
