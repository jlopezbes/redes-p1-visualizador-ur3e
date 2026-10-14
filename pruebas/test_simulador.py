"""
Pruebas de src/simulador.py con un visualizador falso (no abre ninguna ventana).
La prueba con la libreria real esta en pruebas/humo_pybullet.py.

    python -B -m unittest discover -s practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import unittest

import ayudas  # noqa: F401  (pone src/ en sys.path)
from simulador import Simulador


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

    def test_los_demas_se_crean_con_su_posicion_y_se_mueven_por_su_id(self):
        self.sim.agregar_robot("robot1")
        self.sim.agregar_robot("robot2", [1.0, 0, 0, 0, 0, 0])
        self.sim.agregar_robot("robot3", [2.0, 0, 0, 0, 0, 0])
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

    def test_robot_desconocido(self):
        with self.assertRaises(KeyError):
            self.sim.mover("nadie", [0.0] * 6)

    def test_previsualizar_recorre_todos_los_tramos_y_acaba_en_cada_punto(self):
        self.sim.agregar_robot("robot1")
        desde, p1, p2 = [0.0] * 6, [1.0] * 6, [1.0, 1.0, 1.0, 1.0, 1.0, 3.0]
        self.sim.previsualizar("robot1", desde, [p1, p2], pasos=4, duracion_tramo=0.0)
        recibidos = [q[:6] for _, q in self.visualizador.movimientos]
        self.assertEqual(len(recibidos), 8)                     # 4 pasos por tramo, 2 tramos
        self.assertEqual(recibidos[0], [0.25] * 6)              # primer paso del primer tramo
        self.assertEqual(recibidos[3], p1)                      # termina el tramo 1 exactamente en p1
        self.assertEqual(recibidos[7], p2)

    def test_previsualizar_sin_puntos_no_hace_nada(self):
        self.sim.agregar_robot("robot1")
        self.sim.previsualizar("robot1", [0.0] * 6, [])
        self.assertEqual(self.visualizador.movimientos, [])


if __name__ == "__main__":
    unittest.main()
