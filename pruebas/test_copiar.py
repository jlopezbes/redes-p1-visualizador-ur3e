"""
Pruebas de src/copiar.py: eleccion de grabador y ejecutor, 'g' con el q del grabador y main() entero contra DOS robots
falsos de las pruebas (127.0.0.1 = ejecutor, 127.0.0.2 = grabador, mismo puerto) con un simulador falso (no abre ventana).

    python -B -m unittest discover -s pruebas -p test_copiar.py -v

Los ficheros de secuencias y el robots.json van a carpetas temporales y el puerto es uno libre: no se toca datos\\.
"""
import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

import ayudas
import copiar
import ur
from robot_falso import Q_INICIAL, RobotFalso
from secuencia import Reproductor, Secuencia
from test_ensenar import RedGrabadora, esperar, simulador_falso

Q_GRABADOR = [0.05, -1.5, 0.05, -1.5, 0.05, 0.05]          # rad: cerca de Q_INICIAL para que el movimiento sea corto
IP_EJECUTOR = "127.0.0.1"
IP_GRABADOR = "127.0.0.2"                                  # tambien es este PC (loopback)


class LectorQuieto:
    """Hace de HiloLectorUR para _comando: un q fijo (o None)."""

    def __init__(self, q, nombre="robot1"):
        self.nombre = nombre
        self.q = q
        self.ultimo_error = None
        self.cerrojo = threading.Lock()


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
        parche = mock.patch.object(copiar, "SECUENCIAS", self.sec)
        parche.start()
        self.addCleanup(parche.stop)


class PruebasElegirRobots(unittest.TestCase):
    ROBOTS = {"robot1": "10.0.0.1", "robot2": "10.0.0.2", "robot3": "10.0.0.3"}

    def test_sin_argumentos_graba_el_segundo_y_ejecuta_el_primero(self):
        self.assertEqual(copiar._elegir_robots(self.ROBOTS, []), ("robot2", "robot1"))

    def test_con_dos_nombres_se_pueden_cambiar_los_papeles(self):
        self.assertEqual(copiar._elegir_robots(self.ROBOTS, ["robot3", "robot1"]), ("robot3", "robot1"))

    def test_con_un_solo_robot_falla(self):
        with self.assertRaises(ValueError):
            copiar._elegir_robots({"robot1": "10.0.0.1"}, [])

    def test_nombre_que_no_existe_falla_y_dice_los_que_hay(self):
        with self.assertRaises(ValueError) as e:
            copiar._elegir_robots(self.ROBOTS, ["robot1", "robot9"])
        self.assertIn("robot9", str(e.exception))
        self.assertIn("robot2", str(e.exception))

    def test_el_mismo_robot_no_puede_grabar_y_ejecutar(self):
        with self.assertRaises(ValueError):
            copiar._elegir_robots(self.ROBOTS, ["robot1", "robot1"])
        with self.assertRaises(ValueError):                         # dos nombres, la misma IP
            copiar._elegir_robots({"a": "10.0.0.1", "b": "10.0.0.1"}, [])

    def test_un_solo_argumento_o_tres_falla(self):
        for argumentos in (["robot1"], ["robot1", "robot2", "robot3"]):
            with self.assertRaises(ValueError):
                copiar._elegir_robots(self.ROBOTS, argumentos)


class PruebasComandos(Base):
    def setUp(self):
        super().setUp()
        self.red = RedGrabadora()
        robot = ur.ClienteUR("127.0.0.1")
        robot.red = self.red
        self.rep = Reproductor(robot, Secuencia(), 0.1, 0.2)
        self.rep.q = list(Q_INICIAL)                                # el ejecutor esta en otro sitio

    def cmd(self, linea, lector):
        return copiar._comando(linea, self.rep, lector, None, "robot2")

    def test_g_guarda_el_q_del_grabador_no_el_del_ejecutor(self):
        self.cmd("g", LectorQuieto(Q_GRABADOR))
        self.assertEqual(self.rep.secuencia, [Q_GRABADOR])
        self.assertIn("Punto 1 guardado", self.salida.getvalue())

    def test_g_sin_datos_del_grabador_no_guarda(self):
        self.cmd("g", LectorQuieto(None))
        self.assertEqual(self.rep.secuencia, [])
        self.assertIn("Todavia no se ha recibido la posicion del grabador robot1", self.salida.getvalue())

    def test_g_con_angulos_fuera_de_rango_no_guarda(self):
        self.cmd("g", LectorQuieto([10.0] * 6))
        self.assertEqual(self.rep.secuencia, [])
        self.assertIn("No se guarda", self.salida.getvalue())

    def test_g_no_envia_nada_al_ejecutor(self):
        self.cmd("g", LectorQuieto(Q_GRABADOR))
        self.assertEqual(self.red.enviado, [])


class PruebasMain(Base):
    """main() entero en un hilo con dos robots falsos y una consola de mentira (las ordenes entran con poner())."""

    def setUp(self):
        super().setUp()
        parche = mock.patch.object(ur, "REINTENTO", 0.2)
        parche.start()
        self.addCleanup(parche.stop)
        puerto = ayudas.puerto_libre()
        self.ejecutor = RobotFalso(puerto, ip=IP_EJECUTOR).iniciar()
        self.addCleanup(self.ejecutor.parar)
        self.grabador = RobotFalso(puerto, q=Q_GRABADOR, ip=IP_GRABADOR).iniciar()
        self.addCleanup(self.grabador.parar)
        self.puerto = puerto
        self.robots = os.path.join(self.dir, "robots.json")
        with open(self.robots, "w") as f:
            json.dump([{"nombre": "robot1", "ip": IP_EJECUTOR}, {"nombre": "robot2", "ip": IP_GRABADOR}], f)
        self.cola = None
        self.error = None
        self.hilo = None

    def consola(self, cola):
        self.cola = cola

    def arrancar(self, argumentos=()):
        sim = simulador_falso()
        self.sim_clase = sim
        self.addCleanup(self.terminar_si_sigue)
        for p in (mock.patch.object(copiar, "ROBOTS", self.robots),
                  mock.patch.object(ur, "PUERTO_PRIMARIA", self.puerto),
                  mock.patch.object(copiar, "Simulador", sim),
                  mock.patch.object(copiar, "_leer_consola", self.consola)):
            p.start()
            self.addCleanup(p.stop)
        self.hilos_antes = set(threading.enumerate())
        self.hilo = threading.Thread(target=self._correr, args=(argumentos,), name="main-copiar", daemon=True)
        self.hilo.start()
        return sim

    def _correr(self, argumentos):
        try:
            copiar.main(argumentos)
        except BaseException as e:
            self.error = e

    def esperar_texto(self, texto, veces=1, plazo=8.0):
        ok = esperar(lambda: self.salida.getvalue().count(texto) >= veces, plazo)
        self.assertTrue(ok, "no salio {!r} (x{}). Salida:\n{}".format(texto, veces, self.salida.getvalue()))

    def poner(self, linea):
        self.assertTrue(esperar(lambda: self.cola is not None), "main() no arranco la consola")
        self.cola.put(linea)

    def terminar(self, plazo=10.0):
        self.hilo.join(plazo)
        self.assertFalse(self.hilo.is_alive(), "main() no termino. Salida:\n{}".format(self.salida.getvalue()))
        sobran = lambda: [h.name for h in set(threading.enumerate()) - self.hilos_antes if h.is_alive()]
        self.assertTrue(esperar(lambda: not sobran(), 3.0), "hilos colgados: {}".format(sobran()))

    def terminar_si_sigue(self):
        if self.hilo is not None and self.hilo.is_alive():
            if self.cola is not None:
                self.cola.put("q")
            self.hilo.join(10)

    def guardar_del_grabador(self):
        self.esperar_texto("[robot2] recibiendo estados")
        self.poner("g")
        self.esperar_texto("Punto 1 guardado")

    def test_graba_en_uno_y_mueve_el_otro(self):
        sim = self.arrancar()
        self.guardar_del_grabador()
        self.poner("e")
        self.esperar_texto("Secuencia terminada")
        for real, esperado in zip(self.ejecutor.q, Q_GRABADOR):     # el ejecutor ha ido a la pose del grabador
            self.assertAlmostEqual(real, esperado, places=3)
        self.assertEqual(len([o for o in self.ejecutor.ordenes if o.startswith("movej")]), 1)
        self.assertEqual(self.grabador.ordenes, [])                 # al grabador no se le envia nada, nunca
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)
        creado = sim.creados[0]
        self.assertEqual((creado.robots, creado.movidos, creado.cerrado),
                         (["robot2", "robot1"], {"robot1", "robot2"}, True))
        self.assertIn("Conectado a {}:{}".format(IP_EJECUTOR, self.puerto), self.salida.getvalue())

    def test_con_argumentos_se_cambian_los_papeles(self):
        self.arrancar(["robot1", "robot2"])                         # graba 127.0.0.1 y mueve 127.0.0.2
        self.esperar_texto("Conectado a {}:{}".format(IP_GRABADOR, self.puerto))
        self.poner("g")
        self.esperar_texto("Punto 1 guardado")
        self.poner("e")
        self.esperar_texto("Secuencia terminada")
        self.assertEqual(self.ejecutor.ordenes, [])
        self.assertEqual(len([o for o in self.grabador.ordenes if o.startswith("movej")]), 1)
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)

    def empezar_movimiento_largo(self):
        lejos = list(Q_INICIAL)
        lejos[0] = 0.9                                              # rad: a 0,1 rad/s son 9 s
        with open(os.path.join(self.sec, "larga.json"), "w") as f:
            json.dump([lejos], f)
        self.poner("l larga")
        self.poner("e")
        self.esperar_texto("Punto 1/1 enviado")

    def test_q_con_movimiento_en_curso_frena_solo_al_ejecutor(self):
        self.arrancar()
        self.empezar_movimiento_largo()
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)
        self.assertTrue(esperar(lambda: any(o.startswith("stopj") for o in self.ejecutor.ordenes), 3.0))
        self.assertEqual(self.grabador.ordenes, [])

    def test_orden_rechazada_c210_reconecta_el_ejecutor(self):
        self.arrancar()
        self.empezar_movimiento_largo()
        self.ejecutor._difundir(ayudas.mensaje_error(ur.CODIGO_SIN_REMOTO))
        self.esperar_texto("Conectado a", veces=2)                  # cierra la conexion vieja y abre otra
        self.assertIn("no se ha movido", self.salida.getvalue())
        self.assertEqual([o for o in self.ejecutor.ordenes if o.startswith("stopj")], [])
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)

    def test_grabador_caido_no_impide_mover_lo_ya_grabado(self):
        self.arrancar()
        self.guardar_del_grabador()
        self.grabador.parar()
        self.poner("e")
        self.esperar_texto("Secuencia terminada")
        self.poner("q")
        self.terminar()
        self.assertIsNone(self.error)

    def test_ejecutor_caido_la_consola_y_el_grabador_siguen_atendidos(self):
        self.ejecutor.parar()                                       # nadie escucha en 127.0.0.1
        self.arrancar()
        self.esperar_texto("Conexion perdida")
        self.esperar_texto("[robot2] recibiendo estados")
        self.poner("g")                                             # se graba aunque el ejecutor no este
        self.esperar_texto("Punto 1 guardado")
        t0 = time.monotonic()
        self.poner("q")
        self.terminar()
        self.assertLess(time.monotonic() - t0, 5.0)
        self.assertIsNone(self.error)

    def test_robots_json_con_un_solo_robot_falla_antes_de_abrir_nada(self):
        with open(self.robots, "w") as f:
            json.dump([{"nombre": "robot1", "ip": IP_GRABADOR}], f)
        self.arrancar()
        self.terminar()
        self.assertIsInstance(self.error, ValueError)
        self.assertEqual(self.sim_clase.creados, [])


if __name__ == "__main__":
    unittest.main()
