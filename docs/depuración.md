# Depuración

El profesor valora sobre todo saber depurar: cada fallo real queda como caso. Numeración fija F1, F2… con el más reciente arriba.

Los casos F1–F5 vienen de las versiones de partida y se citan con su origen; F6 es de la fase 1 de `src/`; F7–F10 son de la revisión de robustez de la capa 1 (`red.py`) y F11–F14 de la capa 2 (`ur.py`). Cada uno dice qué se ejecutó y qué solo se leyó.

## F14 – `parar()` tardaba hasta 2 s, `puerto=0` se cambiaba por el 30001 y `stopj` aceptaba cualquier cosa (2026-10-14, `src/ur.py`)

- **Síntoma:** (a) con el robot mudo, el hilo `LectorUR` seguía vivo y con el socket abierto 1,5 s después de `parar()`; (b) `UrPrimaria(ip, 0)` conectaba al puerto 30001 sin avisar; (c) `stopj(float("nan"))`, `stopj(-5)` y `stopj(1000)` se enviaban tal cual, y con un texto en `aceleracion` se colaba una segunda orden URScript (`stopj(1)\npowerdown()`); (d) `es_punto_valido(None)` y `movej(velocidad="0.1")` lanzaban `TypeError`.
- **Aislamiento:** ✅ el auditor reprodujo los cuatro (`parar()` → hilo vivo 1,51 s; `puerto 0 → 30001`; las órdenes salían por el socket). Las pruebas nuevas los repiten.
- **Causa:** (a) `parar()` solo ponía un `Event`, que el hilo mira cuando le llega un estado; (b) `puerto or self.PUERTO` trata `0` y `""` como «no hay puerto»; (c) nadie validaba lo que se escribe en la orden; (d) las comparaciones con tipos raros lanzan `TypeError`.
- **Arreglo:** `parar()` marca el `Event` **y cierra el cliente** (seguro desde otro hilo por F8); `detener(timeout)` añade el `join`; el hilo mira `_parar` justo después de conectar. `self.PUERTO if puerto is None else puerto`. `enviar_script` rechaza `\n` y `\r`; `stopj` con un valor que no sea un número en `(0, ACELERACION_MAX]` frena con `ACELERACION_MAX` (un valor mal puesto nunca impide frenar). `es_punto_valido` devuelve `False` con tipos raros y `movej` comprueba el tipo. Pruebas: `test_parar_cierra_el_socket_y_el_hilo_termina_enseguida`, `test_puerto_cero_no_se_cambia_en_silencio_por_el_de_defecto`, `test_stopj_sin_estado_frena_y_un_valor_malo_usa_el_maximo`, `test_enviar_script_rechaza_saltos_de_linea`, `test_movej_con_tipos_raros_es_valueerror`, `test_es_punto_valido_con_tipos_raros_es_false_sin_excepcion`.
- **Commit:** `0cac920`
- **Para la defensa:** una variable de «parar» solo sirve si el hilo la mira; a un hilo bloqueado en un `recv` hay que despertarlo cerrando el socket.

## F13 – Un mensaje cortado, un `q` con `nan` o un texto raro del robot rompían el programa (2026-10-14, `src/ur.py`)

- **Síntoma:** `struct.error: unpack requires a buffer of 8 bytes` crudo al decodificar un subpaquete de articulaciones vacío o de 100 B, un modo de 5 B o un error de 15–18 B; con `nan`, `inf`, `1e300` o grados en lugar de radianes `ultimo_q()` entregaba `[nan, ...]`, que va al simulador y a la secuencia; un texto del robot con bytes no UTF-8 daba `UnicodeEncodeError` al imprimirlo con la salida redirigida y, como es un `ValueError`, `ensenar_reproducir` lo tomaba por «conexión perdida» y reconectaba en bucle; un subpaquete de 256 B se decodificaba con los desplazamientos de 251 B y escribía un aviso por mensaje (hasta 125 líneas/s).
- **Aislamiento:** ✅ el auditor lo reprodujo caso a caso con bytes construidos a mano; las pruebas nuevas lo repiten.
- **Causa:** `ur.py` confiaba en que los bytes del robot tienen el tamaño esperado y dejaba salir `struct.error` y `ValueError` de decodificación, que las capas de arriba tenían que conocer (y que se confundían con los `ValueError` de argumentos).
- **Arreglo:** `leer_estado` y `leer_error` convierten `struct.error` y `ValueError` en `ErrorUR` (un solo `try` en cada una); `ClienteUR._paquetes` hace lo mismo con una longitud imposible; `_q_valido` rechaza `q` no finito o fuera de ±(2π + 0,2) rad; un subpaquete de articulaciones que no mide 251 B lanza `ErrorUR` diciendo el tamaño recibido y el esperado (D13); `_texto_seguro` deja solo ASCII imprimible y 300 caracteres. Pruebas: `PruebasDecodificarRobusto` (7).
- **Commit:** `0cac920`
- **Para la defensa:** los bytes que vienen de fuera no se creen: se comprueba su tamaño y su rango antes de usarlos, y un fallo de formato es un error del robot, no del programa.

## F12 – `movej` se enviaba sin saber si el robot seguía ahí (2026-10-14, `src/ur.py`)

- **Síntoma:** contra un servidor mudo, `movej` se enviaba sin haber recibido ni un estado y sin excepción; lo mismo si el robot llevaba segundos sin enviar o ya había cerrado (el primer `enviar` tras un FIN no falla, ver F9).
- **Aislamiento:** ✅ reproducido por el auditor con un servidor mudo: el servidor recibió `movej([...])`. Prueba nueva: `test_movej_se_niega_sin_estado_reciente_y_no_envia_nada`.
- **Causa:** `movej` solo validaba ángulos y límites; nada decía si había un estado reciente.
- **Arreglo:** `movej` lanza `ErrorUR` y no envía nada si `estado_fresco()` es falso (D12). `stopj` no lo exige: frenar siempre se intenta. `Reproductor._enviar_punto` trata ese `ErrorUR` como cualquier fallo de la secuencia (`stopj` y parada). Pruebas: `test_movej_se_niega_cuando_el_estado_caduca`.
- **Commit:** `0cac920`
- **Para la defensa:** la regla de seguridad es «ante la duda, no mover y avisar»: un envío sin error no prueba nada, hace falta un estado reciente.

## F11 – `ultimo_q()` daba un `q` viejo como actual y un error en el hilo lo mataba en silencio (2026-10-14, `src/ur.py`)

- **Síntoma:** (a) un robot que, tras un estado válido, solo manda mensajes de versión (tipo 20), o que gotea un byte por segundo, mantenía la conexión «viva» y `ultimo_q()` devolvía el mismo `q` 6 s o 8 s después; (b) un `IndexError` dentro del hilo `LectorUR` lo mataba (solo un traceback por `stderr`) y `ultimo_q()` seguía dando el último `q` para siempre.
- **Aislamiento:** ✅ el auditor lo reprodujo con servidores falsos y con un cliente que falla a propósito. Las pruebas nuevas usan `PLAZO_ESTADO` reducido (0,3 s) en vez de esperar 2 s.
- **Causa:** el timeout de red es «no llega **ningún byte**», no «no llega **un estado**»; `LectorUR` no guardaba cuándo llegó el `q` y solo capturaba `ErrorRed`/`ValueError`/`struct.error`.
- **Arreglo:** una sola noción de «estado fresco», `ClienteUR.estado_fresco()` con `PLAZO_ESTADO` (2 s) y `time.monotonic()`; `ultimo_q()` devuelve `None` si no es fresco; `_paquetes()` lanza `ErrorUR` si pasa el plazo sin estados aunque lleguen otros bytes. `LectorUR.run` tiene un único `except Exception` de última defensa que guarda el motivo en `ultimo_error` (con su traceback, una vez), deja sin `q` y sigue reintentando, y un `finally` que borra el `q` al salir; el motivo de una desconexión se escribe solo cuando cambia. Pruebas: `test_solo_mensajes_que_no_son_estado_caducan_con_errorur`, `test_un_servidor_que_gotea_bytes_caduca_con_errorur`, `test_el_lector_deja_de_dar_un_q_viejo`, `test_estado_fresco_es_la_unica_definicion`, `test_un_bug_en_el_hilo_se_registra_y_el_hilo_sigue_vivo`, `test_el_motivo_de_la_desconexion_se_escribe_una_sola_vez`, `test_ultimo_error_se_borra_cuando_vuelven_los_estados`.
- **Commit:** `0cac920`
- **Para la defensa:** «la conexión está abierta» no quiere decir «los datos son actuales»; se guarda cuándo llegó el último estado y se compara con un plazo.

## F10 – `timeout_lectura=None` o `0` en `ConexionTCP`: `recibir()` se cuelga para siempre o falla con un error raro (2026-10-14, `src/red.py`)

- **Síntoma:** con `timeout_lectura=None`, `recibir()` contra un servidor que calla no vuelve nunca (el auditor lo dejó más de 100 s y tuvo que matar el proceso); con `0` sale `BlockingIOError [WinError 10035]`; con `nan`, `inf` o `'2'`, `ValueError`, `OverflowError` o `TypeError` crudos, y el socket recién creado queda sin cerrar.
- **Causa:** `settimeout(None)` significa «sin límite» y `settimeout(0)` «no bloqueante»; el constructor no comprobaba nada. Hoy nadie pasa esos valores, pero la regla es «todo bloqueo tiene timeout».
- **Arreglo:** el constructor exige timeouts numéricos con `0 < t <= 3600` s (`nan`, `inf`, `None`, `bool` y cadenas se rechazan solos con esa comparación) y lanza `ValueError` en español antes de tocar la red. Prueba: `test_timeout_no_valido`.
- **Commit:** `e639b91`
- **Para la defensa:** en Python `None` y `0` en un timeout no son «sin timeout» y «ninguno», significan «espera siempre» y «no esperes»; por eso se validan.

## F9 – Los errores de socket llegaban crudos y `abierta` seguía en `True` (2026-10-14, `src/red.py`)

- **Síntoma:** según la causa salían `ConnectionRefusedError`, `ConnectionResetError`, `ConnectionAbortedError`, `gaierror`, `socket.timeout` u `OSError` con mensajes de Windows sin decir de qué robot se trataba. Tras un RST o un `OSError`, `ConexionTCP.abierta` seguía diciendo `True`. Llamar a `abrir()` dos veces dejaba el primer socket abierto y sin dueño.
- **Aislamiento:** ✅ el auditor reprodujo cada caso contra servidores falsos propios en `127.0.0.1` (RST con `SO_LINGER` a 0, cierre limpio, doble `abrir()`); las pruebas nuevas repiten RST, cierre remoto y doble `abrir()`.
- **Causa:** `red.py` no traducía nada: cada capa de arriba tenía que conocer `socket` y `OSError`, y nadie cerraba el socket tras un error fatal.
- **Arreglo:** una jerarquía propia, `ErrorRed` y `ErrorRedTimeout` (D10). Cualquier fallo de `abrir`, `enviar` o `recibir` sale como `ErrorRed` con `ip:puerto`; cualquier fallo salvo un timeout de lectura cierra la conexión (`_perdida`), así que `abierta` es fiable; `abrir()` empieza llamando a `cerrar()`. Los llamadores (`ur.LectorUR`, `tareas.ensenar_reproducir`, `Reproductor._fallar`) pasan a capturar `ErrorRed`. Pruebas: `test_reset_del_otro_lado_es_errorred_y_cierra`, `test_cierra_el_otro_lado`, `test_puerto_cerrado_es_errorred`, `test_abrir_dos_veces_no_deja_un_socket_suelto`.
- **Limitación que queda:** si el robot cierra, el primer `enviar()` **no falla** (TCP lo acepta); falla el siguiente o el `recibir()`. «Enviado sin error» no quiere decir «el robot lo ha recibido» (misma lección que F6). Prueba: `test_enviar_tras_cierre_remoto_acaba_en_errorred`.
- **Commit:** `e639b91`

## F8 – `cerrar()` desde otro hilo hacía fallar a `recibir()` con un `OSError` crudo (2026-10-14, `src/red.py`)

- **Síntoma:** si otro hilo llamaba a `cerrar()` mientras el hilo lector estaba en `recibir()`, este recibía `OSError [WinError 10038]` («no es un socket») crudo (1500 de 1500 intentos del auditor). Con mala suerte entre `if not self.abierta` y `self._socket.recv(...)` el otro hilo ponía `_socket = None` y salía `AttributeError: 'NoneType' object has no attribute 'recv'`, que `LectorUR` no captura y mataba el hilo en silencio (este segundo caso solo se reprodujo forzando el cambio de hilo, no con hilos reales).
- **Causa:** `enviar` y `recibir` comprobaban `self.abierta` y luego usaban `self._socket` por separado: entre las dos lecturas el valor puede cambiar.
- **Arreglo:** se copia `self._socket` a una variable local una sola vez (`_socket_abierto`) y se usa solo esa; `cerrar()` intercambia `_socket` por `None` de una vez. El `OSError` del cierre ajeno se convierte en `ErrorRed`. En Windows `cerrar()` ya despierta de inmediato a un `recibir()` bloqueado, así que no hace falta `shutdown`. Prueba: `test_cerrar_desde_otro_hilo_despierta_a_recibir_con_errorred` (tarda < 2 s con un timeout de 5 s).
- **Commit:** `e639b91`
- **Para la defensa:** «comprobar y luego usar» no es seguro entre hilos; se lee la variable una vez y se trabaja con la copia.

## F7 – Un puerto fuera de 0–65535 conectaba con OTRO puerto (2026-10-14, `src/red.py`)

- **Síntoma:** `ConexionTCP("127.0.0.1", 32002 + 65536).abrir()` no da error: se conecta al puerto 32002. Con `--puerto 95537` el programa habla con el 30001 creyendo que usa otro. `None`, `0`, `3.5` o `"abc"` daban errores crudos distintos; `ip=None` conectaba en silencio a `127.0.0.1`.
- **Aislamiento:** ✅ ejecutado hoy: con un servidor en `127.0.0.1:32002`, `socket.create_connection(("127.0.0.1", 97538))` conecta (97538 = 32002 + 65536).
- **Causa:** Windows recorta el puerto a 16 bits y `create_connection` no lo comprueba; y `ConexionTCP` no validaba lo que viene de la línea de comandos o de `robots.json`.
- **Arreglo:** el constructor valida: IP literal (`ipaddress.ip_address`, sin nombres de host: así tampoco hay espera de DNS, D10), puerto entero entre 1 y 65535 (sin `bool`), y `ValueError` en español. Pruebas: `test_ip_no_valida`, `test_puerto_no_valido`.
- **Commit:** `e639b91`
- **Consecuencia:** una IP o un puerto mal escritos ahora son un `ValueError` al crear el cliente; `main.py` todavía no lo muestra como un error de argumento limpio (queda para la capa 4).

## F6 – Una prueba falla «a veces»: el `stopj` todavía no ha llegado al robot (2026-10-14, `src/`)

- **Síntoma:** `test_parada_de_proteccion_y_reanudar` (pruebas/test_integracion.py) falló con `AssertionError: 0 != 1` al contar los `stopj` recibidos por el robot falso. La prueba vecina `test_error_del_robot_detiene`, con la misma comprobación, pasó.
- **Hipótesis:** (a) el `Reproductor` no envía el `stopj`; (b) lo envía, pero el robot falso aún no lo ha leído cuando la prueba mira.
- **Aislamiento:** ✅ en `Reproductor._fallar` el `stopj` se envía **antes** de poner `fase = PARADA`, y la prueba esperaba esa fase: si estaba en `PARADA`, el `stopj` ya se había enviado → (a) descartada. Además la prueba pasa en las pruebas unitarias con un robot que graba al instante. Queda (b): el envío es asíncrono.
- **Causa:** carrera en la prueba, no en el código. `sendall` vuelve cuando el sistema operativo ha aceptado los bytes, no cuando el otro extremo los ha procesado; el hilo del robot falso los lee unos milisegundos después. Que `test_error_del_robot_detiene` pasara era suerte.
- **Arreglo:** `esperar_orden("stopj")` espera (máximo 3 s) a que el robot falso la haya recibido antes de contarla, en las tres pruebas que lo comprueban. Tres ejecuciones seguidas de las 84 pruebas, con código de salida 0.
- **Commit:** `800dd7d` (la prueba se confirmó ya corregida).
- **Para la defensa:** un envío correcto por TCP no prueba que el otro lado lo haya procesado; lo mismo pasa con un robot real: tras `stopj` hay que mirar su estado, no dar por hecho que ya se paró.

## F5 – `a_mano/main.py` no imprime nada (2026-10-13, de `versiones/a_mano`)

- **Síntoma:** contra el robot falso en `127.0.0.1` (con una copia de `main.py` con IP y puerto cambiados) no sale nada en 6 s.
- **Hipótesis:** el programa no llega nunca al subpaquete 1 (articulaciones).
- **Aislamiento:** ✅ ejecutado por la Pi con una copia que imprime la cabecera de cada subpaquete (`tam_subpaquete`, `tipo_subpaquete`):

  ```
  sub 47 0
  sub 417 53
  sub 47 0
  sub 417 53
  ```

  Tras el subpaquete 0 (47 B) aparece `417`, tipo `53`: datos leídos como si fueran cabecera.
- **Causa:** tras leer la cabecera de 5 B del subpaquete 0, el `else` de la línea 33 solo suma `tam_subpaquete` al contador y **no lee el cuerpo (42 B)**. La siguiente lectura de 5 B cae en mitad de los datos.
- **Arreglo:** leer siempre `tam_subpaquete − 5` bytes después de cada cabecera, sea cual sea el tipo. No se aplica a `a_mano` (se conserva tal cual); la versión final lo hace desde el principio (D2). El protocolo es el mismo en un robot real, pero **no se ha probado** con uno.
- **Además, leyendo el código (sin ejecutarlo):** `recv(n)` sin bucle en las líneas 16, 24, 28 y 36 (TCP puede devolver menos bytes); `range(0, 5)` en la línea 27 lee 5 de las 6 articulaciones; en la rama del subpaquete 1 el contador no se incrementa.
- **Commit:** —

## F4 – Segundo URSim: red puente frente a NAT, y un clon que hereda las reglas (2026-10-08, de `versiones/claude_1`, docs/06 B4)

- **Síntoma:** al darle a Josu comandos con `<ip_vm2>` y `NOMBRE_DE_TU_TARJETA`, PowerShell los rechazó (`<` es un operador reservado). Además, el clon de la VM heredó las reglas NAT de la VM 1 (mismos puertos de host), y cambiar `nic1` de puente a NAT **en caliente** no renovó la IP del invitado: se quedó sin red hasta reiniciarlo.
- **Aislamiento:** descartada la red puente (comandos con placeholders). Josu propuso dejar ambas VM en NAT con puertos de host distintos; se adoptó.
- **Causa:** placeholders no ejecutables en PowerShell; reglas NAT copiadas con el clon; cambio de adaptador sin reiniciar el invitado.
- **Arreglo:** borrar las 4 reglas heredadas y crear otras (30001/30003 para la VM 1 y 30011/30013 para la VM 2). Contrapartida: `ur_rtde` y el Dashboard usan puertos fijos (30004 y 29999), así que la VM 2 solo se usa por `socket`.
- **Commit:** —

## F3 – `UR3e_rg2` no instala con Python 3.7 (2026-10-08, de `versiones/claude_1`, docs/06 B3)

- **Síntoma:** `BulletGym.py` importa `TypedDict` y `Literal` de `typing` (existen desde Python 3.8) y `setup.py` fija `numpy==1.24.4` y `scipy==1.10.1`, que exigen ≥ 3.8.
- **Causa:** la librería está pensada para Python ≥ 3.8.
- **Arreglo:** instalar con `--no-deps` desde una **copia parcheada** (importar de `typing_extensions`) y las dependencias compatibles a mano. Detalle en [docs/entorno.md](../../../docs/entorno.md).
- **Commit:** —

## F2 – `pip install ur_rtde` falla por permisos (2026-10-08, de `versiones/claude_1`, docs/06 B2)

- **Síntoma:** `pip install ur_rtde` sin `--user` falla por permisos: la sesión no es de administrador.
- **Arreglo:** `pip install --user --only-binary :all: ur_rtde` (ur_rtde 1.6.5 trae rueda para Windows y Python 3.7).
- **Commit:** —

## F1 – `pybullet` no se instala en Windows con Python 3.7 (2026-10-08, de `versiones/claude_1`, docs/06 B1)

- **Síntoma:** `pip install pybullet ur_rtde` falló con `error: command 'cl.exe' failed: No such file or directory`.
- **Aislamiento:** `pip download pybullet --only-binary :all:` dio «no matching distribution». La API JSON de PyPI mostró que todas las ruedas son `manylinux`, sin `win_amd64`: por eso el año anterior, en el Linux del laboratorio, iba sin más.
- **Causa:** no hay rueda para Windows y falta el compilador en el PATH (aunque el PC tiene Visual Studio 2022 Community con MSVC).
- **Arreglo:** compilar desde `vcvars64.bat` con `DISTUTILS_USE_SDK=1` y `MSSdk=1` (pybullet 3.2.7, unos minutos). Descartado: Build Tools con `winget` (pide administrador), otra versión de Python, conda.
- **Commit:** —
