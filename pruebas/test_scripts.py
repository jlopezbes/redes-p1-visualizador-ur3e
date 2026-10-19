"""
Pruebas de los tres scripts de src/ (primaria.py, tiempo_real.py, ensenar.py): rutas relativas al script, main() de
primaria y tiempo_real, y el bloque __main__ (codigos de salida y mensajes). No abren el simulador ni tocan la red.

    python -B -m unittest discover -s 2_practicas\\Practica1_visualizador_UR3e\\pruebas -p test_scripts.py -v

Los casos que ejecutan el script entero van en un SUBPROCESO sobre una copia de src/ y datos/ (el robots.json de la
practica no se toca); los de KeyboardInterrupt y excepciones usan runpy con el simulador falso.
"""
import contextlib
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import ayudas
import ensenar
import primaria
import simulador
import tiempo_real
import ur
from simulador import ErrorSimulador

PRACTICA = os.path.normpath(os.path.join(ayudas.AQUI, ".."))
SRC = ayudas.SRC
LIBRERIAS = ayudas.LIBRERIAS
ROBOTS_PRACTICA = os.path.normpath(os.path.join(SRC, "..", "datos", "robots.json"))
SCRIPTS = ("primaria", "tiempo_real", "ensenar")
MODULOS = {"primaria": primaria, "tiempo_real": tiempo_real, "ensenar": ensenar}

DOS_ROBOTS = [{"nombre": "uno", "ip": "10.0.0.1"}, {"nombre": "dos", "ip": "10.0.0.2"}]
UN_ROBOT = [{"nombre": "solo", "ip": "10.0.0.9"}]


def escribir(ruta, texto):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)


def ruta_script(nombre):
    return os.path.join(SRC, nombre + ".py")


class PruebasRutas(unittest.TestCase):
    """ROBOTS y SECUENCIAS se calculan respecto al script, no al directorio de trabajo; y no hay rutas fijas en el codigo."""

    def test_robots_es_absoluta_y_apunta_al_json_de_la_practica(self):
        for nombre, modulo in MODULOS.items():
            with self.subTest(nombre):
                self.assertTrue(os.path.isabs(modulo.ROBOTS))
                self.assertTrue(modulo.ROBOTS.endswith(os.path.join("datos", "robots.json")))
                self.assertEqual(modulo.ROBOTS, ROBOTS_PRACTICA)
                self.assertTrue(os.path.isfile(modulo.ROBOTS))

    def test_secuencias_de_ensenar_es_la_carpeta_datos_secuencias(self):
        self.assertTrue(os.path.isabs(ensenar.SECUENCIAS))
        self.assertTrue(ensenar.SECUENCIAS.endswith(os.path.join("datos", "secuencias")))
        self.assertEqual(ensenar.SECUENCIAS, os.path.normpath(os.path.join(SRC, "..", "datos", "secuencias")))

    def test_lanzar_desde_otra_carpeta_no_cambia_las_rutas(self):
        codigo = ("import runpy, sys\n"
                  "m = runpy.run_path(sys.argv[1])\n"                  # run_name distinto de __main__: no ejecuta nada
                  "print(m['ROBOTS'])\n"
                  "print(m.get('SECUENCIAS', ''))\n")
        with tempfile.TemporaryDirectory() as otra:
            for nombre in SCRIPTS:
                with self.subTest(nombre):
                    r = subprocess.run([sys.executable, "-B", "-c", codigo, ruta_script(nombre)], cwd=otra,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       universal_newlines=True, timeout=30)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    lineas = r.stdout.splitlines()
                    self.assertEqual(lineas[0], ROBOTS_PRACTICA)
                    if nombre == "ensenar":
                        self.assertEqual(lineas[1], ensenar.SECUENCIAS)

    def test_importar_con_otro_cwd_no_cambia_las_rutas(self):
        antes = os.getcwd()
        with tempfile.TemporaryDirectory() as otra:
            os.chdir(otra)
            try:
                for nombre in SCRIPTS:
                    with self.subTest(nombre):
                        globales = runpy.run_path(ruta_script(nombre))
                        self.assertEqual(globales["ROBOTS"], ROBOTS_PRACTICA)
            finally:
                os.chdir(antes)

    def test_ninguna_ruta_fija_de_windows_o_linux_en_los_fuentes(self):
        patrones = [re.compile(r"\b[A-Za-z]:\\"), re.compile(r"\b[A-Za-z]:/(?!/)"),
                    re.compile(r"/home/"), re.compile(r"/Users/")]
        fuentes = [os.path.join(c, f) for c in (SRC, LIBRERIAS) for f in sorted(os.listdir(c)) if f.endswith(".py")]
        self.assertGreaterEqual(len(fuentes), 7)                 # 3 scripts y 4 librerias
        encontradas = []
        for fuente in fuentes:
            with open(fuente, encoding="utf-8") as f:
                for n, linea in enumerate(f, 1):
                    for patron in patrones:
                        if patron.search(linea):
                            encontradas.append("{}:{}: {}".format(os.path.relpath(fuente, PRACTICA), n, linea.strip()))
        self.assertEqual(encontradas, [])


class PruebasMain(unittest.TestCase):
    """primaria.main() y tiempo_real.main(): cuantos clientes se construyen, con que destino y en que interfaz."""

    CASOS = (("primaria", primaria, 30001, False), ("tiempo_real", tiempo_real, 30003, True))

    def ejecutar(self, modulo, robots, entrada=None):
        """Devuelve el dict de clientes que recibe simulador.visualizar. `entrada`: lo que devuelve input()."""
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "robots.json")
            escribir(ruta, json.dumps(robots))
            with mock.patch.object(modulo, "ROBOTS", ruta), \
                    mock.patch.object(simulador, "visualizar") as visualizar, \
                    mock.patch("builtins.input", return_value=entrada), \
                    contextlib.redirect_stdout(io.StringIO()):
                modulo.main()
        visualizar.assert_called_once()
        return visualizar.call_args[0][0]

    def test_con_2_construye_dos_clientes_con_su_destino_y_su_interfaz(self):
        for nombre, modulo, puerto, rapido in self.CASOS:
            with self.subTest(nombre):
                clientes = self.ejecutar(modulo, DOS_ROBOTS, "2")
                self.assertEqual(list(clientes), ["uno", "dos"])
                self.assertEqual([c.destino for c in clientes.values()],
                                 ["10.0.0.1:{}".format(puerto), "10.0.0.2:{}".format(puerto)])
                for cliente in clientes.values():
                    self.assertIsInstance(cliente, ur.ClienteUR)
                    self.assertIs(cliente.tiempo_real, rapido)

    def test_con_intro_construye_solo_el_primero(self):
        for nombre, modulo, puerto, rapido in self.CASOS:
            with self.subTest(nombre):
                clientes = self.ejecutar(modulo, DOS_ROBOTS, "")
                self.assertEqual(list(clientes), ["uno"])
                self.assertEqual(clientes["uno"].destino, "10.0.0.1:{}".format(puerto))
                self.assertIs(clientes["uno"].tiempo_real, rapido)

    def test_con_un_solo_robot_no_pregunta(self):
        for nombre, modulo, puerto, rapido in self.CASOS:
            with self.subTest(nombre):
                with tempfile.TemporaryDirectory() as carpeta:
                    ruta = os.path.join(carpeta, "robots.json")
                    escribir(ruta, json.dumps(UN_ROBOT))
                    with mock.patch.object(modulo, "ROBOTS", ruta), \
                            mock.patch.object(simulador, "visualizar") as visualizar, \
                            mock.patch("builtins.input", side_effect=AssertionError("no debe preguntar")):
                        modulo.main()
                clientes = visualizar.call_args[0][0]
                self.assertEqual({n: c.destino for n, c in clientes.items()}, {"solo": "10.0.0.9:{}".format(puerto)})
                self.assertIs(clientes["solo"].tiempo_real, rapido)

    def test_con_robots_json_malo_no_llega_a_visualizar(self):
        for nombre, modulo, _, _ in self.CASOS:
            with self.subTest(nombre):
                with tempfile.TemporaryDirectory() as carpeta, \
                        mock.patch.object(simulador, "visualizar") as visualizar:
                    with mock.patch.object(modulo, "ROBOTS", os.path.join(carpeta, "no_existe.json")):
                        with self.assertRaises(ValueError):
                            modulo.main()
                visualizar.assert_not_called()


class PruebasBloqueMainEnSubproceso(unittest.TestCase):
    """Ejecuta el script de verdad sobre una copia de src/ y datos/ con un robots.json malo: codigo 1 y mensaje, sin
    traceback. Los cuatro fallan al leer robots.json o al crear el cliente, antes de abrir ningun simulador."""

    @classmethod
    def setUpClass(cls):
        cls.raiz = tempfile.mkdtemp()
        cls.copia = os.path.join(cls.raiz, "practica")
        ignorar = shutil.ignore_patterns("__pycache__", "*.pyc")
        shutil.copytree(SRC, os.path.join(cls.copia, "src"), ignore=ignorar)
        shutil.copytree(os.path.join(SRC, "..", "datos"), os.path.join(cls.copia, "datos"), ignore=ignorar)
        cls.otro_cwd = os.path.join(cls.raiz, "otro")
        os.mkdir(cls.otro_cwd)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.raiz, ignore_errors=True)

    def lanzar(self, nombre, contenido):
        """Pone `contenido` en robots.json (None = lo borra) y lanza el script desde otra carpeta.
        Devuelve (CompletedProcess, segundos)."""
        ruta = os.path.join(self.copia, "datos", "robots.json")
        if contenido is None:
            if os.path.exists(ruta):
                os.remove(ruta)
        else:
            escribir(ruta, contenido)
        t0 = time.time()
        r = subprocess.run([sys.executable, "-B", os.path.join(self.copia, "src", nombre + ".py")],
                           cwd=self.otro_cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        return r, time.time() - t0

    CASOS = (
        ("inexistente", None),
        ("lista vacia", "[]"),
        ("json roto", '[{"nombre": "a", "ip": '),
        ("sin ip", '[{"nombre": "a"}]'),
        ("no es una lista", '{"nombre": "a", "ip": "10.0.0.1"}'),
        ("ip no literal", '[{"nombre": "a", "ip": "localhost"}, {"nombre": "b", "ip": "10.0.0.2"}]'),
    )

    def test_robots_json_malo_da_codigo_1_con_error_y_sin_traceback(self):
        for nombre in SCRIPTS:
            for caso, contenido in self.CASOS:
                with self.subTest(script=nombre, caso=caso):
                    r, segundos = self.lanzar(nombre, contenido)
                    self.assertEqual(r.returncode, 1, r.stderr)
                    self.assertIn("Error:", r.stderr)
                    self.assertNotIn("Traceback", r.stderr)
                    self.assertLess(segundos, 15)                   # no llega a abrir ningun simulador ni a conectar (con holgura: arrancar Python tarda mas con la maquina cargada)

    def test_ensenar_con_robots_json_malo_sale_antes_de_abrir_el_simulador(self):
        for caso, contenido in self.CASOS:
            with self.subTest(caso):
                r, segundos = self.lanzar("ensenar", contenido)
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertLess(segundos, 15)
                self.assertNotIn("pybullet", r.stderr.lower())


class PruebasBloqueMainConRunpy(unittest.TestCase):
    """Bloque __main__ ejecutado con runpy. runpy vuelve a definir main(), asi que se parchea lo que main() usa:
    ur.leer_robots (robots.json de un robot), simulador.visualizar (primaria, tiempo_real) y simulador.Simulador
    (ensenar, que lo construye tras leer el robot)."""

    def lanzar(self, nombre, efecto, leer_robots=None):
        """Ejecuta el script como __main__ con `efecto` (excepcion) en la primera llamada que hace al simulador.
        Devuelve (codigo de salida o None si no hubo SystemExit, stdout, stderr)."""
        if leer_robots is None:
            leer_robots = mock.Mock(return_value={"solo": "10.0.0.9"})
        err, out = io.StringIO(), io.StringIO()
        destino = (mock.patch.object(simulador, "visualizar", side_effect=efecto) if nombre != "ensenar"
                   else mock.patch.object(simulador, "Simulador", side_effect=efecto))
        codigo = None
        with mock.patch.object(ur, "leer_robots", leer_robots), destino, \
                mock.patch("builtins.input", side_effect=AssertionError("no debe preguntar")), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            try:
                runpy.run_path(ruta_script(nombre), run_name="__main__")
            except SystemExit as e:
                codigo = e.code
        return codigo, out.getvalue(), err.getvalue()

    def test_ctrl_c_sale_sin_excepcion_ni_mensaje(self):
        for nombre in SCRIPTS:
            with self.subTest(nombre):
                codigo, _, err = self.lanzar(nombre, KeyboardInterrupt())
                self.assertIsNone(codigo)                           # termina con normalidad: codigo de salida 0
                self.assertEqual(err, "")

    def test_error_del_simulador_da_codigo_1_con_el_mensaje(self):
        for nombre in SCRIPTS:
            with self.subTest(nombre):
                codigo, _, err = self.lanzar(nombre, ErrorSimulador("ventana cerrada"))
                self.assertEqual(codigo, 1)
                self.assertIn("Error: ventana cerrada", err)
                self.assertNotIn("Traceback", err)

    def test_value_error_da_codigo_1_con_el_mensaje(self):
        for nombre in SCRIPTS:
            with self.subTest(nombre):
                codigo, _, err = self.lanzar(nombre, None, leer_robots=mock.Mock(side_effect=ValueError("ip mala")))
                self.assertEqual(codigo, 1)
                self.assertIn("Error: ip mala", err)
                self.assertNotIn("Traceback", err)

    def test_otra_excepcion_no_se_captura(self):
        for nombre in SCRIPTS:
            with self.subTest(nombre):
                with self.assertRaises(RuntimeError):               # Python imprimira el traceback y saldra con 1
                    self.lanzar(nombre, RuntimeError("bug"))


if __name__ == "__main__":
    unittest.main()
