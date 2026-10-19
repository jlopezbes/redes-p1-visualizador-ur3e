# Decisiones

Numeración fija: D1, D2… (nunca se renumera). Cada una lleva contexto, opciones, la elegida y por qué, y la marca **«distinto»** si se aparta de lo que pide el enunciado o de lo que haría la clase: esas son la materia prima de la memoria.

D1–D5 vienen de las versiones de partida y se aplicaron a `src/` el 2026-10-14. D6–D9 son de esa misma sesión (fase 1: código escrito por la IA, pendiente de revisión de Josu). D10–D11 son de la revisión de robustez de la capa 1 (`red.py`) D12–D13 de la capa 2 (`ur.py`) D14–D15 de la capa 3 (`secuencia.py`, `simulador.py`) y D16 de la capa 4 (`main.py`, `tareas.py`). **D23–D25 son de la reorganización por niveles y la web de control (2026-10-17)**. **D17–D21 son de la limpieza por capas (2026-10-15/16)**, que simplificó parte de lo anterior: las decisiones afectadas llevan una línea **«Hoy»** que dice qué sigue valiendo. El texto original se conserva como historia.

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
- **Hoy (D17, D18):** la clase se llama `HiloLectorUR`, sin `Lock` (un solo hilo escribe) y `ultimo_q()` es el atributo `q`.
- **Commit:** `fe2a2de`, `800dd7d`

## D4 – Una dirección `ip`+`puerto` por robot, en un `robots.json`

- **Contexto:** con dos URSim en el mismo PC (NAT de VirtualBox) los robots comparten IP `127.0.0.1` y solo cambia el puerto (30001 y 30011); con robots reales cambia la IP (laboratorio: `10.172.21.203` a `.206`).
- **Opciones:** (a) IPs y puertos fijos en el código; (b) `robots.json` con nombre, IP, puerto y posición de la base (Claude 2); (c) `ip[:puerto]` en la línea de comandos (Claude 1).
- **Elegida:** (b) para `varios`, y `--ip`/`--puerto` para un solo robot. **Porque** cambiar de robot no obliga a tocar el código, y en la defensa piden cambiar IP o puerto en caliente.
- **Distinto:** no.
- **Hoy (D21):** el JSON lleva solo `nombre` e `ip`; el puerto es el del protocolo y la posición de cada base la decide el simulador. `--ip` y `--puerto` siguen para un solo robot.
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
- **Hoy (D21):** `agregar_robot(nombre)` ya no recibe la posición: coloca los robots en fila a 1 m. Ya no hay colocación del primer robot con `pybullet` (3.) ni `with`: se usa `try/finally` y `cerrar()` (D17).
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
- **Hoy (D18):** `ClienteUR` es una clase única para las dos interfaces (ya no hay base ni subclases `UrPrimaria`/`UrTiempoReal`) y decodifica los mensajes antes de entregarlos.
- **Hoy (D23):** `tareas.py` y `main.py` desaparecen: cada script de `src/` (`primaria.py`, `tiempo_real.py`, `ensenar.py`) es su propio punto de entrada y los módulos están en `src/librerias/`. El reparto red / `ur` / `simulador` / `secuencia` sigue igual.
- **Commit:** `fe2a2de`, `e89e1da`, `800dd7d`

## D9 – Un robot es «varios robots con uno»

- **Contexto:** en `claude_2` `primaria.py` tenía su propio bucle y `varios_robots.py` otro distinto con hilos.
- **Opciones:** (a) un bucle por tarea; (b) una sola mecánica (`LectorUR` + `_dibujar`) para `primaria`, `tiempo-real` y `varios`.
- **Elegida:** (b). **Porque** hay un solo bucle de dibujo y de reconexión que depurar. Coste: con un solo robot también se usa un hilo, y las líneas de información salen una vez por segundo (`[robot] 10 estados/s | q (grados): ...`) en lugar de en cada mensaje.
- **Distinto:** no.
- **Hoy (D17):** una sola función `visualizar(clientes)`; `main.py` crea el cliente que toca y se lo pasa. El bucle `_dibujar` está dentro de ella.
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
- **Hoy (D19):** `ErrorUR` desapareció: `ErrorRed` es la única excepción de comunicación y `ur.py` la deja pasar. Siguen `ErrorRedTimeout`, `ErrorSecuencia` y `ErrorSimulador`. `main.py` ya no captura `ErrorSecuencia` (la captura `_comando`).
- **Commit:** `e639b91` (`ErrorRed`), `0cac920` (`ErrorUR`), `0cff77d` (`ErrorSecuencia`, `ErrorSimulador`)

## D11 – `ConexionTCP` valida sus argumentos y solo acepta IPs, no nombres

- **Contexto:** IP y puerto llegan de la línea de comandos y de `robots.json`; los valores raros daban errores distintos o, peor, conectaban a otro puerto o a `127.0.0.1` en silencio (F7). Resolver un nombre puede bloquear el hilo decenas de segundos y `timeout_conexion` no lo limita.
- **Opciones:** (a) validar fuera, en `main.py` y en `cargar_robots`; (b) validar en `ConexionTCP.__init__`, el único punto por el que pasan todos; (c) además, permitir nombres de host.
- **Elegida:** (b) sin (c): `ip` es una IP literal (`ipaddress.ip_address`), `puerto` un entero entre 1 y 65535 y los timeouts números con `0 < t <= 3600` s; si no, `ValueError` en español al crear el objeto. **Porque** hay una sola comprobación y los robots del laboratorio se dan por IP. Coste: `--ip localhost` ya no vale, hay que escribir `127.0.0.1`.
- **Distinto:** no.
- **Hoy (D17):** se valida la IP (solo literal) y el puerto (1–65535). Ya no se validan los timeouts: son las constantes `TIMEOUT_CONEXION` y `TIMEOUT_LECTURA`.
- **Commit:** `e639b91`

## D12 – Un solo reloj para «datos actuales»: `estado_fresco()` y `PLAZO_ESTADO`

- **Contexto:** un robot mudo o que gotea mantenía la conexión abierta y `ultimo_q()` seguía dando un `q` viejo; `movej` se enviaba sin saber nada del robot (F11, F12).
- **Opciones:** (a) un plazo para la lectura y otro para el movimiento; (b) una sola función `ClienteUR.estado_fresco()` («llegó un estado válido hace menos de `PLAZO_ESTADO` s», con `time.monotonic()`) que usan `ultimo_q()` y `movej`.
- **Elegida:** (b), con `PLAZO_ESTADO = 2,0 s` (igual que `timeout_lectura`; un UR manda 125 estados/s por la interfaz primaria). `movej` lanza `ErrorUR` y no envía nada si no hay estado fresco; `stopj` **nunca** lo exige (frenar siempre se intenta) y con un valor inválido frena con `ACELERACION_MAX`. En los tests se reduce la constante en lugar de esperar. **Porque** dos relojes podrían discrepar y la regla es «ante la duda, no mover y avisar». Un `ErrorUR` (también por falta de estados) hace que el cliente se cierre y se reconecte.
- **Distinto:** sí, respecto a `claude_2` (que enviaba `movej` sin comprobarlo): es más estricto.
- **Hoy: SUSTITUIDA por D20.** `estado_fresco()` y `PLAZO_ESTADO` ya no existen. Se conserva que `stopj` nunca depende de nada y que `movej` se niega ante argumentos fuera de límites.
- **Commit:** `0cac920`

## D13 – Formato inesperado del robot: `ErrorUR` una vez por conexión, no adivinar

- **Contexto:** si el subpaquete de articulaciones no mide 251 B, antes se escribía un aviso por mensaje y se decodificaba igualmente con los desplazamientos de 251 B (F13). Los 251 B y el offset 252 no están verificados con un robot real.
- **Opciones:** (a) tolerar tamaños mayores y avisar; (b) lanzar `ErrorUR` con el tamaño recibido, el esperado y la constante que hay que tocar (`TAM_SUB_JOINTS`).
- **Elegida:** (b). **Porque** un `q` decodificado con desplazamientos equivocados es finito y creíble, y la regla es no mover con datos dudosos: sin estados válidos no hay `movej` (D12). El motivo se escribe una sola vez (no en cada reintento de `LectorUR`). Igual de estrictos son los límites de lectura de `q` (±(2π + 0,2) rad, con margen por si el robot está en el tope de una articulación) frente a los de envío (±2π). El nivel (`reportLevel`) de los mensajes de error **no se mira**: cualquier error o excepción del robot detiene la secuencia (limitación documentada en [arquitectura](arquitectura.md)).
- **Distinto:** no.
- **Hoy (D17, D19):** sigue valiendo lo del tamaño de 251 B (ahora `ErrorRed`, en `ClienteUR._leer_estado`). Ya no se valida el rango de `q` al leer ni se sanea el texto de los errores del robot (`MAX_TEXTO_ERROR` desapareció).
- **Commit:** `0cac920`

## D14 – El `Reproductor` espera un estado reciente, solo la protección y la emergencia bloquean, y si no puede frenar lo grita

- **Contexto:** al exigir `movej` un estado fresco (D12), una vista previa larga hacía fallar el siguiente `e` (F17); el `Reproductor` enviaba `movej` con el robot parado por seguridad (F16) y se tragaba los fallos del `stopj` (F15).
- **Opciones:** (a) subir `PLAZO_ESTADO` o saltarse la comprobación tras una vista previa; (b) una fase `ESPERANDO_ESTADO` con tope (`ESPERA_ESTADO` = 3 s) que envía el primer `movej` cuando llega un estado reciente; para bloquear: (c) `protegido` y `emergencia`, o (d) también el modo del robot (`robotMode` distinto de 7).
- **Elegidas:** (b) y (c). **Porque** (a) quitaría la seguridad de D12 justo donde hace falta; y (d) se descarta porque la decodificación de esos campos no está verificada con un robot real y no se debe inutilizar el programa por una suposición: el modo se guarda y se muestra en un mensaje, pero no bloquea. Si no se puede enviar el `stopj` se escribe una vez, en mayúsculas, que el robot puede seguir moviéndose y que hay que pararlo con el botón del pendant; `cancelar` deja siempre el `Reproductor` libre y nunca se escribe «detenido» sin haber enviado la parada. Un `ErrorUR` del `Reproductor` no sale: pasa a fallo con parada.
- **Distinto:** sí, respecto a `claude_2` (no esperaba ni comprobaba nada).
- **Hoy (D20):** la fase `ESPERANDO_ESTADO` y `ESPERA_ESTADO` se quitaron. Siguen valiendo (c) —solo bloquean `protegido` y `emergencia`— y el aviso en mayúsculas si el `stopj` no sale (`_parar_robot` ya no devuelve un booleano: avisa de ambas cosas).
- **Commit:** `0cff77d`

## D15 – Ficheros de secuencia con tope y guardado atómico; el simulador valida en su frontera

- **Contexto:** un fichero de secuencia es un dato que viene de fuera (F18) y los valores que llegan al simulador acaban dentro de una librería de terceros que no los comprueba (F19).
- **Opciones:** (a) validar en `tareas.py`; (b) validar dentro de `Secuencia.cargar` y `Simulador` y escribir con un temporal.
- **Elegida:** (b). Topes: 1 MB y 1000 puntos por fichero, cada punto una lista de 6 números en ±2π; `guardar` escribe en `ruta.tmp` y `os.replace`. El simulador acepta `q` en ±(2π + 0,2) rad (el mismo `LIMITE_Q_LECTURA` de `ur.py`) y una base en ±100 m/rad, y limita la vista previa a `MAX_PREVIEW` = 20 s. **Porque** así la comprobación está en un solo sitio y las capas de arriba reciben un `ErrorSecuencia`/`ErrorSimulador` con el motivo en español, no un traceback.
- **Distinto:** no.
- **Hoy (D17, D21):** `cargar` ya no limita el tamaño ni el número de puntos y `guardar` escribe directamente (sin `.tmp`); `cargar` sigue exigiendo 6 ángulos en ±2π por punto. El simulador no valida `q` ni posiciones; conserva `MAX_PREVIEW`.
- **Commit:** `0cff77d`

## D16 – Una sola salida de errores en `main()` y un solo `try/finally` en `ensenar_reproducir`

- **Contexto:** hasta la capa 3 los errores esperados llegaban a `main.py` como traceback (F20).
- **Elegida:** primero se crean los clientes y después el `Simulador` dentro de `with`, así un argumento malo falla antes de abrir la ventana sin escribir más validadores. `main()` traduce a una línea `Error: ...` en stderr: `ValueError`/`OSError` (argumentos, `robots.json`) -> código **2**; `ErrorUR`/`ErrorSimulador`/`ErrorSecuencia` -> **1**; Ctrl+C -> **0** (es la forma normal de parar); un fallo inesperado -> traceback y **1** (último `except Exception` de la aplicación). `ensenar_reproducir` cierra el robot en un `finally`, tras frenarlo si se mueve, en cualquier salida (`q`, Ctrl+C, ventana cerrada, bug); en vez de `time.sleep`, la reconexión espera con `comandos.get(timeout=ur.REINTENTO)`, y un EOF de la consola equivale a `q`. Se rechazan `b`, `l` y `g` con la secuencia parada o en espera.
- **Distinto:** no.
- **Hoy (D17, D19):** el `Simulador` va en `try/finally` (sin `with`) y, al salir, el robot se frena **antes** de cerrar la ventana. `main()` captura `ValueError` (2), `ErrorRed` y `ErrorSimulador` (1) y Ctrl+C (0); ya no captura `OSError` ni hay `except Exception` final: un fallo inesperado lo muestra Python con su traceback y código 1.
- **Hoy (D23):** no hay `main()` único: cada script tiene su propio bloque `if __name__ == "__main__"` con el mismo `try/except`, y los códigos de salida son 0 y 1 (el 2 era de `argparse`).
- **Commit:** `5150baf`

## D17 – Limpieza por capas: lo que no aporta se quita y la seguridad con el robot se queda

- **Contexto:** la auditoría de robustez subió `src/` de ≈ 545 a ≈ 800 líneas (más los tests y los docs) y Josu, que tiene que explicar cada línea en la defensa, lo veía excesivo. Pidió una limpieza de arriba (programa) a abajo (sockets), una capa cada vez, que él revisa antes de seguir. Cada capa fue una rama (`limpieza/1-main` … `limpieza/5-coherencia`, ya integradas en `main`).
- **Criterios aplicados** (los dio Josu al revisar cada capa):
  1. Una función auxiliar con 2 usos o menos se **inlina** (solo se dejan, marcadas «dudosa», las que un hilo necesita o las que duplicarían un bloque largo).
  2. Una función que solo reenvía a otra cambiando argumentos sobra (`visualizar_primaria`, `visualizar_tiempo_real` y `visualizar_varios` → `visualizar`).
  3. Una clase que solo envuelve un dato sobra (`UrPrimaria`/`UrTiempoReal` → `ClienteUR`). `Secuencia` se queda como lista con `guardar` y `cargar`.
  4. Un dato que viene dado no se lee de un fichero (puertos del protocolo, posición de los robots: D21).
  5. Un error se dice con un mensaje general y la causa probable y el programa cierra limpio: no se validan tipos de argumentos internos, `nan`, ni se añaden constantes o fases «por si acaso». Tampoco se duplica lo que Python ya hace (el traceback de una excepción inesperada).
  6. Si un dato es solo un dato, es un atributo, no un método (`HiloLectorUR.q`); si deriva de otro, una propiedad (`Reproductor.ocupado`).
  7. Los nombres explican lo que son (`LectorUR` → `HiloLectorUR`, `cerrar` → `desconectar`).
- **Lo que se conserva a propósito, por seguridad con el robot físico:** los límites de velocidad y aceleración de `movej`, `es_punto_valido` (rechaza grados enviados por error), `stopj` siempre, el aviso en mayúsculas si no se pudo frenar, la parada por `protegido`/`emergencia`/error del robot, el tamaño de 251 B, el aviso de puerto equivocado (`MAX_IGNORADOS`) y el tope de la vista previa (`MAX_PREVIEW`).
- **Resultado:** `src/` de 1176 a 817 líneas (−31 %, contando líneas en blanco y docstrings: `ur.py` 404 → 231, `secuencia.py` 275 → 185, `red.py` 115 → 90, `simulador.py` 107 → 77, `tareas.py` 194 → 167, `main.py` 81 → 67). Las pruebas pasaron de 149 a 122 (se quitaron las de lo que ya no existe y se añadieron otras).
- **Distinto:** sí, respecto a la auditoría (D10–D16): es la poda que Josu había aplazado.
- **Commit:** `e5ef55b` (capa 1), `5cdf084` y `ea88e21` (capa 2), `8dd4132` y `4a61cb8` (capa 3), `ad37f9b` y `1cbf228` (capa 4), `493e64b` y `7c6ec6d` (coherencia y tests)

## D18 – `ClienteUR` es el portal entre la red y el robot: una clase, y lo que sube ya está decodificado

- **Contexto:** `ClienteUR` solo conectaba y cortaba paquetes; `UrPrimaria` y `UrTiempoReal` aportaban solo cómo cortar y qué decodificar; `Reproductor` y `LectorUR` recibían bytes o tipos de mensaje y llamaban a funciones `leer_*` de `ur.py`.
- **Opciones:** (a) mantener la herencia; (b) una clase con `tiempo_real=False/True` y la decodificación dentro como métodos privados.
- **Elegida:** (b). **Porque** los dos paquetes empiezan por la longitud, así que cortar es lo mismo (solo cambia el mínimo) y lo único distinto es decodificar; y las capas de arriba no tienen por qué conocer bytes ni tipos de mensaje: `mensajes()` entrega diccionarios (`q`, `ejecutando`, `protegido`, `emergencia`, `modo`) o `{"error": texto}`. Desaparecen la base abstracta y las dos subclases. **Riesgo documentado:** en tiempo real no llegan `ejecutando`, `protegido`, `emergencia` ni errores, así que `ensenar` usa siempre la primaria; y un puerto que no corresponde al formato se detecta con `MAX_IGNORADOS` (F22).
- **Distinto:** no.
- **Commit:** `4a61cb8`

## D19 – Una sola excepción de comunicación (`ErrorRed`) y las clases de error propias se quedan

- **Contexto:** `ErrorUR` era la misma clase vacía que `ErrorRed`, y `ur.py` tenía tres conversiones de una a otra. Josu preguntó para qué valían las cuatro clases de error y, tras la explicación, decidió dejarlas: ayudan a entender el tipo de error.
- **Opciones:** (a) una clase por módulo (D10); (b) excepciones de Python (`ConnectionError`, `TimeoutError`, `RuntimeError`); (c) una sola para la comunicación (`ErrorRed`, con `ErrorRedTimeout` para el timeout) más `ErrorSecuencia` y `ErrorSimulador`.
- **Elegida:** (c). `ur.py` lanza `ErrorRed` también para los fallos de protocolo y `main`, `tareas` y `secuencia` la importan de `red`. **Porque** una clase que solo cambia de nombre no aporta, y las demás sí dicen qué falló. Los mensajes llevan la causa probable («robot apagado o IP de otra red?», «puerto equivocado?»).
- **Distinto:** no.
- **Commit:** `4a61cb8`, `ad37f9b`

## D20 – Sin «estado fresco»: el timeout de lectura basta, y los límites de `movej` no dependen del último estado

- **Contexto:** D12 y D14 añadieron `estado_fresco()` (plazo de 2 s), la fase `ESPERANDO_ESTADO` y una comprobación en `movej` y `guardar_punto`. Tras limpiar `_paquetes`, casi no aportaba: si el robot calla, `recibir` da `ErrorRedTimeout` a los 2 s y `HiloLectorUR` pone `q = None`; y `movej` lleva ángulos absolutos, así que el robot parte de donde esté.
- **Opciones:** (a) conservarlo; (b) quitarlo y exponer `q` como atributo; (c) además, descartar lo acumulado en el socket tras una vista previa (`vaciar()`, ≈ 12 líneas).
- **Elegida:** (b). Josu descartó (c): con el robot parado un dato viejo no importa, y mientras se mueve el bucle procesa los mensajes sin bloquearse. **Límite aceptado:** un `g` justo después de `v` puede guardar una posición vieja (ver [arquitectura](arquitectura.md)). Si `ejecutar` o `reanudar` se encuentran sin conexión, `movej` falla con `ErrorRed` y el `Reproductor` entra en `PARADA` con el motivo. Un mensaje del robot mal formado ya no se salta: provoca una reconexión (≈ 2 s).
- **Distinto:** sí, respecto a D12 y D14.
- **Commit:** `4a61cb8`, `ad37f9b`

## D21 – Los robots simulados se colocan solos en fila y `robots.json` lleva solo nombre e IP

- **Contexto:** `robots.json` tenía IP, puerto y posición de la base. Los puertos los fija el protocolo del UR y las posiciones en el simulador son siempre las mismas; leerlas obligaba a validarlas (`LIMITE_POSE`, `_seis_numeros`, `ORIGEN`, colocar el primer robot con `pybullet`).
- **Opciones:** (a) dejar todo en el JSON; (b) JSON solo con `nombre` e `ip`, y `Simulador.agregar_robot(nombre)` pone el primer robot en el origen y cada siguiente 1 m más lejos en x.
- **Elegida:** (b). Si otra función necesita las posiciones, se pasan como argumento; el JSON solo sería el intermediario si una rama paralela las necesitara. Los campos sobrantes de un JSON antiguo se ignoran. En un PC, dos robots falsos se distinguen por IP de loopback (`127.0.0.1` y `127.0.0.2`) con el mismo puerto.
- **Distinto:** no.
- **Commit:** `ea88e21`, `ad37f9b`, `4a56083` (el `robots.json` de Josu)

## D22 – `primaria`, `tiempo-real` y `ensenar` cogen el robot de `robots.json`; basta editar el JSON

- **Contexto:** con la VM de URSim en el PC de Josu había que repetir la IP en cada comando (`--ip`), y por defecto era `127.0.0.1`. Un solo sitio donde cambiar la IP (y en la defensa, un cambio de robot = editar el JSON).
- **Opciones:** (a) `--ip` obligatorio o por defecto en el código (antes); (b) sin argumentos, el primer robot del JSON; `--robot nombre` elige otro; `--ip` sigue como excepción y ignora el JSON; (c) además, un campo `puerto` opcional en el JSON.
- **Elegida:** (b). Una función nueva, `tareas.ip_robot(ruta, nombre)`, y `--config` en las cuatro órdenes. `--robot` y `--ip` son excluyentes. `--puerto` sigue siendo el estándar de cada orden (30001 o 30003); (c) queda para si hiciera falta URSim 2 por NAT sin `--puerto`. El nombre del robot elegido es el que sale en las líneas de `visualizar`.
- **Distinto:** sí, respecto a D21 (donde `--ip` y `--puerto` eran la vía para un solo robot).
- **Hoy (D23):** sin argumentos: `primaria` y `tiempo_real` preguntan cuántos robots (los primeros N del JSON) y `ensenar` usa el primero. `--robot`, `--ip`, `--puerto` y `--config` ya no existen; el JSON está en `datos/robots.json`.
- **Commit:** `4f21b21`

## D23 – Un script por nivel, las clases en `src/librerias/`, sin `argparse` y con rutas relativas (2026-10-17)

- **Contexto:** el enunciado pide para el aprobado **«dos scripts separados: `primaria.py` y `tiempo_real.py`»** y, para el notable, «un único script que visualiza varios robots»; el repo tenía un `main.py` con subcomandos y un `tareas.py` que solo existía para que lo llamase `main`. Josu no quería `argparse`, quería saber «qué ejecutar y cómo» y que la práctica funcionase al cambiar de PC.
- **Opciones:** (a) dejar `main.py` + `tareas.py`; (b) `main.py` con menú de `input` y `tareas.py` dentro; (c) un script por nivel que llama a las clases, con las clases en otra carpeta.
- **Elegida:** (c). `src/primaria.py`, `src/tiempo_real.py` y `src/ensenar.py`; `src/librerias/` con `red`, `ur`, `simulador`, `secuencia` y `hmi`. `primaria` y `tiempo_real` preguntan con `input` cuántos robots visualizar (1 a N, Intro = 1): con 2 cubren el notable. Se descartó un `varios.py`; si el profesor leyera «un único script» al pie de la letra, serían unas 5 líneas. El bucle `visualizar` pasó a `simulador.py` y `leer_robots`/`elegir_robots` a `ur.py`; la consola, `_comando` y el bucle de enseñar, a `ensenar.py`.
- **Rutas:** cada script calcula `datos/` y `librerias/` desde `os.path.abspath(__file__)` y `..`, así que da igual desde qué carpeta se lance y en qué PC esté (sin rutas absolutas; hay una prueba que lo comprueba). Los módulos son planos (sin paquete) y el script añade `librerias/` a `sys.path`: tres líneas repetidas en cada script, a cambio de no tocar los `import` de las clases ni de las pruebas.
- **Se pierde:** `--ip`, `--robot`, `--puerto`, `--config`, `--v` y `--a`. Cambiar de robot es editar `robots.json` (el enunciado lo pide así: «cambiad la IP de destino en el fichero de configuración, sin tocar el código»); la velocidad, una constante de `ensenar.py` o la web (D25). El código de salida 2 desaparece.
- **Distinto:** sí, respecto a D8 y D22. Cumple la letra del enunciado.
- **Commit:** pendiente.

## D24 – Una web de control en `localhost` para `ensenar`, con `http.server` y sin dependencias (2026-10-17) — RETIRADA el 2026-10-19 (D27)

- **Contexto:** la consola de `ensenar` obliga a recordar letras y no enseña el estado ni las alarmas; Josu quería «una especie de HMI» con el estado del robot, registrar puntos, alarmas, velocidad ajustable y el movimiento de cada articulación en un gráfico. El enunciado no lo pide (solo menciona los deslizadores de PyBullet como opción): no sube nota.
- **Opciones:** (a) ventana con `pygame` o `tkinter`; (b) web servida por el propio programa; (c) Flask u otro framework.
- **Elegida:** (b), con `http.server.ThreadingHTTPServer` (Python 3.7) en un hilo, una página con CSS y JavaScript sin librerías y el gráfico en `canvas`. **Porque** (a) necesita instalar `pygame` (el PC no deja: F1, F2) o, con `tkinter`, ocupar el hilo principal, que ya es de PyBullet; (c) también exige instalar. La web no cambia la lógica: sus órdenes entran en la misma cola que la consola, y el hilo principal sigue siendo el único que toca robot, simulador y puntos. La consola se conserva como respaldo.
- **Seguridad:** la web puede mandar `movej`. Solo escucha en `127.0.0.1`, exige un token aleatorio, rechaza una cabecera `Host` ajena y un `POST` que no sea JSON, y limita las órdenes (ver [arquitectura](arquitectura.md), «HMI web»). «Ejecutar» pide confirmación. La seta del pendant sigue siendo la parada real.
- **Hay `Lock`:** en `hmi.py` el hilo principal publica y los del servidor leen un estado y un historial que crece, así que el `Lock` es lo correcto (a diferencia de `HiloLectorUR.q`, que es una referencia que se reasigna entera, D3).
- **Distinto:** sí: es un extra fuera del enunciado. Va aislado en `hmi.py` y `hmi.html`: si no se quiere entregar, se quitan esos dos ficheros y las líneas que usan `HMI` en `ensenar.py`.
- **Commit:** pendiente.

## D25 – Velocidad y aceleración ajustables en marcha, y los avisos se guardan (2026-10-17)

- **Contexto:** sin `--v` y `--a`, la velocidad era una constante; en la defensa el profesor puede pedir otra. Y la web necesita los avisos que antes solo se imprimían.
- **Elegida:** `Reproductor.ajustar(velocidad, aceleracion)` cambia los valores de los **siguientes** `movej` (no el que está en curso), dentro de los mismos límites de `ur.py` (0,001–0,3 rad/s y 0,001–0,5 rad/s²); fuera de rango no cambia nada y avisa. Se acepta solo con la secuencia libre, como el resto de órdenes. `secuencia.avisar(texto)` sustituye a `print`: imprime igual y guarda los últimos 50 avisos con hora en `secuencia.mensajes`.
- **No se hace:** escribir los avisos en un fichero (el enunciado no lo pide; serían 3 líneas).
- **Distinto:** no.
- **Commit:** pendiente.

## D26 – La práctica es portable: un Python embebido con todo dentro y un `iniciar.bat` (2026-10-19)

- **Contexto:** se ha sabido que la práctica debe poder ejecutarse en cualquier ordenador, sin pelearse con dependencias: solo ejecutar y cambiar las IP de los robots.
- **Opciones:** (a) `requirements.txt` + `venv` que crea el `.bat`; (b) ruedas (`.whl`) en la carpeta e instalación sin internet; (c) un Python embebido (`python-3.7.5-embed-amd64.zip`) con las librerías ya copiadas dentro, y un `.bat` que lo usa.
- **Elegida:** (c). (a) y (b) obligan a que el PC tenga Python 3.7 y a instalar, y **`pybullet` no tiene rueda para Python 3.7 en Windows** (F1): en un PC sin compilador no se instala. (c) no instala nada: la carpeta `entorno\` lleva el `pybullet.pyd` compilado aquí (5,9 MB), `numpy`, `scipy`, `pybullet_planning` y `UR3e_rg2` (la versión parcheada de `docs/entorno.md`). Con `python37._pth` el intérprete ignora el Python y el perfil del PC (comprobado: el humo de extremo a extremo y las 223 pruebas pasan con él).
- **Cómo:** `herramientas/crear_entorno.ps1` lo genera (descarga 7,5 MB y copia lo instalado en este PC) y **no se versiona** (≈ 170 MB, `.gitignore`); `iniciar.bat` (en la carpeta de la práctica, con CRLF por `.gitattributes`) ofrece un menú (primaria, tiempo real, enseñar, editar IP, salir) o recibe el nombre del script, y pide confirmación antes de `ensenar` (envía `movej`). Si falta `entorno\`, usa el `python` del PC con un aviso. Se entrega comprimiendo la carpeta de la práctica con `entorno\`.
- **Se pierde / riesgo:** pesa mucho; solo Windows de 64 bits; las librerías son las de este PC (si cambian, se vuelve a ejecutar el script). Un PC realmente limpio no se ha probado: por eso se copian los runtimes de Visual C++ de `System32`.
- **Distinto:** sí, el enunciado no pide nada de esto; es un requisito nuevo del profesor, de segunda mano.
- **Commit:** pendiente.

## D27 – Se retira la web de control: `ensenar` vuelve a ser solo de consola (2026-10-19)

- **Contexto:** Josu probó `iniciar.bat` (2026-10-19). En la web no entendía para qué servía «previsualizar» y no veía que hiciera nada; para la defensa prefiere guardar puntos por consola y poder explicar cada línea. La web además era un extra fuera del enunciado (D24).
- **Opciones:** (a) dejar la web y explicarla; (b) quitarla entera; (c) dejarla sin la previsualización.
- **Elegida:** (b). Se borran `hmi.py`, `hmi.html`, `test_hmi.py`, `ensenar._estado`, el arranque del servidor y del navegador, y la cola de avisos con hora (`secuencia.avisar` y `mensajes`: solo existían para la web; `avisar` pasa a ser `print`, como antes de D25). Se **conservan** la consola, `ajustar` (cambios de velocidad en caliente) y todo el blindaje de `ensenar`. 223 pruebas pasan a 181.
- **Mejora de paso:** `v` ahora escribe «Previsualizando N puntos en la ventana (el robot real no se mueve)...» y «Previsualizacion terminada», porque desde la consola tampoco se notaba qué hacía. **Qué hace `v`:** mueve el robot **simulado** de la ventana, por interpolación lineal, desde su pose actual por cada punto guardado (≤ 20 s), sin enviar nada al robot real; luego el simulador vuelve a seguir al robot real. Es el «previsualizar» que pide el enunciado.
- **Se pierde:** el gráfico de las 6 articulaciones, el panel de alarmas y los botones. Las alarmas siguen saliendo por consola («ERROR del robot», «*** FALLO DE LA SECUENCIA»). F25–F27 pasan a historia (el código que describen ya no existe).
- **El robot 2 inmóvil (resuelto, F29):** Josu vio el segundo robot de la ventana en la pose por defecto (brazo estirado, q = 0) con `tiempo_real` y dos URSim: no era la web ni URSim, sino una carrera al conectar dos hilos a la vez con el Python portable.
- **Distinto:** sí, respecto a D24 (la sustituye).
- **Commit:** pendiente.

## D28 – Linux: `iniciar.sh` con un kit offline (`uv` + Python 3.11 + ruedas) que monta `entorno-linux/` la primera vez (2026-10-19)

- **Contexto:** se ha sabido que la práctica debe ejecutarse en Windows y en Linux.
- **Opciones:** (a) un entorno embebido también en Linux; (b) `iniciar.sh` que crea un `venv` con el `python3` del sistema; (c) `iniciar.sh` que usa `uv` para crear el entorno con un Python 3.11 propio; (d) exigir que el usuario instale las dependencias a mano.
- **Elegida:** (c), y después se llevó el kit dentro de la carpeta (carpeta `linux/`, no versionada, generada en Windows con `herramientas/preparar_linux.ps1`: el binario de `uv`, un Python 3.11 independiente y las ruedas de `requirements-linux.txt`) para que **funcione desde el pendrive sin internet ni `sudo`**; sin `linux/` usa el `uv` del sistema y descarga todo. Motivo de (c): tras fallar (b) en el primer PC con Ubuntu (2026-10-19): la versión de Ubuntu traía **Python 3.14**, y `pybullet` solo publica binarios para Linux hasta **Python 3.11** (con 3.12 o más hay que compilarlo, y no había `gcc`; `numpy<2` también intentó compilarse, F30). `uv` crea el entorno con un Python 3.11 propio; no importa qué Python traiga el sistema. Se instala **sin dependencias** (`--no-deps`): `pybullet_planning` arrastra `recordclass`, `rich`, `meshio`…, que `UR3e_rg2` no usa (el Python portable de Windows tampoco los lleva) y `recordclass` no tiene binario para Linux. La rueda de `UR3e_rg2` (Python ≥ 3.9) se copia a `recursos/` para que la carpeta sea autónoma. Mismo menú y argumentos que `iniciar.bat`; se lanza con `bash iniciar.sh` desde una terminal. El entorno es `entorno-linux/` (así no choca con el `entorno\` de Windows si la carpeta viaja con los dos).
- **Se pierde / riesgo:** pesa ≈ 240 MB más (`linux/`); solo Linux x86_64 con glibc; la primera vez extrae y monta el entorno (unos segundos). Comprobado en Windows: las ruedas descargadas bastan para resolver `requirements-linux.txt` sin internet (`uv --dry-run`). El script se ejecutó en un Ubuntu de Josu y funcionó (2026-10-19, T24; no consta qué se probó dentro). Antes de eso no se había ejecutado en Linux (no hay Linux ni WSL aquí); la causa del fallo anterior sí se vio en un Ubuntu real (log de Josu). El código Python no tiene nada específico de Windows (sin `msvcrt`, `os.name` ni rutas fijas) y la Pi ejecutó las pruebas de la versión anterior en Linux (T14), pero no `iniciar.sh`, ni la instalación de `pybullet_planning` con la `scipy` de allí (se fija `scipy<1.13` y `numpy<2` por prudencia).
- **Distinto:** sí, el enunciado no lo pide; es un requisito nuevo del profesor, de segunda mano.
- **Commit:** pendiente.
