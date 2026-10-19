"""
Pruebas de src/librerias/hmi.py (HMI web) con http.client contra 127.0.0.1 y puerto elegido por el sistema.
No necesita robot ni navegador.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -p test_hmi.py -v
"""
import http.client
import json
import queue
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.parse import parse_qs, urlparse

import ayudas  # noqa: F401  (pone src/ y src/librerias/ en sys.path)
import hmi

Q6 = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6]      # rad
JSON = {"Content-Type": "application/json"}


class _ServidorRapido(ThreadingHTTPServer):
    """serve_forever con sondeo de 10 ms: con los 0,5 s por defecto cada detener() tardaria 0,5 s y la bateria, 12 s."""

    def serve_forever(self, poll_interval=0.01):
        super().serve_forever(poll_interval)


def setUpModule():
    global _parche
    _parche = mock.patch.object(hmi, "ThreadingHTTPServer", _ServidorRapido)
    _parche.start()


def tearDownModule():
    _parche.stop()


class BaseHMI(unittest.TestCase):
    """Arranca un HMI en un puerto libre y lo para al terminar."""

    def setUp(self):
        self.comandos = queue.Queue()
        self.web = hmi.HMI(self.comandos, puerto=0)
        self.addCleanup(self.web.detener)
        self.url = self.web.iniciar()
        self.puerto = urlparse(self.url).port
        self.token = self.web.token

    def peticion(self, metodo, ruta, cuerpo=None, cabeceras=None, token=True):
        """Devuelve (codigo, cabeceras, cuerpo en str). `ruta` sin token: se le anade ?t=TOKEN salvo token=False/otro str."""
        if token is True:
            ruta = "{}?t={}".format(ruta, self.token)
        elif token:
            ruta = "{}?t={}".format(ruta, token)
        conn = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=5)
        try:
            conn.request(metodo, ruta, body=cuerpo, headers=cabeceras or {})
            r = conn.getresponse()
            return r.status, r, r.read().decode("utf-8")
        finally:
            conn.close()

    def orden(self, linea_json, cabeceras=JSON):
        cuerpo = linea_json if isinstance(linea_json, (str, bytes)) else json.dumps(linea_json)
        return self.peticion("POST", "/orden", cuerpo, cabeceras)[0]


class TestPagina(BaseHMI):
    def test_get_raiz_con_token_devuelve_html_con_canvas_y_el_estado_publicado_sin_marcador(self):
        self.web.publicar({"mensaje": "hola robot", "q": Q6})
        codigo, r, cuerpo = self.peticion("GET", "/")
        self.assertEqual(codigo, 200)
        self.assertTrue(r.getheader("Content-Type").startswith("text/html"))
        self.assertIn("<canvas", cuerpo)
        self.assertNotIn("__INICIAL__", cuerpo)
        self.assertIn("hola robot", cuerpo)

    def test_html_incrustado_escapa_el_menor_que_y_el_json_vuelve_con_el_mensaje_original(self):
        malicioso = "</script><b>x</b>"
        self.web.publicar({"mensaje": malicioso})
        cuerpo = self.peticion("GET", "/")[2]
        self.assertNotIn("</script><b>", cuerpo)
        inicio = cuerpo.index('id="inicial">') + len('id="inicial">')
        fin = cuerpo.index("</script>", inicio)
        incrustado = cuerpo[inicio:fin]
        self.assertNotIn("<", incrustado)
        self.assertEqual(json.loads(incrustado)["mensaje"], malicioso)


class TestSeguridad(BaseHMI):
    def test_sin_token_o_con_token_equivocado_se_responde_403_en_get_y_post(self):
        for token in (False, "equivocado", ""):
            for metodo, ruta in (("GET", "/"), ("GET", "/estado"), ("POST", "/orden")):
                with self.subTest(token=token, metodo=metodo, ruta=ruta):
                    codigo = self.peticion(metodo, ruta, '{"linea": "g"}' if metodo == "POST" else None,
                                           JSON if metodo == "POST" else None, token=token)[0]
                    self.assertEqual(codigo, 403)
        self.assertTrue(self.comandos.empty())

    def test_host_falso_con_token_correcto_se_responde_403(self):
        for host in ("evil.com", "evil.com:80", "127.0.0.1.evil.com"):
            with self.subTest(host=host):
                codigo = self.peticion("GET", "/estado", cabeceras={"Host": host})[0]
                self.assertEqual(codigo, 403)
        codigo = self.peticion("POST", "/orden", '{"linea": "g"}', dict(JSON, Host="evil.com"))[0]
        self.assertEqual(codigo, 403)
        self.assertTrue(self.comandos.empty())

    def test_host_localhost_con_otro_puerto_y_token_correcto_se_acepta(self):
        self.assertEqual(self.peticion("GET", "/estado", cabeceras={"Host": "localhost:1234"})[0], 200)
        self.assertEqual(self.peticion("GET", "/estado", cabeceras={"Host": "localhost"})[0], 200)

    def test_el_token_de_la_url_es_el_del_objeto(self):
        self.assertEqual(parse_qs(urlparse(self.url).query)["t"], [self.token])


class TestEstadoYPublicar(BaseHMI):
    def test_get_estado_devuelve_las_claves_publicadas_mas_t_numerico_e_historial_lista(self):
        self.web.publicar({"mensaje": "ok", "modo": 7, "q": Q6})
        codigo, r, cuerpo = self.peticion("GET", "/estado")
        self.assertEqual(codigo, 200)
        self.assertTrue(r.getheader("Content-Type").startswith("application/json"))
        datos = json.loads(cuerpo)
        for clave in ("mensaje", "modo", "q", "t", "historial"):
            self.assertIn(clave, datos)
        self.assertEqual(datos["mensaje"], "ok")
        self.assertIsInstance(datos["t"], (int, float))
        self.assertIsInstance(datos["historial"], list)
        self.assertEqual(len(datos["historial"]), 1)

    def test_publicar_anade_al_historial_solo_si_el_estado_trae_q_con_seis_valores(self):
        self.web.publicar({"mensaje": "sin q"})
        self.web.publicar({"mensaje": "q None", "q": None})
        self.assertEqual(self.web._instantanea()["historial"], [])
        self.web.publicar({"mensaje": "con q", "q": Q6})
        historial = self.web._instantanea()["historial"]
        self.assertEqual(len(historial), 1)
        self.assertEqual(len(historial[0]), 7)          # [t, q1..q6]
        self.assertEqual(historial[0][1:], Q6)

    def test_publicar_redondea_q_a_cuatro_decimales_en_el_historial(self):
        self.web.publicar({"q": [0.123456, -0.123456, 1.99999, 0.00004, 0.00006, 3.14159265]})
        fila = self.web._instantanea()["historial"][0]
        self.assertEqual(fila[1:], [0.1235, -0.1235, 2.0, 0.0, 0.0001, 3.1416])

    def test_publicar_recorta_del_historial_lo_anterior_a_la_ventana(self):
        with mock.patch.object(hmi, "VENTANA", 0.3):
            self.web.publicar({"q": Q6})
            time.sleep(0.5)                     # en Windows sleep(0.4) puede durar 0.39 s medidos con monotonic
            self.web.publicar({"q": Q6})
            historial = self.web._instantanea()["historial"]
        self.assertEqual(len(historial), 1)
        self.assertGreaterEqual(historial[0][0], 0.4)

    def test_publicar_sin_recorte_conserva_las_muestras_dentro_de_la_ventana(self):
        for _ in range(5):
            self.web.publicar({"q": Q6})
        self.assertEqual(len(self.web._instantanea()["historial"]), 5)


class TestOrdenes(BaseHMI):
    def test_post_orden_valida_devuelve_200_y_mete_la_linea_sin_espacios_en_la_cola(self):
        self.assertEqual(self.orden({"linea": " g "}), 200)
        self.assertEqual(self.comandos.get_nowait(), "g")
        self.assertTrue(self.comandos.empty())

    def test_post_orden_respuesta_es_json_ok(self):
        codigo, _, cuerpo = self.peticion("POST", "/orden", '{"linea": "g"}', JSON)
        self.assertEqual(codigo, 200)
        self.assertEqual(json.loads(cuerpo), {"ok": True})

    def test_varias_ordenes_llegan_a_la_cola_en_orden(self):
        lineas = ["g", "e 1", "c", "g 2", "x"]
        for linea in lineas:
            self.assertEqual(self.orden({"linea": linea}), 200)
        recibidas = [self.comandos.get_nowait() for _ in lineas]
        self.assertEqual(recibidas, lineas)

    def test_post_orden_con_content_type_charset_json_se_acepta(self):
        self.assertEqual(self.orden({"linea": "g"}, {"Content-Type": "application/json; charset=utf-8"}), 200)
        self.assertEqual(self.comandos.get_nowait(), "g")

    def test_post_orden_con_exactamente_100_caracteres_se_acepta(self):
        linea = "a" * 100
        self.assertEqual(self.orden({"linea": linea}), 200)
        self.assertEqual(self.comandos.get_nowait(), linea)

    def test_post_orden_con_content_type_text_plain_responde_415_y_no_encola(self):
        codigo = self.orden('{"linea": "g"}', {"Content-Type": "text/plain"})
        self.assertEqual(codigo, 415)
        self.assertTrue(self.comandos.empty())

    def test_post_orden_sin_content_type_responde_415_y_no_encola(self):
        self.assertEqual(self.orden('{"linea": "g"}', {}), 415)
        self.assertTrue(self.comandos.empty())

    def test_post_orden_no_valida_responde_400_y_la_cola_sigue_vacia(self):
        casos = {
            "json roto": "{linea: g",
            "no es json": "g",
            "objeto vacio": {},
            "linea numerica": {"linea": 5},
            "linea nula": {"linea": None},
            "linea lista": {"linea": ["g"]},
            "linea vacia": {"linea": ""},
            "linea solo espacios": {"linea": "   "},
            "linea de 101 caracteres": {"linea": "a" * 101},
            "salto de linea dentro": {"linea": "g\ne"},
            "salto de linea al final": {"linea": "g\n"},
            "json que no es objeto": [1, 2],
            "json texto": "abc",
        }
        for nombre, cuerpo in casos.items():
            with self.subTest(caso=nombre):
                if nombre == "json texto":
                    cuerpo = json.dumps(cuerpo)
                self.assertEqual(self.orden(cuerpo), 400)
                self.assertTrue(self.comandos.empty())


class TestRutas(BaseHMI):
    def test_post_a_otra_ruta_responde_404(self):
        self.assertEqual(self.peticion("POST", "/otra", '{"linea": "g"}', JSON)[0], 404)
        self.assertEqual(self.peticion("POST", "/", '{"linea": "g"}', JSON)[0], 404)
        self.assertTrue(self.comandos.empty())

    def test_get_a_otra_ruta_con_token_responde_404(self):
        self.assertEqual(self.peticion("GET", "/otra")[0], 404)
        self.assertEqual(self.peticion("GET", "/orden")[0], 404)


class TestCicloDeVida(unittest.TestCase):
    def test_puerto_ocupado_hace_que_iniciar_use_otro_puerto_y_funcione(self):
        ocupante = socket.socket()
        self.addCleanup(ocupante.close)
        ocupante.bind(("127.0.0.1", 0))
        ocupante.listen(1)
        ocupado = ocupante.getsockname()[1]
        web = hmi.HMI(queue.Queue(), puerto=ocupado)
        self.addCleanup(web.detener)
        url = web.iniciar()
        puerto = urlparse(url).port
        self.assertNotEqual(puerto, ocupado)
        conn = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/estado?t=" + web.token)
        r = conn.getresponse()
        r.read()
        self.assertEqual(r.status, 200)

    def test_detener_cierra_el_puerto_y_se_puede_llamar_dos_veces(self):
        web = hmi.HMI(queue.Queue(), puerto=0)
        self.addCleanup(web.detener)
        puerto = urlparse(web.iniciar()).port
        web.detener()
        with self.assertRaises(ConnectionRefusedError):
            socket.create_connection(("127.0.0.1", puerto), timeout=5)      # en Windows rechazar tarda 1-2 s
        web.detener()                           # la segunda vez no hace nada ni falla

    def test_detener_sin_haber_iniciado_no_falla(self):
        hmi.HMI(queue.Queue(), puerto=0).detener()


class TestConcurrencia(BaseHMI):
    def test_publicar_200_estados_en_un_hilo_mientras_se_piden_50_estados_da_siempre_200_y_json_valido(self):
        errores = []

        def publicador():
            try:
                for i in range(200):
                    self.web.publicar({"mensaje": "n{}".format(i), "i": i, "q": Q6})
            except Exception as e:              # noqa: BLE001
                errores.append(e)

        hilo = threading.Thread(target=publicador)
        hilo.start()
        try:
            for _ in range(50):
                codigo, _, cuerpo = self.peticion("GET", "/estado")
                self.assertEqual(codigo, 200)
                datos = json.loads(cuerpo)
                self.assertIsInstance(datos["historial"], list)
                self.assertTrue(all(len(f) == 7 for f in datos["historial"]))
        finally:
            hilo.join(timeout=10)
        self.assertEqual(errores, [])
        self.assertFalse(hilo.is_alive())
        self.assertEqual(self.web._instantanea()["i"], 199)


if __name__ == "__main__":
    unittest.main()
