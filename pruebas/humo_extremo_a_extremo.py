"""
Prueba de humo de extremo a extremo: lanza src\\primaria.py, src\\tiempo_real.py y src\\ensenar.py de verdad (con la ventana
REAL de PyBullet) contra robots falsos de pruebas/robot_falso.py y comprueba lo que imprimen.
Abre una ventana de PyBullet unos 4 s por script.
Envia movej solo al ROBOT FALSO (puertos 31xxx), nunca a URSim ni a un robot.

    python -u pruebas\\humo_extremo_a_extremo.py

Los scripts no tienen argumentos y el JSON de robots no lleva puertos, asi que cada script se arranca con un lanzador:
cambia el puerto de ur.py y las rutas de datos/ del script (ROBOTS, SECUENCIAS) El resto es el script tal cual.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time

import ayudas
from robot_falso import Q_INICIAL, RobotFalso

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(AQUI, "..", "src"))
FALLOS = []

LANZADOR = """
import importlib.util, os, sys
src, script, puerto, robots, secuencias = sys.argv[1:6]
sys.path.insert(0, os.path.join(src, "librerias"))
import ur
ur.PUERTO_PRIMARIA = ur.PUERTO_TIEMPO_REAL = int(puerto)
spec = importlib.util.spec_from_file_location(script, os.path.join(src, script + ".py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)          # no ejecuta el bloque __main__ del script
m.ROBOTS = robots
if hasattr(m, "SECUENCIAS"):
    m.SECUENCIAS = secuencias
try:
    m.main()
except KeyboardInterrupt:
    pass
except (ValueError, m.ErrorSimulador) as e:
    print("Error: {}".format(e), file=sys.stderr)
    sys.exit(1)
"""


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        FALLOS.append(texto)


def lanzar(script, puerto, robots, secuencias=""):
    """Arranca un script de src/ y recoge su salida en una lista desde un hilo."""
    proceso = subprocess.Popen([sys.executable, "-B", "-u", "-c", LANZADOR, SRC, script, str(puerto), robots, secuencias],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               universal_newlines=True, bufsize=1)
    lineas = []

    def leer():
        for linea in proceso.stdout:
            lineas.append(linea.rstrip())       # tambien entra el ruido de PyBullet (b3Printf...): no importa
    threading.Thread(target=leer, daemon=True).start()
    return proceso, lineas


def escribir(proceso, texto, espera=0.0):
    proceso.stdin.write(texto + "\n")
    proceso.stdin.flush()
    time.sleep(espera)


def esperar(lineas, condicion, limite=40.0):
    """Espera (hasta `limite` s) a que alguna linea de la salida cumpla `condicion`. Devuelve si aparecio.
    Asi la prueba no depende de lo rapido que arranque Python o PyBullet en cada PC."""
    t0 = time.time()
    while time.time() - t0 < limite:
        if any(condicion(l) for l in list(lineas)):
            return True
        time.sleep(0.2)
    return False


def terminar(proceso):
    proceso.terminate()
    try:
        proceso.wait(5)
    except subprocess.TimeoutExpired:
        proceso.kill()


def grados(q):
    return [round(math.degrees(a), 1) for a in q]


def escribir_robots(carpeta, robots):
    ruta = os.path.join(carpeta, "robots.json")
    with open(ruta, "w") as f:
        json.dump([{"nombre": n, "ip": ip} for n, ip in robots], f)
    return ruta


def prueba_lectura(nombre, script, formato):
    print(nombre + " (1 robot: no pregunta cuantos)")
    fake = RobotFalso(ayudas.puerto_libre(), formato).iniciar()
    with tempfile.TemporaryDirectory() as d:
        proceso, lineas = lanzar(script, fake.puerto, escribir_robots(d, [("robot1", "127.0.0.1")]))
        esperado = "q (grados): " + str(grados(Q_INICIAL))
        esperar(lineas, lambda l: "[robot1]" in l and esperado in l)
        terminar(proceso)
    fake.parar()
    comprobar(any("[robot1]" in l and esperado in l for l in lineas), "imprime {}".format(esperado))
    comprobar(not any("Traceback" in l for l in lineas), "sin Traceback")
    if not any(esperado in l for l in lineas):
        print("    salida:", [l for l in lineas if l and "b3Printf" not in l][-10:])


def prueba_dos_robots(nombre, script, formato):
    print(nombre + " (2 robots con distinta IP de loopback y el mismo puerto; responde 2 a la pregunta)")
    puerto = ayudas.puerto_libre()
    q2 = [0.1, -1.0, 0.0, -1.0, 0.0, 0.0]
    f1 = RobotFalso(puerto, formato).iniciar()
    f2 = RobotFalso(puerto, formato, q=q2, ip="127.0.0.2").iniciar()
    with tempfile.TemporaryDirectory() as d:
        proceso, lineas = lanzar(script, puerto, escribir_robots(d, [("r1", "127.0.0.1"), ("r2", "127.0.0.2")]))
        esperar(lineas, lambda l: "Robots a visualizar" in l)
        escribir(proceso, "2")
        esperar(lineas, lambda l: "[r1]" in l and str(grados(Q_INICIAL)) in l)
        esperar(lineas, lambda l: "[r2]" in l and str(grados(q2)) in l)
        terminar(proceso)
    f1.parar()
    f2.parar()
    comprobar(any("Robots a visualizar" in l for l in lineas), "pregunta cuantos robots")
    comprobar(any("[r1]" in l and str(grados(Q_INICIAL)) in l for l in lineas), "r1 imprime su q")
    comprobar(any("[r2]" in l and str(grados(q2)) in l for l in lineas), "r2 imprime su q")
    comprobar(not any("Traceback" in l for l in lineas), "sin Traceback")
    if FALLOS:
        t = next((i for i, l in enumerate(lineas) if "Traceback" in l), 0)         # desde el primer Traceback
        print("    salida:", [l for l in lineas[t:] if l and "b3Printf" not in l][:25])


def prueba_ensenar():
    print("ensenar (consola: ajustar, g, l, v, e, q)")
    fake = RobotFalso(ayudas.puerto_libre()).iniciar()
    destino = [Q_INICIAL[0] + 0.2] + Q_INICIAL[1:]
    with tempfile.TemporaryDirectory() as d:
        secuencias = os.path.join(d, "secuencias")
        os.makedirs(secuencias)
        with open(os.path.join(secuencias, "puntos.json"), "w") as f:
            json.dump([destino], f)
        proceso, lineas = lanzar("ensenar", fake.puerto, escribir_robots(d, [("robot1", "127.0.0.1")]), secuencias)
        esperar(lineas, lambda l: l.startswith("Conectado a"))

        escribir(proceso, "ajustar 0.5 0.5")                     # por encima del limite de 0,3 rad/s: no cambia
        esperar(lineas, lambda l: "No se cambia" in l)
        escribir(proceso, "ajustar 0.3 0.5")                     # el limite exacto
        esperar(lineas, lambda l: l.startswith("Velocidad 0.3"))
        escribir(proceso, "g")                                   # guarda el punto actual
        esperar(lineas, lambda l: l == "Punto 1 guardado")
        escribir(proceso, "l puntos")                            # carga una secuencia de 1 punto (reemplaza)
        esperar(lineas, lambda l: "1 puntos cargados" in l)
        escribir(proceso, "v", 2)                                # previsualiza (1 s)
        escribir(proceso, "e")                                   # ejecuta: 0,2 rad a 0,3 rad/s ~ 0,7 s
        esperar(lineas, lambda l: "Secuencia terminada" in l)
        escribir(proceso, "q", 1.5)
        terminar(proceso)
    ordenes = [o for o in fake.ordenes if o.startswith("movej(")]
    fake.parar()
    comprobar(any("No se cambia" in l for l in lineas), "ajustar 0.5 0.5 se rechaza y avisa (limite 0,3 rad/s)")
    comprobar(any("Punto 1 guardado" in l for l in lineas), "g guarda el punto")
    comprobar(any("1 puntos cargados" in l for l in lineas), "l carga la secuencia")
    comprobar(any("Punto 1/1 enviado" in l for l in lineas), "e envia el punto")
    comprobar(any("Secuencia terminada" in l for l in lineas), "la secuencia termina")
    comprobar(len(ordenes) == 1 and "a=0.5, v=0.3" in ordenes[0], "el robot falso recibio 1 movej con a=0.5, v=0.3")
    comprobar(abs(fake.q[0] - destino[0]) < 1e-3, "el robot falso llego a q[0] = {:.3f} rad".format(destino[0]))
    comprobar(not any("Traceback" in l for l in lineas), "sin Traceback")
    if FALLOS:
        print("    salida:", [l for l in lineas if l and "b3Printf" not in l][-15:])


def prueba_robots_json_malo():
    print("robots.json malo: el programa explica el error y sale con codigo 1 sin abrir la ventana")
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, "robots.json")
        with open(ruta, "w") as f:
            f.write("[]")
        for script in ("primaria", "tiempo_real", "ensenar"):
            proceso, lineas = lanzar(script, 30001, ruta)
            try:
                proceso.wait(40)
            except subprocess.TimeoutExpired:
                terminar(proceso)
            esperar(lineas, lambda l: "Error:" in l, 10)     # el hilo que recoge la salida puede ir por detras
            comprobar(proceso.returncode == 1 and any("Error:" in l for l in lineas),
                      "{}.py termina con codigo 1 y explica el error".format(script))


if __name__ == "__main__":
    prueba_lectura("primaria", "primaria", "primaria")
    prueba_lectura("tiempo_real", "tiempo_real", "tiempo_real")
    prueba_dos_robots("primaria", "primaria", "primaria")
    prueba_dos_robots("tiempo_real", "tiempo_real", "tiempo_real")
    prueba_ensenar()
    prueba_robots_json_malo()
    print("FALLOS: {}".format(FALLOS) if FALLOS else "TODO OK")
    sys.exit(1 if FALLOS else 0)
