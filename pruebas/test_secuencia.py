"""
Pruebas de src/secuencia.py: la maquina de estados del Reproductor con un robot que solo graba lo que se le envia
y mensajes del robot construidos con struct (pruebas/ayudas.py). Reloj controlado: no espera segundos reales.

    python -B -m unittest discover -s practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import contextlib
import io
import os
import struct
import tempfile
import unittest
from unittest import mock

import ayudas
import secuencia
import ur

A = [0.0, -1.0, 0.0, -1.0, 0.0, 0.0]       # primer punto
B = [0.5, -1.0, 0.2, -1.0, 0.0, 0.3]        # segundo punto
LEJOS = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]


class RedGrabadora:
    def __init__(self):
        self.enviado = []
        self.caida = False

    def enviar(self, datos):
        if self.caida:
            raise ConnectionError("conexion caida")
        self.enviado.append(datos.decode("utf-8"))


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.reloj = Reloj()
        parche = mock.patch.object(secuencia, "time", self.reloj)
        parche.start()
        self.addCleanup(parche.stop)
        self.salida = io.StringIO()
        redir = contextlib.redirect_stdout(self.salida)
        redir.__enter__()
        self.addCleanup(redir.__exit__, None, None, None)

        self.robot = ur.UrPrimaria("127.0.0.1")
        self.robot.red = RedGrabadora()
        self.seq = secuencia.Secuencia()
        self.rep = secuencia.Reproductor(self.robot, self.seq, velocidad=0.1, aceleracion=0.2)

    @property
    def ordenes(self):
        return self.robot.red.enviado

    def estado(self, q, ejecutando=False, protegido=False):
        self.rep.procesar(16, ayudas.mensaje_estado(q, ejecutando=ejecutando, protegido=protegido))

    def preparar(self, *puntos):
        for p in puntos:
            self.seq.agregar(p)
        self.estado(A)                      # el robot esta en A


class PruebasEjecucion(Base):
    def test_camino_feliz_con_dos_puntos(self):
        self.preparar(A, B)
        self.rep.ejecutar()
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)
        self.assertEqual(len(self.ordenes), 1)
        self.assertTrue(self.ordenes[0].startswith("movej([0.00000, -1.00000"))
        self.assertIn("a=0.2, v=0.1)", self.ordenes[0])

        self.estado(A, ejecutando=True)
        self.assertEqual(self.rep.fase, secuencia.MOVIENDO)
        self.assertEqual(len(self.ordenes), 1)                      # no envia el siguiente hasta que termine

        self.estado(A, ejecutando=False)                            # el programa termino y el robot esta en A (punto 1)
        self.assertEqual(len(self.ordenes), 2)                      # punto 1 alcanzado: se envia el 2
        self.assertTrue(self.ordenes[1].startswith("movej([0.50000"))

        self.estado(B, ejecutando=True)
        self.estado(B, ejecutando=False)
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertIsNone(self.rep.i)
        self.assertIn("Secuencia terminada", self.salida.getvalue())
        self.assertFalse(any(o.startswith("stopj") for o in self.ordenes))

    def test_no_ejecuta_sin_puntos_sin_q_o_en_parada(self):
        self.rep.ejecutar()                                         # sin puntos y sin q
        self.seq.agregar(A)
        self.rep.ejecutar()                                         # con punto pero sin q
        self.assertEqual(self.ordenes, [])
        self.estado(A)
        self.rep.fase = secuencia.PARADA
        self.rep.ejecutar()                                         # parada pendiente
        self.assertEqual(self.ordenes, [])

    def test_ya_estaba_en_el_punto(self):
        self.preparar(A)
        self.rep.ejecutar()
        self.reloj.t += 2.5                                         # el programa no se vio en marcha...
        self.estado(A, ejecutando=False)                            # ...pero el robot ya esta en A
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertIn("Secuencia terminada", self.salida.getvalue())

    def test_dentro_de_la_espera_de_arranque_no_se_falla(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.reloj.t += 1.0
        self.estado(A, ejecutando=False)
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)


class PruebasFallos(Base):
    def test_orden_no_aceptada(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.reloj.t += 2.5
        self.estado(A, ejecutando=False)                            # sigue en A y el programa nunca arranco
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("no ha aceptado", self.salida.getvalue())
        self.assertTrue(self.ordenes[-1].startswith("stopj"))

    def test_programa_termina_sin_llegar(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.estado(A, ejecutando=True)
        self.estado(LEJOS, ejecutando=False)
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("no ha llegado", self.salida.getvalue())

    def test_parada_de_proteccion_y_reanudar(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.estado(A, ejecutando=True)
        self.estado(A, ejecutando=True, protegido=True)
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertEqual(self.ordenes[-1], "stopj(0.2)\n")

        self.rep.reanudar()                                         # sigue protegido: no reenvia
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("sigue en parada de proteccion", self.salida.getvalue())
        antes = len(self.ordenes)

        self.estado(A, protegido=False)                             # se libera la proteccion
        self.rep.reanudar()
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)
        self.assertEqual(len(self.ordenes), antes + 1)
        self.assertTrue(self.ordenes[-1].startswith("movej([0.50000"))     # reenvia el MISMO punto (el 1 = B)
        self.assertEqual(self.rep.i, 0)

    def test_error_del_robot_durante_el_movimiento(self):
        self.preparar(B)
        self.rep.ejecutar()
        cuerpo = struct.pack(">5i", 99, 0, 2, 0, 0) + b"Colision"
        self.rep.procesar(20, ayudas.mensaje_robot(6, cuerpo))
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("Colision", self.salida.getvalue())
        self.assertEqual(self.ordenes[-1], "stopj(0.2)\n")

    def test_error_del_robot_sin_movimiento_solo_se_avisa(self):
        self.preparar(B)
        cuerpo = struct.pack(">5i", 99, 0, 2, 0, 0) + b"Aviso"
        self.rep.procesar(20, ayudas.mensaje_robot(6, cuerpo))
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertEqual(self.ordenes, [])
        self.assertIn("Aviso", self.salida.getvalue())

    def test_mensaje_de_version_se_ignora(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.rep.procesar(20, ayudas.mensaje_robot(3, b"1.2.3"))
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)

    def test_punto_invalido_no_se_envia(self):
        self.preparar([0, 0, 0, 0, 0, 90.0])                        # grados por error
        self.rep.ejecutar()
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertFalse(any(o.startswith("movej") for o in self.ordenes))

    def test_velocidad_por_encima_del_limite_no_se_envia(self):
        rep = secuencia.Reproductor(self.robot, self.seq, velocidad=0.5, aceleracion=0.2)
        self.seq.agregar(B)
        rep.q = A
        rep.ejecutar()
        self.assertEqual(rep.fase, secuencia.PARADA)
        self.assertFalse(any(o.startswith("movej") for o in self.ordenes))

    def test_fallar_con_la_conexion_caida_no_revienta(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.robot.red.caida = True                                 # stopj fallara con OSError
        self.estado(A, ejecutando=True, protegido=True)
        self.assertEqual(self.rep.fase, secuencia.PARADA)


class PruebasCancelarYConexion(Base):
    def test_cancelar_en_movimiento_frena(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.rep.cancelar()
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertIsNone(self.rep.i)
        self.assertEqual(self.ordenes[-1], "stopj(0.2)\n")

    def test_cancelar_sin_movimiento_no_envia_nada(self):
        self.preparar(B)
        self.rep.cancelar()
        self.assertEqual(self.ordenes, [])

    def test_conexion_perdida_en_movimiento_queda_en_parada(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.rep.conexion_perdida()
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("punto 1", self.salida.getvalue())

    def test_conexion_perdida_sin_movimiento_no_hace_nada(self):
        self.rep.conexion_perdida()
        self.assertEqual(self.rep.fase, secuencia.LIBRE)

    def test_guardar_punto(self):
        self.rep.guardar_punto()                                    # sin q todavia
        self.assertEqual(len(self.seq), 0)
        self.estado(A)
        self.rep.guardar_punto()
        self.assertEqual(self.seq.puntos, [A])
        self.estado(B)
        self.assertEqual(self.seq.puntos, [A])                      # el punto guardado es una copia


class PruebasSecuencia(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = temporal.name

    def ruta(self, nombre="s.json"):
        return os.path.join(self.dir, nombre)

    def test_guardar_y_cargar(self):
        s = secuencia.Secuencia()
        s.agregar(A)
        s.agregar(B)
        s.guardar(self.ruta())
        t = secuencia.Secuencia()
        t.cargar(self.ruta())
        self.assertEqual(t.puntos, [A, B])

    def test_cargar_rechaza_angulos_en_grados_y_no_cambia_nada(self):
        with open(self.ruta(), "w") as f:
            f.write("[[0, 0, 0, 0, 0, 90]]")
        s = secuencia.Secuencia()
        s.agregar(A)
        with self.assertRaises(ValueError):
            s.cargar(self.ruta())
        self.assertEqual(s.puntos, [A])

    def test_cargar_fichero_inexistente_o_roto(self):
        s = secuencia.Secuencia()
        with self.assertRaises(OSError):
            s.cargar(self.ruta("no_existe.json"))
        with open(self.ruta("roto.json"), "w") as f:
            f.write("[[0,")
        with self.assertRaises(ValueError):                         # json.JSONDecodeError es un ValueError
            s.cargar(self.ruta("roto.json"))
        with open(self.ruta("numero.json"), "w") as f:
            f.write("5")
        with self.assertRaises(TypeError):
            s.cargar(self.ruta("numero.json"))

    def test_borrar(self):
        s = secuencia.Secuencia()
        s.agregar(A)
        s.borrar()
        self.assertEqual(len(s), 0)


if __name__ == "__main__":
    unittest.main()
