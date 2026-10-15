"""
El visualizador PyBullet de la libreria UR3e_rg2 (UR3eRG2), con los detalles que la libreria no esconde.

Lo que hace esta clase por nosotros:
  - Los robots se llaman por nombre ("robot1"), no por el id de PyBullet.
  - Los robots se colocan solos en fila, a 1 m uno de otro. El primero ya existe (id 0, en el origen); los demas se
    crean con spawn_robot, que devuelve ids que no son consecutivos.
  - mover() pasa una copia del q: UR3eRG2.move_robot alarga la lista que recibe.
  - previsualizar() mueve el robot de punto a punto por interpolacion lineal, sin enviar nada al robot real.
  - Cualquier fallo de la libreria (no instalada, ventana cerrada, pybullet.error...) sale como ErrorSimulador:
    es el unico sitio donde se captura Exception a secas, porque PyBullet no tiene una jerarquia de errores util.

PyBullet no es seguro entre hilos: Simulador se usa siempre desde el hilo principal.
"""
import time

PASOS_TRAMO = 20            # pasos de interpolacion entre dos puntos de la vista previa
DURACION_TRAMO = 1.0        # s por tramo de la vista previa
MAX_PREVIEW = 20.0          # s: mientras dura la vista previa el programa no atiende al robot, asi que no se alarga mas


class ErrorSimulador(Exception):
    """El simulador no funciona: falta la libreria, se cerro la ventana... El mensaje dice que ha pasado."""


class Simulador:
    def __init__(self, visualizador=None):
        """visualizador: algo con move_robot(id, q) y spawn_robot(pose), para pruebas. Si no se da, abre la ventana de UR3eRG2."""
        self._propio = visualizador is None
        self._ids = {}                                    # nombre -> id en PyBullet
        if visualizador is None:
            def abrir():
                from UR3e_rg2.dynamic_ur3e import UR3eRG2     # aqui se abre la ventana de PyBullet
                return UR3eRG2()
            visualizador = self._libreria(abrir, que="no se puede abrir el simulador (esta instalada UR3e_rg2? ver recursos/)")
        self._visualizador = visualizador

    def _libreria(self, funcion, *args, que="el simulador PyBullet ha fallado (se cerro la ventana?)"):
        """Llama a la libreria: lo que lance (ImportError, pybullet.error, SystemError...) sale como ErrorSimulador."""
        try:
            return funcion(*args)
        except Exception as e:
            raise ErrorSimulador("{}: {}".format(que, e)) from e

    def agregar_robot(self, nombre):
        """Anade un robot: el primero en el origen y cada uno de los demas 1 m mas lejos en x."""
        if nombre in self._ids:
            raise ValueError("ya hay un robot llamado {}".format(nombre))
        if self._ids:
            pose = [float(len(self._ids)), 0.0, 0.0, 0.0, 0.0, 0.0]        # [x, y, z, roll, pitch, yaw]: m y rad
            self._ids[nombre] = self._libreria(self._visualizador.spawn_robot, pose)
        else:
            self._ids[nombre] = 0

    def mover(self, nombre, q):
        """Pone el robot en q (6 angulos, rad)."""
        self._libreria(self._visualizador.move_robot, self._ids[nombre], list(q))

    def previsualizar(self, nombre, desde, puntos):
        """Mueve el robot simulado desde `desde` por cada punto de `puntos` (lista de q): DURACION_TRAMO s por tramo
        y como mucho MAX_PREVIEW s en total."""
        duracion_tramo = min(DURACION_TRAMO, MAX_PREVIEW / len(puntos))
        for punto in puntos:
            for k in range(1, PASOS_TRAMO + 1):
                t = k / PASOS_TRAMO
                self.mover(nombre, [a + (b - a) * t for a, b in zip(desde, punto)])
                time.sleep(duracion_tramo / PASOS_TRAMO)
            desde = punto

    def cerrar(self):
        """Cierra la ventana de PyBullet (solo si la abrimos nosotros). Se puede llamar varias veces."""
        if self._propio:
            try:
                import pybullet
                pybullet.disconnect()
            except Exception:                   # ya estaba cerrada: da igual
                pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()
