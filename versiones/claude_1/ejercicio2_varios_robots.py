"""
Ejercicio 2: leer varios UR a la vez (un hilo lector por robot) y mostrarlos en el mismo gemelo.

    python ejercicio2_varios_robots.py --robots 10.172.21.203 10.172.21.206
    python ejercicio2_varios_robots.py --robots 127.0.0.1:30001 127.0.0.1:30011 --gemelo

El visualizador (PyBullet) se actualiza siempre desde el hilo principal; los hilos
solo guardan el ultimo estado recibido de cada robot.
"""
import argparse
import time

from ur_primary import LectorUR, parsear_robot, formatear_estado


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--robots", nargs="+", required=True, help="ip o ip:puerto de cada robot")
    parser.add_argument("--hz", type=float, default=10.0, help="frecuencia de refresco")
    parser.add_argument("--imprimir-cada", type=float, default=1.0, help="segundos entre prints (0 = no imprimir)")
    parser.add_argument("--gemelo", action="store_true", help="muestra los robots en el visualizador 3D")
    args = parser.parse_args()

    lectores = []
    for i, texto in enumerate(args.robots):
        ip, puerto = parsear_robot(texto)
        lectores.append(LectorUR("UR{}".format(i + 1), ip, puerto))

    gemelo = None
    if args.gemelo:
        from gemelo import Gemelo
        gemelo = Gemelo()
        for lector in lectores:
            gemelo.añadir_robot(lector.nombre)

    for lector in lectores:
        lector.start()

    ultimo_print = 0.0
    try:
        while True:
            ahora = time.time()
            imprimir = args.imprimir_cada > 0 and ahora - ultimo_print >= args.imprimir_cada
            for lector in lectores:
                estado = lector.ultimo_estado()
                if imprimir:
                    print(formatear_estado(lector.nombre, estado))
                if gemelo and estado and "joints" in estado:
                    gemelo.mover(lector.nombre, estado["joints"]["q_actual"])
            if imprimir:
                ultimo_print = ahora
                print()
            time.sleep(1.0 / args.hz)
    except KeyboardInterrupt:
        pass
    finally:
        for lector in lectores:
            lector.parar()


if __name__ == "__main__":
    main()
