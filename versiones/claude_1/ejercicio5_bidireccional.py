"""
Ejercicio 5: espejo bidireccional. Mueves cualquiera de los dos robots y el otro lo copia (y viceversa).

    python ejercicio5_bidireccional.py --primario 127.0.0.1:30001 --secundario 127.0.0.1:30011
    python ejercicio5_bidireccional.py --primario 10.172.21.203 --secundario 10.172.21.206 --vmax 0.5

El robot que se mueve (pestaña Move de PolyScope, ejercicio3, ...) pasa a ser el lider y el otro lo sigue
con speedj por la interfaz primaria. Cuando el lider se queda quieto y el seguidor lo alcanza, se suelta
el control y vuelve a esperar: el siguiente robot que se mueva sera el nuevo lider.
Si los dos se mueven a la vez, gana el primario. Al arrancar no se mueve nada hasta que alguno se mueva.
"""
import argparse
import socket
import time

from ur_primary import LectorUR, parsear_robot, formatear_estado

GANANCIA = 5.0        # rad/s de velocidad por cada rad de error
UMBRAL_VEL = 0.03     # rad/s: por encima de esto se considera que el robot se esta moviendo
UMBRAL_POS = 0.01     # rad: error maximo para dar por alcanzado al lider
VENTANA = 0.3         # s: ventana para medir la velocidad a partir de las posiciones
ESPERA_QUIETO = 0.5   # s que el lider debe estar quieto antes de soltar el control
MAX_QUIETO = 3.0      # s: si el lider esta quieto tanto tiempo se suelta aunque el seguidor no llegue
ENFRIAMIENTO = 1.0    # s tras soltar sin detectar lider (el seguidor aun esta frenando)


class Robot:
    """Un robot: su lector, su conexion para enviar ordenes y su velocidad medida."""

    def __init__(self, nombre, texto):
        self.nombre = nombre
        self.ip, self.puerto = parsear_robot(texto)
        self.lector = LectorUR(nombre.upper(), self.ip, self.puerto)
        self.sock = None
        self.q_ref = None
        self.t_ref = 0.0
        self.velocidad = 0.0

    def posicion(self):
        estado = self.lector.ultimo_estado()
        if estado and "joints" in estado:
            return estado["joints"]["q_actual"]
        return None

    def actualizar_velocidad(self, q, ahora):
        # velocidad = mayor desplazamiento de un joint en la ventana / tiempo de la ventana
        if self.q_ref is None:
            self.q_ref, self.t_ref = q, ahora
        elif ahora - self.t_ref >= VENTANA:
            self.velocidad = max(abs(a - b) for a, b in zip(q, self.q_ref)) / (ahora - self.t_ref)
            self.q_ref, self.t_ref = q, ahora

    def enviar(self, script):
        # conexion persistente: evita reconectar en cada orden
        try:
            if self.sock is None:
                self.sock = socket.create_connection((self.ip, self.puerto), timeout=5)
            self.sock.sendall(script.encode("utf-8"))
        except OSError as e:
            print("Error enviando a {}: {}".format(self.nombre, e))
            if self.sock:
                self.sock.close()
            self.sock = None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--primario", required=True, help="primer robot (ip o ip:puerto)")
    parser.add_argument("--secundario", required=True, help="segundo robot (ip o ip:puerto)")
    parser.add_argument("--vmax", type=float, default=1.0, help="velocidad maxima del seguidor por joint (rad/s)")
    parser.add_argument("--periodo", type=float, default=0.1, help="segundos entre ordenes")
    args = parser.parse_args()

    primario = Robot("primario", args.primario)
    secundario = Robot("secundario", args.secundario)
    robots = (primario, secundario)   # el orden decide quien gana si se mueven a la vez
    for r in robots:
        r.lector.start()

    lider = None
    seguidor = None
    quieto_desde = None
    libre_desde = 0.0
    ultimo_print = 0.0
    try:
        while True:
            ahora = time.time()
            q_p = primario.posicion()
            q_s = secundario.posicion()
            if q_p is None or q_s is None:
                time.sleep(0.1)
                continue
            primario.actualizar_velocidad(q_p, ahora)
            secundario.actualizar_velocidad(q_s, ahora)

            if lider is None:
                if ahora >= libre_desde:
                    for r in robots:
                        if r.velocidad > UMBRAL_VEL:
                            lider = r
                            seguidor = secundario if r is primario else primario
                            quieto_desde = None
                            print(">>> Lidera el {}: el {} lo sigue".format(lider.nombre, seguidor.nombre))
                            break
            else:
                q_l = q_p if lider is primario else q_s
                q_f = q_s if lider is primario else q_p
                error = [a - b for a, b in zip(q_l, q_f)]
                velocidades = [max(-args.vmax, min(args.vmax, GANANCIA * e)) for e in error]
                seguidor.enviar("speedj([{}], a=3.0, t={})\n".format(
                    ", ".join("{:.4f}".format(v) for v in velocidades), 2 * args.periodo))

                if lider.velocidad > UMBRAL_VEL:
                    quieto_desde = None
                elif quieto_desde is None:
                    quieto_desde = ahora
                if quieto_desde is not None:
                    tiempo_quieto = ahora - quieto_desde
                    alcanzado = max(abs(e) for e in error) < UMBRAL_POS
                    if (tiempo_quieto > ESPERA_QUIETO and alcanzado) or tiempo_quieto > MAX_QUIETO:
                        seguidor.enviar("stopj(2.0)\n")
                        print(">>> Soltado: esperando a que se mueva algun robot")
                        lider = None
                        seguidor = None
                        libre_desde = ahora + ENFRIAMIENTO

            if ahora - ultimo_print > 1.0:
                print(formatear_estado("PRIMARIO", primario.lector.ultimo_estado()))
                print(formatear_estado("SECUNDARIO", secundario.lector.ultimo_estado()))
                print("    lider: {}\n".format(lider.nombre if lider else "ninguno"))
                ultimo_print = ahora

            time.sleep(args.periodo)
    except KeyboardInterrupt:
        pass
    finally:
        for r in robots:
            r.enviar("stopj(2.0)\n")
            r.lector.parar()


if __name__ == "__main__":
    main()
