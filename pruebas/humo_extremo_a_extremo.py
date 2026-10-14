"""
Prueba de humo de extremo a extremo: lanza src\\main.py de verdad (con la ventana REAL de PyBullet) contra
robots falsos de pruebas/robot_falso.py y comprueba lo que imprime. Abre una ventana de PyBullet unos 4 s por orden.
Envia movej solo al ROBOT FALSO (puertos 31xxx), nunca a URSim ni a un robot.

    python -u practicas\\Practica1_visualizador_UR3e\\pruebas\\humo_extremo_a_extremo.py
"""
import os
import subprocess
import sys
import threading
import time

import ayudas
from robot_falso import Q_INICIAL, RobotFalso

AQUI = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(AQUI, "..", "src", "main.py")
FALLOS = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        FALLOS.append(texto)


def lanzar(*argumentos):
    """Arranca main.py y recoge su salida en una lista desde un hilo."""
    proceso = subprocess.Popen([sys.executable, "-B", "-u", MAIN] + list(argumentos), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
    lineas = []

    def leer():
        for linea in proceso.stdout:
            lineas.append(linea.rstrip())       # tambien entra el ruido de PyBullet (b3Printf...): no importa
    threading.Thread(target=leer, daemon=True).start()
    return proceso, lineas


def terminar(proceso):
    proceso.terminate()
    try:
        proceso.wait(5)
    except subprocess.TimeoutExpired:
        proceso.kill()


def grados(q):
    import math
    return [round(math.degrees(a), 1) for a in q]


def prueba_lectura(nombre, orden, formato):
    print(nombre)
    fake = RobotFalso(ayudas.puerto_libre(), formato).iniciar()
    proceso, lineas = lanzar(orden, "--puerto", str(fake.puerto))
    time.sleep(5)
    terminar(proceso)
    fake.parar()
    esperado = "q (grados): " + str(grados(Q_INICIAL))
    comprobar(any(esperado in l for l in lineas), "imprime {}".format(esperado))
    comprobar(not any("Traceback" in l for l in lineas), "sin Traceback")
    if not any(esperado in l for l in lineas):
        print("    salida:", [l for l in lineas if l and "b3Printf" not in l][-10:])


def prueba_varios():
    print("varios (2 robots, 2 puertos)")
    f1 = RobotFalso(ayudas.puerto_libre()).iniciar()
    f2 = RobotFalso(ayudas.puerto_libre(), q=[0.1, -1.0, 0.0, -1.0, 0.0, 0.0]).iniciar()
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, "robots.json")
        with open(ruta, "w") as f:
            json.dump([{"nombre": "r1", "ip": "127.0.0.1", "puerto": f1.puerto, "posicion": [0, 0, 0, 0, 0, 0]},
                       {"nombre": "r2", "ip": "127.0.0.1", "puerto": f2.puerto, "posicion": [1, 0, 0, 0, 0, 0]}], f)
        proceso, lineas = lanzar("varios", "--config", ruta)
        time.sleep(5)
        terminar(proceso)
    f1.parar()
    f2.parar()
    comprobar(any("[r1]" in l and str(grados(Q_INICIAL)) in l for l in lineas), "r1 imprime su q")
    comprobar(any("[r2]" in l and str(grados([0.1, -1.0, 0.0, -1.0, 0.0, 0.0])) in l for l in lineas), "r2 imprime su q")
    comprobar(not any("Traceback" in l for l in lineas), "sin Traceback")


def prueba_ensenar():
    print("ensenar (g, s, l, v, e, q) con velocidad 0,3 rad/s")
    fake = RobotFalso(ayudas.puerto_libre()).iniciar()
    destino = [Q_INICIAL[0] + 0.2] + Q_INICIAL[1:]
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, "puntos.json")
        with open(ruta, "w") as f:
            json.dump([destino], f)
        proceso, lineas = lanzar("ensenar", "--puerto", str(fake.puerto), "--v", "0.3", "--a", "0.5")

        def escribir(texto, espera):
            proceso.stdin.write(texto + "\n")
            proceso.stdin.flush()
            time.sleep(espera)

        time.sleep(3)
        escribir("g", 0.5)                      # guarda el punto actual
        escribir("l " + ruta, 0.5)              # carga una secuencia de 1 punto (reemplaza)
        escribir("v", 2)                        # previsualiza (1 s)
        escribir("e", 4)                        # ejecuta: 0,2 rad a 0,3 rad/s ~ 0,7 s
        escribir("q", 1)
        terminar(proceso)
    ordenes = [o for o in fake.ordenes if o.startswith("movej(")]
    fake.parar()
    comprobar(any("Punto 1 guardado" in l for l in lineas), "g guarda el punto")
    comprobar(any("1 puntos cargados" in l for l in lineas), "l carga la secuencia")
    comprobar(any("Punto 1/1 enviado" in l for l in lineas), "e envia el punto")
    comprobar(any("Secuencia terminada" in l for l in lineas), "la secuencia termina")
    comprobar(len(ordenes) == 1 and "a=0.5, v=0.3" in ordenes[0], "el robot falso recibio 1 movej con a=0.5, v=0.3")
    comprobar(abs(fake.q[0] - destino[0]) < 1e-3, "el robot falso llego a q[0] = {:.3f} rad".format(destino[0]))
    comprobar(not any("Traceback" in l for l in lineas), "sin Traceback")
    if FALLOS:
        print("    salida:", [l for l in lineas if l and "b3Printf" not in l][-15:])


def prueba_velocidad_excesiva():
    print("ensenar --v 0.5 (por encima del limite) se rechaza al arrancar")
    proceso, lineas = lanzar("ensenar", "--v", "0.5")
    proceso.wait(10)
    comprobar(proceso.returncode == 2, "main.py termina con codigo 2 (error de argumentos)")


if __name__ == "__main__":
    prueba_lectura("primaria", "primaria", "primaria")
    prueba_lectura("tiempo-real", "tiempo-real", "tiempo_real")
    prueba_varios()
    prueba_ensenar()
    prueba_velocidad_excesiva()
    print("FALLOS: {}".format(FALLOS) if FALLOS else "TODO OK")
    sys.exit(1 if FALLOS else 0)
