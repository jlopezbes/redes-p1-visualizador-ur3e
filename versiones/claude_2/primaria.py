"""
Interfaz primaria (puerto 30001): lee los 6 q_actual de un UR y mueve con ellos el UR3e de PyBullet.

    python primaria.py                              (URSim 1 por NAT: 127.0.0.1:30001)
    python primaria.py --ip 10.172.18.50 --puerto 30001

Este fichero tambien se importa desde varios_robots.py y ensenar_reproducir.py.

Formato (todo big-endian):
    mensaje    = [longitud int32][tipo uint8][cuerpo]            la longitud incluye la cabecera (5 bytes)
    tipo 16    = estado del robot; el cuerpo son subpaquetes con el mismo formato [longitud][tipo][datos]
    subpaquete 1 = datos articulares: 6 x ">dddffffB" (41 bytes) -> q_actual es el primer double de cada uno
"""
import argparse
import socket
import struct
import time

CABECERA = 5            # int32 (longitud) + uint8 (tipo)
MAX_LONGITUD = 65536    # un mensaje mas largo significa que el buffer esta desalineado
TIPO_ROBOT_MESSAGE = 20
TIPO_ESTADO = 16
SUB_MODO = 0
SUB_JOINTS = 1
TAM_SUB_JOINTS = 251    # 5 + 6 * 41
BYTES_JOINT = 41


def extraer_mensaje(buffer):
    """Si el buffer (bytearray) empieza por un mensaje completo, lo corta y devuelve (tipo, mensaje).
    Si todavia no ha llegado entero devuelve None. Lanza ValueError si la longitud es imposible."""
    if len(buffer) < CABECERA:
        return None
    longitud, tipo = struct.unpack(">iB", buffer[:CABECERA])
    if longitud < CABECERA or longitud > MAX_LONGITUD:
        raise ValueError("longitud imposible ({}): buffer desalineado".format(longitud))
    if len(buffer) < longitud:
        return None
    mensaje = bytes(buffer[:longitud])
    del buffer[:longitud]
    return tipo, mensaje


def subpaquetes(mensaje):
    """Recorre un mensaje de estado (tipo 16) y devuelve [(tipo, datos), ...] de sus subpaquetes."""
    resultado = []
    pos = CABECERA
    while pos < len(mensaje):
        tam, tipo = struct.unpack(">iB", mensaje[pos:pos + CABECERA])
        if tam < CABECERA or pos + tam > len(mensaje):
            raise ValueError("subpaquete {} se sale del mensaje".format(tipo))
        resultado.append((tipo, mensaje[pos + CABECERA:pos + tam]))
        pos += tam
    return resultado


def leer_q_actual(datos):
    """Datos del subpaquete 1 -> lista con los 6 q_actual (rad)."""
    if len(datos) + CABECERA != TAM_SUB_JOINTS:
        print("Aviso: subpaquete de articulaciones de {} bytes (se esperaban {}); version distinta?".format(
            len(datos) + CABECERA, TAM_SUB_JOINTS))
    return [struct.unpack(">d", datos[BYTES_JOINT * j:BYTES_JOINT * j + 8])[0] for j in range(6)]


def leer_modo(datos):
    """Datos del subpaquete 0 -> (isProgramRunning, isProtectiveStopped, isEmergencyStopped, robotMode)."""
    (_, _, _, _, emergencia, protegido, ejecutando, _, modo
     ) = struct.unpack(">Q???????B", datos[:16])
    return ejecutando, protegido, emergencia, modo


def leer_estado(mensaje):
    """Mensaje tipo 16 -> dict con 'q' (6 q_actual) y, si vienen, 'ejecutando', 'protegido', 'emergencia', 'modo'."""
    estado = {}
    for tipo, datos in subpaquetes(mensaje):
        if tipo == SUB_JOINTS:
            estado["q"] = leer_q_actual(datos)
        elif tipo == SUB_MODO:
            estado["ejecutando"], estado["protegido"], estado["emergencia"], estado["modo"] = leer_modo(datos)
    return estado


def leer_error(mensaje):
    """Mensaje tipo 20 -> texto si es un error (robotMessageType 6 o 10), o None para cualquier otro."""
    # cabecera 5 + timestamp 8 + source 1 + robotMessageType 1 = 15
    if len(mensaje) < 15:
        return None
    subtipo = mensaje[14]
    if subtipo == 6:       # error code: code, argument, reportLevel, dataType, data (5 x int32) y texto
        return "error del robot (codigo {}): {}".format(
            struct.unpack(">i", mensaje[15:19])[0], mensaje[35:].decode("utf-8", "replace"))
    if subtipo == 10:      # excepcion de programa: linea, columna (2 x int32) y texto
        return "excepcion de programa (linea {}): {}".format(
            struct.unpack(">i", mensaje[15:19])[0], mensaje[23:].decode("utf-8", "replace"))
    return None


def conectar(ip, puerto):
    """Abre la conexion TCP con el robot. recv() espera como maximo 2 s para no bloquear nunca el programa."""
    s = socket.create_connection((ip, puerto), timeout=5)
    s.settimeout(2)
    return s


def mensajes(s):
    """Generador: devuelve (tipo, mensaje) de cada mensaje completo que llega por el socket s.
    Acumula los bytes en un buffer y corta con la longitud de cada mensaje (apartado 8 del enunciado).
    Lanza ConnectionError si el robot cierra, socket.timeout si no llega nada, ValueError si se desalinea."""
    buffer = bytearray()
    while True:
        datos = s.recv(4096)
        if not datos:
            raise ConnectionError("el robot ha cerrado la conexion")
        buffer += datos
        while True:
            m = extraer_mensaje(buffer)
            if m is None:
                break
            yield m


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=30001)
    args = parser.parse_args()

    from UR3e_rg2.dynamic_ur3e import UR3eRG2
    visualizador = UR3eRG2()

    while True:                      # si se cae la conexion se vuelve a intentar
        try:
            with conectar(args.ip, args.puerto) as s:
                print("Conectado a {}:{}".format(args.ip, args.puerto))
                for tipo, mensaje in mensajes(s):
                    if tipo != TIPO_ESTADO:
                        continue         # version (20) y demas: se ignoran
                    q = leer_estado(mensaje).get("q")
                    if q:
                        print("q_actual (grados):", [round(v * 57.29578, 1) for v in q])
                        visualizador.move_robot(0, list(q))
        except (OSError, ValueError, struct.error) as e:    # incluye ConnectionError y socket.timeout
            print("Conexion perdida ({}). Reintentando en 2 s...".format(e))
            time.sleep(2)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
