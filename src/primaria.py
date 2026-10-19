"""
Practica 1, aprobado: visualiza 1 o varios robots UR por la interfaz PRIMARIA (puerto 30001) en el simulador PyBullet.

    python -u src\\primaria.py

Los robots (nombre e IP) estan en datos\\robots.json: la IP se cambia solo alli. Pregunta cuantos robots visualizar
(Intro = 1). Parar con Ctrl+C. Fallos: el programa explica la causa y sale con codigo 1 (0 con Ctrl+C).
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))                       # carpeta src
sys.path.insert(0, os.path.join(AQUI, "librerias"))
ROBOTS = os.path.normpath(os.path.join(AQUI, "..", "datos", "robots.json"))      # relativa a este script, no a donde se lance

import simulador  # noqa: E402
import ur  # noqa: E402
from simulador import ErrorSimulador  # noqa: E402


def main():
    robots = ur.elegir_robots(ur.leer_robots(ROBOTS))
    simulador.visualizar({nombre: ur.ClienteUR(ip) for nombre, ip in robots.items()})


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:           # es la forma normal de parar
        pass
    except (ValueError, ErrorSimulador) as e:       # ValueError: robots.json o una IP mal puestos
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    # Cualquier otra excepcion es un fallo del programa: Python imprime el traceback y sale con codigo 1
