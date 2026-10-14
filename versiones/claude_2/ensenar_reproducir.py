"""
Ensenar y reproducir: guarda puntos del robot, los previsualiza en PyBullet y los ejecuta con movej.

    python ensenar_reproducir.py                    (URSim 1 por NAT: 127.0.0.1:30001)
    python ensenar_reproducir.py --ip 10.172.21.203

Se lee el estado y se envian las ordenes por el MISMO socket del puerto 30001.
Comandos (se escriben en la consola):
    g           guardar la posicion actual del robot como siguiente punto
    v           previsualizar la secuencia en PyBullet (el robot no se mueve)
    e           ejecutar la secuencia en el robot, punto a punto
    c           cancelar la ejecucion (o descartar una parada)
    r           reanudar desde el punto donde se paro por un error
    s [fichero] guardar la secuencia en un fichero (por defecto secuencia.json)
    l [fichero] cargar una secuencia de un fichero
    b           borrar todos los puntos
    q           salir
Limites obligatorios en robot real: 0,3 rad/s y 0,5 rad/s2.
"""
import argparse
import json
import math
import queue
import struct
import threading
import time

import primaria

VELOCIDAD = 0.3           # rad/s
ACELERACION = 0.5         # rad/s2
TOLERANCIA = 0.01         # rad: distancia maxima al objetivo para dar el punto por alcanzado
ESPERA_ARRANQUE = 2.0     # s: si el programa no arranca en este tiempo, la orden se da por rechazada
PASOS_PREVIEW = 20        # pasos por tramo de la previsualizacion (1 s por tramo)


def es_valido(punto):
    """6 angulos en radianes entre -2*pi y 2*pi (evita enviar grados por error)."""
    return len(punto) == 6 and all(abs(a) <= 2 * math.pi for a in punto)


class Aplicacion:
    def __init__(self, visualizador):
        self.visualizador = visualizador
        self.s = None
        self.q = None                 # ultimo q_actual
        self.ejecutando = False       # isProgramRunning
        self.protegido = False        # isProtectiveStopped
        self.secuencia = []           # lista de puntos (6 angulos cada uno)
        self.i = None                 # punto que se esta ejecutando
        self.fase = None              # None | "enviado" | "moviendo" | "parada"
        self.t_envio = 0.0
        self.comandos = queue.Queue()
        self.salir = False

    # ---------- envio de ordenes ----------
    def enviar(self, texto):
        self.s.sendall((texto + "\n").encode("utf-8"))      # el salto de linea es obligatorio

    def enviar_punto(self):
        punto = self.secuencia[self.i]
        if not es_valido(punto):
            self.fallar("punto {} con angulos fuera de [-2pi, 2pi]".format(self.i + 1))
            return
        self.enviar("movej([{}], a={}, v={})".format(
            ", ".join("{:.5f}".format(a) for a in punto), ACELERACION, VELOCIDAD))
        self.fase = "enviado"
        self.t_envio = time.time()
        print("Punto {}/{} enviado".format(self.i + 1, len(self.secuencia)))

    def alcanzado(self):
        return max(abs(a - b) for a, b in zip(self.q, self.secuencia[self.i])) < TOLERANCIA

    def siguiente(self):
        self.i += 1
        if self.i < len(self.secuencia):
            self.enviar_punto()
        else:
            print("Secuencia terminada")
            self.i = self.fase = None

    def fallar(self, motivo):
        print("*** SECUENCIA DETENIDA: {}".format(motivo))
        try:
            self.enviar("stopj({})".format(ACELERACION))
        except OSError:
            pass
        self.fase = "parada"
        print("Escribe 'r' para reanudar desde el punto {} o 'c' para cancelar".format(self.i + 1))

    # ---------- supervision: se llama con cada mensaje del robot ----------
    def procesar(self, tipo, mensaje):
        if tipo == primaria.TIPO_ROBOT_MESSAGE:
            error = primaria.leer_error(mensaje)
            if error:
                print("ERROR del robot: " + error)
                if self.fase in ("enviado", "moviendo"):
                    self.fallar(error)
            return
        if tipo != primaria.TIPO_ESTADO:
            return
        estado = primaria.leer_estado(mensaje)
        if "q" in estado:
            self.q = estado["q"]
            self.visualizador.move_robot(0, list(self.q))
        self.ejecutando = estado.get("ejecutando", self.ejecutando)
        self.protegido = estado.get("protegido", self.protegido)

        if self.fase in ("enviado", "moviendo") and self.protegido:
            self.fallar("parada de proteccion")
        elif self.fase == "enviado":
            if self.ejecutando:
                self.fase = "moviendo"
            elif time.time() - self.t_envio > ESPERA_ARRANQUE:
                if self.alcanzado():      # ya estaba en el punto: el programa acabo antes de verlo
                    self.siguiente()
                else:
                    self.fallar("el robot no ha aceptado la orden (modo Remoto? frenos liberados?)")
        elif self.fase == "moviendo" and not self.ejecutando:
            if self.alcanzado():
                self.siguiente()
            else:
                self.fallar("el programa ha terminado pero el robot no ha llegado al punto")

    # ---------- comandos de la consola ----------
    def leer_consola(self):
        while True:
            try:
                self.comandos.put(input().strip())
            except EOFError:
                return

    def atender_comandos(self):
        while not self.comandos.empty():
            self.comando(self.comandos.get())

    def comando(self, linea):
        orden, _, argumento = linea.partition(" ")
        argumento = argumento.strip() or "secuencia.json"
        ocupado = self.fase in ("enviado", "moviendo")
        if orden == "q":
            self.salir = True
        elif orden == "c":
            if ocupado:
                self.enviar("stopj({})".format(ACELERACION))
            self.i = self.fase = None
            print("Cancelado")
        elif ocupado:
            print("Robot en movimiento: solo 'c' (cancelar) o 'q'")
        elif orden == "g":
            if self.q is None:
                print("Todavia no se ha recibido la posicion del robot")
            else:
                self.secuencia.append(list(self.q))
                print("Punto {} guardado".format(len(self.secuencia)))
        elif orden == "b":
            self.secuencia = []
            print("Secuencia borrada")
        elif orden == "v":
            self.previsualizar()
        elif orden == "e":
            if not self.secuencia or self.q is None:
                print("Nada que ejecutar")
            elif self.fase == "parada":
                print("Hay una parada pendiente: 'r' para reanudar o 'c' para cancelar")
            else:
                self.i = 0
                self.enviar_punto()
        elif orden == "r":
            if self.fase != "parada":
                print("No hay ninguna parada que reanudar")
            elif self.protegido:
                print("El robot sigue en parada de proteccion")
            else:
                self.enviar_punto()
        elif orden == "s":
            with open(argumento, "w") as f:
                json.dump(self.secuencia, f)
            print("{} puntos guardados en {}".format(len(self.secuencia), argumento))
        elif orden == "l":
            try:
                with open(argumento) as f:
                    secuencia = json.load(f)
                if not all(es_valido(p) for p in secuencia):
                    raise ValueError("hay puntos con angulos fuera de [-2pi, 2pi]")
                self.secuencia = secuencia
                print("{} puntos cargados de {}".format(len(secuencia), argumento))
            except (OSError, ValueError, TypeError) as e:
                print("No se pudo cargar: {}".format(e))
        else:
            print("Comandos: g (guardar punto), v (previsualizar), e (ejecutar), c (cancelar), r (reanudar), "
                  "s/l [fichero] (salvar/cargar), b (borrar), q (salir)")

    def previsualizar(self):
        if not self.secuencia or self.q is None:
            print("Nada que previsualizar")
            return
        desde = self.q
        for punto in self.secuencia:
            for k in range(1, PASOS_PREVIEW + 1):
                t = k / PASOS_PREVIEW
                self.visualizador.move_robot(0, [a + (b - a) * t for a, b in zip(desde, punto)])
                time.sleep(1.0 / PASOS_PREVIEW)
            desde = punto

    # ---------- bucle principal ----------
    def ejecutar(self, ip, puerto):
        while not self.salir:
            try:
                with primaria.conectar(ip, puerto) as self.s:
                    print("Conectado a {}:{}. Escribe un comando (g, v, e, c, r, s, l, b, q)".format(ip, puerto))
                    try:
                        for tipo, mensaje in primaria.mensajes(self.s):
                            self.procesar(tipo, mensaje)
                            self.atender_comandos()
                            if self.salir:
                                break
                    except KeyboardInterrupt:
                        self.salir = True
                    if self.salir and self.fase in ("enviado", "moviendo"):
                        self.enviar("stopj({})".format(ACELERACION))     # al salir no se deja el robot en marcha
            except (OSError, ValueError, struct.error) as e:
                print("Conexion perdida ({}). Reintentando en 2 s...".format(e))
                if self.fase in ("enviado", "moviendo"):
                    self.fase = "parada"
                    print("Secuencia detenida en el punto {}: 'r' para reanudar o 'c' para cancelar".format(self.i + 1))
                time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=30001)
    args = parser.parse_args()

    from UR3e_rg2.dynamic_ur3e import UR3eRG2
    app = Aplicacion(UR3eRG2())
    threading.Thread(target=app.leer_consola, daemon=True).start()
    app.ejecutar(args.ip, args.puerto)


if __name__ == "__main__":
    main()
