"""
Visualiza varios UR a la vez en la misma ventana de PyBullet (interfaz primaria, un hilo por robot).

    python varios_robots.py                         (lee robots.json)
    python varios_robots.py --config otro.json

Los robots se definen en el fichero de configuracion (ver robots.json), sin tocar el codigo:
    {"nombre": "robot1", "ip": "127.0.0.1", "puerto": 30001, "posicion": [x, y, z, roll, pitch, yaw]}
Cada hilo tiene su socket y su buffer y solo guarda el ultimo q. PyBullet se usa solo desde el bucle principal.
Si un robot se cae, su robot simulado se queda quieto, se avisa por consola y se reintenta la conexion.
"""
import argparse
import json
import struct
import threading
import time

import primaria

HZ_DIBUJO = 30


class Robot(threading.Thread):
    def __init__(self, config):
        super().__init__(daemon=True)
        self.nombre = config["nombre"]
        self.ip = config["ip"]
        self.puerto = config["puerto"]
        self.posicion = config["posicion"]
        self.id = None              # identificador en PyBullet
        self._lock = threading.Lock()
        self._q = None
        self._conectado = False

    def run(self):
        while True:
            try:
                with primaria.conectar(self.ip, self.puerto) as s:
                    print("[{}] conectado a {}:{}".format(self.nombre, self.ip, self.puerto))
                    for tipo, mensaje in primaria.mensajes(s):
                        if tipo != primaria.TIPO_ESTADO:
                            continue
                        q = primaria.leer_estado(mensaje).get("q")
                        if q:
                            with self._lock:
                                self._q = q
                                self._conectado = True
            except (OSError, ValueError, struct.error) as e:
                print("[{}] DESCONECTADO ({}). Reintentando en 2 s...".format(self.nombre, e))
            with self._lock:
                self._conectado = False
            time.sleep(2)

    def ultimo_q(self):
        """Ultimo q recibido, o None si el robot no esta conectado."""
        with self._lock:
            return list(self._q) if self._conectado else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="robots.json")
    args = parser.parse_args()
    with open(args.config, encoding="utf-8-sig") as f:      # utf-8-sig: tolera el BOM que anade el Bloc de notas
        robots = [Robot(c) for c in json.load(f)]

    import pybullet
    from UR3e_rg2.dynamic_ur3e import UR3eRG2
    visualizador = UR3eRG2()
    for i, r in enumerate(robots):
        if i == 0:      # el primer robot es el que trae el visualizador (id 0): solo hay que colocarlo
            r.id = 0
            pybullet.resetBasePositionAndOrientation(
                0, r.posicion[:3], pybullet.getQuaternionFromEuler(r.posicion[3:]))
        else:
            r.id = visualizador.spawn_robot(r.posicion)
    for r in robots:
        r.start()

    try:
        while True:
            for r in robots:
                q = r.ultimo_q()
                if q:           # desconectado: no se mueve
                    visualizador.move_robot(r.id, q)
            time.sleep(1.0 / HZ_DIBUJO)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
