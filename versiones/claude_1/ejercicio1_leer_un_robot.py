"""
Ejercicio 1: leer un UR (URSim o real) y printear sus posiciones.

    python ejercicio1_leer_un_robot.py --robot 127.0.0.1
    python ejercicio1_leer_un_robot.py --robot 127.0.0.1 --gemelo      # con visualizador 3D
"""
import argparse
import time

from ur_primary import LectorUR, parsear_robot, formatear_estado


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--robot", default="127.0.0.1", help="ip o ip:puerto del robot (puerto por defecto 30001)")
    parser.add_argument("--hz", type=float, default=2.0, help="veces por segundo que se imprime")
    parser.add_argument("--completo", action="store_true", help="imprime tambien el subpaquete 0 y el resto de variables de los joints")
    parser.add_argument("--gemelo", action="store_true", help="muestra el robot en el visualizador 3D")
    args = parser.parse_args()

    ip, puerto = parsear_robot(args.robot)
    lector = LectorUR("UR", ip, puerto)
    lector.start()

    gemelo = None
    if args.gemelo:
        from gemelo import Gemelo
        gemelo = Gemelo()
        gemelo.añadir_robot("UR")

    try:
        while True:
            estado = lector.ultimo_estado()
            print(formatear_estado("UR", estado))
            if args.completo and estado:
                print("    modo:", estado.get("modo"))
                print("    joints:", estado.get("joints"))
            if gemelo and estado and "joints" in estado:
                gemelo.mover("UR", estado["joints"]["q_actual"])
            time.sleep(1.0 / args.hz)
    except KeyboardInterrupt:
        pass
    finally:
        lector.parar()


if __name__ == "__main__":
    main()
