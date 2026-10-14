# Decisiones

Numeración fija: D1, D2… (nunca se renumera). Cada una lleva contexto, opciones, la elegida y por qué, y la marca **«distinto»** si se aparta de lo que pide el enunciado o de lo que haría la clase: esas son la materia prima de la memoria.

D1–D5 vienen de las versiones de partida y se aplicaron a `src/` el 2026-10-14. D6–D9 son de esa misma sesión (fase 1: código escrito por la IA, pendiente de revisión de Josu).

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
