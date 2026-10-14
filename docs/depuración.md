# Depuración

El profesor valora sobre todo saber depurar: cada fallo real queda como caso. Numeración fija F1, F2… con el más reciente arriba.

Los casos F1–F5 vienen de las versiones de partida y se citan con su origen; F6 es de la fase 1 de `src/`. Cada uno dice qué se ejecutó y qué solo se leyó.

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
