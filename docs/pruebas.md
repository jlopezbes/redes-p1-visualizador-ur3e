# Pruebas

Leyenda: ✅ ejecutado y verificado · ⚠️ ejecutado con salvedad · ❌ no probado. Cada fila lleva el comando exacto y la salida resumida, con cifras y unidad. No se marca ✅ lo que no se ha ejecutado.

Todos los comandos, desde la raíz del repo, en PowerShell 5.1 con Python 3.7.5. `-B` evita crear `__pycache__`.

**Cambio de ruta (2026-10-14):** `practicas\` pasó a `2_practicas\` después de ejecutar T1 a T4 con la ruta vieja. Los comandos de abajo llevan ya la ruta nueva; tras el cambio solo se repitió T1 (`python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas`: 84 pruebas OK en 12,7 s). T3, T4 y el resto no se repitieron con la ruta nueva (solo cambia el nombre de la carpeta; ningún script la lleva escrita en el código).

## Versión final `src/` (fase 1, 2026-10-14; limpieza por capas, 2026-10-16)

**Aviso general:** las tramas de las pruebas las construyen `pruebas/ayudas.py` y `pruebas/robot_falso.py` a partir del formato descrito en [docs/ur-referencia.md](../../../docs/ur-referencia.md) y en `claude_2`. Si un robot real mandara otra cosa, estas pruebas no lo detectarían. Por eso las que dependen de ellas llevan ⚠️ y no ✅.

| Id | Qué se prueba | Comando | Resultado | Estado | Fecha |
|---|---|---|---|---|---|
| T1 | Pruebas automáticas: `red` (6), `ur` (27), `simulador` (7), `secuencia` (22), `tareas` (13) e integración con el robot falso (9) | `python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas -v` | 84 pruebas OK en ≈ 12,6 s. Tres ejecuciones seguidas, código de salida 0 (se buscaba inestabilidad: ver F6 en [depuración](depuración.md)) | ⚠️ | 2026-10-14 |
| T2 | Que la prueba `test_reconectar_vacia_el_buffer` detecta de verdad el fallo que protege (prueba de mutación: quitar `self._buffer.clear()` de `ClienteUR.conectar`) | script temporal, ejecutado una vez; **no está en el repo** | `MUTANTE DETECTADO`: `ValueError: subpaquete 249 se sale del mensaje` | ✅ | 2026-10-14 |
| T3 | `Simulador` con la librería **real** `UR3e_rg2`: ids de PyBullet, articulaciones, posición de las bases | `python -B 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_pybullet.py` y la misma con `desplazado` | OK las dos veces: robot1 → id 0, robot2 → id 2; las articulaciones leídas con `pybullet.getJointState` coinciden con las enviadas (p. ej. `[0.3, -1.0, 0.5, -1.2, 0.4, 0.1]` rad); base x = 0,00 m / 0,50 m (primer robot) y 1,00 m. Abre la ventana ≈ 2 s | ✅ | 2026-10-14 |
| T4 | `main.py` entero (`primaria`, `tiempo-real`, `varios`, `ensenar`) lanzado como subproceso con la ventana real de PyBullet contra robots falsos en puertos libres | `python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_extremo_a_extremo.py` | TODO OK (15 comprobaciones): imprime `q (grados): [0.0, -90.0, 0.0, -90.0, 0.0, 0.0]` en primaria y tiempo real; los 2 robots de `varios` imprimen su `q`; en `ensenar`: `g`, `l`, `e` funcionan, el robot falso recibe 1 `movej` con `a=0.5, v=0.3` y llega a q[0] = 0,200 rad; `ensenar --v 0.5` sale con código 2. Abre la ventana ≈ 5 s cuatro veces | ⚠️ | 2026-10-14 |
| T5 | Revisión de robustez, capa 1 (`red.py`): errores de socket como `ErrorRed`, `abierta` fiable tras un error, `cerrar()` desde otro hilo, doble `abrir()`, IP/puerto/timeouts inválidos, argumentos raros de `enviar`/`recibir`. Pruebas de `red` pasan de 6 a 14; `test_ur`, `test_secuencia` y `test_integracion` esperan ahora `ErrorRed` donde esperaban `ConnectionError`/`OSError` | `python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas` | 92 pruebas OK en ≈ 13,2 s (con servidores falsos en `127.0.0.1`, sin robots reales ni URSim) | ✅ | 2026-10-14 |
| T6 | Revisión de robustez, capa 2 (`ur.py`): `ErrorUR` como única excepción hacia arriba, mensajes cortados o con `q` no finito, estado fresco (`ultimo_q()` y `movej`), `LectorUR` con un bug inyectado, `parar()`/`detener()` y órdenes `stopj`/`enviar_script`. Pruebas de `ur` pasan de 27 a 48; `test_secuencia`, `test_tareas` e `test_integracion` marcan un estado fresco antes de `movej` y esperan `ErrorUR` | `python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas` | 113 pruebas OK en ≈ 15 s (tres ejecuciones seguidas, servidores falsos en `127.0.0.1`, sin robots reales ni URSim) | ✅ | 2026-10-14 |
| T7 | Revisión de robustez, capa 3 (`secuencia.py`, `simulador.py`): `stopj` que no sale, protección/emergencia, espera de estado tras una vista previa (con `PLAZO_ESTADO` reducido), mensajes mal formados, `reanudar` tras borrar, 13 ficheros de secuencia malos y 5 casos más (binario, enorme, directorio, inexistente, BOM), `guardar` atómico, `Simulador` con visualizador que falla, sin `UR3e_rg2`, `q` no válidos, `cerrar()` y tope de la vista previa. `test_secuencia`: 22 → 40, `test_simulador`: 7 → 14. `test_secuencia`, `test_simulador` y `test_tareas` esperan ahora `ErrorSecuencia`/`ValueError` donde esperaban `OSError`/`KeyError` | `python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas` | 140 pruebas OK en ≈ 15,5 s (tres ejecuciones seguidas; servidores falsos en `127.0.0.1`, sin robots reales ni URSim; sin ventana PyBullet). **No se probó `cerrar()` con la ventana real** | ⚠️ | 2026-10-14 |
| T8 | Revisión de robustez, capa 4 (`main.py`, `tareas.py`): `main()` con argumentos y `robots.json` malos (código 2, sin crear el simulador), errores de capa (1) y Ctrl+C (0); `ensenar_reproducir` contra el robot falso con la ventana (falsa) cerrada en pleno movimiento (llega `stopj`), EOF, `q` con el robot caído; `b/l/g` con la secuencia parada. `test_tareas`: 13 → 22 | `python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas` | 149 pruebas OK en ≈ 19 s (tres ejecuciones seguidas; robot falso en `127.0.0.1`, simulador falso: sin ventana, sin robots reales ni URSim; `robots.json` real solo se parsea en `test_el_robots_json_de_src_es_valido`) | ⚠️ | 2026-10-14 |
| T9 | Tras C1–C4, `main.py` entero con la ventana REAL de PyBullet y robots falsos propios (primaria, tiempo real, varios, `ensenar` con g, l, v, e, q, y `--v 0.5` rechazado). Aquí apareció F21: `ensenar` se quedaba mudo. Además, con la ventana real, `q` cierra la ventana (`btShutDownExampleBrowser ... Thread TERMINATED`: `Simulador.cerrar()` verificado) | `python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_extremo_a_extremo.py` y `python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas` | Antes del arreglo: 6 FALLOS en `ensenar`. Después: `TODO OK` y 149 pruebas OK en ≈ 19 s. Sin robots reales ni URSim | ✅ | 2026-10-14 |

**Las filas T1–T9 son del código anterior a la limpieza** (D17–D21): los nombres (`UrPrimaria`, `LectorUR`, `ErrorUR`, `estado_fresco`…) y los números de pruebas ya no valen; los resultados vigentes son los de T10–T12. T3 también usaba la opción `desplazado`, que ya no existe.

| Id | Qué se prueba | Comando | Resultado | Estado | Fecha |
|---|---|---|---|---|---|
| T10 | Pruebas automáticas tras la limpieza por capas: `red` (12), `ur` (35), `simulador` (9), `secuencia` (28), `tareas` y `main` (28) e integración con el robot falso (10). Cubren: corte y decodificación de paquetes (primaria y tiempo real), `movej` con límites, aviso de puerto equivocado (100 paquetes sin estado), `HiloLectorUR` (reconexión, un solo aviso por motivo, `detener()` inmediato), `Reproductor` (camino feliz, protección, emergencia, `stopj` que no sale), ficheros de secuencia malos, comandos de la consola, `main()` con códigos 0/1/2, `visualizar` con 1 y 2 robots (primaria, tiempo real y uno caído) y `ensenar` contra el robot falso (guardar, ejecutar, terminar, ventana cerrada con el robot en movimiento, robot que se cae) | `python -u -B -m unittest discover -s pruebas` (desde `2_practicas\Practica1_visualizador_UR3e`) | 122 pruebas OK en ≈ 32 s. Robot falso en `127.0.0.1` (y `127.0.0.2`), simulador falso: sin ventana, sin robots reales ni URSim. Las dos primeras ejecuciones dieron 3 fallos que eran de las pruebas y de un caso real (F23, F24) | ⚠️ | 2026-10-16 |
| T11 | `Simulador` con la librería **real** `UR3e_rg2`: ids de PyBullet, articulaciones, posición de las bases | `python -u -B 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_pybullet.py` | OK: robot1 → id 0 y robot2 → id 2; articulaciones leídas con `pybullet.getJointState` iguales a las enviadas (p. ej. `[0.3, -1.0, 0.5, -1.2, 0.4, 0.1]` rad); base x = 0,00 m y 1,00 m (robots colocados en fila por `agregar_robot`). Abre la ventana ≈ 2 s y `Simulador.cerrar()` la cierra | ✅ | 2026-10-16 |
| T12 | `main.py` entero (`primaria`, `tiempo-real`, `varios`, `ensenar`) como subproceso con la ventana real de PyBullet contra robots falsos en puertos libres; `varios` con dos robots en `127.0.0.1` y `127.0.0.2` y el mismo puerto | `python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_extremo_a_extremo.py` | `TODO OK` (15 comprobaciones): imprime `q (grados): [0.0, -90.0, 0.0, -90.0, 0.0, 0.0]` en primaria y tiempo real; los 2 robots de `varios` imprimen su `q`; en `ensenar` funcionan `g`, `l`, `v` y `e` (1 `movej` con `a=0.5, v=0.3`, llega a q[0] = 0,200 rad) y `ensenar --v 0.5` sale con código 2. Abre la ventana ≈ 5 s cuatro veces. Robots falsos: no es URSim ni un UR3e | ⚠️ | 2026-10-16 |

| T13 | D22: robot sacado de `robots.json` (primero por defecto, `--robot`, nombre inexistente, `--robot` con `--ip`) y regresión de T10 y T12 | `python -B -m unittest discover -s 2_practicas\Practica1_visualizador_UR3e\pruebas` y `python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\humo_extremo_a_extremo.py` | 125 pruebas OK en ≈ 32 s (3 nuevas + `ip_robot`); humo `TODO OK` (15 comprobaciones; ahora con `--ip 127.0.0.1` explícito). Robots falsos: no es URSim ni un UR3e | ⚠️ | 2026-10-16 |

Qué cubre T10 en lo que más importa (cada punto con su prueba en `pruebas/`):

- Corte de paquetes con mensajes troceados (byte a byte), longitudes imposibles y desalineación; decodificación de estado y errores → `test_ur.py`.
- `movej` se niega a enviar ángulos en grados, 5 ángulos, velocidades > 0,3 rad/s o aceleraciones > 0,5 rad/s², y no envía nada → `test_ur.py`.
- Máquina de estados: camino feliz, parada de protección y reanudar, error del robot, orden no aceptada, cancelar, conexión perdida → `test_secuencia.py` (reloj controlado) y `test_integracion.py` (contra el robot falso, con movimiento real).
- Reconexión de `HiloLectorUR` cuando el robot corta → `test_ur.py` y `test_integracion.py`.
- Las tareas de la práctica de principio a fin (con simulador falso) → `test_tareas.py`.

Para lanzar el robot falso a mano y probar `main.py` sin URSim (**no usar los puertos 30001–30013 con URSim abierto**):

```powershell
python -u 2_practicas\Practica1_visualizador_UR3e\pruebas\robot_falso.py 31001
python -u 2_practicas\Practica1_visualizador_UR3e\src\main.py primaria --puerto 31001
```

## Versiones de partida desde su nueva carpeta (2026-10-14)

Comprobación posterior a la migración: las versiones archivadas se siguen ejecutando desde `versiones/`. **Todas contra el robot falso** de `claude_1/simulador_ur.py` en `127.0.0.1:31001` (puerto fuera de los de URSim; no había VirtualBox ni puertos 30001–30013 ocupados). Solo lectura: no se envió ningún `movej`.

Preparación común (el simulador se deja en segundo plano y se para al terminar):

```powershell
python -B -u 2_practicas\Practica1_visualizador_UR3e\versiones\claude_1\simulador_ur.py 31001
```

| Id | Qué se prueba | Comando | Resultado | Estado | Fecha |
|---|---|---|---|---|---|
| V1 | `claude_1`: `ejercicio1_leer_un_robot.py` importa `ur_primary` y lee el robot falso | `python -B -u 2_practicas\Practica1_visualizador_UR3e\versiones\claude_1\ejercicio1_leer_un_robot.py --robot 127.0.0.1:31001 --hz 2` (4 s) | «sin datos todavia», «conectado a 127.0.0.1:31001» y después, 2 veces por segundo: joints (rad) `[0.000, -1.570, 0.000, -1.570, 0.000, 0.000]`, TCP en ceros (el robot falso lo emite así) y `modo: running`. Sin errores | ✅ | 2026-10-14 |
| V2 | `claude_2`: `primaria.conectar` + `mensajes` + `leer_estado` | `python -B -u 2_practicas\Practica1_visualizador_UR3e\pruebas\leer_claude2_robot_falso.py` (script en [pruebas/](../pruebas/leer_claude2_robot_falso.py); lee 3 estados) | 1 mensaje tipo 20 ignorado y 3 estados con `q` (rad) = `[0.0, -1.57, 0.0, -1.57, 0.0, 0.0]` y `modo` = 7 | ✅ | 2026-10-14 |
| V3 | `a_mano`: `main.py` | no ejecutada | Falla por el caso F5 de [depuración](depuración.md), verificado por la Pi el 2026-10-13 (no imprime nada en 6 s) | ❌ | 2026-10-14 |

Lo que **no** demuestran V1 y V2: el robot falso no es URSim ni un robot real, así que no validan los 251 B del subpaquete 1, el TCP ni los mensajes de error.

## Lo que no se ha probado

- **`src/` contra URSim o un UR3e real.** Es lo siguiente. Antes de enviar `movej` a URSim hay que avisar a Josu; en un robot real, `--v 0.1 --a 0.2`, zona despejada y primero solo lectura (`primaria`).
- **Lo que se ve en la ventana.** T3 y T4 comprueban los ángulos por la API de PyBullet, no a ojo: la postura reconocible y el convenio de ángulos del enunciado (apartado 9) los tiene que mirar Josu.
- **Formatos del protocolo con un robot:** los 251 B del subpaquete 1, los offsets de los mensajes tipo 20 (subtipos 6 y 10) y el offset 252 del tiempo real salen del PDF a través de `claude_2` y no están verificados.
- **Carga del tiempo real:** el robot falso emite a 10 Hz; un robot real manda ≈ 500 paquetes/s al `HiloLectorUR`.
- **`isProgramRunning` en URSim:** el `Reproductor` supone que sube a `True` mientras dura el `movej`. Si URSim no lo hiciera, a los 2 s daría la orden por rechazada salvo que el robot ya hubiera llegado.
- **Previsualización con un robot real:** `previsualizar` bloquea el hilo principal (ver [arquitectura](arquitectura.md), limitaciones).
- **Versiones archivadas:** cualquiera contra URSim o un robot real (`claude_1` tiene pruebas con 2 URSim del 2026-10-08 en su `docs/05_pruebas_y_resultados.md`, que aquí no se han repetido); de `claude_2`, `tiempo_real.py`, `varios_robots.py` y `ensenar_reproducir.py`; de `claude_1`, los ejercicios 2 a 5, el gemelo 3D, `--metodo rtde` y `--arrancar`.
