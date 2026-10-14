"""
El visualizador PyBullet de la libreria UR3e_rg2 (UR3eRG2), con los detalles que la libreria no esconde.

Lo que hace esta clase por nosotros:
  - Los robots se llaman por nombre ("robot1"), no por el id de PyBullet.
  - El primer robot ya existe (id 0, en el origen): solo se recoloca si su base no esta en el origen.
    Los demas se crean con spawn_robot, que devuelve ids que no son consecutivos.
  - mover() pasa una copia del q: UR3eRG2.move_robot alarga la lista que recibe.
  - previsualizar() mueve el robot de punto a punto por interpolacion lineal, sin enviar nada al robot real.

PyBullet no es seguro entre hilos: Simulador se usa siempre desde el hilo principal.
"""
import time

ORIGEN = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]     # [x, y, z, roll, pitch, yaw] de la base: m y rad


class Simulador:
    def __init__(self, visualizador=None):
        """visualizador: algo con move_robot(id, q) y spawn_robot(pose). Si no se da, abre la ventana de UR3eRG2."""
        if visualizador is None:
            from UR3e_rg2.dynamic_ur3e import UR3eRG2     # aqui se abre la ventana de PyBullet
            visualizador = UR3eRG2()
        self._visualizador = visualizador
        self._ids = {}                                    # nombre -> id en PyBullet

    def agregar_robot(self, nombre, posicion=None):
        """Anade un robot. posicion = [x, y, z, roll, pitch, yaw] de su base (m y rad); por defecto, el origen."""
        posicion = list(posicion) if posicion is not None else list(ORIGEN)
        if nombre in self._ids:
            raise ValueError("ya hay un robot llamado {}".format(nombre))
        if not self._ids:
            id_robot = 0
            if posicion != ORIGEN:
                self._colocar_el_primero(posicion)
        else:
            id_robot = self._visualizador.spawn_robot(posicion)
        self._ids[nombre] = id_robot

    def _colocar_el_primero(self, posicion):
        import pybullet
        pybullet.resetBasePositionAndOrientation(0, posicion[:3], pybullet.getQuaternionFromEuler(posicion[3:]))

    def mover(self, nombre, q):
        """Pone el robot en q (6 angulos, rad)."""
        self._visualizador.move_robot(self._ids[nombre], list(q))

    def previsualizar(self, nombre, desde, puntos, pasos=20, duracion_tramo=1.0):
        """Mueve el robot simulado desde `desde` por cada punto de `puntos` (lista de q), `duracion_tramo` s por tramo."""
        for punto in puntos:
            for k in range(1, pasos + 1):
                t = k / pasos
                self.mover(nombre, [a + (b - a) * t for a, b in zip(desde, punto)])
                time.sleep(duracion_tramo / pasos)
            desde = punto
