# Decisiones

Numeración fija: D1, D2… (nunca se renumera). Cada una lleva contexto, opciones, la elegida y por qué, y la marca **«distinto»** si se aparta de lo que pide el enunciado o de lo que haría la clase: esas son la materia prima de la memoria.

D1–D5 vienen de las versiones de partida y se aplicaron a `src/` el 2026-10-14. D6–D9 son de esa misma sesión (fase 1: código escrito por la IA, pendiente de revisión de Josu). D10–D11 son de la revisión de robustez de la capa 1 (`red.py`) D12–D13 de la capa 2 (`ur.py`) y D14–D15 de la capa 3 (`secuencia.py`, `simulador.py`).

## D1 – Un solo módulo de protocolo, reutilizado por todos los scripts

- **Contexto:** el código del año pasado repetía el parser en varios archivos con pequeñas variaciones (`claude_1/docs/06`, apartado C).
- **Opciones:** (a) un parser por script; (b) un módulo importable con la lectura del robot, y las tareas de cada nivel lo usan.
- **Elegida:** (b), en `ur.py`. **Porque** un arreglo del parser se hace una vez y vale para todos los niveles.
- **Distinto:** no.
- **Commit:** `fe2a2de`

## D2 – Leer el mensaje entero y trocearlo en memoria

- **Contexto:** TCP es un flujo de bytes: `recv(n)` puede devolver menos de `n` bytes. La versión a mano lee campo a campo con `recv` sin bucle y se desalinea (ver F5 en [depuración](depuración.md)).
- **Opciones:** (a) `recv` directo por campo; (b) `recv_exact` en bucle (Claude 1); (c) acumular en un `bytearray` y cortar mensajes por longitud, rechazando longitudes imposibles (> 65 536 B) por si el buffer se desalinea (`extraer_mensaje` en Claude 2).
- **Elegida:** (c), con el buffer dentro de `ClienteUR` y vaciado en cada reconexión. **Porque** se recupera solo de una desalineación y no se queda bloqueado esperando bytes que no llegan. Una prueba de mutación confirmó que sin vaciar el buffer al reconectar los 20 bytes de la conexión anterior desalinean el mensaje nuevo. Los 251 B del subpaquete 1 siguen **sin verificar** contra un robot real.
- **Distinto:** no.
- **Commit:** `fe2a2de`

## D3 – Los hilos de lectura solo guardan el último estado; el hilo principal dibuja

- **Contexto:** hay un hilo por robot y un único visualizador PyBullet.
- **Opciones:** (a) cada hilo llama a `move_robot`; (b) cada hilo guarda su último estado (con `Lock`) y el hilo principal lo dibuja.
- **Elegida:** (b), clase `LectorUR`. **Porque** Claude 1 lo adoptó con el argumento de que PyBullet no es seguro entre hilos (afirmación de su documentación, no comprobada aquí), y además los `print` quedan ordenados. `ultimo_q()` devuelve una copia (prueba) para que quien lo llama no modifique el estado guardado.
- **Distinto:** no.
- **Commit:** `fe2a2de`, `800dd7d`

## D4 – Una dirección `ip`+`puerto` por robot, en un `robots.json`

- **Contexto:** con dos URSim en el mismo PC (NAT de VirtualBox) los robots comparten IP `127.0.0.1` y solo cambia el puerto (30001 y 30011); con robots reales cambia la IP (laboratorio: `10.172.21.203` a `.206`).
- **Opciones:** (a) IPs y puertos fijos en el código; (b) `robots.json` con nombre, IP, puerto y posición de la base (Claude 2); (c) `ip[:puerto]` en la línea de comandos (Claude 1).
- **Elegida:** (b) para `varios`, y `--ip`/`--puerto` para un solo robot. **Porque** cambiar de robot no obliga a tocar el código, y en la defensa piden cambiar IP o puerto en caliente.
- **Distinto:** no.
- **Commit:** `800dd7d`

## D5 – Un robot falso con tramas reales para probar sin hardware

- **Contexto:** URSim y el robot físico no siempre están disponibles, y el simulador de Claude 1 (`claude_1/simulador_ur.py`) no simula `isProgramRunning` ni `stopj`, así que la máquina de estados no se podía probar entera con él.
- **Opciones:** (a) probar solo con URSim o el robot; (b) el simulador archivado de Claude 1; (c) un robot falso propio en `pruebas/robot_falso.py`.
- **Elegida:** (c). **Porque** simula movimiento a la velocidad pedida, `isProgramRunning` mientras se mueve, `stopj`, parada de protección y errores del robot, y solo escucha en `127.0.0.1`. **Aviso:** es nuestra interpretación del protocolo, no un robot (ver [pruebas](pruebas.md)); no se lanza en los puertos 30001–30013 con URSim abierto (VirtualBox los reenvía): se usan 31xxx.
- **Distinto:** no.
- **Commit:** `800dd7d`

## D6 – Una clase `Simulador` propia sobre la librería `UR3e_rg2`

- **Contexto:** Josu pidió una clase dedicada para el simulador «si la librería no simplifica lo suficiente».
- **Opciones:** (a) usar `UR3eRG2` directamente en cada tarea (como `claude_2`); (b) una clase fina que esconda sus detalles.
- **Elegida:** (b), `simulador.py` (≈ 40 líneas). **Porque** la librería no esconde cuatro cosas, y en `claude_2` cada script las resolvía por su cuenta: (1) el primer robot ya existe con id 0 y los demás se crean con `spawn_robot` (en la prueba, el segundo recibió el id 2: el suelo ocupa el 1); (2) `move_robot` alarga en sitio la lista que recibe (`joint_values += ...`), así que hay que pasarle una copia; (3) colocar la base del primer robot exige llamar a `pybullet` directamente; (4) la interpolación de la previsualización estaba en el script de enseñar. Se comprobó con la librería real (`pruebas/humo_pybullet.py`).
- **Distinto:** no (es lo que pidió Josu), pero con un matiz: `Simulador` acepta un visualizador falso en el constructor para poder probarla sin ventana.
- **Commit:** `2f0f5f5`

## D7 – Velocidad y aceleración por defecto bajas y límites que no se pueden saltar

- **Contexto:** el enunciado fija 0,3 rad/s y 0,5 rad/s² como límites en el robot real (según `claude_2`); `CLAUDE.md` pide velocidades bajas en físico (`--v 0.1 --a 0.2`) y `speedj`/`movej` rápidos son agresivos.
- **Opciones:** (a) por defecto 0,3 / 0,5, el máximo permitido (`claude_2`); (b) por defecto 0,1 / 0,2 y rechazo de lo que pase de 0,3 / 0,5.
- **Elegida:** (b). `UrPrimaria.movej` es la que lo impone (no el script de enseñar): lanza `ValueError` y no envía nada si la velocidad, la aceleración o los ángulos están fuera de rango; y `main.py ensenar` lo rechaza al arrancar (`--v 0.5` → código de salida 2). `movej` además exige `velocidad=` y `aceleracion=` por nombre, para no mezclar el orden (el código del año pasado mezclaba `(v, a)`).
- **Distinto:** sí, respecto a `claude_2`: más lento por defecto. Se sube con `--v` y `--a` hasta los límites.
- **Commit:** `fe2a2de`, `800dd7d`

## D8 – Reparto en módulos: red / ur / simulador / secuencia / tareas / main

- **Contexto:** Josu pidió una clase de red, otra que la use para hablar con el UR, y un script de funciones que centralice los controladores.
- **Opciones:** (a) tres módulos tal cual; (b) añadir `secuencia.py` y una clase base `ClienteUR`.
- **Elegida:** (b). **Porque** la máquina de estados de enseñar y reproducir (≈ 100 líneas con estado propio) no cabe como «función» sin volverse ilegible, y las dos interfaces del UR (30001 y 30003) comparten la conexión y el buffer y solo se diferencian en cómo cortan un paquete. `secuencia.py` no abre sockets ni ventanas: recibe el robot y los mensajes.
- **Distinto:** sí, respecto al reparto que pidió Josu: dos piezas más (`ClienteUR` y `secuencia.py`). Para revisar.
- **Commit:** `fe2a2de`, `e89e1da`, `800dd7d`

## D9 – Un robot es «varios robots con uno»

- **Contexto:** en `claude_2` `primaria.py` tenía su propio bucle y `varios_robots.py` otro distinto con hilos.
- **Opciones:** (a) un bucle por tarea; (b) una sola mecánica (`LectorUR` + `_dibujar`) para `primaria`, `tiempo-real` y `varios`.
- **Elegida:** (b). **Porque** hay un solo bucle de dibujo y de reconexión que depurar. Coste: con un solo robot también se usa un hilo, y las líneas de información salen una vez por segundo (`[robot] 10 estados/s | q (grados): ...`) en lugar de en cada mensaje.
- **Distinto:** no.
- **Commit:** `800dd7d`

## D10 – Una clase de excepción por módulo: `ErrorRed`, `ErrorUR`, `ErrorSecuencia` y `ErrorSimulador`

- **Contexto:** los errores de socket salían crudos y de seis tipos distintos (F9), y las capas de arriba capturaban a la vez `OSError`, `ConnectionError`, `socket.timeout`, `ValueError`, `struct.error` y hasta `RecursionError`; el mismo `ValueError` significaba «buffer desalineado» y «argumento mal puesto». El objetivo es que los errores se resuelvan en la capa más baja y que cada capa solo conozca las excepciones de la inmediatamente inferior.
- **Opciones:** (a) dejar `OSError` y mejorar solo los mensajes; (b) clases que heredan de `OSError`, que no obligarían a cambiar a los llamadores; (c) una clase independiente por módulo, sin heredar de `OSError`.
- **Elegida:** (c). La jerarquía completa es esta, y no hay más clases (todas heredan de `Exception` y son ramas distintas del árbol):

  | Módulo | Clase | Qué significa | Quién la captura |
  |---|---|---|---|
  | `red.py` | `ErrorRed`, `ErrorRedTimeout(ErrorRed)` | Fallo de la conexión TCP; el segundo, «no llegó nada en `timeout_lectura` s» (la conexión sigue abierta) | solo `ur.py` |
  | `ur.py` | `ErrorUR` | Envuelve a `ErrorRed` y a los fallos de formato (`struct.error`, `ValueError` de decodificación, `q` no válido, falta de estados) con `raise ... from e` | `Reproductor` (dentro) y `tareas.py` (el que sale del generador de mensajes) |
  | `secuencia.py` | `ErrorSecuencia` | No se puede leer o guardar el fichero de la secuencia (ilegible, vacío, enorme, con puntos no válidos, disco) | `tareas.py` |
  | `simulador.py` | `ErrorSimulador` | Falta la librería, se cerró la ventana, PyBullet falló | `tareas.py` / `main.py` (capa 4) |

  `ValueError`/`TypeError` quedan para argumentos mal puestos (IP, puerto, timeouts, velocidad, un `q` con `nan`...): son errores de configuración o de programación, y `main.py` los valida antes de crear nada (capa 4). **Un solo `except Exception` fuera de `main` y del bucle de un hilo:** `Simulador._libreria()`, acotado a la llamada a PyBullet/`UR3eRG2` (código de terceros sin una jerarquía de errores útil: `pybullet.error`, `SystemError`, `ImportError`...), que siempre convierte en `ErrorSimulador ... from e`.
  **Porque** con (b) cualquier `OSError` ajeno (p. ej. al guardar un fichero) seguiría pareciendo «un fallo de conexión». Los mensajes de cada capa añaden una frase corta y encadenan la causa, sin repetirse en cascada. Toda conexión perdida cierra el socket, de modo que `abierta` es fiable.
- **Distinto:** no (el enunciado no dice nada).
- **Commit:** `e639b91` (`ErrorRed`), `0cac920` (`ErrorUR`), `0cff77d` (`ErrorSecuencia`, `ErrorSimulador`)

## D11 – `ConexionTCP` valida sus argumentos y solo acepta IPs, no nombres

- **Contexto:** IP y puerto llegan de la línea de comandos y de `robots.json`; los valores raros daban errores distintos o, peor, conectaban a otro puerto o a `127.0.0.1` en silencio (F7). Resolver un nombre puede bloquear el hilo decenas de segundos y `timeout_conexion` no lo limita.
- **Opciones:** (a) validar fuera, en `main.py` y en `cargar_robots`; (b) validar en `ConexionTCP.__init__`, el único punto por el que pasan todos; (c) además, permitir nombres de host.
- **Elegida:** (b) sin (c): `ip` es una IP literal (`ipaddress.ip_address`), `puerto` un entero entre 1 y 65535 y los timeouts números con `0 < t <= 3600` s; si no, `ValueError` en español al crear el objeto. **Porque** hay una sola comprobación y los robots del laboratorio se dan por IP. Coste: `--ip localhost` ya no vale, hay que escribir `127.0.0.1`.
- **Distinto:** no.
- **Commit:** `e639b91`

## D12 – Un solo reloj para «datos actuales»: `estado_fresco()` y `PLAZO_ESTADO`

- **Contexto:** un robot mudo o que gotea mantenía la conexión abierta y `ultimo_q()` seguía dando un `q` viejo; `movej` se enviaba sin saber nada del robot (F11, F12).
- **Opciones:** (a) un plazo para la lectura y otro para el movimiento; (b) una sola función `ClienteUR.estado_fresco()` («llegó un estado válido hace menos de `PLAZO_ESTADO` s», con `time.monotonic()`) que usan `ultimo_q()` y `movej`.
- **Elegida:** (b), con `PLAZO_ESTADO = 2,0 s` (igual que `timeout_lectura`; un UR manda 125 estados/s por la interfaz primaria). `movej` lanza `ErrorUR` y no envía nada si no hay estado fresco; `stopj` **nunca** lo exige (frenar siempre se intenta) y con un valor inválido frena con `ACELERACION_MAX`. En los tests se reduce la constante en lugar de esperar. **Porque** dos relojes podrían discrepar y la regla es «ante la duda, no mover y avisar». Un `ErrorUR` (también por falta de estados) hace que el cliente se cierre y se reconecte.
- **Distinto:** sí, respecto a `claude_2` (que enviaba `movej` sin comprobarlo): es más estricto.
- **Commit:** `0cac920`

## D13 – Formato inesperado del robot: `ErrorUR` una vez por conexión, no adivinar

- **Contexto:** si el subpaquete de articulaciones no mide 251 B, antes se escribía un aviso por mensaje y se decodificaba igualmente con los desplazamientos de 251 B (F13). Los 251 B y el offset 252 no están verificados con un robot real.
- **Opciones:** (a) tolerar tamaños mayores y avisar; (b) lanzar `ErrorUR` con el tamaño recibido, el esperado y la constante que hay que tocar (`TAM_SUB_JOINTS`).
- **Elegida:** (b). **Porque** un `q` decodificado con desplazamientos equivocados es finito y creíble, y la regla es no mover con datos dudosos: sin estados válidos no hay `movej` (D12). El motivo se escribe una sola vez (no en cada reintento de `LectorUR`). Igual de estrictos son los límites de lectura de `q` (±(2π + 0,2) rad, con margen por si el robot está en el tope de una articulación) frente a los de envío (±2π). El nivel (`reportLevel`) de los mensajes de error **no se mira**: cualquier error o excepción del robot detiene la secuencia (limitación documentada en [arquitectura](arquitectura.md)).
- **Distinto:** no.
- **Commit:** `0cac920`

## D14 – El `Reproductor` espera un estado reciente, solo la protección y la emergencia bloquean, y si no puede frenar lo grita

- **Contexto:** al exigir `movej` un estado fresco (D12), una vista previa larga hacía fallar el siguiente `e` (F17); el `Reproductor` enviaba `movej` con el robot parado por seguridad (F16) y se tragaba los fallos del `stopj` (F15).
- **Opciones:** (a) subir `PLAZO_ESTADO` o saltarse la comprobación tras una vista previa; (b) una fase `ESPERANDO_ESTADO` con tope (`ESPERA_ESTADO` = 3 s) que envía el primer `movej` cuando llega un estado reciente; para bloquear: (c) `protegido` y `emergencia`, o (d) también el modo del robot (`robotMode` distinto de 7).
- **Elegidas:** (b) y (c). **Porque** (a) quitaría la seguridad de D12 justo donde hace falta; y (d) se descarta porque la decodificación de esos campos no está verificada con un robot real y no se debe inutilizar el programa por una suposición: el modo se guarda y se muestra en un mensaje, pero no bloquea. Si no se puede enviar el `stopj` se escribe una vez, en mayúsculas, que el robot puede seguir moviéndose y que hay que pararlo con el botón del pendant; `cancelar` deja siempre el `Reproductor` libre y nunca se escribe «detenido» sin haber enviado la parada. Un `ErrorUR` del `Reproductor` no sale: pasa a fallo con parada.
- **Distinto:** sí, respecto a `claude_2` (no esperaba ni comprobaba nada).
- **Commit:** `0cff77d`

## D15 – Ficheros de secuencia con tope y guardado atómico; el simulador valida en su frontera

- **Contexto:** un fichero de secuencia es un dato que viene de fuera (F18) y los valores que llegan al simulador acaban dentro de una librería de terceros que no los comprueba (F19).
- **Opciones:** (a) validar en `tareas.py`; (b) validar dentro de `Secuencia.cargar` y `Simulador` y escribir con un temporal.
- **Elegida:** (b). Topes: 1 MB y 1000 puntos por fichero, cada punto una lista de 6 números en ±2π; `guardar` escribe en `ruta.tmp` y `os.replace`. El simulador acepta `q` en ±(2π + 0,2) rad (el mismo `LIMITE_Q_LECTURA` de `ur.py`) y una base en ±100 m/rad, y limita la vista previa a `MAX_PREVIEW` = 20 s. **Porque** así la comprobación está en un solo sitio y las capas de arriba reciben un `ErrorSecuencia`/`ErrorSimulador` con el motivo en español, no un traceback.
- **Distinto:** no.
- **Commit:** `0cff77d`
