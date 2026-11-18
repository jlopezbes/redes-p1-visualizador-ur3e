"""
Pruebas de src/ensenar.py: _ruta, los comandos de la consola (_comando, ajustar) y main() entero contra el robot falso
de las pruebas (127.0.0.1) con un simulador falso (no abre ventana).

    python -B -m unittest discover -s pruebas -p test_ensenar.py -v

Los ficheros de secuencias y el robots.json van a carpetas temporales y el puerto del robot es uno libre: no se toca datos\\.
"""
import contextlib
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

import ayudas
import ensenar
import secuencia
import ur
from robot_falso import Q_INICIAL, RobotFalso
from simulador import ErrorSimulador

Q = [0.0, -1.0, 0.0, -1.0, 0.0, 0.0]            # rad


def esperar(condicion, plazo=8.0):
    """Espera (s) a que `condicion()` sea verdadera; devuelve si lo fue."""
    limite = time.monotonic() + plazo
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return bool(condicion())


class RedGrabadora:
    """Hace de ConexionTCP: guarda lo que se envia."""

    def __init__(self):
        self.enviado = []

    def enviar(self, datos):
        self.enviado.append(datos)


class SimuladorComandos:
    """Solo para _comando: apunta las previsualizaciones."""

    def __init__(self):
        self.previsualizaciones = []

    def previsualizar(self, nombre, desde, puntos):
        self.previsualizaciones.append((nombre, list(desde), [list(p) for p in puntos]))


def simulador_falso(fallar_en=None, error=None):
    """Clase que hace de Simulador: apunta los robots, lo movido y si se cerro; falla en la llamada n a mover()."""
    class Falso:
        creados = []

        def __init__(self):
            self.cerrado = False
            self.llamadas = 0
            self.robots = []
            self.movidos = set()
            Falso.creados.append(self)

        def agregar_robot(self, nombre):
            self.robots.append(nombre)

        def mover(self, nombre, q):
            self.llamadas += 1
            self.movidos.add(nombre)
            if self.llamadas == fallar_en:
                raise error

        def previsualizar(self, *args):
            pass

        def cerrar(self):
            self.cerrado = True
    return Falso


class Base(unittest.TestCase):
    """Salida capturada y SECUENCIAS en una carpeta temporal."""

    def setUp(self):
        self.salida = io.StringIO()
        redir = contextlib.redirect_stdout(self.salida)
        redir.__enter__()
        self.addCleanup(redir.__exit__, None, None, None)
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = temporal.name
        self.sec = os.path.join(self.dir, "secuencias")
        os.makedirs(self.sec)
        parche = mock.patch.object(ensenar, "SECUENCIAS", self.sec)
        parche.start()
        self.addCleanup(parche.stop)

    def escribir_secuencia(self, nombre, puntos):
        ruta = os.path.join(self.sec, nombre)
        with open(ruta, "w") as f:
            json.dump(puntos, f)
        return ruta


class PruebasRuta(Base):
    def test_solo_cuenta_el_nombre_y_se_anade_json(self):
        self.assertEqual(ensenar._ruta("mi"), os.path.join(self.sec, "mi.json"))
        self.assertEqual(ensenar._ruta("mi.json"), os.path.join(self.sec, "mi.json"))
        self.assertEqual(ensenar._ruta("  mi  "), os.path.join(self.sec, "mi.json"))
        self.assertEqual(ensenar._ruta("sub/carpeta/mi"), os.path.join(self.sec, "mi.json"))

    def test_rutas_con_carpetas_o_absolutas_quedan_dentro_de_secuencias(self):
        casos = {"../x": "x.json", "../../x.json": "x.json", "/etc/passwd": "passwd.json",
                 "C:\\x\\y": "y.json", "..\\x": "x.json", "a/b/": "secuencia.json", "..": "...json"}
        for entrada, esperado in casos.items():
            with self.subTest(entrada):
                ruta = ensenar._ruta(entrada)
                self.assertEqual(os.path.dirname(ruta), self.sec)
                self.assertEqual(os.path.basename(ruta), esperado)

    def test_vacio_es_secuencia_json(self):
        for entrada in ("", "   ", "\t"):
            with self.subTest(repr(entrada)):
                self.assertEqual(ensenar._ruta(entrada), os.path.join(self.sec, "secuencia.json"))


class PruebasComandos(Base):
    def setUp(self):
        super().setUp()
        self.robot = ur.ClienteUR("127.0.0.1")
        self.robot.red = RedGrabadora()
        self.rep = secuencia.Reproductor(self.robot, secuencia.Secuencia(), velocidad=0.1, aceleracion=0.2)
        self.sim = SimuladorComandos()
        self.nueva = ""                 # lo que ha escrito el ultimo cmd()

    def cmd(self, linea):
        antes = len(self.salida.getvalue())
        resultado = ensenar._comando(linea, self.rep, self.sim, "robot1")
        self.nueva = self.salida.getvalue()[antes:]
        return resultado

    def enviado(self):
        return self.robot.red.enviado

    # ---- q ----
    def test_q_sale_y_el_resto_no(self):
        self.assertTrue(self.cmd("q"))
        for orden in ("g", "b", "v", "e", "c", "r", "s", "l", "ajustar 0.1 0.2", "zzz", ""):
            with self.subTest(orden):
                self.assertFalse(self.cmd(orden))

    def test_q_vale_con_el_robot_en_marcha_y_no_envia_nada(self):
        self.rep.fase = secuencia.MOVIENDO
        self.assertTrue(self.cmd("q"))
        self.assertEqual(self.enviado(), [])            # frenar es cosa del finally de main()

    # ---- g, b, v, e ----
    def test_g_guarda_la_posicion_actual(self):
        self.rep.q = Q
        self.cmd("g")
        self.assertEqual(self.rep.secuencia, [Q])
        self.assertIn("Punto 1 guardado", self.nueva)

    def test_g_sin_posicion_no_guarda(self):
        self.cmd("g")
        self.assertEqual(self.rep.secuencia, [])
        self.assertIn("Todavia no se ha recibido la posicion", self.nueva)

    def test_b_borra(self):
        self.rep.secuencia.append(Q)
        self.cmd("b")
        self.assertEqual(len(self.rep.secuencia), 0)
        self.assertIn("Secuencia borrada", self.nueva)

    def test_v_previsualiza_desde_la_posicion_actual_con_el_nombre_del_robot(self):
        self.rep.q = Q
        self.cmd("v")
        self.assertIn("Nada que previsualizar", self.nueva)             # sin puntos
        self.rep.secuencia.append([0.1] * 6)
        self.cmd("v")
        self.assertEqual(self.sim.previsualizaciones, [("robot1", Q, [[0.1] * 6])])

    def test_v_sin_posicion_no_previsualiza(self):
        self.rep.secuencia.append(Q)
        self.cmd("v")
        self.assertEqual(self.sim.previsualizaciones, [])
        self.assertIn("Nada que previsualizar", self.nueva)

    def test_e_envia_el_primer_movej(self):
        self.rep.q = Q
        self.rep.secuencia.append(Q)
        self.cmd("e")
        self.assertTrue(self.enviado()[0].startswith(b"movej(["))
        self.assertEqual((self.rep.fase, self.rep.i), (secuencia.ENVIADO, 0))

    def test_e_sin_puntos_no_envia_nada(self):
        self.rep.q = Q
        self.cmd("e")
        self.assertEqual(self.enviado(), [])
        self.assertIn("Nada que ejecutar", self.nueva)

    # ---- c y r ----
    def test_c_frena_y_deja_la_secuencia_libre(self):
        self.rep.q = Q
        self.rep.secuencia.append([0.1] * 6)
        self.cmd("e")
        self.assertFalse(self.cmd("c"))
        self.assertEqual(self.enviado()[-1], b"stopj(0.2)\n")
        self.assertEqual((self.rep.fase, self.rep.i), (secuencia.LIBRE, None))
        self.assertIn("Cancelado", self.nueva)

    def test_c_sin_nada_en_marcha_no_envia_stopj(self):
        self.cmd("c")
        self.assertEqual(self.enviado(), [])
        self.assertIn("Cancelado", self.nueva)

    def test_r_reanuda_desde_la_parada(self):
        self.rep.q = Q
        self.rep.secuencia.append([0.1] * 6)
        self.rep.i = 0
        self.rep.fase = secuencia.PARADA
        self.cmd("r")
        self.assertTrue(self.enviado()[-1].startswith(b"movej(["))
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)

    def test_r_sin_parada_no_hace_nada(self):
        self.rep.secuencia.append(Q)
        self.cmd("r")
        self.assertEqual(self.enviado(), [])
        self.assertIn("No hay ninguna parada que reanudar", self.nueva)

    # ---- bloqueo mientras fase != LIBRE ----
    def test_con_la_secuencia_en_marcha_o_parada_solo_valen_c_r_y_q(self):
        self.rep.q = Q
        self.rep.secuencia.append(Q)
        self.rep.i = 0
        for fase in (secuencia.ENVIADO, secuencia.MOVIENDO, secuencia.PARADA):
            for orden in ("g", "b", "v", "e", "s x", "l x", "ajustar 0.2 0.3", "zzz"):
                with self.subTest(fase=fase, orden=orden):
                    self.rep.fase = fase
                    self.assertFalse(self.cmd(orden))
                    self.assertIn("Secuencia en marcha o parada", self.nueva)
                    self.assertEqual(self.enviado(), [])                # no se envio nada
                    self.assertEqual(self.rep.secuencia, [Q])           # ni b borro ni g añadio
                    self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.1, 0.2))
                    self.assertEqual(self.sim.previsualizaciones, [])
                    self.assertEqual(os.listdir(self.sec), [])          # ni s guardo
                    self.assertNotIn("Comandos:", self.nueva)
        self.rep.fase = secuencia.MOVIENDO
        self.cmd("c")                                                   # c y q si valen
        self.assertEqual(self.enviado()[-1], b"stopj(0.2)\n")
        self.assertTrue(self.cmd("q"))

    # ---- s y l ----
    def test_salvar_y_cargar_por_nombre_en_secuencias(self):
        self.rep.secuencia.append(Q)
        self.cmd("s mi")
        self.assertEqual(os.listdir(self.sec), ["mi.json"])
        self.assertIn("1 puntos guardados en mi.json", self.nueva)
        self.rep.secuencia.clear()
        self.cmd("l mi")
        self.assertEqual(self.rep.secuencia, [Q])
        self.assertIn("1 puntos cargados de mi.json", self.nueva)

    def test_sin_nombre_usa_secuencia_json(self):
        self.rep.secuencia.append(Q)
        self.cmd("s")
        self.assertEqual(os.listdir(self.sec), ["secuencia.json"])
        self.rep.secuencia.clear()
        self.cmd("l")
        self.assertEqual(self.rep.secuencia, [Q])

    def test_salvar_con_ruta_no_sale_de_secuencias(self):
        self.rep.secuencia.append(Q)
        self.cmd("s ../fuera")
        self.cmd("s /etc/absoluto")
        self.assertEqual(sorted(os.listdir(self.sec)), ["absoluto.json", "fuera.json"])
        self.assertEqual(sorted(os.listdir(self.dir)), ["secuencias"])      # nada en la carpeta de arriba

    def test_salvar_crea_la_carpeta_si_no_existe(self):
        nueva = os.path.join(self.dir, "otra", "secuencias")
        self.rep.secuencia.append(Q)
        with mock.patch.object(ensenar, "SECUENCIAS", nueva):
            self.cmd("s mi")
        self.assertEqual(os.listdir(nueva), ["mi.json"])

    def test_salvar_en_un_sitio_imposible_avisa(self):
        self.rep.secuencia.append(Q)
        os.makedirs(os.path.join(self.sec, "x.json"))                       # un directorio donde iria el fichero
        self.assertFalse(self.cmd("s x"))
        self.assertIn("No se pudo guardar", self.nueva)
        fichero = os.path.join(self.dir, "fichero")
        with open(fichero, "w"):
            pass
        with mock.patch.object(ensenar, "SECUENCIAS", os.path.join(fichero, "dentro")):   # carpeta bajo un fichero
            self.assertFalse(self.cmd("s y"))
        self.assertIn("No se pudo guardar", self.nueva)

    def test_cargar_ficheros_malos_avisa_y_no_cambia_la_secuencia(self):
        self.rep.secuencia.append(Q)
        with open(os.path.join(self.sec, "roto.json"), "w") as f:
            f.write("{no es json")
        self.escribir_secuencia("grados.json", [[0, 0, 0, 0, 0, 90.0]])
        self.escribir_secuencia("forma.json", {"a": 1})
        for nombre in ("roto", "grados", "forma", "no_existe"):
            with self.subTest(nombre):
                self.assertFalse(self.cmd("l " + nombre))
                self.assertIn("No se pudo cargar", self.nueva)
                self.assertEqual(self.rep.secuencia, [Q])

    # ---- cualquier otra cosa ----
    def test_orden_desconocida_muestra_la_ayuda(self):
        for linea in ("zzz", "", "G", "ajustarr 0.1 0.2"):
            with self.subTest(repr(linea)):
                self.cmd(linea)
                self.assertIn(ensenar.AYUDA, self.nueva)
        self.assertIn("ajustar", ensenar.AYUDA)


class PruebasAjustar(Base):
    def setUp(self):
        super().setUp()
        self.robot = ur.ClienteUR("127.0.0.1")
        self.robot.red = RedGrabadora()
        self.rep = secuencia.Reproductor(self.robot, secuencia.Secuencia(), velocidad=0.1, aceleracion=0.2)
        self.nueva = ""

    def cmd(self, linea):
        antes = len(self.salida.getvalue())
        resultado = ensenar._comando(linea, self.rep, SimuladorComandos(), "robot1")
        self.nueva = self.salida.getvalue()[antes:]
        return resultado

    def test_valido_cambia_velocidad_y_aceleracion(self):
        self.assertFalse(self.cmd("ajustar 0.2 0.3"))
        self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.2, 0.3))
        self.assertIn("Velocidad 0.2 rad/s y aceleracion 0.3 rad/s2", self.nueva)

    def test_los_limites_son_validos(self):
        self.cmd("ajustar {} {}".format(ur.MINIMO, ur.MINIMO))
        self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (ur.MINIMO, ur.MINIMO))
        self.cmd("ajustar {} {}".format(ur.VELOCIDAD_MAX, ur.ACELERACION_MAX))
        self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (ur.VELOCIDAD_MAX, ur.ACELERACION_MAX))

    def test_los_movej_siguientes_usan_lo_ajustado(self):
        self.rep.q = Q
        self.rep.secuencia.append(Q)
        self.cmd("ajustar 0.2 0.3")
        self.cmd("e")
        self.assertIn(b"a=0.3, v=0.2", self.robot.red.enviado[-1])

    def test_fuera_de_rango_no_cambia_y_avisa(self):
        for linea in ("ajustar 0.5 0.3", "ajustar 0.2 0.6", "ajustar 0 0.2", "ajustar 0.2 0", "ajustar -0.1 0.2",
                      "ajustar nan 0.2", "ajustar 0.2 inf"):
            with self.subTest(linea):
                self.assertFalse(self.cmd(linea))
                self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.1, 0.2))
                self.assertIn("No se cambia", self.nueva)

    def test_mal_formado_da_el_uso(self):
        for linea in ("ajustar", "ajustar a b", "ajustar 0.1", "ajustar 0.1 0.2 0.3", "ajustar 0,1 0,2"):
            with self.subTest(linea):
                self.assertFalse(self.cmd(linea))
                self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.1, 0.2))
                self.assertIn("Uso: ajustar", self.nueva)

    def test_bloqueado_mientras_hay_una_secuencia_en_marcha_o_parada(self):
        for fase in (secuencia.ENVIADO, secuencia.MOVIENDO, secuencia.PARADA):
            with self.subTest(fase):
                self.rep.fase = fase
                self.cmd("ajustar 0.2 0.3")
                self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.1, 0.2))
                self.assertIn("Secuencia en marcha o parada", self.nueva)
        self.rep.fase = secuencia.LIBRE
        self.cmd("ajustar 0.2 0.3")
        self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.2, 0.3))


class PruebasMain(Base):
    """main() entero en un hilo: robot falso en un puerto libre, simulador falso y una consola de mentira que solo
    guarda la cola (las ordenes entran con poner())."""

    def setUp(self):
        super().setUp()
        parche = mock.patch.object(ur, "REINTENTO", 0.2)
        parche.start()
        self.addCleanup(parche.stop)
        self.fake = RobotFalso(ayudas.puerto_libre()).iniciar()
        self.addCleanup(self.fake.parar)
        self.robots = os.path.join(self.dir, "robots.json")
        self.escribir_robots([{"nombre": "robot1", "ip": "127.0.0.1"}, {"nombre": "robot2", "ip": "10.255.255.1"}])
        self.cola = None
        self.error = None                   # lo que lanzo main()
        self.hilo = None

    def escribir_robots(self, robots):
        with open(self.robots, "w") as f:
            json.dump(robots, f)

    def consola(self, cola):
        self.cola = cola

    def arrancar(self, sim=None, puerto=None, consola=True):
        """Lanza ensenar.main() en un hilo con todo parcheado. Devuelve la clase del simulador falso."""
        sim = sim or simulador_falso()
        self.sim_clase = sim
        self.addCleanup(self.terminar_si_sigue)         # se ejecuta antes que el stop de los parches
        parches = [
            mock.patch.object(ensenar, "ROBOTS", self.robots),
            mock.patch.object(ur, "PUERTO_PRIMARIA", puerto or self.fake.puerto),
            mock.patch.object(ensenar, "Simulador", sim),
        ]
        if consola:
            parches.append(mock.patch.object(ensenar, "_leer_consola", self.consola))
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        self.hilos_antes = set(threading.enumerate())
        self.hilo = threading.Thread(target=self._correr, name="main-ensenar", daemon=True)
        self.t0 = time.monotonic()
        self.hilo.start()
        return sim

    def _correr(self):
        try:
            ensenar.main()
        except BaseException as e:          # KeyboardInterrupt incluido: main() la deja pasar
            self.error = e

    def sim(self):
        self.assertTrue(esperar(lambda: self.sim_clase.creados), "main() no creo el simulador")
        return self.sim_clase.creados[0]

    # ---- ayudas ----
    def esperar_texto(self, texto, veces=1, plazo=8.0):
        ok = esperar(lambda: self.salida.getvalue().count(texto) >= veces, plazo)
        self.assertTrue(ok, "no salio {!r} (x{}). Salida:\n{}".format(texto, veces, self.salida.getvalue()))

    def esperar_orden(self, prefijo, veces=1, plazo=8.0):
        ok = esperar(lambda: len([o for o in self.fake.ordenes if o.startswith(prefijo)]) >= veces, plazo)
        self.assertTrue(ok, "el robot falso no recibio {!r}: {}".format(prefijo, self.fake.ordenes))

    def poner(self, linea):
        self.assertTrue(esperar(lambda: self.cola is not None), "main() no arranco la consola")
        self.cola.put(linea)

    def terminar(self, plazo=10.0):
        """Espera a que main() acabe y comprueba que no quedan hilos suyos."""
        self.hilo.join(plazo)
        self.assertFalse(self.hilo.is_alive(), "main() no termino. Salida:\n{}".format(self.salida.getvalue()))
        sobran = lambda: [h.name for h in set(threading.enumerate()) - self.hilos_antes if h.is_alive()]
        self.assertTrue(esperar(lambda: not sobran(), 3.0), "hilos colgados: {}".format(sobran()))

    def terminar_si_sigue(self):
        """Limpieza: si una prueba fallo a medias, para main() con una 'q' para que no siga imprimiendo."""
        if self.hilo is not None and self.hilo.is_alive():
            if self.cola is not None:
                self.cola.put("q")
            self.hilo.join(10)

    # ---- guardar, ejecutar, terminar ----
    def test_guardar_ejecutar_y_terminar_una_secuencia(self):
        sim = self.arrancar()
        self.poner("g")
        self.esperar_texto("Punto 1 guardado")
        self.poner("e")
        self.esperar_texto("Secuencia terminada")
        self.esperar_orden("movej")
        self.poner("s guardada")
        self.esperar_texto("1 puntos guardados en guardada.json")
        with open(os.path.join(self.sec, "guardada.json")) as f:
            self.assertEqual(json.load(f), [Q_INICIAL])
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)
        self.assertEqual(len([o for o in self.fake.ordenes if o.startswith("movej")]), 1)
        creado = sim.creados[0]
        self.assertEqual((creado.robots, creado.movidos, creado.cerrado), (["robot1"], {"robot1"}, True))
        self.assertIn("Conectado a 127.0.0.1:{}".format(self.fake.puerto), self.salida.getvalue())

    def test_secuencia_de_dos_puntos_mueve_el_robot_y_termina(self):
        lejos = list(Q_INICIAL)
        lejos[0] = 0.05                                             # rad: a 0,1 rad/s son 0,5 s
        self.escribir_secuencia("ida_y_vuelta.json", [lejos, Q_INICIAL])
        self.arrancar()
        self.poner("l ida_y_vuelta")
        self.poner("e")
        self.esperar_texto("Secuencia terminada")
        self.assertEqual(len([o for o in self.fake.ordenes if o.startswith("movej")]), 2)
        self.assertIn("Punto 2/2 enviado", self.salida.getvalue())
        self.assertAlmostEqual(self.fake.q[0], Q_INICIAL[0], places=3)
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)

    # ---- el robot se frena en el finally ----
    def preparar_movimiento_largo(self):
        destino = list(Q_INICIAL)
        destino[0] = 0.9                                            # rad: a 0,1 rad/s son 9 s
        self.escribir_secuencia("larga.json", [destino])
        self.poner("l larga")
        self.poner("e")
        self.esperar_orden("movej")

    def test_q_con_movimiento_en_curso_frena_el_robot_y_cierra(self):
        sim = self.arrancar()
        self.preparar_movimiento_largo()
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)
        self.esperar_orden("stopj")
        self.assertIn("Cancelado", self.salida.getvalue())
        self.assertTrue(sim.creados[0].cerrado)

    def test_q_con_el_robot_quieto_no_envia_stopj(self):
        self.arrancar()
        self.poner("g")
        self.esperar_texto("Punto 1 guardado")
        self.poner("q")
        self.terminar()
        time.sleep(0.2)
        self.assertEqual([o for o in self.fake.ordenes if o.startswith("stopj")], [])

    def test_ventana_cerrada_con_el_robot_en_movimiento_envia_stopj_y_cierra(self):
        sim = self.arrancar(simulador_falso(12, ErrorSimulador("ventana cerrada")))
        self.preparar_movimiento_largo()
        self.terminar()
        self.assertIsInstance(self.error, ErrorSimulador)
        self.esperar_orden("stopj")
        self.assertTrue(sim.creados[0].cerrado)

    def test_ctrl_c_con_el_robot_en_movimiento_envia_stopj_y_cierra(self):
        sim = self.arrancar(simulador_falso(12, KeyboardInterrupt()))
        self.preparar_movimiento_largo()
        self.terminar()
        self.assertIsInstance(self.error, KeyboardInterrupt)
        self.esperar_orden("stopj")
        self.assertTrue(sim.creados[0].cerrado)

    def test_ventana_que_falla_sin_movimiento_cierra_sin_stopj(self):
        sim = self.arrancar(simulador_falso(3, ErrorSimulador("ventana cerrada")))
        self.terminar()
        self.assertIsInstance(self.error, ErrorSimulador)
        self.assertTrue(sim.creados[0].cerrado)
        self.assertEqual([o for o in self.fake.ordenes if o.startswith("stopj")], [])

    # ---- red ----
    def test_robot_que_se_cae_con_movimiento_en_curso_queda_en_parada_y_reconecta(self):
        sim = self.arrancar()
        self.preparar_movimiento_largo()
        self.esperar_texto("Punto 1/1 enviado")
        with self.fake._lock:               # shutdown: en Linux close() no corta un recv() bloqueado del robot falso
            for cliente in self.fake._clientes:
                cliente.shutdown(socket.SHUT_RDWR)
        self.fake.cortar_clientes()
        self.esperar_texto("Conexion perdida")
        self.esperar_texto("Secuencia interrumpida en el punto 1")
        self.esperar_texto("Conectado a", veces=2)                  # y vuelve a conectar
        self.assertIn("NO SE HA PODIDO ENVIAR LA PARADA", self.salida.getvalue())     # sin conexion no se pudo frenar
        self.poner("e")                                             # en parada solo valen 'c', 'r' y 'q'
        self.esperar_texto("Secuencia en marcha o parada")
        self.poner("c")
        self.esperar_texto("Cancelado")
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)
        self.assertTrue(sim.creados[0].cerrado)

    def test_q_con_el_robot_caido_sale_sin_esperar_y_cierra(self):
        sim = self.arrancar(puerto=ayudas.puerto_libre())           # nadie escucha en ese puerto
        self.poner("q")
        self.terminar()
        self.assertLess(time.monotonic() - self.t0, 5.0)
        self.assertIsNone(self.error)
        self.assertTrue(sim.creados[0].cerrado)
        self.assertIn("Conexion perdida", self.salida.getvalue())
        self.assertNotIn("Conectado a", self.salida.getvalue())

    def test_con_el_robot_caido_la_consola_sigue_atendida(self):
        self.arrancar(puerto=ayudas.puerto_libre())
        self.esperar_texto("Conexion perdida")
        self.poner("zzz")                                           # mientras reintenta atiende las ordenes
        self.esperar_texto(ensenar.AYUDA, veces=1)
        self.poner("q")
        self.terminar()

    # ---- consola ----
    def test_eof_en_la_consola_sale_como_una_q(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            sim = self.arrancar(consola=False)
            self.terminar()
        self.assertIsNone(self.error)
        self.assertTrue(sim.creados[0].cerrado)

    def test_la_consola_lee_lineas_y_las_pasa_a_la_cola(self):
        with mock.patch("builtins.input", side_effect=["  g  ", "q", EOFError]):
            sim = self.arrancar(consola=False)
            self.esperar_texto("Punto 1 guardado")
            self.terminar()
        self.assertIsNone(self.error)
        self.assertTrue(sim.creados[0].cerrado)

    # ---- arranque ----
    def test_usa_el_primer_robot_del_json(self):
        sim = self.arrancar()
        self.poner("q")
        self.terminar()
        self.assertEqual(sim.creados[0].robots, ["robot1"])         # el segundo (robot2) ni se intenta

    def test_robots_json_malo_falla_antes_de_abrir_nada(self):
        os.remove(self.robots)
        self.arrancar()
        self.terminar()
        self.assertIsInstance(self.error, ValueError)
        self.assertIn(self.robots, str(self.error))
        self.assertEqual(self.sim_clase.creados, [])                # ni ventana

    def test_ip_mala_en_el_json_falla_antes_de_abrir_nada(self):
        self.escribir_robots([{"nombre": "robot1", "ip": "no-es-una-ip"}])
        self.arrancar()
        self.terminar()
        self.assertIsInstance(self.error, ValueError)
        self.assertEqual(self.sim_clase.creados, [])


if __name__ == "__main__":
    unittest.main()
