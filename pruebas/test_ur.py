"""
Pruebas de src/ur.py: decodificacion con bytes, orden movej con una conexion falsa, y UrPrimaria,
UrTiempoReal y LectorUR contra un servidor local. No necesita robot.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import struct
import time
import unittest

import ayudas
import ur

Q = [0.0, -1.57, 0.0, -1.57, 0.0, 0.5]


def casi_igual(a, b):
    return all(abs(x - y) < 1e-9 for x, y in zip(a, b)) and len(a) == len(b)


class PruebasExtraerMensaje(unittest.TestCase):
    def test_mensaje_incompleto_devuelve_none(self):
        buffer = bytearray(ayudas.mensaje_estado(Q)[:-1])
        self.assertIsNone(ur.extraer_mensaje(buffer))
        self.assertEqual(len(buffer), len(ayudas.mensaje_estado(Q)) - 1)    # no se ha consumido nada

    def test_corta_un_mensaje_y_deja_el_resto(self):
        m = ayudas.mensaje_estado(Q)
        buffer = bytearray(m + m[:10])
        tipo, mensaje = ur.extraer_mensaje(buffer)
        self.assertEqual((tipo, mensaje), (16, m))
        self.assertEqual(bytes(buffer), m[:10])

    def test_byte_a_byte_da_el_mismo_resultado(self):
        m = ayudas.mensaje_estado(Q)
        buffer = bytearray()
        resultados = []
        for b in m + m:
            buffer.append(b)
            r = ur.extraer_mensaje(buffer)
            if r:
                resultados.append(r)
        self.assertEqual(resultados, [(16, m), (16, m)])

    def test_longitud_imposible_lanza_valueerror(self):
        for longitud in (0, 4, ur.MAX_LONGITUD + 1):
            with self.assertRaises(ValueError):
                ur.extraer_mensaje(bytearray(struct.pack(">iB", longitud, 16)))


class PruebasDecodificar(unittest.TestCase):
    def test_leer_estado(self):
        e = ur.leer_estado(ayudas.mensaje_estado(Q, ejecutando=True, protegido=False, emergencia=False, modo=7))
        self.assertTrue(casi_igual(e["q"], Q))
        self.assertEqual((e["ejecutando"], e["protegido"], e["emergencia"], e["modo"]), (True, False, False, 7))

    def test_leer_estado_distingue_protegido_y_emergencia(self):
        e = ur.leer_estado(ayudas.mensaje_estado(Q, protegido=True))
        self.assertEqual((e["protegido"], e["emergencia"], e["ejecutando"]), (True, False, False))
        e = ur.leer_estado(ayudas.mensaje_estado(Q, emergencia=True))
        self.assertEqual((e["protegido"], e["emergencia"]), (False, True))

    def test_subpaquete_que_se_sale_del_mensaje(self):
        m = bytearray(ayudas.mensaje_estado(Q))
        struct.pack_into(">i", m, 5, 9999)          # longitud del primer subpaquete: absurda
        with self.assertRaises(ValueError):
            ur.leer_estado(bytes(m))

    def test_leer_error_codigo(self):
        cuerpo = struct.pack(">5i", 123, 0, 2, 0, 0) + b"Fallo de prueba"
        texto = ur.leer_error(ayudas.mensaje_robot(6, cuerpo))
        self.assertIn("123", texto)
        self.assertIn("Fallo de prueba", texto)

    def test_leer_error_excepcion_de_programa(self):
        cuerpo = struct.pack(">2i", 7, 3) + b"Excepcion"
        texto = ur.leer_error(ayudas.mensaje_robot(10, cuerpo))
        self.assertIn("7", texto)
        self.assertIn("Excepcion", texto)

    def test_leer_error_ignora_otros_mensajes(self):
        self.assertIsNone(ur.leer_error(ayudas.mensaje_robot(3, b"1.2.3")))     # version
        self.assertIsNone(ur.leer_error(b"corto"))

    def test_es_punto_valido(self):
        self.assertTrue(ur.es_punto_valido(Q))
        self.assertFalse(ur.es_punto_valido([0, 0, 0, 0, 0]))               # solo 5
        self.assertFalse(ur.es_punto_valido([0, 0, 0, 0, 0, 90.0]))         # grados en vez de radianes
        self.assertFalse(ur.es_punto_valido([0, 0, 0, 0, 0, 0, 0]))


class PruebasTiempoReal(unittest.TestCase):
    def test_extraer_y_leer_q(self):
        p = ayudas.paquete_tiempo_real(Q)
        buffer = bytearray(p + p[:50])
        paquete = ur.extraer_paquete(buffer)
        self.assertEqual(paquete, p)
        self.assertEqual(len(buffer), 50)
        self.assertTrue(casi_igual(ur.leer_q_tiempo_real(paquete), Q))

    def test_incompleto_y_longitud_imposible(self):
        self.assertIsNone(ur.extraer_paquete(bytearray(ayudas.paquete_tiempo_real(Q)[:100])))
        with self.assertRaises(ValueError):
            ur.extraer_paquete(bytearray(struct.pack(">i", 10) + bytes(20)))


class RedGrabadora:
    """Hace de ConexionTCP: guarda lo que se envia."""

    def __init__(self):
        self.enviado = []

    def enviar(self, datos):
        self.enviado.append(datos)


class PruebasOrdenes(unittest.TestCase):
    def setUp(self):
        self.robot = ur.UrPrimaria("127.0.0.1")
        self.robot.red = RedGrabadora()

    def test_movej_formato(self):
        self.robot.movej([0, -1.5, 0, -1.5, 0, 0.123456789], velocidad=0.1, aceleracion=0.2)
        self.assertEqual(self.robot.red.enviado,
                         [b"movej([0.00000, -1.50000, 0.00000, -1.50000, 0.00000, 0.12346], a=0.2, v=0.1)\n"])

    def test_movej_se_niega_con_datos_peligrosos(self):
        casos = [
            ([0, 0, 0, 0, 0], 0.1, 0.2),                    # faltan angulos
            ([0, 0, 0, 0, 0, 90.0], 0.1, 0.2),              # grados
            (Q, 0.31, 0.2),                                 # mas rapido que el limite del robot real
            (Q, 0.0, 0.2),
            (Q, 0.1, 0.51),
            (Q, 0.1, -0.2),
        ]
        for q, v, a in casos:
            with self.assertRaises(ValueError, msg=str((q, v, a))):
                self.robot.movej(q, velocidad=v, aceleracion=a)
        self.assertEqual(self.robot.red.enviado, [])        # no se envio nada

    def test_movej_solo_acepta_velocidad_y_aceleracion_por_nombre(self):
        with self.assertRaises(TypeError):
            self.robot.movej(Q, 0.1, 0.2)

    def test_stopj(self):
        self.robot.stopj(0.5)
        self.assertEqual(self.robot.red.enviado, [b"stopj(0.5)\n"])


def servir_trozos(*trozos, pausa=0.02):
    """Atiende una conexion enviando cada trozo con una pausa (TCP puede partir los mensajes como quiera)."""
    def atender(conn):
        for t in trozos:
            conn.sendall(t)
            time.sleep(pausa)
        time.sleep(0.3)
    return atender


class PruebasClientes(unittest.TestCase):
    def test_primaria_junta_mensajes_troceados(self):
        m = ayudas.mensaje_estado(Q)
        srv = ayudas.ServidorSecuencial(servir_trozos(m[:3], m[3:100], m[100:] + m))
        self.addCleanup(srv.cerrar)
        with ur.UrPrimaria("127.0.0.1", srv.puerto) as robot:
            estados = robot.estados()
            self.assertTrue(casi_igual(next(estados), Q))
            self.assertTrue(casi_igual(next(estados), Q))

    def test_primaria_estados_ignora_mensajes_que_no_son_de_estado(self):
        q2 = [0.1] * 6
        srv = ayudas.ServidorSecuencial(servir_trozos(
            ayudas.mensaje_robot(3, b"version"), ayudas.mensaje_estado(q2)))
        self.addCleanup(srv.cerrar)
        with ur.UrPrimaria("127.0.0.1", srv.puerto) as robot:
            self.assertTrue(casi_igual(next(robot.estados()), q2))

    def test_primaria_mensajes_devuelve_tipo_y_mensaje(self):
        e = ayudas.mensaje_estado(Q)
        srv = ayudas.ServidorSecuencial(servir_trozos(ayudas.mensaje_robot(3, b"v"), e))
        self.addCleanup(srv.cerrar)
        with ur.UrPrimaria("127.0.0.1", srv.puerto) as robot:
            tipos = []
            for tipo, mensaje in robot.mensajes():
                tipos.append(tipo)
                if tipo == 16:
                    break
            self.assertEqual(tipos, [20, 16])

    def test_primaria_desalineada_lanza_valueerror(self):
        srv = ayudas.ServidorSecuencial(servir_trozos(b"\xff" * 20))
        self.addCleanup(srv.cerrar)
        with ur.UrPrimaria("127.0.0.1", srv.puerto) as robot:
            with self.assertRaises(ValueError):
                next(robot.estados())

    def test_tiempo_real_varios_paquetes(self):
        p1, p2 = ayudas.paquete_tiempo_real(Q), ayudas.paquete_tiempo_real([0.2] * 6)
        srv = ayudas.ServidorSecuencial(servir_trozos(p1[:500], p1[500:] + p2[:10], p2[10:]))
        self.addCleanup(srv.cerrar)
        with ur.UrTiempoReal("127.0.0.1", srv.puerto) as robot:
            estados = robot.estados()
            self.assertTrue(casi_igual(next(estados), Q))
            self.assertTrue(casi_igual(next(estados), [0.2] * 6))

    def test_puertos_por_defecto(self):
        self.assertEqual(ur.UrPrimaria("127.0.0.1").red.puerto, 30001)
        self.assertEqual(ur.UrTiempoReal("127.0.0.1").red.puerto, 30003)

    def test_reconectar_vacia_el_buffer(self):
        m = ayudas.mensaje_estado(Q)
        srv = ayudas.ServidorSecuencial(servir_trozos(m[:20]), servir_trozos(m))
        self.addCleanup(srv.cerrar)
        robot = ur.UrPrimaria("127.0.0.1", srv.puerto)
        with robot:
            with self.assertRaises(ur.ErrorRed):
                next(robot.estados())       # llega medio mensaje y el servidor cierra
        with robot:                         # si el buffer no se vaciara, los 20 bytes viejos desalinearian todo
            self.assertTrue(casi_igual(next(robot.estados()), Q))


class PruebasLector(unittest.TestCase):
    def setUp(self):
        self.reintento = ur.REINTENTO
        ur.REINTENTO = 0.1
        self.addCleanup(setattr, ur, "REINTENTO", self.reintento)

    def esperar(self, condicion, segundos=3.0):
        fin = time.time() + segundos
        while time.time() < fin:
            if condicion():
                return True
            time.sleep(0.02)
        return False

    def test_guarda_el_ultimo_q_y_reconecta(self):
        q1, q2 = [0.1] * 6, [0.2] * 6
        mantener = ayudas.threading.Event()
        srv = ayudas.ServidorSecuencial(
            lambda conn: conn.sendall(ayudas.mensaje_estado(q1)),           # envia un estado y cierra
            lambda conn: (conn.sendall(ayudas.mensaje_estado(q2)), mantener.wait(3)))
        self.addCleanup(srv.cerrar)
        self.addCleanup(mantener.set)
        lector = ur.LectorUR("prueba", ur.UrPrimaria("127.0.0.1", srv.puerto))
        self.addCleanup(lector.parar)
        self.assertIsNone(lector.ultimo_q())                               # antes de arrancar
        lector.start()
        self.assertTrue(self.esperar(lambda: lector.ultimo_q() is not None and casi_igual(lector.ultimo_q(), q2)),
                        "no llego a leer q2 tras reconectar; ultimo_q = {}".format(lector.ultimo_q()))
        self.assertGreaterEqual(lector.recibidos, 2)

    def test_ultimo_q_devuelve_una_copia(self):
        mantener = ayudas.threading.Event()
        srv = ayudas.ServidorSecuencial(lambda conn: (conn.sendall(ayudas.mensaje_estado(Q)), mantener.wait(3)))
        self.addCleanup(srv.cerrar)
        self.addCleanup(mantener.set)
        lector = ur.LectorUR("prueba", ur.UrPrimaria("127.0.0.1", srv.puerto))
        self.addCleanup(lector.parar)
        lector.start()
        self.assertTrue(self.esperar(lambda: lector.ultimo_q() is not None))
        q = lector.ultimo_q()
        q[0] = 99.0                                                         # modificar la copia...
        self.assertTrue(casi_igual(lector.ultimo_q(), Q))                   # ...no cambia el estado guardado

    def test_sin_servidor_no_se_cuelga_y_no_hay_q(self):
        lector = ur.LectorUR("prueba", ur.UrPrimaria("127.0.0.1", ayudas.puerto_libre()))
        lector.start()
        time.sleep(0.4)
        self.assertIsNone(lector.ultimo_q())
        lector.parar()
        lector.join(3)
        self.assertFalse(lector.is_alive())


if __name__ == "__main__":
    unittest.main()
