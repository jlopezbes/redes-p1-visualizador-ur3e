"""
Ayudas comunes de las pruebas: rutas a src/ y src/librerias/, constructores de tramas del UR y un servidor local.
Las tramas se construyen aqui con struct a partir del formato descrito en src/librerias/ur.py y docs/ur-referencia.md:
si el formato fuera otro en un robot real, estas pruebas no lo detectarian (ver docs/pruebas.md).
"""
import os
import socket
import struct
import sys
import threading

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(AQUI, "..", "src"))                 # los scripts: import ensenar, import primaria...
LIBRERIAS = os.path.join(SRC, "librerias")                              # los modulos planos: import ur, import red...
for carpeta in (SRC, LIBRERIAS):
    if carpeta not in sys.path:
        sys.path.insert(0, carpeta)


def subpaquete(tipo, datos):
    return struct.pack(">iB", len(datos) + 5, tipo) + datos


def mensaje_estado(q, ejecutando=False, protegido=False, emergencia=False, modo=7):
    """Mensaje tipo 16 con el subpaquete 0 (modo) y el 1 (6 articulaciones de 41 bytes)."""
    datos_modo = struct.pack(">Q???????BBdddB", 0, True, True, True, emergencia, protegido, ejecutando, False,
                             modo, 0, 1.0, 1.0, 1.0, 0)
    joints = b"".join(struct.pack(">dddffffB", a, a, 0.0, 0.0, 0.0, 0.0, 0.0, 253) for a in q)
    cuerpo = subpaquete(0, datos_modo) + subpaquete(1, joints)
    return struct.pack(">iB", len(cuerpo) + 5, 16) + cuerpo


def mensaje_robot(subtipo, cuerpo):
    """Mensaje tipo 20: timestamp (8) + source (1) + robotMessageType (1) + cuerpo."""
    datos = struct.pack(">QBB", 0, 0, subtipo) + cuerpo
    return struct.pack(">iB", len(datos) + 5, 20) + datos


def mensaje_error(codigo, texto=b"", argumento=0):
    """Mensaje tipo 20, subtipo 6: code, argument, reportLevel (3 x int32), dataType (uint8), data (uint32) y texto."""
    return mensaje_robot(6, struct.pack(">3iBI", codigo, argumento, 2, 0, 0) + texto)


def paquete_tiempo_real(q, longitud=1116):
    """Paquete de la interfaz de tiempo real: longitud en los 4 primeros bytes y q_actual en el byte 252."""
    paquete = bytearray(longitud)
    struct.pack_into(">i", paquete, 0, longitud)
    struct.pack_into(">6d", paquete, 252, *q)
    return bytes(paquete)


def puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    return puerto


class ServidorSecuencial:
    """Atiende una conexion tras otra: la n-esima la atiende atender[n](conn). Cuando se acaba la lista deja de aceptar."""

    def __init__(self, *atender):
        self.servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.servidor.bind(("127.0.0.1", 0))
        self.servidor.listen(5)
        self.puerto = self.servidor.getsockname()[1]
        self._atender = list(atender)
        threading.Thread(target=self._servir, daemon=True).start()

    def _servir(self):
        for atender in self._atender:
            try:
                conn, _ = self.servidor.accept()
            except OSError:
                return
            with conn:
                atender(conn)

    def cerrar(self):
        self.servidor.close()
