"""
Pruebas de src/red.py contra un servidor local (127.0.0.1, puerto libre). No necesita robot.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import os
import socket
import struct
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from red import ConexionTCP, ErrorRed, ErrorRedTimeout  # noqa: E402


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


def cortar_con_rst(conn):
    """Cierra de golpe (SO_LINGER 0): el cliente recibe un RST, no un cierre limpio."""
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))


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
            with self.assertRaises(ErrorRed) as e:
                red.recibir()
            self.assertIn("127.0.0.1:{}".format(srv.puerto), str(e.exception))     # dice con quien
            self.assertFalse(red.abierta)                                          # y ya no se da por abierta

    def test_timeout_si_no_llega_nada(self):
        parar = threading.Event()
        srv = ServidorLocal(lambda conn: parar.wait(2))     # acepta y calla
        self.addCleanup(srv.cerrar)
        self.addCleanup(parar.set)
        with ConexionTCP("127.0.0.1", srv.puerto, timeout_lectura=0.2) as red:
            with self.assertRaises(ErrorRedTimeout):
                red.recibir()
            self.assertTrue(red.abierta)                    # un timeout de lectura NO cierra la conexion

    def test_sin_abrir_falla_con_errorred(self):
        red = ConexionTCP("127.0.0.1", 1)
        self.assertFalse(red.abierta)
        with self.assertRaises(ErrorRed):
            red.enviar(b"x")
        with self.assertRaises(ErrorRed):
            red.recibir()

    def test_puerto_cerrado_es_errorred(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
        s.close()                                   # nadie escucha en ese puerto
        red = ConexionTCP("127.0.0.1", puerto, timeout_conexion=1.0)
        with self.assertRaises(ErrorRed) as e:
            red.abrir()
        self.assertIn("127.0.0.1:{}".format(puerto), str(e.exception))
        self.assertFalse(red.abierta)

    def test_cerrar_deja_la_conexion_cerrada(self):
        srv = ServidorLocal(lambda conn: None)
        self.addCleanup(srv.cerrar)
        red = ConexionTCP("127.0.0.1", srv.puerto)
        red.abrir()
        self.assertTrue(red.abierta)
        red.cerrar()
        self.assertFalse(red.abierta)
        red.cerrar()                                # cerrar dos veces no falla

    # ---- errores de socket que salen como ErrorRed ----

    def test_reset_del_otro_lado_es_errorred_y_cierra(self):
        srv = ServidorLocal(cortar_con_rst)
        self.addCleanup(srv.cerrar)
        red = ConexionTCP("127.0.0.1", srv.puerto)
        self.addCleanup(red.cerrar)
        red.abrir()
        with self.assertRaises(ErrorRed):           # antes: ConnectionResetError (WinError 10054)
            red.recibir()
        self.assertFalse(red.abierta)
        red.cerrar()                                # sigue siendo idempotente tras el error

    def test_enviar_tras_cierre_remoto_acaba_en_errorred(self):
        srv = ServidorLocal(lambda conn: None)
        self.addCleanup(srv.cerrar)
        red = ConexionTCP("127.0.0.1", srv.puerto)
        self.addCleanup(red.cerrar)
        red.abrir()
        time.sleep(0.2)                             # da tiempo a que llegue el cierre del servidor
        with self.assertRaises(ErrorRed):
            for _ in range(20):                     # el primer envio puede pasar: TCP todavia no sabe nada
                red.enviar(b"x" * 1000)
                time.sleep(0.05)
        self.assertFalse(red.abierta)

    def test_cerrar_desde_otro_hilo_despierta_a_recibir_con_errorred(self):
        parar = threading.Event()
        srv = ServidorLocal(lambda conn: parar.wait(5))     # acepta y calla
        self.addCleanup(srv.cerrar)
        self.addCleanup(parar.set)
        red = ConexionTCP("127.0.0.1", srv.puerto, timeout_lectura=5.0)
        red.abrir()
        threading.Timer(0.2, red.cerrar).start()
        t0 = time.time()
        with self.assertRaises(ErrorRed):           # antes: OSError WinError 10038 (o AttributeError)
            red.recibir()
        self.assertLess(time.time() - t0, 2.0)      # no espera los 5 s del timeout

    def test_abrir_dos_veces_no_deja_un_socket_suelto(self):
        servidor = socket.socket()
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(2)
        self.addCleanup(servidor.close)
        red = ConexionTCP("127.0.0.1", servidor.getsockname()[1])
        self.addCleanup(red.cerrar)
        red.abrir()
        primera, _ = servidor.accept()
        self.addCleanup(primera.close)
        red.abrir()
        segunda, _ = servidor.accept()
        self.addCleanup(segunda.close)
        primera.settimeout(2.0)
        self.assertEqual(primera.recv(10), b"")     # la primera conexion se cerro al abrir la segunda

    # ---- argumentos que vienen de fuera ----

    def test_ip_no_valida(self):
        for ip in (None, "", "   ", 127, "no es una ip", "localhost", "999.1.1.1"):
            with self.subTest(ip=ip):
                with self.assertRaises(ValueError):
                    ConexionTCP(ip, 30001)

    def test_puerto_no_valido(self):
        # 70000 y -1 no dan error en el sistema: Windows los recorta a 16 bits y conectaria a otro puerto
        for puerto in (0, -1, 65536, 70000, 98002, 3.5, "30001", None, True):
            with self.subTest(puerto=puerto):
                with self.assertRaises(ValueError):
                    ConexionTCP("127.0.0.1", puerto)

    def test_timeout_no_valido(self):
        for valor in (None, 0, -1, float("nan"), float("inf"), 1e10, "2", True):
            with self.subTest(timeout=valor):
                with self.assertRaises(ValueError):
                    ConexionTCP("127.0.0.1", 30001, timeout_lectura=valor)
                with self.assertRaises(ValueError):
                    ConexionTCP("127.0.0.1", 30001, timeout_conexion=valor)

    def test_argumentos_raros_de_enviar_y_recibir_no_cierran_la_conexion(self):
        srv = ServidorLocal(lambda conn: time.sleep(1))
        self.addCleanup(srv.cerrar)
        with ConexionTCP("127.0.0.1", srv.puerto) as red:
            for maximo in (0, -1, 10 ** 10):
                with self.subTest(maximo=maximo):
                    with self.assertRaises(ValueError):
                        red.recibir(maximo)
            with self.assertRaises(TypeError):
                red.enviar("hola")                  # str, no bytes
            self.assertTrue(red.abierta)


if __name__ == "__main__":
    unittest.main()
