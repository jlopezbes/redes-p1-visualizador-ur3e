"""
Falso UR para probar el codigo sin URSim: emite paquetes tipo 20 y 16 (subpaquetes 0, 1 y 4)
a 10 Hz y entiende lineas "movej([q1,...,q6], a=..., v=...)". Un robot por puerto.
El TCP que emite es falso (ceros); solo las articulaciones son reales.

    python simulador_ur.py 30001 30011
"""
import re
import socket
import sys
import threading
import time
from struct import pack

VELOCIDAD = 0.5   # rad/s
HZ = 10


def subpaquete(tipo, datos):
    return pack(">iB", len(datos) + 5, tipo) + datos


class RobotFalso:
    def __init__(self, puerto):
        self.puerto = puerto
        self.q = [0.0, -1.57, 0.0, -1.57, 0.0, 0.0]
        self.objetivo = list(self.q)

    def paquete_estado(self):
        modo = pack(">Q???????BBdddB", int(time.time() * 1000), True, True, True, False, False, False, False,
                    7, 0, 1.0, 1.0, 1.0, 0)
        joints = b"".join(pack(">dddffffB", q, o, 0.0, 0.0, 0.0, 0.0, 0.0, 253)
                          for q, o in zip(self.q, self.objetivo))
        tcp = pack(">dddddd", 0, 0, 0, 0, 0, 0) + pack(">dddddd", 0, 0, 0, 0, 0, 0)
        cuerpo = subpaquete(0, modo) + subpaquete(1, joints) + subpaquete(4, tcp)
        return pack(">iB", len(cuerpo) + 5, 16) + cuerpo

    def mover_un_paso(self, dt):
        for i, (q, o) in enumerate(zip(self.q, self.objetivo)):
            paso = VELOCIDAD * dt
            self.q[i] = o if abs(o - q) <= paso else q + paso * (1 if o > q else -1)


def atender_cliente(robot, conn):
    def escuchar():
        buffer = ""
        try:
            while True:
                datos = conn.recv(1024)
                if not datos:
                    return
                buffer += datos.decode("utf-8", errors="ignore")
                for m in re.finditer(r"movej\(\[([^\]]+)\]", buffer):
                    robot.objetivo = [float(x) for x in m.group(1).split(",")]
                    print("[:{}] movej recibido -> {}".format(robot.puerto, robot.objetivo))
                buffer = buffer[buffer.rfind("\n") + 1:]
        except OSError:
            pass
    threading.Thread(target=escuchar, daemon=True).start()
    try:
        conn.sendall(pack(">iB", 15, 20) + b"\x00" * 10)   # "mensaje de version" falso
        while True:
            conn.sendall(robot.paquete_estado())
            time.sleep(1.0 / HZ)
    except OSError:
        conn.close()


def servir(robot):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", robot.puerto))
    server.listen(5)
    print("Robot falso escuchando en el puerto {}".format(robot.puerto))
    while True:
        conn, _ = server.accept()
        threading.Thread(target=atender_cliente, args=(robot, conn), daemon=True).start()


def main():
    robots = [RobotFalso(int(p)) for p in (sys.argv[1:] or ["30001"])]
    for robot in robots:
        threading.Thread(target=servir, args=(robot,), daemon=True).start()
    try:
        while True:
            time.sleep(1.0 / HZ)
            for robot in robots:
                robot.mover_un_paso(1.0 / HZ)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
