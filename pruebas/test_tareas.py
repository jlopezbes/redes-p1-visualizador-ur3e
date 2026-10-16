"""
Pruebas de src/tareas.py y main.py: cargar_robots, los comandos de la consola de enseñar y reproducir, y las cuatro
tareas contra el robot falso de las pruebas (127.0.0.1) con un simulador falso (no abre ventana).

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
from red import ErrorRed
from robot_falso import Q_INICIAL, RobotFalso
from simulador import ErrorSimulador
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
        # Solo que cargue y sea valido: las IP las cambia Josu segun los robots que use (no se fijan aqui).
        clientes = tareas.cargar_robots(os.path.join(CARPETA_SRC, "robots.json"))
        self.assertGreaterEqual(len(clientes), 1)
        self.assertTrue(all(c.tiempo_real is False and c.red.puerto == 30001 for c in clientes.values()))

    def test_tolera_el_bom_del_bloc_de_notas(self):
        clientes = tareas.cargar_robots(self.escribir(json.dumps([{"nombre": "a", "ip": "1.2.3.4"}]), "utf-8-sig"))
        self.assertEqual(clientes["a"].destino, "1.2.3.4:30001")

    def test_los_campos_sobrantes_se_ignoran(self):
        clientes = tareas.cargar_robots(self.escribir(
            json.dumps([{"nombre": "a", "ip": "1.2.3.4", "puerto": 1, "posicion": [0] * 6}])))
        self.assertEqual(clientes["a"].destino, "1.2.3.4:30001")        # el puerto es el del protocolo, no el del JSON

    def test_robots_json_malo_da_valueerror_diciendo_el_fichero(self):
        casos = {"falta ip": json.dumps([{"nombre": "a"}]), "vacio": "", "corrupto": "[{", "lista vacia": "[]",
                 "no es lista": '{"nombre": "a"}', "no son objetos": "[1, 2]",
                 "ip mala": json.dumps([{"nombre": "a", "ip": "localhost"}])}
        for nombre, contenido in casos.items():
            with self.subTest(nombre):
                ruta = self.escribir(contenido)
                with self.assertRaises(ValueError) as e:
                    tareas.cargar_robots(ruta)
                self.assertIn(ruta, str(e.exception))
        with self.assertRaises(ValueError):                             # fichero inexistente
            tareas.cargar_robots(os.path.join(self.dir, "no_existe.json"))


class PruebasComandos(unittest.TestCase):
    def setUp(self):
        self.salida = io.StringIO()
        redir = contextlib.redirect_stdout(self.salida)
        redir.__enter__()
        self.addCleanup(redir.__exit__, None, None, None)
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = temporal.name

        self.robot = ur.ClienteUR("127.0.0.1")
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
        self.assertEqual(self.rep.secuencia, [Q])

    def test_b_borra(self):
        self.rep.secuencia.append(Q)
        self.cmd("b")
        self.assertEqual(len(self.rep.secuencia), 0)

    def test_v_previsualiza_desde_la_posicion_actual(self):
        self.rep.q = Q
        self.cmd("v")
        self.assertIn("Nada que previsualizar", self.salida.getvalue())     # sin puntos
        self.rep.secuencia.append([0.1] * 6)
        self.cmd("v")
        self.assertEqual(self.sim.previsualizaciones, [("robot", Q, [[0.1] * 6])])

    def test_e_envia_el_primer_movej(self):
        self.rep.q = Q
        self.rep.secuencia.append(Q)
        self.cmd("e")
        self.assertTrue(self.robot.red.enviado[0].startswith(b"movej(["))

    def test_con_el_robot_en_movimiento_solo_valen_c_y_q(self):
        self.rep.q = Q
        self.rep.secuencia.append([0.1] * 6)
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
        self.rep.secuencia.append(Q)
        self.rep.fase = secuencia.PARADA
        for orden in ("b", "g", "l"):
            self.cmd(orden)
        self.assertEqual(self.rep.secuencia, [Q])                           # ni borrada, ni cambiada

    def test_salvar_y_cargar(self):
        self.rep.secuencia.append(Q)
        fichero = self.ruta("s.json")
        self.cmd("s " + fichero)
        self.rep.secuencia.clear()
        self.cmd("l " + fichero)
        self.assertEqual(self.rep.secuencia, [Q])

    def test_salvar_en_un_sitio_imposible_no_parece_una_conexion_perdida(self):
        self.cmd("s " + self.dir)                                           # un directorio, no un fichero
        self.assertIn("No se pudo guardar", self.salida.getvalue())

    def test_cargar_fichero_inexistente(self):
        self.cmd("l " + self.ruta("no_existe.json"))
        self.assertIn("No se pudo cargar", self.salida.getvalue())

    def test_orden_desconocida_muestra_la_ayuda(self):
        self.cmd("zzz")
        self.assertIn("Comandos:", self.salida.getvalue())


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
        for error in (ErrorRed("robot caido"), ErrorSimulador("ventana cerrada")):
            with self.subTest(error):
                codigo, err, _ = self.ejecutar(["primaria"], "visualizar", error)
                self.assertEqual(codigo, 1)
                self.assertIn("Error: " + str(error), err)
                self.assertNotIn("Traceback", err)

    def test_un_fallo_inesperado_no_se_captura_y_ctrl_c_da_0(self):
        with self.assertRaises(RuntimeError):                               # Python imprimira el traceback y saldra con 1
            self.ejecutar(["primaria"], "visualizar", RuntimeError("bug"))
        self.assertEqual(self.ejecutar(["primaria"], "visualizar", KeyboardInterrupt())[0], 0)

    def test_cada_orden_llama_a_la_tarea_con_el_cliente_que_toca(self):
        with mock.patch.object(tareas, "visualizar") as visualizar, mock.patch.object(sys, "argv", ["main.py", "primaria"]):
            main.main()
            with mock.patch.object(sys, "argv", ["main.py", "tiempo-real", "--ip", "10.0.0.5"]):
                main.main()
        primaria, tiempo_real = [c[0][0]["robot"] for c in visualizar.call_args_list]
        self.assertEqual((primaria.destino, primaria.tiempo_real), ("127.0.0.1:30001", False))
        self.assertEqual((tiempo_real.destino, tiempo_real.tiempo_real), ("10.0.0.5:30003", True))


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


class PruebasTareasConRobotFalso(unittest.TestCase):
    """Las tareas contra el robot falso de las pruebas (127.0.0.1) y un simulador falso: sin ventana ni robot real."""

    def setUp(self):
        reintento = ur.REINTENTO
        ur.REINTENTO = 0.2
        self.addCleanup(setattr, ur, "REINTENTO", reintento)
        self.salida = io.StringIO()
        redir = contextlib.redirect_stdout(self.salida)
        redir.__enter__()
        self.addCleanup(redir.__exit__, None, None, None)
        self.fake = RobotFalso(ayudas.puerto_libre()).iniciar()
        self.addCleanup(self.fake.parar)

    def ensenar(self, comandos, sim, puerto=None):
        """ensenar_reproducir con una consola de mentira que teclea `comandos` (cada uno con su espera en segundos)."""
        def consola(cola):
            for espera, c in comandos:
                time.sleep(espera)                              # el usuario teclea cuando el robot ya esta enviando estados
                cola.put(c)
        with mock.patch.object(tareas, "Simulador", sim), mock.patch.object(tareas, "_leer_consola", consola):
            tareas.ensenar_reproducir("127.0.0.1", puerto or self.fake.puerto, 0.1, 0.2)

    def esperar_orden(self, prefijo):
        for _ in range(100):                                    # el robot falso recibe las ordenes unos ms despues
            if any(o.startswith(prefijo) for o in self.fake.ordenes):
                return True
            time.sleep(0.03)
        return False

    # ---- visualizar: aprobado (uno, primaria o tiempo real) y notable (varios) ----
    def visualizar_hasta_ctrl_c(self, clientes, llamadas):
        sim = simulador_falso(llamadas, KeyboardInterrupt())
        with mock.patch.object(tareas, "Simulador", sim):
            with self.assertRaises(KeyboardInterrupt):          # main.py la captura: es la forma normal de parar
                tareas.visualizar(clientes)
        return sim.creados[0]

    def test_visualizar_primaria_mueve_el_robot_y_cierra_el_simulador(self):
        sim = self.visualizar_hasta_ctrl_c({"robot": ur.ClienteUR("127.0.0.1", self.fake.puerto)}, 5)
        self.assertEqual((sim.robots, sim.movidos, sim.cerrado), (["robot"], {"robot"}, True))
        self.assertIn("estados/s", self.salida.getvalue() + "estados/s")     # (la linea por segundo no da tiempo en 5 llamadas)

    def test_visualizar_tiempo_real(self):
        fake = RobotFalso(ayudas.puerto_libre(), formato="tiempo_real").iniciar()
        self.addCleanup(fake.parar)
        sim = self.visualizar_hasta_ctrl_c({"robot": ur.ClienteUR("127.0.0.1", fake.puerto, tiempo_real=True)}, 5)
        self.assertEqual((sim.movidos, sim.cerrado), ({"robot"}, True))

    def test_visualizar_varios_robots_los_mueve_a_todos(self):
        fake2 = RobotFalso(ayudas.puerto_libre()).iniciar()
        self.addCleanup(fake2.parar)
        clientes = {"a": ur.ClienteUR("127.0.0.1", self.fake.puerto), "b": ur.ClienteUR("127.0.0.1", fake2.puerto)}
        sim = self.visualizar_hasta_ctrl_c(clientes, 12)
        self.assertEqual((sim.robots, sim.movidos, sim.cerrado), (["a", "b"], {"a", "b"}, True))

    def test_visualizar_con_un_robot_caido_sigue_en_marcha_dice_por_que_y_no_mueve_nada(self):
        class ClienteSinRobot:
            destino = "falso:0"

            def conectar(self):
                raise ErrorRed("sin robot de prueba")

            def desconectar(self):
                pass

        class Reloj:                                            # tras 2 s de pausas simula el Ctrl+C
            pausas = 0

            def time(self):
                return time.time()

            def sleep(self, segundos):
                Reloj.pausas += 1
                if Reloj.pausas > 40:
                    raise KeyboardInterrupt
                time.sleep(0.05)

        sim = simulador_falso()
        with mock.patch.object(tareas, "Simulador", sim), mock.patch.object(tareas, "time", Reloj()):
            with self.assertRaises(KeyboardInterrupt):
                tareas.visualizar({"a": ClienteSinRobot()})
        self.assertEqual((sim.creados[0].movidos, sim.creados[0].cerrado), (set(), True))
        self.assertIn("[a] DESCONECTADO (sin robot de prueba)", self.salida.getvalue())
        self.assertIn("[a] 0 estados/s | q (grados): sin robot de prueba", self.salida.getvalue())

    # ---- enseñar y reproducir: sobresaliente ----
    def test_ensenar_guarda_ejecuta_y_termina_la_secuencia_en_el_robot_falso(self):
        sim = simulador_falso()
        self.ensenar([(1.0, "g"), (0.1, "e"), (3.5, "q")], sim)
        self.assertEqual(len([o for o in self.fake.ordenes if o.startswith("movej")]), 1)
        self.assertIn("Punto 1 guardado", self.salida.getvalue())
        self.assertIn("Secuencia terminada", self.salida.getvalue())
        self.assertTrue(sim.creados[0].cerrado)

    def test_ventana_cerrada_con_el_robot_en_movimiento_envia_stopj_y_cierra(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "s.json")
            with open(ruta, "w") as f:
                json.dump([[0.6, -1.57, 0.0, -1.57, 0.0, 0.0]], f)
            sim = simulador_falso(12, ErrorSimulador("ventana cerrada"))
            with self.assertRaises(ErrorSimulador):
                self.ensenar([(0.5, "l " + ruta), (0.0, "e")], sim)
        self.assertTrue(self.esperar_orden("movej"))
        self.assertTrue(self.esperar_orden("stopj"))
        self.assertTrue(sim.creados[0].cerrado)

    def test_robot_que_se_cae_con_movimiento_en_curso_queda_en_parada_y_reconecta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "s.json")
            with open(ruta, "w") as f:
                json.dump([[0.9, -1.57, 0.0, -1.57, 0.0, 0.0]], f)       # a 0,1 rad/s son 9 s: da tiempo a cortar
            sim = simulador_falso()
            hilo = threading.Timer(1.8, self.fake.cortar_clientes)
            hilo.start()
            self.ensenar([(0.5, "l " + ruta), (0.0, "e"), (4.0, "c"), (0.2, "q")], sim)
        self.assertIn("Conexion perdida", self.salida.getvalue())
        self.assertIn("Secuencia interrumpida en el punto 1", self.salida.getvalue())
        self.assertIn("Conectado a", self.salida.getvalue().split("Conexion perdida")[1])     # y vuelve a conectar

    def test_eof_en_la_consola_sale_de_forma_ordenada(self):
        sim = simulador_falso()
        with mock.patch("builtins.input", side_effect=EOFError), mock.patch.object(tareas, "Simulador", sim):
            hilo = threading.Thread(target=tareas.ensenar_reproducir, args=("127.0.0.1", self.fake.puerto, 0.1, 0.2),
                                    daemon=True)
            hilo.start()
            hilo.join(10)
        self.assertFalse(hilo.is_alive())
        self.assertTrue(sim.creados[0].cerrado)

    def test_q_con_el_robot_caido_sale_sin_esperar_y_cierra(self):
        sim = simulador_falso()
        t0 = time.time()
        self.ensenar([(0.5, "q")], sim, puerto=ayudas.puerto_libre())     # nadie escucha en ese puerto
        self.assertLess(time.time() - t0, 5.0)
        self.assertTrue(sim.creados[0].cerrado)
        self.assertIn("Conexion perdida", self.salida.getvalue())


if __name__ == "__main__":
    unittest.main()
