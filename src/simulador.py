"""
El visualizador PyBullet de la libreria UR3e_rg2 (UR3eRG2), con los detalles que la libreria no esconde.

Lo que hace esta clase por nosotros:
  - Los robots se llaman por nombre ("robot1"), no por el id de PyBullet.
  - El primer robot ya existe (id 0, en el origen): solo se recoloca si su base no esta en el origen.
    Los demas se crean con spawn_robot, que devuelve ids que no son consecutivos.
  - mover() pasa una copia del q: UR3eRG2.move_robot alarga la lista que recibe.
  - previsualizar() mueve el robot de punto a punto por interpolacion lineal, sin enviar nada al robot real.
  - Cualquier fallo de la libreria (no instalada, ventana cerrada, pybullet.error...) sale como ErrorSimulador:
    es el unico sitio donde se captura Exception a secas, porque PyBullet no tiene una jerarquia de errores util.
    Los argumentos mal puestos (q con nan, 5 angulos, un robot que no existe) son ValueError.

PyBullet no es seguro entre hilos: Simulador se usa siempre desde el hilo principal.
"""
import time

from ur import LIMITE_Q_LECTURA

ORIGEN = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]     # [x, y, z, roll, pitch, yaw] de la base: m y rad
LIMITE_POSE = 100.0                         # m y rad: una base mas lejos es casi seguro un error de escritura
MAX_PREVIEW = 20.0                          # s: una vista previa no bloquea el hilo principal mas que esto


class ErrorSimulador(Exception):
    """El simulador no funciona: falta la libreria, se cerro la ventana... El mensaje dice que ha pasado."""


def _seis_numeros(valores, limite, que):
    """Comprueba que valores son 6 numeros finitos con |valor| <= limite (nan e inf no cumplen la comparacion)."""
    if not (len(valores) == 6 and all(isinstance(a, (int, float)) and abs(a) <= limite for a in valores)):
        raise ValueError("{} debe ser 6 numeros finitos (|valor| <= {}): {}".format(que, round(limite, 2), valores))


class Simulador:
    def __init__(self, visualizador=None):
        """visualizador: algo con move_robot(id, q) y spawn_robot(pose). Si no se da, abre la ventana de UR3eRG2."""
        self._propio = visualizador is None
        self._cerrado = False
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

    def agregar_robot(self, nombre, posicion=None):
        """Anade un robot. posicion = [x, y, z, roll, pitch, yaw] de su base (m y rad); por defecto, el origen."""
        posicion = list(posicion) if posicion is not None else list(ORIGEN)
        _seis_numeros(posicion, LIMITE_POSE, "la posicion de la base")
        if nombre in self._ids:
            raise ValueError("ya hay un robot llamado {}".format(nombre))
        if not self._ids:
            id_robot = 0
            if posicion != ORIGEN:
                self._libreria(self._colocar_el_primero, posicion)
        else:
            id_robot = self._libreria(self._visualizador.spawn_robot, posicion)
        self._ids[nombre] = id_robot

    def _colocar_el_primero(self, posicion):
        import pybullet
        pybullet.resetBasePositionAndOrientation(0, posicion[:3], pybullet.getQuaternionFromEuler(posicion[3:]))

    def mover(self, nombre, q):
        """Pone el robot en q (6 angulos, rad)."""
        if nombre not in self._ids:
            raise ValueError("no hay un robot llamado {}".format(nombre))
        _seis_numeros(q, LIMITE_Q_LECTURA, "q")
        self._libreria(self._visualizador.move_robot, self._ids[nombre], list(q))

    def previsualizar(self, nombre, desde, puntos, pasos=20, duracion_tramo=1.0):
        """Mueve el robot simulado desde `desde` por cada punto de `puntos` (lista de q), `duracion_tramo` s por tramo
        (en total, como mucho MAX_PREVIEW s)."""
        if not puntos:
            return
        duracion_tramo = min(duracion_tramo, MAX_PREVIEW / len(puntos))
        for punto in puntos:
            for k in range(1, pasos + 1):
                t = k / pasos
                self.mover(nombre, [a + (b - a) * t for a, b in zip(desde, punto)])
                time.sleep(duracion_tramo / pasos)
            desde = punto

    def cerrar(self):
        """Cierra la ventana de PyBullet (solo si la abrimos nosotros). Se puede llamar varias veces."""
        if self._propio and not self._cerrado:
            self._cerrado = True
            try:
                import pybullet
                pybullet.disconnect()
            except Exception:                   # ya estaba cerrada: da igual
                pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()
