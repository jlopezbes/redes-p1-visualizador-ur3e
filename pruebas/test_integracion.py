"""
Pruebas de integracion: ur.py y secuencia.py contra pruebas/robot_falso.py por sockets reales (127.0.0.1, puerto libre).
Envian movej al ROBOT FALSO, nunca a URSim ni a un robot. Tardan unos segundos porque el robot falso mueve de verdad.

    python -B -m unittest discover -s pruebas -v
"""
import contextlib
import io
import time
import unittest

import ayudas
import secuencia
import ur
from red import ErrorRed
from robot_falso import Q_INICIAL, RobotFalso

SEGUNDOS = 15.0         # tiempo maximo de cada espera


def con_offset(q, indice, delta):
    nuevo = list(q)
    nuevo[indice] += delta
    return nuevo


def casi_igual(a, b, tol=1e-3):
    return len(a) == len(b) and all(abs(x - y) < tol for x, y in zip(a, b))


class Base(unittest.TestCase):
    def setUp(self):
        salida = contextlib.redirect_stdout(io.StringIO())
        salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)
        self.fake = RobotFalso(ayudas.puerto_libre()).iniciar()
        self.addCleanup(self.fake.parar)

    def esperar(self, condicion, segundos=SEGUNDOS):
        fin = time.time() + segundos
        while time.time() < fin:
            if condicion():
                return True
            time.sleep(0.01)
        return False

    def ordenes(self, prefijo):
        return [o for o in self.fake.ordenes if o.startswith(prefijo)]

    def esperar_orden(self, prefijo, cantidad=1):
        """El robot falso recibe las ordenes unos ms despues de enviarlas: hay que esperar a que lleguen."""
        self.assertTrue(self.esperar(lambda: len(self.ordenes(prefijo)) >= cantidad, 3),
                        "el robot falso no recibio {} x {}".format(cantidad, prefijo))

    def conectar(self, **kw):
        robot = ur.ClienteUR("127.0.0.1", kw.pop("puerto", self.fake.puerto), **kw)
        self.addCleanup(robot.desconectar)
        robot.conectar()
        return robot


class PruebasLectura(Base):
    def test_lee_el_estado_inicial(self):
        self.assertTrue(casi_igual(next(self.conectar().mensajes())["q"], Q_INICIAL))

    def test_movej_llega_al_punto(self):
        punto = con_offset(Q_INICIAL, 0, 0.3)
        robot = self.conectar()
        robot.movej(punto, velocidad=0.3, aceleracion=0.5)
        for datos in robot.mensajes():
            if casi_igual(datos["q"], punto):
                break
        self.assertEqual(len(self.ordenes("movej(")), 1)

    def test_tiempo_real(self):
        fake = RobotFalso(ayudas.puerto_libre(), formato="tiempo_real").iniciar()
        self.addCleanup(fake.parar)
        robot = self.conectar(puerto=fake.puerto, tiempo_real=True)
        self.assertTrue(casi_igual(next(robot.mensajes())["q"], Q_INICIAL))

    def test_hilo_se_recupera_cuando_el_robot_corta(self):
        reintento = ur.REINTENTO
        ur.REINTENTO = 0.5
        self.addCleanup(setattr, ur, "REINTENTO", reintento)
        hilo = ur.HiloLectorUR("falso", ur.ClienteUR("127.0.0.1", self.fake.puerto))
        self.addCleanup(hilo.detener)
        hilo.start()
        self.assertTrue(self.esperar(lambda: hilo.q is not None))
        self.fake.cortar_clientes()
        self.assertTrue(self.esperar(lambda: hilo.q is None, 3), "no detecto la desconexion")
        self.assertTrue(self.esperar(lambda: hilo.q is not None, 5), "no reconecto")
        self.assertTrue(casi_igual(hilo.q, Q_INICIAL))

    def test_dos_robots_en_la_misma_maquina_con_distinta_ip(self):
        # Como en "varios": el mismo puerto en dos robots distintos (127.0.0.2 tambien es este PC en Windows y Linux).
        segundo = RobotFalso(self.fake.puerto, q=[0.1, -1.0, 0.0, -1.0, 0.0, 0.0], ip="127.0.0.2").iniciar()
        self.addCleanup(segundo.parar)
        robot2 = ur.ClienteUR("127.0.0.2", self.fake.puerto)
        self.addCleanup(robot2.desconectar)
        robot2.conectar()
        self.assertTrue(casi_igual(next(robot2.mensajes())["q"], [0.1, -1.0, 0.0, -1.0, 0.0, 0.0]))
        self.assertTrue(casi_igual(next(self.conectar().mensajes())["q"], Q_INICIAL))


class PruebasReproductor(Base):
    def preparar(self, *puntos):
        self.robot = self.conectar()
        self.seq = secuencia.Secuencia(puntos)
        self.rep = secuencia.Reproductor(self.robot, self.seq, velocidad=0.3, aceleracion=0.5)
        self.fases = set()
        self.bombear(lambda: self.rep.q is not None)        # espera el primer estado

    def bombear(self, hasta, segundos=SEGUNDOS):
        """Procesa los mensajes del robot en el hilo de la prueba hasta que hasta() sea cierto."""
        fin = time.time() + segundos
        for datos in self.robot.mensajes():
            self.rep.procesar(datos)
            self.fases.add(self.rep.fase)
            if hasta():
                return
            if time.time() > fin:
                self.fail("tiempo agotado; fase = {}, q = {}".format(self.rep.fase, self.rep.q))

    def test_ejecuta_una_secuencia_entera(self):
        p1, p2, p3 = (con_offset(Q_INICIAL, 0, 0.2), con_offset(Q_INICIAL, 1, 0.2), con_offset(Q_INICIAL, 2, -0.2))
        self.preparar(p1, p2, p3)
        self.rep.ejecutar()
        self.bombear(lambda: self.rep.fase == secuencia.LIBRE)
        self.assertIn(secuencia.MOVIENDO, self.fases)
        self.assertTrue(casi_igual(self.rep.q, p3))
        self.assertEqual(len(self.ordenes("movej(")), 3)
        self.assertEqual(self.ordenes("stopj"), [])

    def test_parada_de_proteccion_y_reanudar(self):
        punto = con_offset(Q_INICIAL, 0, 0.9)               # a 0,3 rad/s son 3 s: da tiempo a interrumpir
        self.preparar(punto)
        self.rep.ejecutar()
        self.bombear(lambda: self.rep.fase == secuencia.MOVIENDO)
        self.fake.protegido = True
        self.bombear(lambda: self.rep.fase == secuencia.PARADA)
        self.esperar_orden("stopj")
        self.assertEqual(len(self.ordenes("stopj")), 1)
        self.assertFalse(casi_igual(self.rep.q, punto))     # se quedo a medias

        self.fake.protegido = False
        self.bombear(lambda: not self.rep.protegido)
        self.rep.reanudar()
        self.bombear(lambda: self.rep.fase == secuencia.LIBRE)
        self.assertTrue(casi_igual(self.rep.q, punto))
        self.assertEqual(len(self.ordenes("movej(")), 2)    # el original y el de la reanudacion

    def test_error_del_robot_detiene(self):
        self.preparar(con_offset(Q_INICIAL, 0, 0.9))
        self.rep.ejecutar()
        self.bombear(lambda: self.rep.fase == secuencia.MOVIENDO)
        self.fake.enviar_error("Colision de prueba")
        self.bombear(lambda: self.rep.fase == secuencia.PARADA)
        self.esperar_orden("stopj")
        self.assertEqual(len(self.ordenes("stopj")), 1)

    def test_cancelar_frena_el_robot(self):
        self.preparar(con_offset(Q_INICIAL, 0, 0.9))
        self.rep.ejecutar()
        self.bombear(lambda: self.rep.fase == secuencia.MOVIENDO)
        self.rep.cancelar()
        self.bombear(lambda: not self.fake.ejecutando)      # el robot falso ya no esta en marcha
        self.assertEqual(self.rep.fase, secuencia.LIBRE)
        self.esperar_orden("stopj")
        self.assertEqual(len(self.ordenes("stopj")), 1)

    def test_conexion_cortada_en_movimiento_deja_parada(self):
        self.preparar(con_offset(Q_INICIAL, 0, 0.9))
        self.rep.ejecutar()
        self.bombear(lambda: self.rep.fase == secuencia.MOVIENDO)
        self.fake.cortar_clientes()
        with self.assertRaises(ErrorRed):
            self.bombear(lambda: False)
        self.rep.conexion_perdida()
        self.assertEqual(self.rep.fase, secuencia.PARADA)


if __name__ == "__main__":
    unittest.main()
