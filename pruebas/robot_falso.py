"""
UR falso para probar sin URSim ni robot: emite tramas con el formato real (las de ayudas.py), entiende
movej(...) y stopj(...) y simula el movimiento. Solo escucha en loopback (127.0.0.1 por defecto). Ver el aviso de pruebas.md:
es nuestra interpretacion del protocolo, no un robot.

    python -u 2_practicas\\Practica1_visualizador_UR3e\\pruebas\\robot_falso.py 31001                (primaria)
    python -u 2_practicas\\Practica1_visualizador_UR3e\\pruebas\\robot_falso.py 31003 tiempo_real

NO lanzarlo con URSim abierto si se usan los puertos 30001-30013 (VirtualBox los reenvia). Por defecto, usar 31001 y siguientes.
"""
import re
import socket
import sys
import threading
import time

import ayudas

Q_INICIAL = [0.0, -1.57, 0.0, -1.57, 0.0, 0.0]      # rad
HZ = 10
MOVEJ = re.compile(r"movej\(\[([^\]]+)\],\s*a=([\d.]+),\s*v=([\d.]+)\)")
STOPJ = re.compile(r"stopj\(([\d.]+)\)")


class RobotFalso:
    def __init__(self, puerto, formato="primaria", q=None, ip="127.0.0.1"):
        self.ip = ip                                # siempre de loopback (127.x.x.x): 127.0.0.2 tambien es este PC
        self.puerto = puerto
        self.formato = formato                      # "primaria" o "tiempo_real"
        self.q = list(q or Q_INICIAL)               # rad
        self.objetivo = list(self.q)
        self.velocidad = 0.5                        # rad/s: la del ultimo movej
        self.ejecutando = False                     # isProgramRunning: True mientras se mueve
        self.protegido = False                      # isProtectiveStopped: lo cambian las pruebas
        self.ordenes = []                           # lineas recibidas, en orden
        self._lock = threading.Lock()
        self._clientes = []
        self._servidor = None
        self._activo = False

    def iniciar(self):
        self._servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._servidor.bind((self.ip, self.puerto))
        self._servidor.listen(5)
        self._activo = True
        threading.Thread(target=self._aceptar, daemon=True).start()
        threading.Thread(target=self._emitir, daemon=True).start()
        return self

    def parar(self):
        self._activo = False
        self._servidor.close()
        self.cortar_clientes()

    def cortar_clientes(self):
        """Cierra las conexiones abiertas (simula que el robot se cae)."""
        with self._lock:
            clientes, self._clientes = self._clientes, []
        for c in clientes:
            try:
                c.close()
            except OSError:
                pass

    def enviar_error(self, texto):
        """Manda un mensaje de error (tipo 20, subtipo 6) a los clientes."""
        import struct
        self._difundir(ayudas.mensaje_robot(6, struct.pack(">5i", 99, 0, 2, 0, 0) + texto.encode("utf-8")))

    # ---------- hilos ----------
    def _aceptar(self):
        while self._activo:
            try:
                conn, _ = self._servidor.accept()
            except OSError:
                return
            with self._lock:
                self._clientes.append(conn)
            if self.formato == "primaria":
                try:
                    conn.sendall(ayudas.mensaje_robot(3, b"falso"))       # "mensaje de version"
                except OSError:
                    pass
                threading.Thread(target=self._escuchar, args=(conn,), daemon=True).start()

    def _escuchar(self, conn):
        buffer = ""
        try:
            while True:
                datos = conn.recv(1024)
                if not datos:
                    return
                buffer += datos.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    self._ejecutar_linea(linea.strip())
        except OSError:
            pass

    def _ejecutar_linea(self, linea):
        with self._lock:
            self.ordenes.append(linea)
            m = MOVEJ.fullmatch(linea)
            if m and not self.protegido:            # en parada de proteccion un UR rechaza el movimiento
                self.objetivo = [float(x) for x in m.group(1).split(",")]
                self.velocidad = float(m.group(3))
                self.ejecutando = True
            elif STOPJ.fullmatch(linea):
                self.objetivo = list(self.q)
                self.ejecutando = False

    def _emitir(self):
        dt = 1.0 / HZ
        while self._activo:
            with self._lock:
                self._avanzar(dt)
                if self.formato == "primaria":
                    trama = ayudas.mensaje_estado(self.q, ejecutando=self.ejecutando, protegido=self.protegido)
                else:
                    trama = ayudas.paquete_tiempo_real(self.q)
            self._difundir(trama)
            time.sleep(dt)

    def _avanzar(self, dt):
        paso = self.velocidad * dt
        for i, (q, o) in enumerate(zip(self.q, self.objetivo)):
            self.q[i] = o if abs(o - q) <= paso else q + paso * (1 if o > q else -1)
        if self.ejecutando and self.q == self.objetivo:
            self.ejecutando = False

    def _difundir(self, datos):
        with self._lock:
            clientes = list(self._clientes)
        for c in clientes:
            try:
                c.sendall(datos)
            except OSError:
                with self._lock:
                    if c in self._clientes:
                        self._clientes.remove(c)


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 31001
    formato = sys.argv[2] if len(sys.argv) > 2 else "primaria"
    robot = RobotFalso(puerto, formato).iniciar()
    print("Robot falso ({}) escuchando en 127.0.0.1:{}. Ctrl+C para parar.".format(formato, puerto))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        robot.parar()
