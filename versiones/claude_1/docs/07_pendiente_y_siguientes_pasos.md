# 07 – Pendiente y siguientes pasos (para el siguiente agente)

## Qué NO hacer sin preguntar

- **No muevas los robots** (ejercicio 3/4, `speedj`, `movej`) sin avisar al usuario: aunque sean URSim, para él son reales (ver incidente en `05`).
- No lances `simulador_ur.py` si hay URSim abierto (colisión de puertos 30001/30011).
- No modifiques `VIEJO COMUNICACIONES\`.
- No reinicies/apagues las VMs del usuario sin pedirlo (están encendidas con PolyScope abierto).

## Pendiente conocido (por prioridad probable)

1. **Robots del laboratorio.** El usuario dijo "primero las instancias, luego los del laboratorio". Con IPs reales (`10.172.21.203`, `10.172.21.206` el año pasado) basta `--robots IP1 IP2`. Será el momento de **probar por primera vez** `--metodo rtde` (ejercicio 3 y 4) y `--arrancar`. Precauciones: robots físicos → velocidades bajas (`--v 0.1 --a 0.2`), área despejada, probar primero lectura (ejercicio 2), luego un movimiento pequeño. Considera añadir un **límite de seguridad** (velocidad máxima y saturación) al ejercicio 4 antes de usarlo en físico: ahora `speedj` satura a ±1.5 rad/s con ganancia 4, que es **agresivo para un robot real**; sugiere bajar `GANANCIA` y el límite.
2. **Enunciado oficial de este año.** No se ha visto. El usuario quiere "afinar" con él: contrastar qué pide exactamente (¿gemelo 3D obligatorio?, ¿qué formato de salida?, ¿memoria PDF como el año pasado?, ¿más ejercicios?). El año pasado solo se entregaron los 3 primeros ejercicios y una memoria muy corta.
3. **Verificar el gemelo 3D visualmente** (`--gemelo` en ejercicios 1 y 2). Está instalado y arranca, pero no hay confirmación de que el modelo siga a los robots. Si el enunciado lo exige, considerar un `--gemelo` en el ejercicio 4 (hoy no lo tiene) y valorar actualizar el 3D al ritmo del bucle.
4. **Probar `--arrancar` y `--dashboard-puertos`** con los dashboards `29999` (VM1) y `29998` (VM2).
5. **Probar el espejo moviendo el origen a mano** (pestaña Move de PolyScope) y no solo por script.
6. **Medir la frecuencia real** del puerto 30001 (si hace falta mejorar el seguimiento o justificar `--periodo`).

## Posibles mejoras (no pedidas; confirmar antes de hacerlas)

- Ejercicio 3: enviar el movimiento a todos los robots en paralelo y esperar llegada en paralelo (hoy es secuencial).
- Ejercicio 4: `GANANCIA`/límite como argumentos de línea de comandos; opción `--gemelo`; modo bidireccional.
- Ampliar `simulador_ur.py` para entender `speedj`/`stopj` y emitir un TCP coherente (hoy es ceros).
- Pinza RG2: el proyecto antiguo la controla con `xmlrpc http://IP:41414 rg_grip i/0 d/<ancho> d/<fuerza>`. No se ha pedido ahora.
- Tests automáticos (hoy no hay): el parser (`ur_primary.py`) es fácilmente testeable con los paquetes que genera `simulador_ur.py`.
- Convertir la memoria/entrega a PDF si el enunciado lo pide (los archivos del año pasado están en `VIEJO COMUNICACIONES\Prácticas\Práctica1_JosuLópez\`).

## Riesgos y trampas conocidas

| Riesgo | Detalle |
|---|---|
| Anomalía no reproducida del ejercicio 3 | Una vez los dos robots no llegaron a `pose1` (ver `05`, B2). Si reaparece, mirar: pestaña **Move** de PolyScope abierta, protective stop (`modo.isProtectiveStopped`), captura de pantalla de la VM (`VBoxManage controlvm <vm> screenshotpng`) |
| `Test-NetConnection` en NAT da falsos positivos | VirtualBox acepta la conexión aunque el invitado no responda; comprobar siempre con una lectura real |
| `ur_rtde` con puerto fijo | En las VMs NAT solo el robot 1 (30004) es utilizable como destino RTDE |
| Python 3.7 | No usar sintaxis ≥ 3.8; `ur_rtde` 1.6.5 y `pybullet` 3.2.7 compatibles; muchas librerías actuales ya no |
| Salida redirigida de Python | Usar `python -u` |
| Reinicio de PC | Los paquetes están en el site-packages de usuario y siguen; las VMs hay que volver a arrancarlas y abrir URSim (UR3e) y encender los robots |
| Temporales | Los directorios en `%TEMP%` pueden desaparecer; no hay nada imprescindible en ellos (el parche de `UR3e_rg2` está documentado en `04`) |

## Cómo retomar rápido (checklist)

1. Leer `docs\README.md` (estado) y esta página.
2. Preguntar al usuario: ¿ya tiene el enunciado? ¿trabajamos ya con robots físicos? ¿qué quiere ajustar?
3. Comprobar que las VMs están arrancadas y los puertos en escucha:
   ```powershell
   & "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" list runningvms
   Get-NetTCPConnection -State Listen -LocalPort 30001,30011,29999,29998 | Select LocalAddress,LocalPort
   ```
4. Prueba de humo **solo de lectura**:
   ```powershell
   cd "C:\Users\Estudiante\Josu\Redes\practica 1"
   python ejercicio2_varios_robots.py --robots 127.0.0.1:30001 127.0.0.1:30011
   ```
   Si UR2 no da datos: ver `04` (sección "Problema" de la VM2) y reiniciar el invitado.
5. Cualquier movimiento: **avisar primero**.

## Preguntas abiertas para el usuario (sin respuesta aún)

- ¿El enunciado exige el visualizador 3D (`UR3e_rg2`) o basta con URSim?
- ¿Qué robots físicos del laboratorio y qué IPs este año?
- ¿Hay que entregar memoria (PDF) además del código?
- ¿Son necesarios más movimientos/poses que `home` y `pose1`?
