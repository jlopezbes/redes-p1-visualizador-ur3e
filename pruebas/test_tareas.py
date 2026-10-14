"""
Pruebas de src/tareas.py: cargar_robots y los comandos de la consola de enseñar y reproducir,
con un simulador falso (no abre ventana) y un robot que solo graba lo que se le envia.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import contextlib
import io
import json
import os
import tempfile
import unittest

import ayudas
import secuencia
import tareas
import ur
from test_ur import RedGrabadora

Q = [0.0, -1.0, 0.0, -1.0, 0.0, 0.0]
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
        robots = tareas.cargar_robots(os.path.join(CARPETA_SRC, "robots.json"))
        self.assertEqual([r["nombre"] for r in robots], ["robot1", "robot2"])
        self.assertEqual([r["puerto"] for r in robots], [30001, 30011])

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


if __name__ == "__main__":
    unittest.main()
