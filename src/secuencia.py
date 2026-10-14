"""
Enseñar y reproducir: una secuencia de puntos (cada uno, 6 angulos en rad) y quien la ejecuta en el robot.

    Secuencia    la lista de puntos, con guardar y cargar en JSON
    Reproductor  envia un movej por punto, sin enviar el siguiente hasta que el anterior termina, y supervisa errores

Fases del Reproductor (self.fase):
    LIBRE     no hay nada en marcha
    ENVIADO   se envio un movej y todavia no se ve el programa en marcha
    MOVIENDO  el robot esta ejecutando el movej (isProgramRunning)
    PARADA    algo fallo: se envio stopj y se espera 'reanudar' o 'cancelar'

El Reproductor no abre sockets ni ventanas: recibe un robot (UrPrimaria) y los mensajes que llegan de el.
"""
import json
import time

import ur

LIBRE, ENVIADO, MOVIENDO, PARADA = None, "enviado", "moviendo", "parada"

TOLERANCIA = 0.01         # rad: distancia maxima al objetivo para dar el punto por alcanzado
ESPERA_ARRANQUE = 2.0     # s: si el programa no arranca en este tiempo, la orden se da por rechazada


class Secuencia:
    def __init__(self):
        self.puntos = []

    def __len__(self):
        return len(self.puntos)

    def agregar(self, q):
        self.puntos.append(list(q))

    def borrar(self):
        self.puntos = []

    def guardar(self, ruta):
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.puntos, f)

    def cargar(self, ruta):
        """Lee la secuencia de un JSON. Lanza OSError, ValueError o TypeError y deja la secuencia como estaba."""
        with open(ruta, encoding="utf-8") as f:
            puntos = json.load(f)
        if not all(ur.es_punto_valido(p) for p in puntos):
            raise ValueError("hay puntos con angulos fuera de [-2pi, 2pi]")
        self.puntos = puntos


class Reproductor:
    def __init__(self, robot, secuencia, velocidad, aceleracion):
        """robot: UrPrimaria ya conectada. velocidad en rad/s y aceleracion en rad/s2 de los movej."""
        self.robot = robot
        self.secuencia = secuencia
        self.velocidad = velocidad
        self.aceleracion = aceleracion
        self.q = None                 # ultimo q_actual recibido (rad)
        self.ejecutando = False       # isProgramRunning
        self.protegido = False        # isProtectiveStopped
        self.i = None                 # indice del punto en curso
        self.fase = LIBRE
        self.t_envio = 0.0            # s (time.time) del ultimo movej enviado

    @property
    def ocupado(self):
        return self.fase in (ENVIADO, MOVIENDO)

    # ---------- ordenes del usuario ----------
    def guardar_punto(self):
        if self.q is None:
            print("Todavia no se ha recibido la posicion del robot")
        else:
            self.secuencia.agregar(self.q)
            print("Punto {} guardado".format(len(self.secuencia)))

    def ejecutar(self):
        if not len(self.secuencia) or self.q is None:
            print("Nada que ejecutar")
        elif self.fase == PARADA:
            print("Hay una parada pendiente: 'r' para reanudar o 'c' para cancelar")
        else:
            self.i = 0
            self._enviar_punto()

    def reanudar(self):
        if self.fase != PARADA:
            print("No hay ninguna parada que reanudar")
        elif self.protegido:
            print("El robot sigue en parada de proteccion")
        else:
            self._enviar_punto()

    def cancelar(self):
        if self.ocupado:
            self.robot.stopj(self.aceleracion)
        self.i = None
        self.fase = LIBRE
        print("Cancelado")

    def conexion_perdida(self):
        """Se llama cuando se cae la conexion: si habia un movimiento en curso, queda en parada."""
        if self.ocupado:
            self.fase = PARADA
            print("Secuencia detenida en el punto {}: 'r' para reanudar o 'c' para cancelar".format(self.i + 1))

    # ---------- supervision: se llama con cada mensaje del robot ----------
    def procesar(self, tipo, mensaje):
        if tipo == ur.TIPO_ROBOT_MESSAGE:
            error = ur.leer_error(mensaje)
            if error:
                print("ERROR del robot: " + error)
                if self.ocupado:
                    self._fallar(error)
            return
        if tipo != ur.TIPO_ESTADO:
            return
        estado = ur.leer_estado(mensaje)
        if "q" in estado:
            self.q = estado["q"]
        self.ejecutando = estado.get("ejecutando", self.ejecutando)
        self.protegido = estado.get("protegido", self.protegido)

        if self.ocupado and self.protegido:
            self._fallar("parada de proteccion")
        elif self.fase == ENVIADO:
            if self.ejecutando:
                self.fase = MOVIENDO
            elif time.time() - self.t_envio > ESPERA_ARRANQUE:
                if self._alcanzado():      # ya estaba en el punto: el programa acabo antes de verlo
                    self._siguiente()
                else:
                    self._fallar("el robot no ha aceptado la orden (modo Remoto? frenos liberados?)")
        elif self.fase == MOVIENDO and not self.ejecutando:
            if self._alcanzado():
                self._siguiente()
            else:
                self._fallar("el programa ha terminado pero el robot no ha llegado al punto")

    # ---------- internos ----------
    def _enviar_punto(self):
        punto = self.secuencia.puntos[self.i]
        try:
            self.robot.movej(punto, velocidad=self.velocidad, aceleracion=self.aceleracion)
        except ValueError as e:
            self._fallar("punto {}: {}".format(self.i + 1, e))
            return
        self.fase = ENVIADO
        self.t_envio = time.time()
        print("Punto {}/{} enviado".format(self.i + 1, len(self.secuencia)))

    def _alcanzado(self):
        return max(abs(a - b) for a, b in zip(self.q, self.secuencia.puntos[self.i])) < TOLERANCIA

    def _siguiente(self):
        self.i += 1
        if self.i < len(self.secuencia):
            self._enviar_punto()
        else:
            print("Secuencia terminada")
            self.i = None
            self.fase = LIBRE

    def _fallar(self, motivo):
        print("*** SECUENCIA DETENIDA: {}".format(motivo))
        try:
            self.robot.stopj(self.aceleracion)
        except OSError:
            pass
        self.fase = PARADA
        print("Escribe 'r' para reanudar desde el punto {} o 'c' para cancelar".format(self.i + 1))
