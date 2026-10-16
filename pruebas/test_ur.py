"""
Pruebas de src/ur.py: decodificacion con bytes, ordenes movej/stopj con una conexion falsa, y ClienteUR (primaria y
tiempo real) y HiloLectorUR contra un servidor local. No necesita robot.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import contextlib
import io
import struct
import time
import unittest

import ayudas
import ur
from red import ErrorRed

Q = [0.0, -1.57, 0.0, -1.57, 0.0, 0.5]


def casi_igual(a, b):
    return len(a) == len(b) and all(abs(x - y) < 1e-9 for x, y in zip(a, b))


def mensaje_con_subpaquete(tipo_sub, datos):
    """Mensaje tipo 16 con un solo subpaquete (para probar tamanos que el robot real no manda)."""
    cuerpo = ayudas.subpaquete(tipo_sub, datos)
    return struct.pack(">iB", len(cuerpo) + 5, 16) + cuerpo


class PruebasDecodificarPrimaria(unittest.TestCase):
    def setUp(self):
        self.cliente = ur.ClienteUR("127.0.0.1")

    def test_estado(self):
        e = self.cliente._decodificar(ayudas.mensaje_estado(Q, ejecutando=True, modo=7))
        self.assertTrue(casi_igual(e["q"], Q))
        self.assertEqual((e["ejecutando"], e["protegido"], e["emergencia"], e["modo"]), (True, False, False, 7))

    def test_estado_distingue_protegido_y_emergencia(self):
        e = self.cliente._decodificar(ayudas.mensaje_estado(Q, protegido=True))
        self.assertEqual((e["protegido"], e["emergencia"], e["ejecutando"]), (True, False, False))
        e = self.cliente._decodificar(ayudas.mensaje_estado(Q, emergencia=True))
        self.assertEqual((e["protegido"], e["emergencia"]), (False, True))

    def test_subpaquete_que_se_sale_del_mensaje(self):
        m = bytearray(ayudas.mensaje_estado(Q))
        struct.pack_into(">i", m, 5, 9999)          # longitud del primer subpaquete: absurda
        with self.assertRaises(ErrorRed):
            self.cliente._decodificar(bytes(m))

    def test_mensajes_de_estado_cortados_dan_errorred(self):
        casos = {
            "cola de 1 byte": struct.pack(">iB", 6, 16) + b"\x00",
            "subpaquete 1 vacio": mensaje_con_subpaquete(1, b""),
            "subpaquete 1 de 100 bytes": mensaje_con_subpaquete(1, bytes(100)),
            "subpaquete 0 de 5 bytes": mensaje_con_subpaquete(0, b"12345"),
        }
        for nombre, mensaje in casos.items():
            with self.subTest(nombre):
                with self.assertRaises(ErrorRed):
                    self.cliente._decodificar(mensaje)

    def test_tamano_distinto_de_251_bytes_dice_cual_llego_y_cual_se_esperaba(self):
        with self.assertRaises(ErrorRed) as e:
            self.cliente._decodificar(mensaje_con_subpaquete(1, bytes(256 - ur.CABECERA)))
        self.assertIn("256", str(e.exception))
        self.assertIn("251", str(e.exception))

    def test_error_codigo(self):
        cuerpo = struct.pack(">5i", 123, 0, 2, 0, 0) + b"Fallo de prueba"
        texto = self.cliente._decodificar(ayudas.mensaje_robot(6, cuerpo))["error"]
        self.assertIn("123", texto)
        self.assertIn("Fallo de prueba", texto)

    def test_error_excepcion_de_programa(self):
        cuerpo = struct.pack(">2i", 7, 3) + b"Excepcion"
        texto = self.cliente._decodificar(ayudas.mensaje_robot(10, cuerpo))["error"]
        self.assertIn("7", texto)
        self.assertIn("Excepcion", texto)

    def test_otros_mensajes_no_interesan(self):
        self.assertEqual(self.cliente._decodificar(ayudas.mensaje_robot(3, b"1.2.3")), {})      # version
        self.assertEqual(self.cliente._decodificar(struct.pack(">iB", 5, 99)), {})               # tipo desconocido

    def test_mensaje_de_error_cortado_da_errorred(self):
        for subtipo in (6, 10):
            for longitud_cuerpo in (0, 1, 3):                   # mensaje de 15, 16 y 18 bytes
                with self.subTest(subtipo=subtipo, cuerpo=longitud_cuerpo):
                    with self.assertRaises(ErrorRed):
                        self.cliente._decodificar(ayudas.mensaje_robot(subtipo, bytes(longitud_cuerpo)))


class PruebasCortarPaquetes(unittest.TestCase):
    def test_primaria_incompleto_devuelve_none_y_no_consume(self):
        cliente = ur.ClienteUR("127.0.0.1")
        cliente._buffer += ayudas.mensaje_estado(Q)[:-1]
        self.assertIsNone(cliente._cortar())
        self.assertEqual(len(cliente._buffer), len(ayudas.mensaje_estado(Q)) - 1)

    def test_primaria_corta_un_mensaje_y_deja_el_resto(self):
        m = ayudas.mensaje_estado(Q)
        cliente = ur.ClienteUR("127.0.0.1")
        cliente._buffer += m + m[:10]
        self.assertEqual(cliente._cortar(), m)
        self.assertEqual(bytes(cliente._buffer), m[:10])

    def test_primaria_byte_a_byte_da_el_mismo_resultado(self):
        m = ayudas.mensaje_estado(Q)
        cliente = ur.ClienteUR("127.0.0.1")
        resultados = []
        for b in m + m:
            cliente._buffer.append(b)
            r = cliente._cortar()
            if r:
                resultados.append(r)
        self.assertEqual(resultados, [m, m])

    def test_primaria_longitud_imposible(self):
        for longitud in (0, 4, ur.MAX_LONGITUD + 1):
            cliente = ur.ClienteUR("127.0.0.1")
            cliente._buffer += struct.pack(">iB", longitud, 16)
            with self.assertRaises(ErrorRed):
                cliente._cortar()

    def test_tiempo_real_corta_y_decodifica_q(self):
        p = ayudas.paquete_tiempo_real(Q)
        cliente = ur.ClienteUR("127.0.0.1", tiempo_real=True)
        cliente._buffer += p + p[:50]
        paquete = cliente._cortar()
        self.assertEqual(paquete, p)
        self.assertEqual(len(cliente._buffer), 50)
        self.assertTrue(casi_igual(cliente._decodificar(paquete)["q"], Q))

    def test_tiempo_real_incompleto_y_longitud_imposible(self):
        cliente = ur.ClienteUR("127.0.0.1", tiempo_real=True)
        cliente._buffer += ayudas.paquete_tiempo_real(Q)[:100]
        self.assertIsNone(cliente._cortar())
        cliente = ur.ClienteUR("127.0.0.1", tiempo_real=True)
        cliente._buffer += struct.pack(">i", 10) + bytes(20)
        with self.assertRaises(ErrorRed):
            cliente._cortar()


class PruebasPuntoValido(unittest.TestCase):
    def test_es_punto_valido(self):
        self.assertTrue(ur.es_punto_valido(Q))
        self.assertFalse(ur.es_punto_valido([0, 0, 0, 0, 0]))               # solo 5
        self.assertFalse(ur.es_punto_valido([0, 0, 0, 0, 0, 90.0]))         # grados en vez de radianes
        self.assertFalse(ur.es_punto_valido([0, 0, 0, 0, 0, 0, 0]))

    def test_tipos_raros_es_false_sin_excepcion(self):
        for q in (None, 5, "abcdef", [None] * 6, [float("nan")] * 6):
            with self.subTest(q=q):
                self.assertFalse(ur.es_punto_valido(q))


class RedGrabadora:
    """Hace de ConexionTCP: guarda lo que se envia."""

    def __init__(self):
        self.enviado = []

    def enviar(self, datos):
        self.enviado.append(datos)


class PruebasOrdenes(unittest.TestCase):
    def setUp(self):
        self.robot = ur.ClienteUR("127.0.0.1")
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
            (Q, 1e-5, 0.2),                                 # se escribiria como '1e-05'
            (Q, 0.1, 0.51),
            (Q, 0.1, -0.2),
            (Q, 0.1, 1e-5),
            (Q, float("nan"), 0.2),
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


class PruebasClienteConRed(unittest.TestCase):
    def conectado(self, srv, **kw):
        cliente = ur.ClienteUR("127.0.0.1", srv.puerto, **kw)
        self.addCleanup(cliente.desconectar)
        cliente.conectar()
        return cliente

    def test_primaria_junta_mensajes_troceados(self):
        m = ayudas.mensaje_estado(Q)
        srv = ayudas.ServidorSecuencial(servir_trozos(m[:3], m[3:100], m[100:] + m))
        self.addCleanup(srv.cerrar)
        mensajes = self.conectado(srv).mensajes()
        self.assertTrue(casi_igual(next(mensajes)["q"], Q))
        self.assertTrue(casi_igual(next(mensajes)["q"], Q))

    def test_primaria_ignora_la_version_y_entrega_estado_y_errores(self):
        q2 = [0.1] * 6
        error = ayudas.mensaje_robot(6, struct.pack(">5i", 5, 0, 2, 0, 0) + b"Colision")
        srv = ayudas.ServidorSecuencial(servir_trozos(
            ayudas.mensaje_robot(3, b"version"), ayudas.mensaje_estado(q2), error))
        self.addCleanup(srv.cerrar)
        mensajes = self.conectado(srv).mensajes()
        self.assertTrue(casi_igual(next(mensajes)["q"], q2))        # la version no se entrega
        self.assertIn("Colision", next(mensajes)["error"])

    def test_primaria_desalineada_lanza_errorred(self):
        srv = ayudas.ServidorSecuencial(servir_trozos(b"\xff" * 20))
        self.addCleanup(srv.cerrar)
        with self.assertRaises(ErrorRed):
            next(self.conectado(srv).mensajes())

    def test_tiempo_real_varios_paquetes(self):
        p1, p2 = ayudas.paquete_tiempo_real(Q), ayudas.paquete_tiempo_real([0.2] * 6)
        srv = ayudas.ServidorSecuencial(servir_trozos(p1[:500], p1[500:] + p2[:10], p2[10:]))
        self.addCleanup(srv.cerrar)
        mensajes = self.conectado(srv, tiempo_real=True).mensajes()
        self.assertTrue(casi_igual(next(mensajes)["q"], Q))
        self.assertTrue(casi_igual(next(mensajes)["q"], [0.2] * 6))

    def test_puertos_por_defecto_y_destino(self):
        self.assertEqual(ur.ClienteUR("127.0.0.1").red.puerto, 30001)
        self.assertEqual(ur.ClienteUR("127.0.0.1", tiempo_real=True).red.puerto, 30003)
        self.assertEqual(ur.ClienteUR("127.0.0.1").destino, "127.0.0.1:30001")

    def test_puerto_cero_no_se_cambia_en_silencio_por_el_de_defecto(self):
        with self.assertRaises(ValueError):
            ur.ClienteUR("127.0.0.1", 0)

    def test_reconectar_vacia_el_buffer(self):
        m = ayudas.mensaje_estado(Q)
        srv = ayudas.ServidorSecuencial(servir_trozos(m[:20]), servir_trozos(m))
        self.addCleanup(srv.cerrar)
        cliente = self.conectado(srv)
        with self.assertRaises(ErrorRed):
            next(cliente.mensajes())        # llega medio mensaje y el servidor cierra
        cliente.conectar()                  # si el buffer no se vaciara, los 20 bytes viejos desalinearian todo
        self.assertTrue(casi_igual(next(cliente.mensajes())["q"], Q))

    def test_puerto_equivocado_primaria_contra_tiempo_real_avisa(self):
        paquetes = b"".join(ayudas.paquete_tiempo_real(Q) for _ in range(ur.MAX_IGNORADOS + 20))
        srv = ayudas.ServidorSecuencial(servir_trozos(paquetes))
        self.addCleanup(srv.cerrar)
        with self.assertRaises(ErrorRed) as e:
            next(self.conectado(srv).mensajes())            # el cliente espera la primaria y llega tiempo real
        self.assertIn("puerto", str(e.exception))

    def test_muchos_mensajes_que_no_son_estado_pero_con_estados_en_medio_no_avisan(self):
        trozo = ayudas.mensaje_robot(3, b"v") * (ur.MAX_IGNORADOS - 1) + ayudas.mensaje_estado(Q)
        srv = ayudas.ServidorSecuencial(servir_trozos(trozo * 3))
        self.addCleanup(srv.cerrar)
        mensajes = self.conectado(srv).mensajes()
        for _ in range(3):
            self.assertTrue(casi_igual(next(mensajes)["q"], Q))


class ClienteQueFalla:
    """Cliente falso para HiloLectorUR: conectar() no falla pero mensajes() falla enseguida con `error`."""

    destino = "falso:0"

    def __init__(self, error):
        self.error = error
        self.conexiones = 0

    def conectar(self):
        self.conexiones += 1

    def desconectar(self):
        pass

    def mensajes(self):
        raise self.error
        yield                                           # (hace de esto un generador)


class PruebasHilo(unittest.TestCase):
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
        hilo = ur.HiloLectorUR("prueba", ur.ClienteUR("127.0.0.1", srv.puerto))
        self.addCleanup(hilo.detener)
        self.assertIsNone(hilo.q)                                           # antes de arrancar
        hilo.start()
        self.assertTrue(self.esperar(lambda: hilo.q is not None and casi_igual(hilo.q, q2)),
                        "no llego a leer q2 tras reconectar; q = {}".format(hilo.q))
        self.assertGreaterEqual(hilo.recibidos, 2)

    def test_sin_servidor_no_se_cuelga_y_no_hay_q(self):
        hilo = ur.HiloLectorUR("prueba", ur.ClienteUR("127.0.0.1", ayudas.puerto_libre()))
        hilo.start()
        self.assertTrue(self.esperar(lambda: hilo.ultimo_error is not None, 6.0))   # Windows tarda 1-2 s en rechazar
        self.assertIsNone(hilo.q)
        self.assertIn("127.0.0.1", hilo.ultimo_error)
        hilo.detener()
        self.assertFalse(hilo.is_alive())

    def test_detener_cierra_el_socket_y_el_hilo_termina_enseguida(self):
        conectado = ayudas.threading.Event()
        mantener = ayudas.threading.Event()
        srv = ayudas.ServidorSecuencial(lambda conn: (conectado.set(), mantener.wait(5)))      # acepta y calla
        self.addCleanup(srv.cerrar)
        self.addCleanup(mantener.set)
        hilo = ur.HiloLectorUR("mudo", ur.ClienteUR("127.0.0.1", srv.puerto))
        hilo.start()
        self.assertTrue(conectado.wait(3))
        t0 = time.time()
        hilo.detener()
        self.assertLess(time.time() - t0, 0.5)          # no espera el timeout de lectura (2 s)
        self.assertFalse(hilo.is_alive())

    def test_el_motivo_de_la_desconexion_se_escribe_una_sola_vez(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            hilo = ur.HiloLectorUR("sin_robot", ClienteQueFalla(ErrorRed("sin robot de prueba")))
            hilo.start()
            time.sleep(0.8)                             # unos 8 reintentos de 0,1 s, todos con el mismo motivo
            hilo.detener()
        self.assertEqual(hilo.ultimo_error, "sin robot de prueba")
        self.assertIsNone(hilo.q)                       # el q de antes del fallo no se sigue dando como actual
        self.assertEqual(salida.getvalue().count("DESCONECTADO"), 1)
        self.assertGreater(hilo.cliente.conexiones, 3)  # reintenta

    def test_ultimo_error_se_borra_cuando_vuelven_los_estados(self):
        mantener = ayudas.threading.Event()
        srv = ayudas.ServidorSecuencial(lambda conn: (conn.sendall(ayudas.mensaje_estado(Q)), mantener.wait(3)))
        self.addCleanup(srv.cerrar)
        self.addCleanup(mantener.set)
        hilo = ur.HiloLectorUR("prueba", ur.ClienteUR("127.0.0.1", srv.puerto))
        self.addCleanup(hilo.detener)
        hilo.start()
        self.assertTrue(self.esperar(lambda: hilo.q is not None))
        self.assertIsNone(hilo.ultimo_error)


if __name__ == "__main__":
    unittest.main()
