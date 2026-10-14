"""
Pruebas de src/red.py contra un servidor local (127.0.0.1, puerto libre). No necesita robot.

    python -B -m unittest discover -s practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from red import ConexionTCP  # noqa: E402


class ServidorLocal:
    """Acepta una conexion y ejecuta `atender(conn)` en un hilo. Puerto elegido por el sistema."""

    def __init__(self, atender):
        self.servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.servidor.bind(("127.0.0.1", 0))
        self.servidor.listen(1)
        self.puerto = self.servidor.getsockname()[1]
        self.atender = atender
        threading.Thread(target=self._servir, daemon=True).start()

    def _servir(self):
        conn, _ = self.servidor.accept()
        with conn:
            self.atender(conn)

    def cerrar(self):
        self.servidor.close()


class PruebasConexionTCP(unittest.TestCase):
    def test_enviar_y_recibir(self):
        def eco(conn):
            conn.sendall(conn.recv(100).upper())
        srv = ServidorLocal(eco)
        self.addCleanup(srv.cerrar)
        with ConexionTCP("127.0.0.1", srv.puerto) as red:
            red.enviar(b"hola")
            self.assertEqual(red.recibir(), b"HOLA")

    def test_cierra_el_otro_lado(self):
        srv = ServidorLocal(lambda conn: None)      # acepta y cierra
        self.addCleanup(srv.cerrar)
        with ConexionTCP("127.0.0.1", srv.puerto) as red:
            with self.assertRaises(ConnectionError):
                red.recibir()

    def test_timeout_si_no_llega_nada(self):
        parar = threading.Event()
        srv = ServidorLocal(lambda conn: parar.wait(2))     # acepta y calla
        self.addCleanup(srv.cerrar)
        self.addCleanup(parar.set)
        with ConexionTCP("127.0.0.1", srv.puerto, timeout_lectura=0.2) as red:
            with self.assertRaises(socket.timeout):
                red.recibir()

    def test_sin_abrir_falla_con_connectionerror(self):
        red = ConexionTCP("127.0.0.1", 1)
        self.assertFalse(red.abierta)
        with self.assertRaises(ConnectionError):
            red.enviar(b"x")
        with self.assertRaises(ConnectionError):
            red.recibir()

    def test_puerto_cerrado_es_oserror(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
        s.close()                                   # nadie escucha en ese puerto
        with self.assertRaises(OSError):
            ConexionTCP("127.0.0.1", puerto, timeout_conexion=1.0).abrir()

    def test_cerrar_deja_la_conexion_cerrada(self):
        srv = ServidorLocal(lambda conn: None)
        self.addCleanup(srv.cerrar)
        red = ConexionTCP("127.0.0.1", srv.puerto)
        red.abrir()
        self.assertTrue(red.abierta)
        red.cerrar()
        self.assertFalse(red.abierta)
        red.cerrar()                                # cerrar dos veces no falla


if __name__ == "__main__":
    unittest.main()
