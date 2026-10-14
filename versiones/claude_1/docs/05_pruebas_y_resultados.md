# 05 – Pruebas y resultados

Leyenda: ✅ verificado con ejecución real · ⚠️ ejecutado pero con salvedad · ❌ no probado.

## Fase A – Contra el robot falso (`simulador_ur.py`), antes de existir URSim

Dos robots falsos en `30001` y `30011`.

| Prueba | Resultado |
|---|---|
| Ejercicio 1 lee posiciones | ✅ `joints (rad): [0.000, -1.570, 0.000, -1.570, 0.000, 0.000] … modo: running` |
| Ejercicio 2 con 2 robots | ✅ ambos robots impresos |
| Ejercicio 3 `--pose pose1` a ambos | ✅ llegan a `[0.785, -0.785, -1.570, -1.570, 2.570, 0.000]`, "llego al destino" |
| Ejercicio 4 (origen movido por `movej`, destino sigue) | ✅ `diferencia máxima: 0.000 rad` |

(El simulador no entiende `speedj`, por lo que el método `speed` **no** se probó con él.)

## Fase B – Contra URSim reales (2 VMs)

### B1. Lectura – ✅
`ejercicio2_varios_robots.py --robots 127.0.0.1:30001 127.0.0.1:30011` (salida pegada por el usuario tras reiniciar la VM2):
```
[UR1] joints (rad): [ -1.601,  -1.508,  -1.936,  -1.294,   1.596,  -0.031] | TCP: [-0.137, -0.267,  0.237, -0.001,  3.116,  0.039] | modo: running
[UR2] joints (rad): [ -1.601,  -1.727,  -2.203,  -0.808,   1.595,  -0.031] | TCP: [-0.137, -0.267,  0.147, -0.001,  3.116,  0.039] | modo: running
```
Robots independientes con poses distintas. El TCP real (no ceros) se obtiene del subpaquete 4. Estado de seguridad leído de ambos: `isProtectiveStopped=False`, `isEmergencyStopped=False`, `robotMode=7`, todos los `jointMode=253`.

### B2. Movimiento (ejercicio 3, `socket`) – ✅ (con una anomalía no reproducida)
- **Segunda ejecución** (robots en `home`), `--pose pose1 --v 0.5 --a 0.5`, ambos robots:
  - Llegan a `[0.784, -0.787, -1.566, -1.570, 2.564, 0.000]` (UR1) y `[0.783, -0.788, -1.565, -1.570, 2.563, 0.000]` (UR2). Duración total **8.2 s**. Ambos "llego al destino".
- Solo el robot 1 a `home` (`--pose home`): llegó correctamente.
- **Anomalía (1ª ejecución, no reproducida):** al enviar `pose1` a ambos con los robots en poses arbitrarias, el script terminó con **"NO llego al destino"** en ambos y los robots quedaron en posiciones intermedias distintas (UR1 `[-1.455, -1.447, -1.825, -1.415, 1.655, -0.029]`, UR2 `[1.115, -0.459, -1.542, -2.205, 1.821, 0.296]`). No se comprobó el estado de seguridad en ese momento (la lectura de `isProtectiveStopped=False` en ambos robots se hizo después, con los robots ya en `home`). Al repetir desde `home` funcionó. Una captura de pantalla de la VM2 tomada justo después mostraba la pestaña **Move** de PolyScope abierta; **es solo una hipótesis** de que interfiriera. Causa real: desconocida.

### B3. Espejo (ejercicio 4) – ✅ para `socket` y `speed`; ❌ para `rtde`
Prueba: `ejercicio4_espejo.py --origen 127.0.0.1:30001 --destino 127.0.0.1:30011`, y **solo el robot 1 recibe orden** (ejercicio 3, lento: `--v 0.15 --a 0.3`); el robot 2 no recibe ninguna orden directa.

| Método | Retraso durante el movimiento | Al terminar |
|---|---|---|
| `socket` (movej cortos, periodo 0.2) | crece hasta **0.6–0.8 rad** (máximo medido 0.794) | tarda varios segundos más en converger (aún 0.257 rad cuando se cortó la prueba, con el origen ya parado) |
| **`speed`** (speedj, periodo 0.1, ganancia 4) | estable en **≈ 0.04 rad** (0.034–0.052) | **0.000 rad** |

Conclusión: `speed` es el método por defecto.

### B4. Gemelo 3D – ⚠️
`ejercicio2_varios_robots.py --robots 127.0.0.1:30001 127.0.0.1:30011 --gemelo` ejecutado 15 s: proceso vivo, ventana de PyBullet iniciada ("ExampleBrowserThreadFunc started"), **sin tracebacks en stderr**. **Nadie confirmó visualmente** que el modelo se mueva con los robots. Los imports (`pybullet`, `UR3e_rg2.dynamic_ur3e`, `gemelo`) se comprobaron aparte: OK.

## Lo que NO se ha probado (importante)

| Funcionalidad | Motivo |
|---|---|
| `ejercicio3_mover.py --metodo rtde` | nunca se ejecutó; `ur_rtde` solo se instaló y se comprobó `import rtde_control` |
| `ejercicio4_espejo.py --metodo rtde` (`servoJ`) | idem |
| `--arrancar` y `--dashboard-puertos` | el usuario encendía los robots desde PolyScope; el dashboard (29999/29998) no se ejercitó |
| Mover el origen **a mano** (pestaña Move/Freedrive) y ver al destino seguirlo | solo se movió el origen con scripts |
| Cualquier cosa con **robots físicos** del laboratorio | aún no disponibles |
| Gemelo 3D con movimiento visible | ver B4 |
| Estabilidad prolongada (> unos minutos), pérdida y reconexión de un robot a mitad de ejecución | solo se vio un `timed out` + reintento automático durante el problema de red de la VM2 (funcionó: "Reintentando en 2 s…") |
| Frecuencia real de emisión del puerto 30001 de URSim | no medida |

## Incidente de prueba (para no repetirlo)

Al probar el ejercicio 4 por primera vez con `simulador_ur.py 30001 30011` mientras el URSim del usuario ya escuchaba en `127.0.0.1:30001` (reenvío de VirtualBox), el **"origen" era en realidad el URSim real** y se le envió `movej([0.5,-1.2,-1.0,-1.5,1.5,0.2], …)`, que **movió el robot virtual del usuario** sin que lo supiera (se detectó porque el TCP no era ceros). Se le informó al instante. Lección: antes de lanzar el simulador falso, comprobar con `Get-NetTCPConnection -State Listen -LocalPort 30001` que el puerto está libre; y avisar siempre antes de mover.
