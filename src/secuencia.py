"""
Enseñar y reproducir: una secuencia de puntos (cada uno, 6 angulos en rad) y quien la ejecuta en el robot.

    Secuencia    la lista de puntos, con guardar y cargar en JSON
    Reproductor  envia un movej por punto, sin enviar el siguiente hasta que el anterior termina, y supervisa errores

Fases del Reproductor (self.fase):
    LIBRE            no hay nada en marcha
    ENVIADO          se envio un movej y todavia no se ve el programa en marcha
    MOVIENDO         el robot esta ejecutando el movej (isProgramRunning)
    PARADA           algo fallo: se intento enviar stopj y se espera 'reanudar' o 'cancelar'

El Reproductor no abre sockets ni ventanas: recibe un robot (UrPrimaria) y los mensajes que llegan de el.
Hacia fuera no deja salir ErrorUR: lo trata dentro (parada, aviso y fase). De los ficheros solo sale ErrorSecuencia.
"""
import json
import time

import ur

LIBRE, ENVIADO, MOVIENDO, PARADA = None, "enviado", "moviendo", "parada"

TOLERANCIA = 0.01         # rad: distancia maxima al objetivo para dar el punto por alcanzado
ESPERA_ARRANQUE = 2.0     # s: si el programa no arranca en este tiempo, la orden se da por rechazada


class ErrorSecuencia(Exception):
    """No se puede leer o guardar el fichero de la secuencia. El mensaje dice cual y por que."""


class Secuencia:
    def __init__(self):
        self.puntos = []

    def __len__(self):
        return len(self.puntos)

    def guardar(self, ruta):
        """Lanza ErrorSecuencia si no se puede escribir."""
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(self.puntos, f)
        except OSError as e:
            raise ErrorSecuencia("no se puede guardar {}: {}".format(ruta, e)) from e

    def cargar(self, ruta):
        """Lee la secuencia de un JSON. Si algo falla lanza ErrorSecuencia y deja la secuencia como estaba."""
        try:
            with open(ruta, encoding="utf-8-sig") as f:        # utf-8-sig: tolera el BOM del Bloc de notas
                puntos = json.load(f)
        except (OSError, ValueError) as e:                     # ValueError incluye JSONDecodeError
            raise ErrorSecuencia("no se puede leer {}: {}".format(ruta, e)) from e
        if not isinstance(puntos, list) or not all(ur.es_punto_valido(p) for p in puntos):
            raise ErrorSecuencia("{}: debe ser una lista de puntos de 6 angulos en rad entre -2pi y 2pi".format(ruta))
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
        self.emergencia = False       # isEmergencyStopped
        self.modo = None              # robotMode: solo informativo, no bloquea nada (su decodificacion no esta verificada)
        self.i = None                 # indice del punto en curso
        self.fase = LIBRE
        self.t_envio = 0.0            # s (time.monotonic) del ultimo movej enviado

    @property
    def ocupado(self):
        """El robot se esta moviendo (o se acaba de ordenar): solo valen 'cancelar' y salir."""
        return self.fase in (ENVIADO, MOVIENDO)

    def _motivo_bloqueo(self):
        """None si se puede mover el robot; si no, el motivo. Solo bloquean la proteccion y la emergencia."""
        if self.emergencia:
            return "parada de emergencia: liberala en el pendant"
        if self.protegido:
            return "parada de proteccion: espera a que el robot la libere"
        return None

    # ---------- ordenes del usuario ----------
    def guardar_punto(self):
        if self.q is None:
            print("Todavia no se ha recibido la posicion del robot")
        elif not self.robot.estado_fresco():
            print("Sin datos actuales del robot: no guardo el punto")
        else:
            self.secuencia.puntos.append(list(self.q))
            print("Punto {} guardado".format(len(self.secuencia)))

    def ejecutar(self):
        if not len(self.secuencia) or self.q is None:
            print("Nada que ejecutar")
        elif self.fase == PARADA:
            print("Hay una parada pendiente: 'r' para reanudar o 'c' para cancelar")
        elif self.fase != LIBRE:
            print("Ya hay una secuencia en marcha")
        elif self._motivo_bloqueo():
            print("No se ejecuta: " + self._motivo_bloqueo())
        else:
            self.i = 0
            self._enviar_punto()

    def reanudar(self):
        if self.fase != PARADA:
            print("No hay ninguna parada que reanudar")
        elif self._motivo_bloqueo():
            print("No se reanuda: {}. El robot sigue en parada de proteccion o de emergencia".format(self._motivo_bloqueo()))
        else:
            self._enviar_punto()

    def cancelar(self):
        if self.ocupado:
            self._parar_robot()             # aunque falle, el Reproductor queda libre: no depende de la red
        self.i = None
        self.fase = LIBRE
        print("Cancelado")

    def conexion_perdida(self):
        """Se llama cuando se cae la conexion: si habia un movimiento en curso, queda en parada."""
        if self.ocupado:
            self._parar_robot()             # sin conexion fallara, y avisara de que el robot puede seguir moviendose
            self.fase = PARADA
            print("Secuencia interrumpida en el punto {}: 'r' para reanudar o 'c' para cancelar".format(self.i + 1))

    # ---------- supervision: se llama con cada mensaje del robot ----------
    def procesar(self, tipo, mensaje):
        try:
            if tipo == ur.TIPO_ROBOT_MESSAGE:
                error = ur.leer_error(mensaje)
                if error:
                    print("ERROR del robot: " + error)
                    if self.ocupado:
                        self._fallar(error)
            elif tipo == ur.TIPO_ESTADO:
                self._procesar_estado(ur.leer_estado(mensaje))
        except ur.ErrorUR as e:             # mensaje cortado o mal formado: no se sabe en que estado esta el robot
            print("Aviso: mensaje del robot no valido ({})".format(e))
            if self.ocupado:
                self._fallar("mensaje del robot no valido")

    def _procesar_estado(self, estado):
        if "q" in estado:
            self.q = estado["q"]
        self.ejecutando = estado.get("ejecutando", self.ejecutando)
        self.protegido = estado.get("protegido", self.protegido)
        self.emergencia = estado.get("emergencia", self.emergencia)
        self.modo = estado.get("modo", self.modo)

        if self.ocupado and self._motivo_bloqueo():
            self._fallar(self._motivo_bloqueo())
        elif self.fase == ENVIADO and self.ejecutando:
            self.fase = MOVIENDO
        elif self.ocupado and not self.ejecutando and (self.fase == MOVIENDO or time.monotonic() - self.t_envio > ESPERA_ARRANQUE):
            # el programa ha terminado (o nunca arranco): se comprueba si el robot esta en el punto
            if max(abs(a - b) for a, b in zip(self.q, self.secuencia.puntos[self.i])) < TOLERANCIA:
                self.i += 1
                if self.i < len(self.secuencia):
                    self._enviar_punto()
                else:
                    print("Secuencia terminada")
                    self.i = None
                    self.fase = LIBRE
            else:
                self._fallar("el robot no ha llegado al punto {} (modo {}; modo Remoto? frenos liberados?)".format(
                    self.i + 1, self.modo))

    # ---------- internos ----------
    def _enviar_punto(self):
        try:
            self.robot.movej(self.secuencia.puntos[self.i], velocidad=self.velocidad, aceleracion=self.aceleracion)
        except (ValueError, ur.ErrorUR) as e:       # punto/velocidad no validos, o sin estado fresco / sin conexion
            self._fallar("punto {}: {}".format(self.i + 1, e))
            return
        self.fase = ENVIADO
        self.t_envio = time.monotonic()
        print("Punto {}/{} enviado".format(self.i + 1, len(self.secuencia)))

    def _parar_robot(self):
        """Intenta frenar el robot (stopj). Si no puede, lo dice muy claro."""
        try:
            self.robot.stopj(self.aceleracion)
        except ur.ErrorUR as e:
            print("*** NO SE HA PODIDO ENVIAR LA PARADA ({}): el robot puede seguir moviendose hasta el punto {}. "
                  "PARALO CON EL BOTON DEL PENDANT ***".format(e, (self.i or 0) + 1))
        else:
            print("Robot detenido.")

    def _fallar(self, motivo):
        print("*** FALLO DE LA SECUENCIA: {}".format(motivo))
        self._parar_robot()
        self.fase = PARADA
        print("Escribe 'r' para reanudar desde el punto {} o 'c' para cancelar".format((self.i or 0) + 1))
