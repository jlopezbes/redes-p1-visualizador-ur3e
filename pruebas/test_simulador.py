"""
Pruebas de src/simulador.py con un visualizador falso (no abre ninguna ventana).
La prueba con la libreria real esta en pruebas/humo_pybullet.py.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import sys
import unittest
from unittest import mock

import ayudas  # noqa: F401  (pone src/ en sys.path)
import simulador
from simulador import ErrorSimulador, Simulador


class VisualizadorFalso:
    """Imita a UR3eRG2, incluido el defecto de alargar en sitio la lista que recibe move_robot."""

    def __init__(self):
        self.movimientos = []       # (id, lista tal como quedo)
        self.creados = []
        self._siguiente_id = 5      # ids no consecutivos, como en la libreria real

    def spawn_robot(self, pose):
        self.creados.append(list(pose))
        self._siguiente_id += 3
        return self._siguiente_id

    def move_robot(self, robot_id, joint_values):
        joint_values += [0.0] * 6   # como BulletGym.move_joints: joint_values += estado_actual[len:]
        self.movimientos.append((robot_id, joint_values))


class PruebasSimulador(unittest.TestCase):
    def setUp(self):
        self.visualizador = VisualizadorFalso()
        self.sim = Simulador(self.visualizador)

    def test_el_primer_robot_es_el_id_0_y_no_se_crea(self):
        self.sim.agregar_robot("robot1")
        self.sim.mover("robot1", [0.1] * 6)
        self.assertEqual(self.visualizador.creados, [])
        self.assertEqual(self.visualizador.movimientos[0][0], 0)

    def test_los_demas_se_crean_en_fila_a_1_m_y_se_mueven_por_su_id(self):
        self.sim.agregar_robot("robot1")
        self.sim.agregar_robot("robot2")
        self.sim.agregar_robot("robot3")
        self.assertEqual(self.visualizador.creados, [[1.0, 0, 0, 0, 0, 0], [2.0, 0, 0, 0, 0, 0]])
        self.sim.mover("robot2", [0.2] * 6)
        self.sim.mover("robot3", [0.3] * 6)
        ids = [i for i, _ in self.visualizador.movimientos]
        self.assertEqual(ids, [8, 11])      # los ids que devolvio spawn_robot, no 1 y 2

    def test_mover_no_cambia_la_lista_del_que_llama(self):
        self.sim.agregar_robot("robot1")
        q = [0.1] * 6
        self.sim.mover("robot1", q)
        self.assertEqual(q, [0.1] * 6)      # la libreria la habia alargado a 12: se le paso una copia

    def test_nombre_repetido(self):
        self.sim.agregar_robot("robot1")
        with self.assertRaises(ValueError):
            self.sim.agregar_robot("robot1")

    def test_previsualizar_recorre_todos_los_tramos_y_acaba_en_cada_punto(self):
        self.sim.agregar_robot("robot1")
        desde, p1, p2 = [0.0] * 6, [1.0] * 6, [1.0, 1.0, 1.0, 1.0, 1.0, 3.0]
        with mock.patch.object(simulador, "PASOS_TRAMO", 4), mock.patch.object(simulador, "time"):
            self.sim.previsualizar("robot1", desde, [p1, p2])
        recibidos = [q[:6] for _, q in self.visualizador.movimientos]
        self.assertEqual(len(recibidos), 8)                     # 4 pasos por tramo, 2 tramos
        self.assertEqual(recibidos[0], [0.25] * 6)              # primer paso del primer tramo
        self.assertEqual(recibidos[3], p1)                      # termina el tramo 1 exactamente en p1
        self.assertEqual(recibidos[7], p2)

    def test_la_vista_previa_tiene_tope_de_duracion(self):
        self.sim.agregar_robot("robot1")
        esperas = []
        falso = mock.Mock()
        falso.sleep = esperas.append
        with mock.patch.object(simulador, "PASOS_TRAMO", 2), mock.patch.object(simulador, "time", falso):
            self.sim.previsualizar("robot1", [0.0] * 6, [[0.1] * 6] * 100)
        self.assertLessEqual(sum(esperas), simulador.MAX_PREVIEW + 1e-6)         # sin tope serian 100 s


class VisualizadorQueFalla(VisualizadorFalso):
    """Imita una ventana de PyBullet cerrada por el usuario."""

    def move_robot(self, robot_id, joint_values):
        raise RuntimeError("Not connected to physics server.")

    def spawn_robot(self, pose):
        raise RuntimeError("Not connected to physics server.")


class PruebasErroresSimulador(unittest.TestCase):
    def test_un_fallo_de_la_libreria_sale_como_errorsimulador(self):
        sim = Simulador(VisualizadorQueFalla())
        sim.agregar_robot("robot1")
        with self.assertRaises(ErrorSimulador):
            sim.mover("robot1", [0.1] * 6)
        with self.assertRaises(ErrorSimulador):
            sim.agregar_robot("robot2")                 # spawn_robot falla

    def test_sin_la_libreria_ur3e_rg2_sale_errorsimulador(self):
        bloqueo = {"UR3e_rg2": None, "UR3e_rg2.dynamic_ur3e": None}     # None en sys.modules: el import falla
        with mock.patch.dict(sys.modules, bloqueo):
            with self.assertRaises(ErrorSimulador) as e:
                Simulador()
        self.assertIn("UR3e_rg2", str(e.exception))

    def test_cerrar_con_visualizador_ajeno_no_hace_nada_y_se_puede_repetir(self):
        sim = Simulador(VisualizadorFalso())
        sim.agregar_robot("robot1")
        sim.cerrar()
        sim.cerrar()


if __name__ == "__main__":
    unittest.main()
