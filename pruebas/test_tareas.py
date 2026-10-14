"""
Pruebas de src/tareas.py: cargar_robots y los comandos de la consola de enseñar y reproducir,
con un simulador falso (no abre ventana) y un robot que solo graba lo que se le envia.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import ayudas
import main
import secuencia
import tareas
import ur
from robot_falso import RobotFalso
from secuencia import ErrorSecuencia
from simulador import ErrorSimulador
from test_ur import RedGrabadora

Q = [0.0, -1.0, 0.0, -1.0, 0.0, 0.0]
ROBOT = {"nombre": "a", "ip": "127.0.0.1", "puerto": 30001, "posicion": [0] * 6}
CARPETA_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


class SimuladorFalso:
    def __init__(self):
        self.previsualizaciones = []

    def previsualizar(self, nombre, desde, puntos):
        self.previsualizaciones.append((nombre, list(desde), [list(p) for p in puntos]))


class PruebasCargarRobots(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = temporal.name

    def escribir(self, contenido, codificacion="utf-8"):
        ruta = os.path.join(self.dir, "robots.json")
        with open(ruta, "w", encoding=codificacion) as f:
            f.write(contenido)
        return ruta

    def test_el_robots_json_de_src_es_valido(self):
        # Solo que cargue y sea valido: las IP y los puertos los cambia Josu segun el robot que use (no se fijan aqui).
        robots = tareas.cargar_robots(os.path.join(CARPETA_SRC, "robots.json"))
        self.assertGreaterEqual(len(robots), 1)

    def test_tolera_el_bom_del_bloc_de_notas(self):
        robots = tareas.cargar_robots(self.escribir(
            json.dumps([{"nombre": "a", "ip": "1.2.3.4", "puerto": 30001, "posicion": [0] * 6}]), "utf-8-sig"))
        self.assertEqual(robots[0]["ip"], "1.2.3.4")

    def test_falta_un_campo(self):
        with self.assertRaises(ValueError) as e:
            tareas.cargar_robots(self.escribir(json.dumps([{"nombre": "a", "ip": "1.2.3.4", "puerto": 30001}])))
        self.assertIn("posicion", str(e.exception))


class PruebasComandos(unittest.TestCase):
    def setUp(self):
        self.salida = io.StringIO()
        redir = contextlib.redirect_stdout(self.salida)
        redir.__enter__()
        self.addCleanup(redir.__exit__, None, None, None)
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = temporal.name

        self.robot = ur.UrPrimaria("127.0.0.1")
        self.robot.red = RedGrabadora()
        self.robot.marcar_estado()          # movej exige un estado fresco
        self.rep = secuencia.Reproductor(self.robot, secuencia.Secuencia(), velocidad=0.1, aceleracion=0.2)
        self.sim = SimuladorFalso()

    def cmd(self, linea):
        return tareas._comando(linea, self.rep, self.sim)

    def ruta(self, nombre):
        return os.path.join(self.dir, nombre)

    def test_q_sale(self):
        self.assertTrue(self.cmd("q"))
        self.assertFalse(self.cmd("g"))

    def test_g_guarda_la_posicion_actual(self):
        self.rep.q = Q
        self.cmd("g")
        self.assertEqual(self.rep.secuencia.puntos, [Q])

    def test_b_borra(self):
        self.rep.secuencia.agregar(Q)
        self.cmd("b")
        self.assertEqual(len(self.rep.secuencia), 0)

    def test_v_previsualiza_desde_la_posicion_actual(self):
        self.rep.q = Q
        self.cmd("v")
        self.assertIn("Nada que previsualizar", self.salida.getvalue())     # sin puntos
        self.rep.secuencia.agregar([0.1] * 6)
        self.cmd("v")
        self.assertEqual(self.sim.previsualizaciones, [("robot", Q, [[0.1] * 6])])

    def test_e_envia_el_primer_movej(self):
        self.rep.q = Q
        self.rep.secuencia.agregar(Q)
        self.cmd("e")
        self.assertTrue(self.robot.red.enviado[0].startswith(b"movej(["))

    def test_con_el_robot_en_movimiento_solo_valen_c_y_q(self):
        self.rep.q = Q
        self.rep.secuencia.agregar([0.1] * 6)
        self.cmd("e")
        enviados = len(self.robot.red.enviado)
        for orden in ("g", "b", "v", "e", "r", "s", "l"):
            self.assertFalse(self.cmd(orden))
        self.assertEqual(len(self.robot.red.enviado), enviados)             # no se envio nada mas
        self.assertEqual(len(self.rep.secuencia), 1)                        # b no borro
        self.assertEqual(self.sim.previsualizaciones, [])
        self.cmd("c")
        self.assertEqual(self.robot.red.enviado[-1], b"stopj(0.2)\n")
        self.assertTrue(self.cmd("q"))

    def test_con_la_secuencia_parada_no_se_puede_cambiar(self):
        self.rep.secuencia.agregar(Q)
        self.rep.fase = secuencia.PARADA
        for orden in ("b", "g", "l"):
            self.cmd(orden)
        self.assertEqual(self.rep.secuencia.puntos, [Q])                    # ni borrada, ni cambiada

    def test_salvar_y_cargar(self):
        self.rep.secuencia.agregar(Q)
        fichero = self.ruta("s.json")
        self.cmd("s " + fichero)
        self.rep.secuencia.borrar()
        self.cmd("l " + fichero)
        self.assertEqual(self.rep.secuencia.puntos, [Q])

    def test_salvar_en_un_sitio_imposible_no_parece_una_conexion_perdida(self):
        self.cmd("s " + self.dir)                                           # un directorio, no un fichero
        self.assertIn("No se pudo guardar", self.salida.getvalue())

    def test_cargar_fichero_inexistente(self):
        self.cmd("l " + self.ruta("no_existe.json"))
        self.assertIn("No se pudo cargar", self.salida.getvalue())

    def test_orden_desconocida_muestra_la_ayuda(self):
        self.cmd("zzz")
        self.assertIn("Comandos:", self.salida.getvalue())


class PruebasRobotsJson(unittest.TestCase):
    def test_robots_json_malo_da_valueerror_en_español(self):
        casos = {"vacio": "", "corrupto": "[{", "lista vacia": "[]", "no es lista": '{"nombre": "a"}', "no son objetos": "[1, 2]",
                 "nombre repetido": json.dumps([ROBOT, ROBOT]), "nombre no texto": json.dumps([dict(ROBOT, nombre=5)])}
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "robots.json")
            for nombre, contenido in casos.items():
                with self.subTest(nombre):
                    with open(ruta, "w") as f:
                        f.write(contenido)
                    with self.assertRaises(ValueError):
                        tareas.cargar_robots(ruta)
            with self.assertRaises(ValueError):                         # fichero inexistente
                tareas.cargar_robots(os.path.join(carpeta, "no_existe.json"))


class PruebasMain(unittest.TestCase):
    """main.main(): codigo 2 si los argumentos o robots.json estan mal (sin abrir el simulador), 1 si falla una capa, 0 con Ctrl+C."""

    def ejecutar(self, argv, tarea=None, error=None):
        """Devuelve (codigo de salida, lo escrito en stderr, simulador falso). Si `tarea`, esa tarea lanza `error`."""
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["main.py"] + argv), mock.patch.object(tareas, "Simulador") as sim, \
                contextlib.redirect_stderr(err), contextlib.ExitStack() as pila:
            if tarea:
                pila.enter_context(mock.patch.object(tareas, tarea, side_effect=error))
            try:
                main.main()
                codigo = 0
            except SystemExit as e:
                codigo = e.code
        return codigo, err.getvalue(), sim

    def test_argumentos_y_configuracion_malos_dan_codigo_2_sin_abrir_el_simulador(self):
        with tempfile.TemporaryDirectory() as carpeta:
            vacio = os.path.join(carpeta, "vacio.json")
            with open(vacio, "w") as f:
                f.write("[]")
            casos = [["primaria", "--puerto", "99999"], ["primaria", "--puerto", "0"], ["primaria", "--ip", "localhost"],
                     ["tiempo-real", "--ip", ""], ["ensenar", "--ip", "localhost"], ["ensenar", "--v", "0.0005"],
                     ["varios", "--config", os.path.join(carpeta, "no_existe.json")], ["varios", "--config", vacio]]
            for argv in casos:
                with self.subTest(argv):
                    codigo, _, sim = self.ejecutar(argv)
                    self.assertEqual(codigo, 2)
                    sim.assert_not_called()

    def test_error_de_una_capa_da_codigo_1_con_mensaje_y_sin_traceback(self):
        for error in (ur.ErrorUR("robot caido"), ErrorSimulador("ventana cerrada"), ErrorSecuencia("fichero malo")):
            with self.subTest(error):
                codigo, err, _ = self.ejecutar(["primaria"], "visualizar_primaria", error)
                self.assertEqual(codigo, 1)
                self.assertIn("Error: " + str(error), err)
                self.assertNotIn("Traceback", err)

    def test_fallo_inesperado_da_codigo_1_con_traceback_y_ctrl_c_da_0(self):
        codigo, err, _ = self.ejecutar(["primaria"], "visualizar_primaria", RuntimeError("bug"))
        self.assertEqual(codigo, 1)
        self.assertIn("Traceback", err)
        self.assertEqual(self.ejecutar(["primaria"], "visualizar_primaria", KeyboardInterrupt())[0], 0)


def simulador_falso(fallar_en=None, error=None):
    """Clase que hace de Simulador con `with`: apunta si se cerro y falla en la llamada n a mover()."""
    class Falso:
        creados = []

        def __init__(self):
            self.cerrado = False
            self.llamadas = 0
            Falso.creados.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.cerrado = True

        def agregar_robot(self, nombre, posicion=None):
            pass

        def mover(self, nombre, q):
            self.llamadas += 1
            if self.llamadas == fallar_en:
                raise error

        def previsualizar(self, *args):
            pass
    return Falso


class PruebasTareasConRobotFalso(unittest.TestCase):
    """Las tareas contra el robot falso de las pruebas (127.0.0.1) y un simulador falso: sin ventana ni robot real."""

    def setUp(self):
        reintento = ur.REINTENTO
        ur.REINTENTO = 0.2
        self.addCleanup(setattr, ur, "REINTENTO", reintento)
        salida = contextlib.redirect_stdout(io.StringIO())
        salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)
        self.fake = RobotFalso(ayudas.puerto_libre()).iniciar()
        self.addCleanup(self.fake.parar)

    def ensenar(self, comandos, sim, puerto=None):
        """ensenar_reproducir con una consola de mentira que teclea `comandos`."""
        def consola(cola):
            time.sleep(0.5)                                     # el usuario teclea cuando el robot ya esta enviando estados
            for c in comandos:
                cola.put(c)
        with mock.patch.object(tareas, "Simulador", sim), mock.patch.object(tareas, "_leer_consola", consola):
            tareas.ensenar_reproducir("127.0.0.1", puerto or self.fake.puerto)

    def test_ventana_cerrada_con_el_robot_en_movimiento_envia_stopj_y_cierra(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "s.json")
            with open(ruta, "w") as f:
                json.dump([[0.6, -1.57, 0.0, -1.57, 0.0, 0.0]], f)
            sim = simulador_falso(12, ErrorSimulador("ventana cerrada"))
            with self.assertRaises(ErrorSimulador):
                self.ensenar(["l " + ruta, "e"], sim)
        for _ in range(100):                                # el robot falso recibe las ordenes unos ms despues
            if any(o.startswith("stopj") for o in self.fake.ordenes):
                break
            time.sleep(0.03)
        self.assertTrue(any(o.startswith("movej") for o in self.fake.ordenes))
        self.assertTrue(any(o.startswith("stopj") for o in self.fake.ordenes))
        self.assertTrue(sim.creados[0].cerrado)

    def test_eof_en_la_consola_sale_de_forma_ordenada(self):
        sim = simulador_falso()
        with mock.patch("builtins.input", side_effect=EOFError), mock.patch.object(tareas, "Simulador", sim):
            hilo = threading.Thread(target=tareas.ensenar_reproducir, args=("127.0.0.1", self.fake.puerto), daemon=True)
            hilo.start()
            hilo.join(10)
        self.assertFalse(hilo.is_alive())
        self.assertTrue(sim.creados[0].cerrado)

    def test_q_con_el_robot_caido_sale_sin_esperar_y_cierra(self):
        sim = simulador_falso()
        t0 = time.time()
        self.ensenar(["q"], sim, puerto=ayudas.puerto_libre())          # nadie escucha en ese puerto
        self.assertLess(time.time() - t0, 5.0)
        self.assertTrue(sim.creados[0].cerrado)

    def test_ctrl_c_al_visualizar_cierra_el_simulador(self):
        sim = simulador_falso(1, KeyboardInterrupt())
        with mock.patch.object(tareas, "Simulador", sim):
            tareas.visualizar_primaria("127.0.0.1", self.fake.puerto)       # vuelve sin excepcion
        self.assertTrue(sim.creados[0].cerrado)


if __name__ == "__main__":
    unittest.main()
