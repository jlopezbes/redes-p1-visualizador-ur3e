"""
Pruebas de src/secuencia.py: la maquina de estados del Reproductor con un robot que solo graba lo que se le envia
y mensajes del robot construidos con struct (pruebas/ayudas.py) y decodificados por el ClienteUR real.
Reloj controlado: no espera segundos reales.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import contextlib
import io
import json
import math
import os
import re
import tempfile
import unittest
from unittest import mock

import ayudas
import secuencia
import ur
from red import ErrorRed

A = [0.0, -1.0, 0.0, -1.0, 0.0, 0.0]       # primer punto
B = [0.5, -1.0, 0.2, -1.0, 0.0, 0.3]        # segundo punto
LEJOS = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]

decodificar = ur.ClienteUR("127.0.0.1")._decodificar


class RedGrabadora:
    def __init__(self):
        self.enviado = []
        self.caida = False

    def enviar(self, datos):
        if self.caida:
            raise ErrorRed("conexion caida")
        self.enviado.append(datos.decode("utf-8"))


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
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

        self.robot = ur.ClienteUR("127.0.0.1")
        self.robot.red = RedGrabadora()
        self.seq = secuencia.Secuencia()
        self.rep = secuencia.Reproductor(self.robot, self.seq, velocidad=0.1, aceleracion=0.2)

    @property
    def ordenes(self):
        return self.robot.red.enviado

    def estado(self, q, ejecutando=False, protegido=False, emergencia=False, modo=7):
        self.rep.procesar(decodificar(ayudas.mensaje_estado(
            q, ejecutando=ejecutando, protegido=protegido, emergencia=emergencia, modo=modo)))

    def error_del_robot(self, texto):
        self.rep.procesar(decodificar(ayudas.mensaje_error(99, texto.encode())))

    def preparar(self, *puntos):
        self.seq.extend(puntos)
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
        self.seq.append(A)
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

    def test_ejecutar_con_el_robot_ocupado_no_envia_otro_movej(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.rep.ejecutar()
        self.assertEqual(len([o for o in self.ordenes if o.startswith("movej")]), 1)
        self.assertIn("Ya hay una secuencia", self.salida.getvalue())


class PruebasFallos(Base):
    def test_orden_no_aceptada(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.reloj.t += 2.5
        self.estado(A, ejecutando=False)                            # sigue en A y el programa nunca arranco
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("no ha llegado", self.salida.getvalue())
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
        self.error_del_robot("Colision")
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("Colision", self.salida.getvalue())
        self.assertEqual(self.ordenes[-1], "stopj(0.2)\n")

    def test_movej_rechazado_en_modo_local_para_sin_stopj_y_lo_explica(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.rep.procesar(decodificar(ayudas.mensaje_error(ur.CODIGO_SIN_REMOTO)))
        salida = self.salida.getvalue()
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertFalse(any(o.startswith("stopj") for o in self.ordenes))     # tambien se rechazaria
        self.assertTrue(self.rep.reconectar)
        self.assertIn("no se ha movido", salida)
        self.assertNotIn("Robot detenido", salida)

    def test_error_del_robot_sin_movimiento_solo_se_avisa(self):
        self.preparar(B)
        self.error_del_robot("Aviso")
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertEqual(self.ordenes, [])
        self.assertIn("Aviso", self.salida.getvalue())

    def test_punto_invalido_no_se_envia(self):
        self.preparar([0, 0, 0, 0, 0, 90.0])                        # grados por error
        self.rep.ejecutar()
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertFalse(any(o.startswith("movej") for o in self.ordenes))

    def test_velocidad_por_encima_del_limite_no_se_envia(self):
        rep = secuencia.Reproductor(self.robot, self.seq, velocidad=0.5, aceleracion=0.2)
        self.seq.append(B)
        rep.q = A
        rep.ejecutar()
        self.assertEqual(rep.fase, secuencia.PARADA)
        self.assertFalse(any(o.startswith("movej") for o in self.ordenes))

    def test_sin_conexion_al_ejecutar_falla_a_parada_y_dice_que_no_pudo_frenar(self):
        self.preparar(B)
        self.robot.red.caida = True
        self.rep.ejecutar()                                         # movej y stopj fallan con ErrorRed
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("NO SE HA PODIDO ENVIAR LA PARADA", self.salida.getvalue())


class PruebasParadasYSeguridad(Base):
    """El Reproductor no deja escapar ErrorRed, no mueve con parada de proteccion/emergencia y avisa si no puede frenar."""

    def test_si_no_sale_el_stopj_se_avisa_en_mayusculas_y_no_se_dice_detenido(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.robot.red.caida = True
        self.estado(A, ejecutando=True, protegido=True)
        salida = self.salida.getvalue()
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("NO SE HA PODIDO ENVIAR LA PARADA", salida)
        self.assertIn("PENDANT", salida)
        self.assertNotIn("Robot detenido", salida)

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

    def test_cancelar_sin_conexion_deja_libre_y_avisa(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.robot.red.caida = True
        self.rep.cancelar()
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertIsNone(self.rep.i)
        self.assertIn("NO SE HA PODIDO ENVIAR LA PARADA", self.salida.getvalue())

    def test_conexion_perdida_en_movimiento_queda_en_parada_y_avisa_si_no_puede_frenar(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.robot.red.caida = True
        self.rep.conexion_perdida()
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("NO SE HA PODIDO ENVIAR LA PARADA", self.salida.getvalue())
        self.assertIn("punto 1", self.salida.getvalue())

    def test_conexion_perdida_sin_movimiento_no_hace_nada(self):
        self.rep.conexion_perdida()
        self.assertEqual(self.rep.fase, secuencia.LIBRE)

    def test_no_ejecuta_ni_reanuda_con_proteccion_o_emergencia(self):
        self.preparar(B)
        for kwargs in ({"protegido": True}, {"emergencia": True}):
            self.estado(A, **kwargs)
            self.rep.ejecutar()
            self.assertEqual(self.rep.fase, secuencia.LIBRE, kwargs)
        self.assertEqual(self.ordenes, [])
        self.rep.fase = secuencia.PARADA
        self.rep.reanudar()                                         # sigue la emergencia
        self.assertEqual(self.ordenes, [])
        self.assertIn("emergencia", self.salida.getvalue())

    def test_la_emergencia_durante_el_movimiento_frena(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.estado(A, ejecutando=True, emergencia=True)
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertEqual(self.ordenes[-1], "stopj(0.2)\n")

    def test_el_modo_del_robot_es_solo_informativo(self):
        self.preparar(B)
        self.estado(A, modo=3)                                      # power off: no bloquea (decodificacion no verificada)
        self.rep.ejecutar()
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)
        self.assertEqual(self.rep.modo, 3)

    def test_guardar_punto(self):
        self.rep.guardar_punto()                                    # sin q todavia
        self.assertEqual(len(self.seq), 0)
        self.estado(A)
        self.rep.guardar_punto()
        self.assertEqual(self.seq, [A])
        self.estado(B)
        self.assertEqual(self.seq, [A])                             # el punto guardado es una copia


class PruebasFicherosSecuencia(unittest.TestCase):
    """Un fichero malo sale como ErrorSecuencia y no cambia la secuencia."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = temporal.name
        self.s = secuencia.Secuencia()
        self.s.append(A)

    def ruta(self, nombre="s.json"):
        return os.path.join(self.dir, nombre)

    def escribir(self, contenido, modo="w", **kwargs):
        with open(self.ruta(), modo, **kwargs) as f:
            f.write(contenido)

    def test_guardar_y_cargar(self):
        self.s.append(B)
        self.s.guardar(self.ruta())
        t = secuencia.Secuencia()
        t.cargar(self.ruta())
        self.assertEqual(t, [A, B])

    def test_ficheros_malos_dan_errorsecuencia_y_no_cambian_nada(self):
        casos = {
            "vacio": "",
            "truncado": "[[0,",
            "objeto": "{}",
            "null": "null",
            "un numero": "5",
            "texto": '[["a", "b", "c", "d", "e", "f"]]',
            "5 angulos": "[[0, 0, 0, 0, 0]]",
            "NaN": "[[NaN, 0, 0, 0, 0, 0]]",
            "infinito": "[[1e999, 0, 0, 0, 0, 0]]",
            "grados": "[[0, 0, 0, 0, 0, 90]]",
        }
        for nombre, contenido in casos.items():
            with self.subTest(nombre):
                self.escribir(contenido)
                with self.assertRaises(secuencia.ErrorSecuencia):
                    self.s.cargar(self.ruta())
                self.assertEqual(self.s, [A])

    def test_fichero_binario_directorio_o_inexistente(self):
        self.escribir(b"\xff\xfe\x00\x80", "wb")
        with self.assertRaises(secuencia.ErrorSecuencia):
            self.s.cargar(self.ruta())
        for ruta in (self.dir, self.ruta("no_existe.json")):
            with self.assertRaises(secuencia.ErrorSecuencia) as e:
                self.s.cargar(ruta)
            self.assertIn(ruta, str(e.exception))                   # dice cual fichero
        self.assertEqual(self.s, [A])

    def test_cargar_tolera_el_bom_del_bloc_de_notas_y_acepta_la_secuencia_vacia(self):
        self.escribir(json.dumps([A, B]), encoding="utf-8-sig")
        self.s.cargar(self.ruta())
        self.assertEqual(self.s, [A, B])
        self.escribir("[]")
        self.s.cargar(self.ruta())
        self.assertEqual(self.s, [])

    def test_guardar_en_un_sitio_imposible_da_errorsecuencia(self):
        with self.assertRaises(secuencia.ErrorSecuencia):
            self.s.guardar(self.dir)                                # un directorio, no un fichero


class PruebasAjustar(Base):
    """Reproductor.ajustar: cambia la velocidad (rad/s) y la aceleracion (rad/s2) de los proximos movej."""

    def test_cambia_velocidad_y_aceleracion_y_avisa(self):
        self.rep.ajustar(0.2, 0.3)
        self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.2, 0.3))
        self.assertIn("Velocidad 0.2 rad/s y aceleracion 0.3 rad/s2", self.salida.getvalue())

    def test_fuera_de_rango_no_cambia_nada_y_avisa(self):
        casos = {"velocidad bajo el minimo": (0.0005, 0.3), "velocidad sobre el maximo": (0.31, 0.3),
                 "aceleracion sobre el maximo": (0.2, 0.51), "aceleracion bajo el minimo": (0.2, 0.0005),
                 "velocidad 0": (0, 0.3), "aceleracion 0": (0.2, 0), "velocidad negativa": (-0.1, 0.3),
                 "velocidad nan": (math.nan, 0.3), "aceleracion nan": (0.2, math.nan)}
        for nombre, (velocidad, aceleracion) in casos.items():
            with self.subTest(nombre):
                antes = len(self.salida.getvalue())
                self.rep.ajustar(velocidad, aceleracion)
                self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (0.1, 0.2))
                self.assertIn("No se cambia", self.salida.getvalue()[antes:])
        self.assertNotIn("Velocidad", self.salida.getvalue())           # nunca llega a decir que lo ha cambiado

    def test_los_limites_exactos_valen(self):
        for velocidad, aceleracion in ((ur.MINIMO, ur.MINIMO), (ur.VELOCIDAD_MAX, ur.ACELERACION_MAX)):
            with self.subTest(velocidad=velocidad, aceleracion=aceleracion):
                self.rep.ajustar(velocidad, aceleracion)
                self.assertEqual((self.rep.velocidad, self.rep.aceleracion), (velocidad, aceleracion))
                self.assertNotIn("No se cambia", self.salida.getvalue())

    def test_el_siguiente_movej_lleva_los_valores_nuevos(self):
        self.preparar(B)
        self.rep.ajustar(0.2, 0.3)
        self.rep.ejecutar()
        self.assertEqual(len(self.ordenes), 1)
        self.assertTrue(self.ordenes[0].endswith("a=0.3, v=0.2)\n"), self.ordenes[0])

    def test_un_ajuste_rechazado_deja_los_valores_anteriores_en_el_movej(self):
        self.preparar(B)
        self.rep.ajustar(0.31, 0.3)
        self.rep.ejecutar()
        self.assertTrue(self.ordenes[0].endswith("a=0.2, v=0.1)\n"), self.ordenes[0])

    def test_un_movej_ya_enviado_no_cambia(self):
        self.preparar(B, A)
        self.rep.ejecutar()
        self.rep.ajustar(0.2, 0.3)
        self.assertTrue(self.ordenes[0].endswith("a=0.2, v=0.1)\n"), self.ordenes[0])
        self.assertEqual(len(self.ordenes), 1)


if __name__ == "__main__":
    unittest.main()
