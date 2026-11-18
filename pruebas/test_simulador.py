"""
Pruebas de src/simulador.py con un visualizador falso (no abre ninguna ventana).
La prueba con la libreria real esta en pruebas/humo_pybullet.py.

    python -B -m unittest discover -s pruebas -v
"""
import contextlib
import io
import sys
import time
import unittest
from unittest import mock

import ayudas
import simulador
import ur
from red import ErrorRed
from robot_falso import RobotFalso
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

        def cerrar(self):
            self.cerrado = True
    return Falso


class RelojConCtrlC:
    """Hace de `time` en simulador: espera de verdad (para que los hilos lectores trabajen) y, tras `pausas` pausas,
    simula el Ctrl+C del usuario."""

    def __init__(self, pausas):
        self.pausas = pausas
        self.llamadas = 0

    def time(self):
        return time.time()

    def sleep(self, segundos):
        self.llamadas += 1
        if self.llamadas > self.pausas:
            raise KeyboardInterrupt
        time.sleep(0.05)


class ClienteSinRobot:
    """Un ClienteUR cuyo robot no esta: conectar() siempre falla."""
    destino = "falso:0"

    def conectar(self):
        raise ErrorRed("sin robot de prueba")

    def desconectar(self):
        pass


class PruebasVisualizar(unittest.TestCase):
    """simulador.visualizar contra el robot falso de las pruebas (127.0.0.x) y un simulador falso: sin ventana."""

    def setUp(self):
        reintento = ur.REINTENTO
        ur.REINTENTO = 0.2
        self.addCleanup(setattr, ur, "REINTENTO", reintento)
        self.salida = io.StringIO()
        redir = contextlib.redirect_stdout(self.salida)
        redir.__enter__()
        self.addCleanup(redir.__exit__, None, None, None)

    def robot_falso(self, ip="127.0.0.1", formato="primaria"):
        robot = RobotFalso(ayudas.puerto_libre(), formato=formato, ip=ip).iniciar()
        self.addCleanup(robot.parar)
        return robot

    def visualizar(self, clientes, pausas=15, sim=None, excepcion=KeyboardInterrupt):
        """Ejecuta visualizar hasta que `pausas` pausas despues salte el Ctrl+C simulado (o `sim` falle).
        Devuelve (simulador falso, hilos lectores creados)."""
        sim = sim or simulador_falso()
        lectores = []

        class LectorRegistrado(ur.HiloLectorUR):
            def __init__(self, *args):
                super().__init__(*args)
                lectores.append(self)

        with mock.patch.object(simulador, "Simulador", sim), mock.patch.object(simulador, "time", RelojConCtrlC(pausas)), \
                mock.patch.object(ur, "HiloLectorUR", LectorRegistrado):
            with self.assertRaises(excepcion):
                simulador.visualizar(clientes)
        return sim.creados[0], lectores

    def comprobar_hilos_parados(self, lectores):
        for lector in lectores:
            with self.subTest(lector.nombre):
                self.assertFalse(lector.is_alive())

    def test_primaria_mueve_el_robot_y_cierra_el_simulador(self):
        fake = self.robot_falso()
        sim, lectores = self.visualizar({"robot": ur.ClienteUR("127.0.0.1", fake.puerto)})
        self.assertEqual((sim.robots, sim.movidos, sim.cerrado), (["robot"], {"robot"}, True))
        self.assertEqual(len(lectores), 1)
        self.comprobar_hilos_parados(lectores)

    def test_tiempo_real(self):
        fake = self.robot_falso(formato="tiempo_real")
        sim, lectores = self.visualizar({"robot": ur.ClienteUR("127.0.0.1", fake.puerto, tiempo_real=True)})
        self.assertEqual((sim.movidos, sim.cerrado), ({"robot"}, True))
        self.comprobar_hilos_parados(lectores)

    def test_usa_los_puertos_por_defecto_de_la_primaria_y_del_tiempo_real(self):
        for formato, atributo, tiempo_real in (("primaria", "PUERTO_PRIMARIA", False),
                                               ("tiempo_real", "PUERTO_TIEMPO_REAL", True)):
            with self.subTest(formato):
                fake = self.robot_falso(formato=formato)
                with mock.patch.object(ur, atributo, fake.puerto):
                    cliente = ur.ClienteUR("127.0.0.1", tiempo_real=tiempo_real)
                sim, lectores = self.visualizar({"robot": cliente})
                self.assertEqual(sim.movidos, {"robot"})
                self.comprobar_hilos_parados(lectores)

    def test_varios_robots_los_mueve_a_todos(self):
        fake1, fake2 = self.robot_falso("127.0.0.1"), self.robot_falso("127.0.0.2")
        clientes = {"a": ur.ClienteUR(fake1.ip, fake1.puerto), "b": ur.ClienteUR(fake2.ip, fake2.puerto)}
        sim, lectores = self.visualizar(clientes)
        self.assertEqual((sim.robots, sim.movidos, sim.cerrado), (["a", "b"], {"a", "b"}, True))
        self.assertEqual([l.nombre for l in lectores], ["a", "b"])
        self.comprobar_hilos_parados(lectores)
        self.assertIn("[a] recibiendo estados de 127.0.0.1:{}".format(fake1.puerto), self.salida.getvalue())
        self.assertIn("[b] recibiendo estados de 127.0.0.2:{}".format(fake2.puerto), self.salida.getvalue())

    def test_con_un_robot_caido_el_otro_sigue_en_marcha(self):
        fake = self.robot_falso("127.0.0.2")
        clientes = {"vivo": ur.ClienteUR(fake.ip, fake.puerto), "caido": ur.ClienteUR("127.0.0.1", ayudas.puerto_libre())}
        sim, lectores = self.visualizar(clientes, pausas=80)        # 4 s: en Windows rechazar un puerto cerrado tarda 1-2 s
        self.assertEqual((sim.robots, sim.movidos, sim.cerrado), (["vivo", "caido"], {"vivo"}, True))
        self.assertIn("[caido] DESCONECTADO", self.salida.getvalue())
        self.comprobar_hilos_parados(lectores)

    def test_un_robot_desconectado_no_se_mueve_y_se_dice_por_que(self):
        sim, lectores = self.visualizar({"a": ClienteSinRobot()}, pausas=30)
        self.assertEqual((sim.movidos, sim.cerrado), (set(), True))
        self.assertIn("[a] DESCONECTADO (sin robot de prueba)", self.salida.getvalue())
        self.assertIn("[a] 0 estados/s | q (grados): sin robot de prueba", self.salida.getvalue())
        self.comprobar_hilos_parados(lectores)

    def test_escribe_los_estados_por_segundo_y_el_q_en_grados(self):
        fake = self.robot_falso()
        self.visualizar({"robot": ur.ClienteUR("127.0.0.1", fake.puerto)}, pausas=30)
        linea = [l for l in self.salida.getvalue().splitlines() if l.startswith("[robot] ") and "estados/s" in l][0]
        self.assertIn("q (grados): [0.0, -90.0, 0.0, -90.0, 0.0, 0.0]", linea)        # Q_INICIAL = -1,57 rad = -89,95 grados

    def test_si_el_simulador_falla_al_mover_detiene_los_hilos_y_lo_cierra(self):
        fake = self.robot_falso()
        sim = simulador_falso(fallar_en=3, error=ErrorSimulador("ventana cerrada"))
        sim, lectores = self.visualizar({"robot": ur.ClienteUR("127.0.0.1", fake.puerto)}, sim=sim, excepcion=ErrorSimulador)
        self.assertTrue(sim.cerrado)
        self.comprobar_hilos_parados(lectores)

    def test_si_falla_al_anadir_un_robot_tambien_detiene_los_hilos_y_cierra(self):
        class SimuladorSinSitio(simulador_falso()):
            def agregar_robot(self, nombre):
                raise ErrorSimulador("no se puede crear el robot")

        fake = self.robot_falso()
        sim, lectores = self.visualizar({"robot": ur.ClienteUR("127.0.0.1", fake.puerto)}, sim=SimuladorSinSitio,
                                        excepcion=ErrorSimulador)
        self.assertTrue(sim.cerrado)
        self.comprobar_hilos_parados(lectores)


if __name__ == "__main__":
    unittest.main()
