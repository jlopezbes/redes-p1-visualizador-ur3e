"""
Practica 1: visualizador de un UR3e por TCP/IP. Punto de entrada; el trabajo esta en tareas.py.

    python src\\main.py primaria                         URSim 1 por NAT: 127.0.0.1:30001
    python src\\main.py primaria --ip 10.172.21.203      un robot del laboratorio
    python src\\main.py tiempo-real                      127.0.0.1:30003
    python src\\main.py varios                           los robots de src\\robots.json
    python src\\main.py varios --config otro.json
    python src\\main.py ensenar --v 0.1 --a 0.2          enseñar y reproducir (ENVIA movej: robot con frenos liberados)

Parar con Ctrl+C. Con un robot real: velocidades bajas y la zona despejada.
"""
import argparse
import os

import tareas
import ur

CARPETA = os.path.dirname(os.path.abspath(__file__))


def crear_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    orden = parser.add_subparsers(dest="orden")
    orden.required = True

    for nombre, puerto in (("primaria", ur.UrPrimaria.PUERTO), ("tiempo-real", ur.UrTiempoReal.PUERTO),
                           ("ensenar", ur.UrPrimaria.PUERTO)):
        p = orden.add_parser(nombre)
        p.add_argument("--ip", default="127.0.0.1")
        p.add_argument("--puerto", type=int, default=puerto)
        if nombre == "ensenar":
            p.add_argument("--v", dest="velocidad", type=float, default=0.1, help="rad/s (maximo 0,3)")
            p.add_argument("--a", dest="aceleracion", type=float, default=0.2, help="rad/s2 (maximo 0,5)")

    varios = orden.add_parser("varios")
    varios.add_argument("--config", default=os.path.join(CARPETA, "robots.json"))
    return parser


def main():
    parser = crear_parser()
    args = parser.parse_args()
    if args.orden == "ensenar":         # mejor rechazarlo al arrancar que al enviar el primer punto
        if not 0 < args.velocidad <= ur.VELOCIDAD_MAX:
            parser.error("--v debe estar en (0, {}] rad/s".format(ur.VELOCIDAD_MAX))
        if not 0 < args.aceleracion <= ur.ACELERACION_MAX:
            parser.error("--a debe estar en (0, {}] rad/s2".format(ur.ACELERACION_MAX))
    if args.orden == "primaria":
        tareas.visualizar_primaria(args.ip, args.puerto)
    elif args.orden == "tiempo-real":
        tareas.visualizar_tiempo_real(args.ip, args.puerto)
    elif args.orden == "varios":
        tareas.visualizar_varios(tareas.cargar_robots(args.config))
    else:
        tareas.ensenar_reproducir(args.ip, args.puerto, args.velocidad, args.aceleracion)


if __name__ == "__main__":
    main()
