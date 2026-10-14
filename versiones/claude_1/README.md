# Práctica 1 – Comunicación con UR (URSim / robots reales)

> **Documentación detallada del proceso, el entorno y lo pendiente: [`docs/README.md`](docs/README.md)** (empieza por ahí si retomas el trabajo).

| Archivo | Qué hace |
|---|---|
| `ur_primary.py` | Lectura de la interfaz primaria (puerto 30001): paquete tipo 16, subpaquetes 0 (modo), 1 (joints) y 4 (TCP). Hilo `LectorUR`. |
| `gemelo.py` | Wrapper del visualizador 3D `UR3e_rg2` (PyBullet). Opcional; `pybullet` no está instalado (no hay binario para Windows + Python 3.7). |
| `ejercicio1_leer_un_robot.py` | Lee un robot y printea sus posiciones. |
| `ejercicio2_varios_robots.py` | Lee varios robots (un hilo por robot). |
| `ejercicio3_mover.py` | Mueve uno o varios robots (URScript por socket o `ur_rtde`) y comprueba que llegan. |
| `ejercicio4_espejo.py` | Lee un robot (origen) y mueve otro (destino) para que lo copie. |
| `ejercicio5_bidireccional.py` | Espejo en los dos sentidos: el robot que se mueve (primario o secundario) lidera y el otro lo copia. |
| `simulador_ur.py` | Robot falso para probar sin URSim (no usar a la vez que URSim: pisa los puertos). |

## Instancias de URSim en este PC (VirtualBox, red NAT)

| | Primary | RTDE | Dashboard |
|---|---|---|---|
| Robot 1 (`URSim_VIRTUAL-5.12.6...`) | `127.0.0.1:30001` | 30004 | 29999 |
| Robot 2 (`URSim2`) | `127.0.0.1:30011` | 30014 (ur_rtde no admite cambiar puerto) | 29998 |

```powershell
cd "C:\Users\Estudiante\Josu\Redes\practica 1"
python ejercicio1_leer_un_robot.py --robot 127.0.0.1
python ejercicio2_varios_robots.py --robots 127.0.0.1:30001 127.0.0.1:30011
python ejercicio3_mover.py --robots 127.0.0.1:30001 127.0.0.1:30011 --pose pose1 --arrancar --dashboard-puertos 29999 29998
python ejercicio4_espejo.py --origen 127.0.0.1:30001 --destino 127.0.0.1:30011
python ejercicio5_bidireccional.py --primario 127.0.0.1:30001 --secundario 127.0.0.1:30011
```

Con los robots del laboratorio solo cambian las IPs (`--robots 10.172.21.203 10.172.21.206`).
Dependencias opcionales: `pip install ur_rtde` (ya instalado, `--metodo rtde`) y el gemelo 3D (`UR3e_rg2`, requiere `pybullet`).
