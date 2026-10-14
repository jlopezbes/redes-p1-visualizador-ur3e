# 06 – Problemas encontrados y decisiones tomadas

## A. Bugs / defectos del código del año pasado (y cómo se resolvieron)

| Dónde | Defecto | Solución actual |
|---|---|---|
| `ProyectoUR.py` | Usa `s.recv(n)` directo: TCP puede devolver menos bytes → lecturas corruptas | `recv_exact` (bucle hasta completar) |
| `ProyectoUR.py` | Lee solo **5** articulaciones (`range(5)`) en un robot de 6 | `N_JOINTS = 6` |
| `ProyectoUR.py` | `V_actuales.append(q_actual)` guarda la posición en vez de la tensión | `parsear_joints` guarda `V_actual` real |
| `ProyectoUR.py` | Parsea el paquete de versión (tipo 20) con tamaños frágiles y sin usarlo | Se descarta |
| `ProyectoUR.py` | Los hilos llaman a `visualizacion.move_robot` (PyBullet no es thread‑safe) | Los hilos solo guardan el último estado; el principal dibuja |
| `ProyectoUR.py` | `crear_hilo` devuelve `None`; la lista `hilos` es local y no se usa | `LectorUR(Thread)` con `parar()` |
| `ProyectoUR.py` | Sin reconexión ni manejo de errores | `LectorUR` reconecta cada 2 s |
| `practica1_Asier_Burgos.py` | Al desempaquetar el subpaquete 0 nombra solo 6 booleanas → nombres desplazados | `parsear_modo_robot` con las 7 (`isProtectiveStopped` incluida) |
| `practica1_Asier_Burgos.py` | `robot_joint('10.172.21.202',)` llamada con argumentos faltantes; bloques comentados | Reescrito |
| `practica1_Asier_Burgos.py` | `move_robot` con `rtde_c.moveJ(q, 0.2, 0.3)`: mezcla de orden `(velocidad, aceleración)` | `moveJ(q, v, a)` explícito y documentado |
| `controladorUR3_TCP.py` | `go_home` pasa `v` como `lineal` (argumentos mal colocados) | No se reutilizó |
| Memoria PDF práctica 1 | Los dos ejercicios de mover el robot **no estaban hechos** | Hechos (ejercicios 3 y 4) |

## B. Problemas de entorno y cómo se resolvieron

### B1. `pybullet` no se instala en Windows con Python 3.7
- `pip install pybullet ur_rtde` falló: `error: command 'cl.exe' failed: No such file or directory`.
- `pip download pybullet --only-binary :all:` → "no matching distribution". La consulta a la API JSON de PyPI mostró que **todas las ruedas son `manylinux`** (no hay `win_amd64`), por eso el año pasado (Linux del laboratorio) iba sin más.
- **Solución:** el usuario ya tenía **Visual Studio 2022 Community** con MSVC; `cl.exe` simplemente no estaba en el PATH. Compilar desde `vcvars64.bat` con `DISTUTILS_USE_SDK=1` y `MSSdk=1` funcionó (pybullet 3.2.7, unos minutos).
- Alternativas descartadas (no hizo falta): instalar Build Tools con `winget` (pide admin), otra versión de Python, conda.

### B2. `ur_rtde` y permisos
`pip install ur_rtde` sin `--user` falló por permisos (sesión sin admin). Con `--user --only-binary :all:` funcionó (ur_rtde 1.6.5 trae rueda para Windows/3.7).

### B3. `UR3e_rg2` incompatible con Python 3.7
- `BulletGym.py` importa `TypedDict`/`Literal` de `typing` (≥ 3.8) y `setup.py` fija `numpy==1.24.4`, `scipy==1.10.1`, etc. (requieren ≥ 3.8).
- **Solución:** instalar con `--no-deps` desde una **copia parcheada** (importar de `typing_extensions`), con dependencias compatibles instaladas a mano. Detalle en `04`.
- Alternativa no tomada: instalar Python ≥ 3.8 (el usuario tiene 3.7 como único Python; los `.pyc` antiguos muestran 3.7, 3.11, 3.13 y 3.8 en distintos equipos).

### B4. Segundo URSim: bridged vs NAT
- Propuesta inicial del asistente: clonar la VM con **red puente** (IP propia, puertos estándar). Los comandos que se le dieron al usuario contenían placeholders `<ip_vm2>` y `NOMBRE_DE_TU_TARJETA`; **PowerShell rechaza `<`** ("operador reservado") y el usuario respondió "no ejecuta ese código".
- El usuario propuso: "al final esto será localhost también, no? cambiará el puerto si acaso". **Se adoptó su idea**: ambas VMs en NAT con puertos de host distintos.
- Contrapartida aceptada: `ur_rtde` y el dashboard usan puertos fijos (30004/29999); la VM2 solo es utilizable por `socket`/`speed`. Para el dashboard se añadió `--dashboard-puertos`; para RTDE no hay solución con NAT (se podría usar la VM2 como **origen** y la VM1 como **destino**).
- El clon heredó las reglas NAT de la VM1 (mismos puertos de host) → hubo que **borrar** las 4 reglas y crear otras.
- Cambiar `nic1` de bridged a NAT **en caliente** no renovó la IP del invitado; el invitado quedó sin red hasta reiniciarlo.

## C. Decisiones de diseño y por qué

| Decisión | Motivo |
|---|---|
| Un solo parser (`ur_primary.py`) y un hilo `LectorUR` reutilizable por los 4 ejercicios | El año pasado el código estaba duplicado en varios archivos con pequeñas variaciones |
| Leer el cuerpo del paquete entero y trocear en memoria | Más robusto que leer subpaquete a subpaquete del socket |
| Hilos solo guardan el último estado | PyBullet y los prints se manejan desde el hilo principal |
| Gemelo 3D **opcional**, import perezoso | Aún no está claro si el enunciado lo exige ("como sea más fácil"); además fue lo más costoso de instalar |
| `ip[:puerto]` por robot | Permite varias instancias en `127.0.0.1` con puertos distintos y robots reales por IP |
| Mover por **socket** (URScript en 30001) como método por defecto | Funciona con los puertos NAT; `ur_rtde` no |
| Ejercicio 4: método `speed` (P-control con `speedj`) como defecto | Medido: 0.04 rad de retraso vs 0.6–0.8 rad con `movej` cortos (ver `05`) |
| `ejercicio3`: espera de llegada con tolerancia 0.01 rad y timeout 60 s | Para que la prueba demuestre que "leer + mover" funciona de extremo a extremo |
| Simulador falso con paquetes reales | Permitió desarrollar y verificar todo antes de que el usuario tuviera URSim |
| No tocar `VIEJO COMUNICACIONES` | Es referencia; las extracciones se hicieron en `%TEMP%` |

## D. Elecciones que el usuario hizo explícitamente

1. "Primero las instancias [URSim], luego los del laboratorio."
2. "Aún no está claro [el gemelo 3D], como sea más fácil y con el enunciado ya afinaremos."
3. Aprobó instalar dependencias.
4. Aceptó que `--arrancar` y las notas sobre modo remoto se quedaran como estaban.
5. Aclaró que lo que quería en el ejercicio 4 era que **mover un robot de una VM mueva el robot de la otra VM**, no el simulador PyBullet.
6. Cerró la fase: "Perfecto. Buen trabajo, terminado."
