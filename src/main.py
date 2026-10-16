"""
Practica 1: visualizador de un UR3e por TCP/IP. Punto de entrada; el trabajo esta en tareas.py.

    python src\\main.py primaria                         el primer robot de src\\robots.json (puerto 30001)
    python src\\main.py primaria --robot robot2          otro robot de ese JSON, por nombre
    python src\\main.py primaria --ip 10.172.21.203      una IP suelta, sin mirar el JSON
    python src\\main.py tiempo-real                      el primer robot del JSON, puerto 30003
    python src\\main.py varios                           todos los robots de src\\robots.json
    python src\\main.py ensenar --v 0.1 --a 0.2          enseñar y reproducir (ENVIA movej: robot con frenos liberados)
    (todas aceptan --config otro.json)

Parar con Ctrl+C. Con un robot real: velocidades bajas y la zona despejada.
Codigos de salida: 0 normal o Ctrl+C; 1 fallo al hablar con el robot o con el simulador; 2 argumentos o
configuracion (robots.json) mal puestos.
"""
import argparse
import os
import sys

import tareas
import ur
from red import ErrorRed
from simulador import ErrorSimulador


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    orden = parser.add_subparsers(dest="orden")
    orden.required = True

    config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "robots.json")

    for nombre, puerto in (("primaria", ur.PUERTO_PRIMARIA), ("tiempo-real", ur.PUERTO_TIEMPO_REAL),
                           ("ensenar", ur.PUERTO_PRIMARIA)):
        p = orden.add_parser(nombre)
        p.add_argument("--config", default=config, help="fichero JSON de robots")
        quien = p.add_mutually_exclusive_group()        # sin ninguno de los dos: el primer robot del JSON
        quien.add_argument("--robot", help="nombre de un robot del JSON")
        quien.add_argument("--ip", help="IP del robot, p. ej. 10.172.21.203 (no un nombre); ignora el JSON")
        p.add_argument("--puerto", type=int, default=puerto, help="puerto TCP (1-65535)")
        if nombre == "ensenar":
            p.add_argument("--v", dest="velocidad", type=float, default=0.1, help="rad/s (0,001 a 0,3)")
            p.add_argument("--a", dest="aceleracion", type=float, default=0.2, help="rad/s2 (0,001 a 0,5)")

    varios = orden.add_parser("varios")
    varios.add_argument("--config", default=config, help="fichero JSON de robots")

    args = parser.parse_args()
    if args.orden == "ensenar":         # mejor rechazarlo al arrancar que al enviar el primer punto
        if not ur.MINIMO <= args.velocidad <= ur.VELOCIDAD_MAX:
            parser.error("--v debe estar en [{}, {}] rad/s".format(ur.MINIMO, ur.VELOCIDAD_MAX))
        if not ur.MINIMO <= args.aceleracion <= ur.ACELERACION_MAX:
            parser.error("--a debe estar en [{}, {}] rad/s2".format(ur.MINIMO, ur.ACELERACION_MAX))
    try:
        if args.orden == "varios":
            tareas.visualizar(tareas.cargar_robots(args.config))
            return
        nombre, ip = "robot", args.ip
        if ip is None:                  # --ip "" no es "no puesta": ClienteUR la rechaza
            nombre, ip = tareas.ip_robot(args.config, args.robot)
        if args.orden == "primaria":
            tareas.visualizar({nombre: ur.ClienteUR(ip, args.puerto)})
        elif args.orden == "tiempo-real":
            tareas.visualizar({nombre: ur.ClienteUR(ip, args.puerto, tiempo_real=True)})
        else:
            tareas.ensenar_reproducir(ip, args.puerto, args.velocidad, args.aceleracion)
    except KeyboardInterrupt:           # es la forma normal de parar
        pass
    except (ValueError, ErrorRed, ErrorSimulador) as e:     # ValueError: IP, puerto o robots.json mal puestos
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(2 if isinstance(e, ValueError) else 1)
    # Cualquier otra excepcion es un fallo del programa: Python imprime el traceback y sale con codigo 1


if __name__ == "__main__":
    main()
    