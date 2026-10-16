"""
Prueba de humo de src/simulador.py con la libreria REAL UR3e_rg2. Abre la ventana de PyBullet unos 2 s y la cierra.
No toca ningun robot ni abre ningun socket.

    python -B 2_practicas\\Practica1_visualizador_UR3e\\pruebas\\humo_pybullet.py

Comprueba con pybullet.getJointState / getBasePositionAndOrientation que lo que dice Simulador es lo que ocurre:
robot1 en el origen y robot2 a 1 m en x.
"""
import sys
import time

import ayudas  # noqa: F401  (pone src/ en sys.path)
import pybullet
from simulador import Simulador

JOINTS_BRAZO = (1, 2, 3, 4, 5, 6)       # indices de las 6 articulaciones del brazo en el URDF (ver dynamic_ur3e.py)

sim = Simulador()
sim.agregar_robot("robot1")
sim.agregar_robot("robot2")
q1 = [0.3, -1.0, 0.5, -1.2, 0.4, 0.1]
q2 = [-0.3, -1.5, 0.2, -0.8, -0.4, 0.6]
copia = list(q1)
sim.mover("robot1", q1)
sim.mover("robot2", q2)
time.sleep(2)

fallos = []
for nombre, esperado in (("robot1", copia), ("robot2", q2)):
    id_robot = sim._ids[nombre]
    leido = [pybullet.getJointState(id_robot, j)[0] for j in JOINTS_BRAZO]
    if any(abs(a - b) > 1e-6 for a, b in zip(leido, esperado)):
        fallos.append("{} (id {}): esperado {} y leido {}".format(nombre, id_robot, esperado, leido))
    print("{} -> id {}; articulaciones leidas (rad): {}".format(nombre, id_robot, [round(a, 3) for a in leido]))

x1 = pybullet.getBasePositionAndOrientation(sim._ids["robot1"])[0][0]
x2 = pybullet.getBasePositionAndOrientation(sim._ids["robot2"])[0][0]
print("base x (m): robot1 = {:.2f}, robot2 = {:.2f}".format(x1, x2))
if abs(x1) > 1e-6 or abs(x2 - 1.0) > 1e-6:
    fallos.append("posicion de la base incorrecta")
if q1 != copia:
    fallos.append("mover() ha modificado la lista del que llama")

sim.cerrar()
print("FALLOS: " + "; ".join(fallos) if fallos else "OK")
sys.exit(1 if fallos else 0)
