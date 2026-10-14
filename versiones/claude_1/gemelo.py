"""
Visualizador 3D (gemelo digital) basado en UR3e_rg2 / PyBullet.

Instalacion: pip install "VIEJO COMUNICACIONES/UR3e_rg2-0.1.tar.gz"
El import es perezoso para que el resto de la practica funcione sin PyBullet (--sin-gemelo).
"""


class Gemelo:
    def __init__(self, separacion=1.0):
        from UR3e_rg2.dynamic_ur3e import UR3eRG2
        self.visualizacion = UR3eRG2()
        self.separacion = separacion
        self.ids = {}   # nombre del robot -> id en el visualizador

    def añadir_robot(self, nombre):
        """El primer robot es el que trae el visualizador (id 0); los demas se colocan en fila sobre X."""
        if not self.ids:
            self.ids[nombre] = 0
        else:
            x = self.separacion * len(self.ids)
            self.ids[nombre] = self.visualizacion.spawn_robot([x, 0, 0, 0, 0, 0])

    def mover(self, nombre, joints):
        self.visualizacion.move_robot(self.ids[nombre], list(joints))
