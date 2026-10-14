"""
Pruebas de src/ur.py: decodificacion con bytes, orden movej con una conexion falsa, y UrPrimaria,
UrTiempoReal y LectorUR contra un servidor local. No necesita robot.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import contextlib
import io
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
        with self.assertRaises(ur.ErrorUR):
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
        self.robot.marcar_estado()          # movej exige un estado fresco

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

    def test_primaria_desalineada_lanza_errorur(self):
        srv = ayudas.ServidorSecuencial(servir_trozos(b"\xff" * 20))
        self.addCleanup(srv.cerrar)
        with ur.UrPrimaria("127.0.0.1", srv.puerto) as robot:
            with self.assertRaises(ur.ErrorUR):
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
            with self.assertRaises(ur.ErrorUR):
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


def mensaje_con_subpaquete(tipo_sub, datos):
    """Mensaje tipo 16 con un solo subpaquete (para probar tamanos que el robot real no manda)."""
    cuerpo = ayudas.subpaquete(tipo_sub, datos)
    return struct.pack(">iB", len(cuerpo) + 5, 16) + cuerpo


class PruebasDecodificarRobusto(unittest.TestCase):
    """Bytes cortados, absurdos o hostiles: siempre ErrorUR, nunca struct.error ni un q no finito."""

    def test_mensajes_de_estado_cortados_dan_errorur(self):
        casos = {
            "cola de 1 byte": struct.pack(">iB", 6, 16) + b"\x00",
            "subpaquete 1 vacio": mensaje_con_subpaquete(1, b""),
            "subpaquete 1 de 100 bytes": mensaje_con_subpaquete(1, bytes(100)),
            "subpaquete 0 de 5 bytes": mensaje_con_subpaquete(0, b"12345"),
        }
        for nombre, mensaje in casos.items():
            with self.subTest(nombre):
                with self.assertRaises(ur.ErrorUR):
                    ur.leer_estado(mensaje)

    def test_tamano_distinto_de_251_bytes_dice_cual_llego_y_cual_se_esperaba(self):
        with self.assertRaises(ur.ErrorUR) as e:
            ur.leer_estado(mensaje_con_subpaquete(1, bytes(256 - ur.CABECERA)))
        self.assertIn("256", str(e.exception))
        self.assertIn("251", str(e.exception))

    def test_q_no_finito_o_absurdo_se_rechaza(self):
        for q in ([float("nan")] * 6, [float("inf")] * 6, [1e300] * 6, [-90.0] * 6):     # -90.0: grados como rad
            with self.subTest(q=q[0]):
                with self.assertRaises(ur.ErrorUR):
                    ur.leer_estado(ayudas.mensaje_estado(q))
                with self.assertRaises(ur.ErrorUR):
                    ur.leer_q_tiempo_real(ayudas.paquete_tiempo_real(q))

    def test_q_en_el_tope_de_la_articulacion_se_acepta(self):
        q = [2 * 3.14159265358979 + 0.1] + [0.0] * 5            # algo por encima de 2*pi: margen de lectura
        self.assertTrue(casi_igual(ur.leer_estado(ayudas.mensaje_estado(q))["q"], q))

    def test_mensaje_de_error_cortado_da_errorur(self):
        for subtipo in (6, 10):
            for longitud_cuerpo in (0, 1, 3):                   # mensaje de 15, 16 y 18 bytes
                with self.subTest(subtipo=subtipo, cuerpo=longitud_cuerpo):
                    with self.assertRaises(ur.ErrorUR):
                        ur.leer_error(ayudas.mensaje_robot(subtipo, bytes(longitud_cuerpo)))

    def test_texto_del_robot_se_sanea_y_se_acota(self):
        cuerpo = struct.pack(">5i", 99, 0, 2, 0, 0) + b"Fallo \xff\xfe \x1b[31mROJO\x1b[0m\nlinea2"
        texto = ur.leer_error(ayudas.mensaje_robot(6, cuerpo))
        self.assertTrue(all(" " <= c <= "~" for c in texto), repr(texto))     # solo ASCII imprimible
        enorme = ur.leer_error(ayudas.mensaje_robot(6, struct.pack(">5i", 1, 0, 2, 0, 0) + b"x" * 60000))
        self.assertLess(len(enorme), 400)

    def test_es_punto_valido_con_tipos_raros_es_false_sin_excepcion(self):
        for q in (None, 5, "abcdef", [None] * 6, [float("nan")] * 6):
            with self.subTest(q=q):
                self.assertFalse(ur.es_punto_valido(q))


class PruebasOrdenesSeguras(unittest.TestCase):
    def setUp(self):
        self.robot = ur.UrPrimaria("127.0.0.1")
        self.robot.red = RedGrabadora()                 # sin estado recibido todavia

    def test_movej_se_niega_sin_estado_reciente_y_no_envia_nada(self):
        self.robot.red.destino = "127.0.0.1:30001"
        with self.assertRaises(ur.ErrorUR):
            self.robot.movej(Q, velocidad=0.1, aceleracion=0.2)
        self.assertEqual(self.robot.red.enviado, [])

    def test_movej_se_niega_cuando_el_estado_caduca(self):
        self.robot.red.destino = "127.0.0.1:30001"
        self.addCleanup(setattr, ur, "PLAZO_ESTADO", ur.PLAZO_ESTADO)
        ur.PLAZO_ESTADO = 0.05                          # s: se reduce el plazo en vez de esperar 2 s
        self.robot.marcar_estado()
        self.robot.movej(Q, velocidad=0.1, aceleracion=0.2)         # fresco: se envia
        time.sleep(0.1)
        with self.assertRaises(ur.ErrorUR):
            self.robot.movej(Q, velocidad=0.1, aceleracion=0.2)     # caducado: no
        self.assertEqual(len(self.robot.red.enviado), 1)

    def test_movej_con_tipos_raros_es_valueerror(self):
        self.robot.marcar_estado()
        for velocidad, aceleracion in (("0.1", 0.2), (0.1, "0.2"), (None, 0.2), (float("nan"), 0.2),
                                       (1e-5, 0.2), (0.1, 1e-5)):        # 1e-5 se escribiria como '1e-05'
            with self.subTest(v=velocidad, a=aceleracion):
                with self.assertRaises(ValueError):
                    self.robot.movej(Q, velocidad=velocidad, aceleracion=aceleracion)
        self.assertEqual(self.robot.red.enviado, [])

    def test_stopj_sin_estado_frena_y_un_valor_malo_usa_el_maximo(self):
        for malo in (float("nan"), float("inf"), -5, 0, 1000, None, "1)\npowerdown("):
            self.robot.red.enviado.clear()
            self.robot.stopj(malo)                      # sin estado fresco y aun asi se envia
            self.assertEqual(self.robot.red.enviado, [b"stopj(0.5)\n"], repr(malo))

    def test_enviar_script_rechaza_saltos_de_linea(self):
        for texto in ("stopj(1)\npowerdown()", "a\rb"):
            with self.assertRaises(ValueError):
                self.robot.enviar_script(texto)
        self.assertEqual(self.robot.red.enviado, [])

    def test_puerto_cero_no_se_cambia_en_silencio_por_el_de_defecto(self):
        for puerto in (0, ""):
            with self.assertRaises(ValueError):
                ur.UrPrimaria("127.0.0.1", puerto)
        self.assertEqual(ur.UrPrimaria("127.0.0.1", None).red.puerto, 30001)


def estado_y_versiones(cuantas):
    """Atiende enviando un estado y despues `cuantas` mensajes de version (tipo 20), uno cada 0,05 s."""
    def atender(conn):
        try:
            conn.sendall(ayudas.mensaje_estado(Q))
            for _ in range(cuantas):
                conn.sendall(ayudas.mensaje_robot(3, b"version"))
                time.sleep(0.05)
        except OSError:
            pass                                        # el cliente se fue
    return atender


class PruebasEstadoFresco(unittest.TestCase):
    """Un robot que deja de mandar estados (o los gotea) no mantiene la conexion 'viva'. Plazo reducido, sin esperas largas."""

    def setUp(self):
        self.addCleanup(setattr, ur, "PLAZO_ESTADO", ur.PLAZO_ESTADO)
        ur.PLAZO_ESTADO = 0.3                           # s

    def test_solo_mensajes_que_no_son_estado_caducan_con_errorur(self):
        srv = ayudas.ServidorSecuencial(estado_y_versiones(40))
        self.addCleanup(srv.cerrar)
        with ur.UrPrimaria("127.0.0.1", srv.puerto) as robot:
            estados = robot.estados()
            self.assertTrue(casi_igual(next(estados), Q))
            t0 = time.time()
            with self.assertRaises(ur.ErrorUR):
                next(estados)
            self.assertLess(time.time() - t0, 1.5)

    def test_un_servidor_que_gotea_bytes_caduca_con_errorur(self):
        m = ayudas.mensaje_estado(Q)

        def atender(conn):
            try:
                for i in range(len(m) - 1):             # un byte cada 0,1 s: el mensaje nunca se completa en 0,3 s
                    conn.sendall(m[i:i + 1])
                    time.sleep(0.1)
            except OSError:
                pass                                    # el cliente se fue
        srv = ayudas.ServidorSecuencial(atender)
        self.addCleanup(srv.cerrar)
        with ur.UrPrimaria("127.0.0.1", srv.puerto) as robot:
            with self.assertRaises(ur.ErrorUR):
                next(robot.estados())

    def test_el_lector_deja_de_dar_un_q_viejo(self):
        srv = ayudas.ServidorSecuencial(estado_y_versiones(60))
        self.addCleanup(srv.cerrar)
        lector = ur.LectorUR("prueba", ur.UrPrimaria("127.0.0.1", srv.puerto))
        self.addCleanup(lector.detener)
        lector.start()
        fin = time.time() + 3
        while lector.ultimo_q() is None and time.time() < fin:
            time.sleep(0.01)
        self.assertTrue(casi_igual(lector.ultimo_q(), Q))               # primero, el q es actual
        fin = time.time() + 3
        while lector.ultimo_q() is not None and time.time() < fin:
            time.sleep(0.01)
        self.assertIsNone(lector.ultimo_q())                            # pasado el plazo, ya no
        self.assertTrue(lector.vivo)

    def test_estado_fresco_es_la_unica_definicion(self):
        robot = ur.UrPrimaria("127.0.0.1")
        self.assertFalse(robot.estado_fresco())
        robot.marcar_estado()
        self.assertTrue(robot.estado_fresco())
        time.sleep(0.4)
        self.assertFalse(robot.estado_fresco())


class ClienteRoto:
    """Cliente falso cuyo estados() falla con un bug (no con un ErrorUR): para probar la ultima defensa del hilo."""

    def __init__(self, error=None):
        self.error = error
        self.red = type("Red", (), {"destino": "falso:0"})()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def cerrar(self):
        pass

    def estado_fresco(self):
        return True

    def estados(self):
        if self.error:
            raise self.error                            # fallo esperado: lo trata el hilo sin traceback
        yield [0.3] * 6
        raise IndexError("fallo inyectado")


class PruebasLectorRobusto(unittest.TestCase):
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

    def test_un_bug_en_el_hilo_se_registra_y_el_hilo_sigue_vivo(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            lector = ur.LectorUR("roto", ClienteRoto())
            lector.start()
            self.assertTrue(self.esperar(lambda: lector.ultimo_error is not None))
            lector.detener()
        self.assertIn("error inesperado", lector.ultimo_error)
        self.assertIn("IndexError", lector.ultimo_error)
        self.assertIn("Traceback", salida.getvalue())
        self.assertIsNone(lector.ultimo_q())            # el q de antes del fallo no se sigue dando como actual
        self.assertFalse(lector.vivo)

    def test_parar_cierra_el_socket_y_el_hilo_termina_enseguida(self):
        conectado = ayudas.threading.Event()
        mantener = ayudas.threading.Event()
        srv = ayudas.ServidorSecuencial(lambda conn: (conectado.set(), mantener.wait(5)))      # acepta y calla
        self.addCleanup(srv.cerrar)
        self.addCleanup(mantener.set)
        lector = ur.LectorUR("mudo", ur.UrPrimaria("127.0.0.1", srv.puerto))
        lector.start()
        self.assertTrue(conectado.wait(3))
        t0 = time.time()
        lector.detener(3.0)
        self.assertLess(time.time() - t0, 0.5)          # antes tardaba hasta timeout_lectura (2 s)
        self.assertFalse(lector.vivo)

    def test_el_motivo_de_la_desconexion_se_escribe_una_sola_vez(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            lector = ur.LectorUR("sin_robot", ClienteRoto(ur.ErrorUR("sin robot de prueba")))
            lector.start()
            time.sleep(0.8)                             # unos 8 reintentos de 0,1 s, todos con el mismo motivo
            lector.detener()
        self.assertEqual(lector.ultimo_error, "sin robot de prueba")
        self.assertEqual(salida.getvalue().count("DESCONECTADO"), 1)

    def test_ultimo_error_se_borra_cuando_vuelven_los_estados(self):
        mantener = ayudas.threading.Event()
        srv = ayudas.ServidorSecuencial(lambda conn: (conn.sendall(ayudas.mensaje_estado(Q)), mantener.wait(3)))
        self.addCleanup(srv.cerrar)
        self.addCleanup(mantener.set)
        lector = ur.LectorUR("prueba", ur.UrPrimaria("127.0.0.1", srv.puerto))
        self.addCleanup(lector.detener)
        lector.start()
        self.assertTrue(self.esperar(lambda: lector.ultimo_q() is not None))
        self.assertIsNone(lector.ultimo_error)


if __name__ == "__main__":
    unittest.main()
