"""
Pruebas de src/secuencia.py: la maquina de estados del Reproductor con un robot que solo graba lo que se le envia
y mensajes del robot construidos con struct (pruebas/ayudas.py). Reloj controlado: no espera segundos reales.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -v
"""
import contextlib
import io
import json
import os
import struct
import tempfile
import time
import unittest
from unittest import mock

import ayudas
import secuencia
import ur
from red import ErrorRed

A = [0.0, -1.0, 0.0, -1.0, 0.0, 0.0]       # primer punto
B = [0.5, -1.0, 0.2, -1.0, 0.0, 0.3]        # segundo punto
LEJOS = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]


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

        self.robot = ur.UrPrimaria("127.0.0.1")
        self.robot.red = RedGrabadora()
        self.robot.marcar_estado()          # movej exige un estado fresco
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
        self.robot.red.caida = True                                 # stopj fallara con ErrorRed
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
        with self.assertRaises(secuencia.ErrorSecuencia):
            s.cargar(self.ruta())
        self.assertEqual(s.puntos, [A])

    def test_cargar_fichero_inexistente_o_roto(self):
        s = secuencia.Secuencia()
        with self.assertRaises(secuencia.ErrorSecuencia):
            s.cargar(self.ruta("no_existe.json"))
        with open(self.ruta("roto.json"), "w") as f:
            f.write("[[0,")
        with self.assertRaises(secuencia.ErrorSecuencia):
            s.cargar(self.ruta("roto.json"))
        with open(self.ruta("numero.json"), "w") as f:
            f.write("5")
        with self.assertRaises(secuencia.ErrorSecuencia):
            s.cargar(self.ruta("numero.json"))

    def test_borrar(self):
        s = secuencia.Secuencia()
        s.agregar(A)
        s.borrar()
        self.assertEqual(len(s), 0)


class PruebasReproductorRobusto(Base):
    """C3: el Reproductor no deja escapar ErrorUR, no mueve con datos dudosos y avisa si no puede frenar."""

    def setUp(self):
        super().setUp()
        self.addCleanup(setattr, ur, "PLAZO_ESTADO", ur.PLAZO_ESTADO)

    def estado_viejo(self):
        """El ultimo estado del robot pasa a ser viejo, sin esperar los 2 s reales."""
        ur.PLAZO_ESTADO = 0.05
        time.sleep(0.1)

    def estado_con(self, q, **kwargs):
        self.rep.procesar(16, ayudas.mensaje_estado(q, **kwargs))

    # ---- A3.1: si no sale el stopj, se dice ----
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

    def test_cancelar_sin_conexion_deja_libre_y_avisa(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.robot.red.caida = True
        self.rep.cancelar()                                         # antes: ErrorUR y la fase se quedaba en moviendo
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertIsNone(self.rep.i)
        self.assertIn("NO SE HA PODIDO ENVIAR LA PARADA", self.salida.getvalue())

    def test_conexion_perdida_avisa_de_que_el_robot_puede_seguir_moviendose(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.robot.red.caida = True
        self.rep.conexion_perdida()
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("NO SE HA PODIDO ENVIAR LA PARADA", self.salida.getvalue())
        self.assertNotIn("detenida", self.salida.getvalue())

    # ---- A3.2: parada de proteccion y de emergencia ----
    def test_no_ejecuta_ni_reanuda_con_proteccion_o_emergencia(self):
        self.preparar(B)
        for kwargs in ({"protegido": True}, {"emergencia": True}):
            self.estado_con(A, **kwargs)
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
        self.estado_con(A, ejecutando=True, emergencia=True)
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertEqual(self.ordenes[-1], "stopj(0.2)\n")

    def test_el_modo_del_robot_es_solo_informativo(self):
        self.preparar(B)
        self.estado_con(A, modo=3)                                  # power off: no bloquea (decodificacion no verificada)
        self.rep.ejecutar()
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)
        self.assertEqual(self.rep.modo, 3)

    # ---- A3.3: tras una vista previa larga no se envia movej con datos viejos ----
    def test_ejecutar_con_estado_viejo_espera_a_un_estado_reciente(self):
        self.preparar(B)
        self.estado_viejo()                                         # como tras una vista previa de varios segundos
        self.rep.ejecutar()
        self.assertEqual(self.rep.fase, secuencia.ESPERANDO_ESTADO)
        self.assertEqual(self.ordenes, [])                          # no se envia nada ni se falla
        self.robot.marcar_estado()                                  # llega un estado nuevo (lo marca mensajes())
        self.estado(A)
        self.assertEqual(self.rep.fase, secuencia.ENVIADO)
        self.assertTrue(self.ordenes[0].startswith("movej("))

    def test_la_espera_de_estado_tiene_tope(self):
        self.preparar(B)
        self.estado_viejo()
        self.rep.ejecutar()
        self.reloj.t += secuencia.ESPERA_ESTADO + 0.5
        self.estado(A)                                              # llegan mensajes, pero el estado sigue sin ser reciente
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertIn("no envia un estado reciente", self.salida.getvalue())

    def test_cancelar_o_perder_la_conexion_mientras_se_espera_no_envia_stopj_ni_asusta(self):
        self.preparar(B)
        self.estado_viejo()
        self.rep.ejecutar()
        self.robot.red.caida = True
        self.rep.conexion_perdida()
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertNotIn("NO SE HA PODIDO", self.salida.getvalue())

    # ---- A3.4: mensajes mal formados ----
    def test_mensaje_de_estado_mal_formado_en_movimiento_frena_sin_excepcion(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.rep.procesar(16, struct.pack(">iB", 6, 16) + b"\x00")      # subpaquete cortado
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertEqual(self.ordenes[-1], "stopj(0.2)\n")
        self.assertIn("mensaje del robot no valido", self.salida.getvalue())

    def test_mensaje_de_error_cortado_sin_movimiento_solo_avisa(self):
        self.rep.procesar(20, ayudas.mensaje_robot(6, b"\x00"))
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertIn("Aviso", self.salida.getvalue())

    # ---- A3.5: reanudar tras cambiar la secuencia ----
    def test_reanudar_tras_borrar_la_secuencia_no_revienta(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.estado(A, ejecutando=True, protegido=True)             # PARADA en el punto 1
        self.seq.borrar()
        self.estado(A, protegido=False)
        self.rep.reanudar()                                         # antes: IndexError
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.assertIn("ha cambiado", self.salida.getvalue())

    # ---- A3.9 y A3.13 ----
    def test_guardar_punto_exige_estado_fresco(self):
        self.estado(A)
        self.estado_viejo()
        self.rep.guardar_punto()
        self.assertEqual(len(self.seq), 0)
        self.assertIn("Sin datos actuales", self.salida.getvalue())

    def test_con_estado_viejo_no_se_da_un_punto_por_alcanzado(self):
        self.preparar(A)
        self.rep.ejecutar()
        self.reloj.t += 2.5                                         # el programa no se vio en marcha
        self.estado_viejo()
        self.estado(A, ejecutando=False)                            # el q coincide, pero es un dato viejo
        self.assertEqual(self.rep.fase, secuencia.PARADA)
        self.assertNotIn("Secuencia terminada", self.salida.getvalue())

    def test_ejecutar_con_el_robot_ocupado_no_envia_otro_movej(self):
        self.preparar(B)
        self.rep.ejecutar()
        self.rep.ejecutar()
        self.assertEqual(len([o for o in self.ordenes if o.startswith("movej")]), 1)
        self.assertIn("Ya hay una secuencia", self.salida.getvalue())


class PruebasFicherosSecuencia(unittest.TestCase):
    """C3: un fichero malo sale como ErrorSecuencia y no cambia la secuencia; guardar es atomico."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = temporal.name
        self.s = secuencia.Secuencia()
        self.s.agregar(A)

    def ruta(self, nombre="s.json"):
        return os.path.join(self.dir, nombre)

    def escribir(self, contenido, modo="w", **kwargs):
        with open(self.ruta(), modo, **kwargs) as f:
            f.write(contenido)

    def test_ficheros_malos_dan_errorsecuencia_y_no_cambian_nada(self):
        casos = {
            "vacio": "",
            "truncado": "[[0,",
            "objeto": "{}",
            "null": "null",
            "un numero": "5",
            "booleanos": "[[true, true, true, true, true, true]]",
            "texto": '[["a", "b", "c", "d", "e", "f"]]',
            "5 angulos": "[[0, 0, 0, 0, 0]]",
            "NaN": "[[NaN, 0, 0, 0, 0, 0]]",
            "infinito": "[[1e999, 0, 0, 0, 0, 0]]",
            "grados": "[[0, 0, 0, 0, 0, 90]]",
            "anidado enorme": "[" * 5000 + "]" * 5000,
            "demasiados puntos": json.dumps([A] * (secuencia.MAX_PUNTOS + 1)),
        }
        for nombre, contenido in casos.items():
            with self.subTest(nombre):
                self.escribir(contenido)
                with self.assertRaises(secuencia.ErrorSecuencia):
                    self.s.cargar(self.ruta())
                self.assertEqual(self.s.puntos, [A])

    def test_fichero_binario_o_demasiado_grande_o_directorio_o_inexistente(self):
        self.escribir(b"\xff\xfe\x00\x80", "wb")
        with self.assertRaises(secuencia.ErrorSecuencia):
            self.s.cargar(self.ruta())
        self.escribir(" " * (secuencia.MAX_BYTES_FICHERO + 1))
        with self.assertRaises(secuencia.ErrorSecuencia):
            self.s.cargar(self.ruta())
        for ruta in (self.dir, self.ruta("no_existe.json")):
            with self.assertRaises(secuencia.ErrorSecuencia):
                self.s.cargar(ruta)
        self.assertEqual(self.s.puntos, [A])

    def test_cargar_tolera_el_bom_del_bloc_de_notas_y_acepta_la_secuencia_vacia(self):
        self.escribir(json.dumps([A, B]), encoding="utf-8-sig")
        self.s.cargar(self.ruta())
        self.assertEqual(self.s.puntos, [A, B])
        self.escribir("[]")
        self.s.cargar(self.ruta())
        self.assertEqual(self.s.puntos, [])

    def test_guardar_con_fallo_a_mitad_no_pierde_el_fichero_anterior(self):
        self.s.guardar(self.ruta())
        self.s.puntos = [B, object()]                               # json.dump fallara tras escribir el primer punto
        with self.assertRaises(TypeError):
            self.s.guardar(self.ruta())
        with open(self.ruta(), encoding="utf-8") as f:
            self.assertEqual(json.load(f), [A])
        self.assertFalse(os.path.exists(self.ruta() + ".tmp"))      # y no queda el temporal

    def test_guardar_en_un_sitio_imposible_da_errorsecuencia(self):
        with self.assertRaises(secuencia.ErrorSecuencia):
            self.s.guardar(self.dir)                                # un directorio, no un fichero
        self.assertFalse(os.path.exists(self.dir + ".tmp"))


if __name__ == "__main__":
    unittest.main()
