"""
Ejercicio 4: leer un robot (origen) y mover otro (destino) para que copie su posicion.

    python ejercicio4_espejo.py --origen 127.0.0.1:30001 --destino 127.0.0.1:30011
    python ejercicio4_espejo.py --origen 127.0.0.1:30001 --destino 127.0.0.1:30011 --metodo rtde

Mueve el origen (pestaña Move de PolyScope, o ejercicio3) y el destino lo sigue. Sin PyBullet.
Metodos:
  speed:  (por defecto) speedj por la interfaz primaria cada --periodo segundos, con velocidad
          proporcional al error; sigue bien (~0.04 rad de retraso en URSim) y vale con puertos NAT.
  socket: reenvia un movej corto cada --periodo segundos (arranca y frena: va muy retrasado).
  rtde:   servoJ en bucle con ur_rtde (el mas suave para robots reales; el destino debe usar el
          puerto RTDE 30004, asi que en las VM con NAT solo sirve el robot 1 como destino).
"""
import argparse
import socket
import time

from ur_primary import LectorUR, parsear_robot, formatear_estado

UMBRAL = 0.005   # rad: por debajo de esta diferencia no se manda nada
GANANCIA = 10.0   # metodo speed: rad/s de velocidad por cada rad de error


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--origen", required=True, help="robot que se lee (ip o ip:puerto)")
    parser.add_argument("--destino", required=True, help="robot que se mueve (ip o ip:puerto)")
    parser.add_argument("--metodo", choices=["socket", "speed", "rtde"], default="speed")
    parser.add_argument("--periodo", type=float, default=0.1, help="segundos entre ordenes (socket y speed)")
    parser.add_argument("--hz", type=float, default=50.0, help="frecuencia del bucle servoJ (rtde)")
    args = parser.parse_args()

    ip_o, puerto_o = parsear_robot(args.origen)
    ip_d, puerto_d = parsear_robot(args.destino)
    origen = LectorUR("ORIGEN", ip_o, puerto_o)
    destino = LectorUR("DESTINO", ip_d, puerto_d)
    origen.start()
    destino.start()

    rtde_c = None
    if args.metodo == "rtde":
        import rtde_control
        rtde_c = rtde_control.RTDEControlInterface(ip_d)

    conexion = {"sock": None}   # conexion persistente al destino: evita reconectar en cada orden

    def enviar_script(script):
        try:
            if conexion["sock"] is None:
                conexion["sock"] = socket.create_connection((ip_d, puerto_d), timeout=5)
            conexion["sock"].sendall(script.encode("utf-8"))
        except OSError as e:
            print("Error enviando al destino: {}".format(e))
            if conexion["sock"]:
                conexion["sock"].close()
            conexion["sock"] = None

    ultimo_print = 0.0
    try:
        while True:
            e_o = origen.ultimo_estado()
            e_d = destino.ultimo_estado()
            if not (e_o and e_d and "joints" in e_o and "joints" in e_d):
                time.sleep(0.1)
                continue
            q_o = e_o["joints"]["q_actual"]
            q_d = e_d["joints"]["q_actual"]
            diferencia = max(abs(a - b) for a, b in zip(q_o, q_d))

            if args.metodo == "speed":
                # control proporcional: velocidad de cada joint proporcional al error, sin parar entre ordenes
                velocidades = [max(-1.5, min(1.5, GANANCIA * (a - b))) for a, b in zip(q_o, q_d)]
                script = "speedj([{}], a=3.0, t={})\n".format(
                    ", ".join("{:.4f}".format(v) for v in velocidades), 2 * args.periodo)
                enviar_script(script)
            elif diferencia > UMBRAL:
                if rtde_c:
                    dt = 1.0 / args.hz
                    # servoJ(q, vel, acel, tiempo, lookahead, ganancia): vel y acel no se usan
                    rtde_c.servoJ(list(q_o), 0.0, 0.0, dt, 0.1, 300)
                else:
                    enviar_script("movej([{}], a=1.0, v=1.0, t={})\n".format(
                        ", ".join(str(q) for q in q_o), args.periodo))

            if time.time() - ultimo_print > 1.0:
                print(formatear_estado("ORIGEN", e_o))
                print(formatear_estado("DESTINO", e_d))
                print("    diferencia maxima: {:.3f} rad\n".format(diferencia))
                ultimo_print = time.time()

            time.sleep(1.0 / args.hz if rtde_c else args.periodo)
    except KeyboardInterrupt:
        pass
    finally:
        if rtde_c:
            rtde_c.servoStop()
            rtde_c.stopScript()
        if args.metodo == "speed":
            enviar_script("stopj(2.0)\n")
        origen.parar()
        destino.parar()


if __name__ == "__main__":
    main()
