"""
Ejercicio 3: mover uno o varios UR y comprobar leyendo su posicion que llegan al destino.

    python ejercicio3_mover.py --robots 127.0.0.1 --pose pose1
    python ejercicio3_mover.py --robots 10.172.21.203 10.172.21.206 --metodo rtde --pose home
    python ejercicio3_mover.py --robots 127.0.0.1 --joints 0.5 -1.2 -1.0 -1.5 1.5 0 --arrancar

Metodos:
  socket: envia una linea de URScript (movej) por TCP al puerto 30001 del robot.
  rtde:   usa la libreria ur_rtde (pip install ur_rtde), puerto 30004.
"""
import argparse
import socket
import time
from math import pi

from ur_primary import LectorUR, parsear_robot, formatear_estado

POSES = {
    "home": [0.0, -pi / 2, 0.0, -pi / 2, 0.0, 0.0],
    "pose1": [pi / 4, -pi / 4, -1.57, -1.57, 2.57, 0.0],   # la del codigo del año pasado
}


def dashboard(ip, comando, puerto=29999):
    """Envia un comando al Dashboard Server (power on, brake release...) y devuelve la respuesta."""
    with socket.create_connection((ip, puerto), timeout=5) as s:
        s.recv(1024)   # saludo "Connected: Universal Robots Dashboard Server"
        s.sendall((comando + "\n").encode("utf-8"))
        return s.recv(1024).decode("utf-8").strip()


def arrancar_robot(ip, puerto_dashboard=29999):
    """Enciende el robot y suelta frenos (necesario en URSim recien abierto)."""
    print("[{}:{}] power on: {}".format(ip, puerto_dashboard, dashboard(ip, "power on", puerto_dashboard)))
    time.sleep(2)
    print("[{}:{}] brake release: {}".format(ip, puerto_dashboard, dashboard(ip, "brake release", puerto_dashboard)))
    time.sleep(5)


def mover_socket(ip, puerto, joints, a, v):
    script = "movej([{}], a={}, v={})\n".format(", ".join(str(q) for q in joints), a, v)
    with socket.create_connection((ip, puerto), timeout=5) as s:
        s.sendall(script.encode("utf-8"))
    print("[{}] enviado por socket: {}".format(ip, script.strip()))


def mover_rtde(ip, joints, a, v):
    import rtde_control   # import perezoso: solo hace falta con --metodo rtde
    rtde_c = rtde_control.RTDEControlInterface(ip)
    rtde_c.moveJ(list(joints), v, a)   # ojo: en ur_rtde el orden es (q, velocidad, aceleracion)
    rtde_c.stopScript()
    print("[{}] movimiento rtde terminado".format(ip))


def esperar_llegada(lector, objetivo, tolerancia=0.01, timeout=60):
    """Bloquea hasta que todas las articulaciones esten a menos de `tolerancia` rad del objetivo."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        estado = lector.ultimo_estado()
        if estado and "joints" in estado:
            q = estado["joints"]["q_actual"]
            if max(abs(a - b) for a, b in zip(q, objetivo)) < tolerancia:
                return True
        time.sleep(0.1)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--robots", nargs="+", required=True, help="ip o ip:puerto de cada robot")
    parser.add_argument("--pose", choices=list(POSES), default="pose1", help="pose predefinida")
    parser.add_argument("--joints", nargs=6, type=float, help="6 valores en rad (sustituye a --pose)")
    parser.add_argument("--metodo", choices=["socket", "rtde"], default="socket")
    parser.add_argument("--a", type=float, default=0.2, help="aceleracion (rad/s^2)")
    parser.add_argument("--v", type=float, default=0.2, help="velocidad (rad/s)")
    parser.add_argument("--arrancar", action="store_true", help="hace power on + brake release por el dashboard antes de mover")
    parser.add_argument("--dashboard-puertos", nargs="+", type=int,
                        help="puerto del dashboard de cada robot, en el mismo orden que --robots (por defecto 29999)")
    args = parser.parse_args()

    objetivo = args.joints if args.joints else POSES[args.pose]
    robots = [parsear_robot(r) for r in args.robots]

    lectores = []
    for i, (ip, puerto) in enumerate(robots):
        lector = LectorUR("UR{}".format(i + 1), ip, puerto)
        lector.start()
        lectores.append(lector)

    try:
        if args.arrancar:
            puertos_dash = args.dashboard_puertos or [29999] * len(robots)
            for (ip, _), puerto_dash in zip(robots, puertos_dash):
                arrancar_robot(ip, puerto_dash)

        time.sleep(1)
        for lector in lectores:
            print(formatear_estado(lector.nombre, lector.ultimo_estado()), "(antes)")

        for ip, puerto in robots:
            if args.metodo == "socket":
                mover_socket(ip, puerto, objetivo, args.a, args.v)
            else:
                mover_rtde(ip, objetivo, args.a, args.v)

        for lector in lectores:
            llegado = esperar_llegada(lector, objetivo)
            print(formatear_estado(lector.nombre, lector.ultimo_estado()),
                  "(llego al destino)" if llegado else "(NO llego al destino)")
    finally:
        for lector in lectores:
            lector.parar()


if __name__ == "__main__":
    main()
