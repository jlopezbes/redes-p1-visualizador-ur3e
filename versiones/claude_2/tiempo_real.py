"""
Interfaz de tiempo real (puerto 30003): lee los 6 q_actual de un UR y mueve con ellos el UR3e de PyBullet.

    python tiempo_real.py                           (URSim 1 por NAT: 127.0.0.1:30003)
    python tiempo_real.py --ip 10.172.18.50 --puerto 30003

Formato (big-endian): un unico tipo de paquete, sin campo de tipo:
    [longitud int32][time double][q_target 6xdouble]... q_actual empieza siempre en el byte 252
La longitud total depende de la version del robot, por eso se lee del propio paquete.
"""
import argparse
import socket
import struct
import time

CABECERA = 4              # solo la longitud (int32)
MAX_LONGITUD = 65536
OFFSET_Q_ACTUAL = 252     # 4 + 8 + 5 bloques de 6 doubles (q_target, qd_target, qdd_target, I_target, M_target)
HZ_DIBUJO = 60            # el robot llega a 500 Hz: se consume todo pero se dibuja a un ritmo razonable


def extraer_paquete(buffer):
    """Si el buffer (bytearray) empieza por un paquete completo, lo corta y lo devuelve; si no, None.
    Lanza ValueError si la longitud es imposible."""
    if len(buffer) < CABECERA:
        return None
    longitud = struct.unpack(">i", buffer[:CABECERA])[0]
    if longitud < OFFSET_Q_ACTUAL + 48 or longitud > MAX_LONGITUD:
        raise ValueError("longitud imposible ({}): buffer desalineado".format(longitud))
    if len(buffer) < longitud:
        return None
    paquete = bytes(buffer[:longitud])
    del buffer[:longitud]
    return paquete


def leer_q_actual(paquete):
    return list(struct.unpack(">6d", paquete[OFFSET_Q_ACTUAL:OFFSET_Q_ACTUAL + 48]))


def recibir(ip, puerto, visualizador):
    """Una conexion: consume todo lo que llega y dibuja el ultimo q a HZ_DIBUJO. Termina con una excepcion."""
    with socket.create_connection((ip, puerto), timeout=5) as s:
        s.settimeout(2)         # si no llega nada en 2 s, recv() lanza una excepcion en vez de bloquearse
        print("Conectado a {}:{}".format(ip, puerto))
        buffer = bytearray()
        q = None
        contados = 0
        t_dibujo = t_cuenta = time.time()
        while True:
            datos = s.recv(65536)
            if not datos:
                raise ConnectionError("el robot ha cerrado la conexion")
            buffer += datos
            while True:
                paquete = extraer_paquete(buffer)
                if paquete is None:
                    break
                q = leer_q_actual(paquete)      # solo interesa el ultimo
                contados += 1
            ahora = time.time()
            if q and ahora - t_dibujo >= 1.0 / HZ_DIBUJO:
                visualizador.move_robot(0, list(q))
                t_dibujo = ahora
            if ahora - t_cuenta >= 1.0:
                print("{} paquetes/s | q_actual (grados): {}".format(
                    contados, [round(v * 57.29578, 1) for v in q] if q else "-"))
                contados = 0
                t_cuenta = ahora


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=30003)
    args = parser.parse_args()

    from UR3e_rg2.dynamic_ur3e import UR3eRG2
    visualizador = UR3eRG2()

    while True:                      # si se cae la conexion se vuelve a intentar
        try:
            recibir(args.ip, args.puerto, visualizador)
        except (OSError, ValueError, struct.error) as e:    # incluye ConnectionError y socket.timeout
            print("Conexion perdida ({}). Reintentando en 2 s...".format(e))
            time.sleep(2)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
