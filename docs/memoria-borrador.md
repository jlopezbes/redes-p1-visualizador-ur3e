# Memoria · Práctica 1: visualizador de un UR3e por TCP/IP (borrador)

> **Borrador de la Pi (2026-10-17), no es la memoria.** El enunciado pide máximo 6 páginas y tú quieres que sea corta: este borrador ocupa unas 3. Cuenta lo que hiciste tú, qué se podía haber hecho de otra forma y por qué lo defiendes. `[JOSU]` = solo lo sabes tú; `[MEDIR]` = falta un dato real. **Reescríbela con tus palabras antes de entregar** (y borra esta nota).

## 1. Qué entrego y cómo se ejecuta

Nivel al que opto: **sobresaliente** `[JOSU: confirma]`. Python 3.7.5, solo `socket`, `struct`, `threading` y la biblioteca estándar, más el visualizador `UR3e_rg2` (PyBullet) que da el enunciado.

| Script (`src\`) | Nivel | Qué hace |
|---|---|---|
| `primaria.py` | Aprobado | Lee 1 o varios robots por la interfaz primaria (30001) y mueve el UR3e de PyBullet |
| `tiempo_real.py` | Aprobado | Lo mismo por la interfaz de tiempo real (30003) |
| `ensenar.py` | Sobresaliente | Enseñar puntos, previsualizar, ejecutar con `movej` y supervisar; desde la consola |

Las IP de los robots están solo en `datos\robots.json`: para pasar de URSim al UR3e se cambia ese fichero, no el código. `primaria.py` y `tiempo_real.py` preguntan cuántos robots visualizar; con 2 se cubre el notable. Las clases están en `src\librerias\`.

## 2. Estructura y estrategia de lectura

Cuatro capas, cada una con una sola responsabilidad: `red.py` (una conexión TCP con timeouts; traduce todo fallo de socket a `ErrorRed`), `ur.py` (`ClienteUR`: entiende el protocolo del UR y entrega diccionarios ya decodificados; `HiloLectorUR`), `simulador.py` (envuelve PyBullet) y `secuencia.py` (la máquina de estados de enseñar y reproducir).

**Lectura.** TCP es un flujo de bytes: un `recv()` puede traer medio mensaje o uno y medio. `ClienteUR` acumula los bytes en un buffer y `_cortar` saca solo paquetes completos usando la longitud (`int32`) con la que empieza cada uno; después `_leer_estado` recorre los subpaquetes del mensaje de tipo 16 con la misma regla y decodifica en big-endian (`">d"`) las 6 articulaciones del subpaquete 1 (41 B cada una, 251 B en total). Lo que no entiende lo salta con su longitud. En tiempo real el paquete tiene estructura fija y el `q_actual` empieza en el byte 252.

**Hilos.** Con varios robots, un `recv()` bloqueante congelaría a los demás: hay un `HiloLectorUR` por robot que solo guarda el **último** `q`; el hilo principal lo lee y dibuja 30 veces por segundo, y es el único que toca PyBullet. Si un robot se cae, su hilo reintenta cada 2 s y el robot simulado se queda quieto sin afectar a los otros. `ensenar.py` usa la primaria (no `HiloLectorUR`) porque necesita todos los mensajes: `isProgramRunning`, las paradas y los errores.

**Enseñar y reproducir.** Un `movej` por punto; no se envía el siguiente hasta confirmar la ejecución con el propio estado del robot (`isProgramRunning` sube y baja, y `q` queda a menos de 0,01 rad del punto). Un error del robot (tipo 20) o una parada de protección o de emergencia detienen la secuencia con `stopj`, muestran el motivo y esperan `Reanudar` o `Cancelar`. Límites obligatorios en el código: 0,3 rad/s y 0,5 rad/s², y no se envían ángulos fuera de ±2π (evita mandar grados).

## 3. Lo que decidí yo y qué se podía haber hecho de otra forma

`[JOSU: quédate con las 4 o 5 que de verdad decidiste tú y cuéntalas a tu manera; este es el orden sugerido]`

- **Menos código, no más robustez.** Una auditoría con IA llenó `src/` de validaciones de casos que no ocurren en uso real (1176 líneas contando todo). Pedí una limpieza por capas con mis propios criterios (no validar lo que no pasa; un mensaje general con la causa probable y salida limpia; inlinar lo que se usa una o dos veces) y bajó a 817 líneas. **Alternativa:** dejarlo todo «por si acaso». **Por qué lo defiendo:** tengo que poder explicar cada línea y depurar; se conservó solo lo que protege al robot (límites, `es_punto_valido`, `stopj`, parada por protección o emergencia).
- **Una sola clase para las dos interfaces.** `ClienteUR` sirve para la primaria y el tiempo real: comparten conexión, buffer y corte por longitud y solo cambia cómo se decodifica. **Alternativa:** una clase por interfaz (la primera versión).
- **Un solo tipo de error de comunicación (`ErrorRed`)**, más `ErrorRedTimeout`, `ErrorSecuencia` y `ErrorSimulador`: el mensaje dice con quién y por qué falló. **Alternativa:** usar `OSError` y excepciones de Python.
- **Sin `Lock` en `HiloLectorUR`.** Un solo hilo escribe y lo hace **reasignando la lista entera**; el principal la lee una vez en una variable local. **Alternativa (la del enunciado):** protegerlo con `threading.Lock`. Admito que no es lo recomendado; es correcto por cómo se escribe `q` `[JOSU: decide si lo dejas o añades el Lock]`.
- **Un script por nivel, rutas relativas y sin `argparse`.** Cada entregable se ejecuta por separado, sin argumentos, y funciona desde cualquier carpeta y PC. **Alternativa:** un `main.py` con subcomandos (lo que había).
- **Una web de control** se probó y se **retiró** (D27): no aportaba al enunciado y no se podía defender línea a línea con el robot delante; `ensenar` se maneja por consola.
- **No hecho, por alcance:** trayectoria suave entre puntos (`movej` con radio de empalme o `speedj`; hoy el robot se para en cada punto), RTDE y gráfico en los scripts de visualización.

## 4. Respuestas a las preguntas del enunciado

`[JOSU: una o dos frases cada una, con tus palabras. Guía en docs/desde-pi/defensa-p1.md]`

1. **Bytes por `recv()`.** `[MEDIR: cifras de un minuto]` No coinciden siempre con la longitud de un mensaje; por eso hay buffer y corte por longitud.
2. **Por qué la longitud.** Delimitar mensajes y saltar lo que no se entiende (un tipo desconocido se ignora con su longitud).
3. **Sin big-endian.** `3F F0 00 00 00 00 00 00` es `1.0` con `">d"` y `3.03865e-319` con `"<d"`; en el programa saldrían todos los ángulos a 0.
4. **Primaria o tiempo real.** Primaria (≈ 10 Hz, con modo, paradas y errores) para supervisión; tiempo real (≈ 500 Hz) para registrar un movimiento rápido.
5. **NAT y puente.** En NAT la VM tiene una IP privada que el PC no alcanza sin reenvío; en puente es un equipo más con su MAC y su IP; la MAC la ven el switch y la red local.
6. **Cable fuera 5 s.** `[MEDIR: qué se vio]` El programa avisa tras 2 s sin datos, deja quieto el robot simulado y reconecta cada 2 s.
7. **(N) Retraso.** `[MEDIR]` Depende de los 10 Hz o 500 Hz del robot, de los 30 redibujados por segundo y de la red.
8. **(N) Sin `Lock`.** Se vería un vector a medio escribir si se modificara elemento a elemento; aquí se reasigna entero (ver sección 3).
9. **(S) Por qué no basta con `movej`.** El ACK de TCP solo dice que los bytes llegaron; se confirma con `isProgramRunning` y con `q` a menos de 0,01 rad.
10. **(S) Puerto 30001 abierto.** Cualquiera puede mandar un programa. En el robot: deshabilitar o dejar en solo lectura las interfaces que no se usen; en la red: segmentar y filtrar por IP.

## 5. Pruebas, resultados y diferencias con el robot real

223 pruebas automáticas y un humo de extremo a extremo con robots falsos que emiten las tramas con el formato real (no sustituyen a un robot). `[JOSU: resultados con URSim; robot real usado en el laboratorio y diferencias observadas con respecto a URSim (el enunciado lo pide); si el formato de 251 B y el offset 252 se confirmaron con el robot]`.

## 6. Uso de la IA

El régimen de la asignatura permite la IA y la promueve. `[JOSU: tu versión honesta: qué generó Claude Code (código de comunicación a partir del enunciado), qué decidiste y corregiste tú (la limpieza y sus criterios, la estructura por scripts, la retirada de la web), cómo comprobaste que entendías cada línea (lectura, cambios en caliente sin IA, depuración de fallos) y qué probaste tú con el robot]`.
