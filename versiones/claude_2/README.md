# Práctica 1 – Visualizador de un UR3e por TCP/IP

Lee el estado de un UR3e (real o URSim) por TCP/IP y lo reproduce en PyBullet.

| Nivel | Script | Qué hace |
|---|---|---|
| Aprobado | `primaria.py` | Interfaz primaria (30001): 1 robot → PyBullet |
| Aprobado | `tiempo_real.py` | Interfaz de tiempo real (30003): 1 robot → PyBullet |
| Notable | `varios_robots.py` + `robots.json` | Varios robots en la misma ventana, un hilo por robot |
| Sobresaliente | `ensenar_reproducir.py` | Enseñar puntos, previsualizar, ejecutar con `movej`, supervisar errores |

`primaria.py` también es un módulo: lo importan `varios_robots.py` y `ensenar_reproducir.py`.

## Requisitos

- Python 3.7 o superior y el visualizador `UR3e_rg2` (en Python ≥ 3.9: `pip install ur3e_rg2-0.1.0-py3-none-any.whl`).
- Solo se usan `socket`, `struct`, `threading` y otros módulos estándar.

## Cómo ejecutar

```powershell
cd "C:\Users\Estudiante\Josu\Redes\practica1"
python primaria.py                      # URSim 1: 127.0.0.1 puerto 30001
python tiempo_real.py                   # URSim 1: 127.0.0.1 puerto 30003
python varios_robots.py                 # lee robots.json
python ensenar_reproducir.py            # URSim 1: 127.0.0.1 puerto 30001
```

Para otro robot basta cambiar la IP (en el laboratorio, `10.172.21.203` a `.206`), sin tocar el código:

```powershell
python primaria.py --ip 10.172.21.203
python tiempo_real.py --ip 10.172.21.203
python ensenar_reproducir.py --ip 10.172.21.203
```

## Configuración de robots (`robots.json`)

```json
[
  {"nombre": "robot1", "ip": "127.0.0.1", "puerto": 30001, "posicion": [0, 0, 0, 0, 0, 0]},
  {"nombre": "robot2", "ip": "127.0.0.1", "puerto": 30011, "posicion": [1, 0, 0, 0, 0, 0]}
]
```

`posicion` es `[x, y, z, roll, pitch, yaw]` de la base del robot simulado (m y rad). Con robots reales: IP real y
puerto 30001 en todos. Con otro fichero: `python varios_robots.py --config otro.json`.

## URSim en este PC (VirtualBox con NAT)

| | Primaria | Tiempo real |
|---|---|---|
| URSim 1 (`URSim_VIRTUAL-5.12.6...`) | `127.0.0.1:30001` | `127.0.0.1:30003` |
| URSim 2 (`URSim2`) | `127.0.0.1:30011` | `127.0.0.1:30013` |

En modo puente (como en el aula) cada VM tiene su propia IP 10.172.18.x y se usan los puertos estándar 30001 y 30003.
Para la interfaz de tiempo real con URSim 2: `python tiempo_real.py --puerto 30013`.

## Enseñar y reproducir

Los comandos se escriben en la consola mientras la ventana de PyBullet sigue el robot:

| Comando | Acción |
|---|---|
| `g` | guardar la posición actual como siguiente punto |
| `v` | previsualizar la secuencia en PyBullet (el robot no se mueve) |
| `e` | ejecutar: un `movej` por punto, sin enviar el siguiente hasta que el anterior termina y `q_actual` está a menos de 0,01 rad |
| `c` | cancelar |
| `r` | reanudar desde el punto donde se paró por un error |
| `s [fichero]` / `l [fichero]` | guardar / cargar la secuencia (por defecto `secuencia.json`) |
| `b` | borrar todos los puntos |
| `q` | salir |

La secuencia se detiene (`stopj`) y se muestra el motivo si llega un mensaje de error (tipo 20, subtipos 6 o 10), si se
activa una parada de protección, si el robot no acepta la orden en 2 s o si el programa termina sin llegar al punto.

**Antes de enviar órdenes**: el robot encendido con frenos liberados (`robotMode = 7`), y en URSim/PolyScope 5
*Ajustes → Sistema → Control remoto* y seleccionar **Remoto** arriba a la derecha.

**Robot real**: límites fijos en el código a 0,3 rad/s y 0,5 rad/s²; probar antes en URSim y con el profesor presente.
