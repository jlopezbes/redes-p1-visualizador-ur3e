"""
Enseñar y reproducir: una secuencia de puntos (cada uno, 6 angulos en rad) y quien la ejecuta en el robot.

    Secuencia    la lista de puntos, con guardar y cargar en JSON
    Reproductor  envia un movej por punto, sin enviar el siguiente hasta que el anterior termina, y supervisa errores

Fases del Reproductor (self.fase):
    LIBRE            no hay nada en marcha
    ESPERANDO_ESTADO se ha pedido ejecutar, pero aun no hay un estado reciente del robot (ver ur.estado_fresco)
    ENVIADO          se envio un movej y todavia no se ve el programa en marcha
    MOVIENDO         el robot esta ejecutando el movej (isProgramRunning)
    PARADA           algo fallo: se intento enviar stopj y se espera 'reanudar' o 'cancelar'

El Reproductor no abre sockets ni ventanas: recibe un robot (UrPrimaria) y los mensajes que llegan de el.
Hacia fuera no deja salir ErrorUR: lo trata dentro (parada, aviso y fase). De los ficheros solo sale ErrorSecuencia.
"""
import json
import os
import time

import ur

LIBRE, ESPERANDO_ESTADO, ENVIADO, MOVIENDO, PARADA = None, "esperando", "enviado", "moviendo", "parada"

TOLERANCIA = 0.01         # rad: distancia maxima al objetivo para dar el punto por alcanzado
ESPERA_ARRANQUE = 2.0     # s: si el programa no arranca en este tiempo, la orden se da por rechazada
ESPERA_ESTADO = 3.0       # s: maximo que se espera a un estado reciente antes de enviar el primer movej
MAX_PUNTOS = 1000         # puntos de una secuencia cargada de un fichero
MAX_BYTES_FICHERO = 1000000     # B: un fichero mayor no es una secuencia


class ErrorSecuencia(Exception):
    """No se puede leer o guardar el fichero de la secuencia. El mensaje dice cual y por que."""


def _punto_valido(p):
    """Una lista de 6 numeros (no bool) dentro de [-2pi, 2pi]. Un NaN, un texto o un grado de mas no pasan."""
    return (isinstance(p, list) and len(p) == 6 and ur.es_punto_valido(p)
            and all(isinstance(a, (int, float)) and not isinstance(a, bool) for a in p))


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
        """Escribe en un temporal y lo renombra: si algo falla a mitad, el fichero anterior queda intacto.
        Lanza ErrorSecuencia si no se puede escribir."""
        temporal = ruta + ".tmp"
        try:
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(self.puntos, f)
            os.replace(temporal, ruta)
        except OSError as e:
            raise ErrorSecuencia("no se puede guardar {}: {}".format(ruta, e.strerror)) from e
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)

    def cargar(self, ruta):
        """Lee la secuencia de un JSON. Si algo falla lanza ErrorSecuencia con el motivo en español y deja la secuencia como estaba."""
        try:
            if os.path.getsize(ruta) > MAX_BYTES_FICHERO:
                raise ValueError("demasiado grande")
            with open(ruta, encoding="utf-8-sig") as f:        # utf-8-sig: tolera el BOM del Bloc de notas
                puntos = json.load(f)
        except OSError as e:
            raise ErrorSecuencia("no se puede abrir {}: {}".format(ruta, e.strerror)) from e
        except (ValueError, RecursionError) as e:              # incluye JSONDecodeError y UnicodeDecodeError
            raise ErrorSecuencia("{} no es un fichero de secuencia valido (JSON mal formado, vacio o enorme)".format(
                ruta)) from e
        if not (isinstance(puntos, list) and len(puntos) <= MAX_PUNTOS and all(_punto_valido(p) for p in puntos)):
            raise ErrorSecuencia("{}: debe ser una lista de como mucho {} puntos de 6 angulos en rad entre -2pi y 2pi".format(
                ruta, MAX_PUNTOS))
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
        self.t_espera = 0.0           # s (time.monotonic) de cuando se empezo a esperar un estado reciente

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
            self.secuencia.agregar(self.q)
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
            self._empezar()

    def reanudar(self):
        if self.fase != PARADA:
            print("No hay ninguna parada que reanudar")
        elif self._motivo_bloqueo():
            print("No se reanuda: {}. El robot sigue en parada de proteccion o de emergencia".format(self._motivo_bloqueo()))
        else:
            self._empezar()

    def cancelar(self):
        if self.ocupado:
            self._parar_robot()             # aunque falle, el Reproductor queda libre: no depende de la red
        self.i = None
        self.fase = LIBRE
        print("Cancelado")

    def conexion_perdida(self):
        """Se llama cuando se cae la conexion: si habia un movimiento en curso, queda en parada."""
        if self.fase == ESPERANDO_ESTADO:
            self.fase = LIBRE
            print("Conexion perdida: no se habia enviado ninguna orden")
        elif self.ocupado:
            self._parar_robot()             # sin conexion fallara, y avisara de que el robot puede seguir moviendose
            self.fase = PARADA
            print("Secuencia interrumpida en el punto {}: 'r' para reanudar o 'c' para cancelar".format(self.i + 1))

    # ---------- supervision: se llama con cada mensaje del robot ----------
    def procesar(self, tipo, mensaje):
        try:
            if tipo == ur.TIPO_ROBOT_MESSAGE:
                error, estado = ur.leer_error(mensaje), None
            elif tipo == ur.TIPO_ESTADO:
                error, estado = None, ur.leer_estado(mensaje)
            else:
                return
        except ur.ErrorUR as e:             # mensaje cortado o mal formado: no se sabe en que estado esta el robot
            if self.ocupado:
                self._fallar("mensaje del robot no valido: {}".format(e))
            else:
                print("Aviso: mensaje del robot no valido ({})".format(e))
            return
        if error:
            print("ERROR del robot: " + error)
            if self.ocupado:
                self._fallar(error)
        if estado is not None:
            self._procesar_estado(estado)

    def _procesar_estado(self, estado):
        if "q" in estado:
            self.q = estado["q"]
        self.ejecutando = estado.get("ejecutando", self.ejecutando)
        self.protegido = estado.get("protegido", self.protegido)
        self.emergencia = estado.get("emergencia", self.emergencia)
        self.modo = estado.get("modo", self.modo)

        if self.ocupado and self._motivo_bloqueo():
            self._fallar(self._motivo_bloqueo())
        elif "q" not in estado:             # sin posicion no se avanza ninguna fase
            return
        elif self.fase == ESPERANDO_ESTADO:
            if self.robot.estado_fresco():
                self._enviar_punto()
            elif time.monotonic() - self.t_espera > ESPERA_ESTADO:
                self._fallar("el robot no envia un estado reciente")
        elif self.fase == ENVIADO:
            if self.ejecutando:
                self.fase = MOVIENDO
            elif time.monotonic() - self.t_envio > ESPERA_ARRANQUE:
                if self._alcanzado():      # ya estaba en el punto: el programa acabo antes de verlo
                    self._siguiente()
                else:
                    self._fallar("el robot no ha aceptado la orden (modo {}; modo Remoto? frenos liberados?)".format(self.modo))
        elif self.fase == MOVIENDO and not self.ejecutando:
            if self._alcanzado():
                self._siguiente()
            else:
                self._fallar("el programa ha terminado pero el robot no ha llegado al punto")

    # ---------- internos ----------
    def _empezar(self):
        """Envia el punto actual si hay un estado reciente; si no, espera a que llegue uno (p. ej. tras una vista previa larga)."""
        if self.robot.estado_fresco():
            self._enviar_punto()
        else:
            self.fase = ESPERANDO_ESTADO
            self.t_espera = time.monotonic()
            print("Esperando un estado reciente del robot...")

    def _enviar_punto(self):
        if self.i is None or self.i >= len(self.secuencia):       # se borro o cargo otra secuencia durante la parada
            self.i = None
            self.fase = LIBRE
            print("La secuencia ha cambiado: usa 'e' para ejecutarla desde el principio")
            return
        if self._motivo_bloqueo():                  # p. ej. tras esperar un estado llego una parada de proteccion
            self._fallar(self._motivo_bloqueo())
            return
        try:
            self.robot.movej(self.secuencia.puntos[self.i], velocidad=self.velocidad, aceleracion=self.aceleracion)
        except (ValueError, ur.ErrorUR) as e:       # punto/velocidad no validos, o sin estado fresco / sin conexion
            self._fallar("punto {}: {}".format(self.i + 1, e))
            return
        self.fase = ENVIADO
        self.t_envio = time.monotonic()
        print("Punto {}/{} enviado".format(self.i + 1, len(self.secuencia)))

    def _alcanzado(self):
        if not self.robot.estado_fresco():          # con datos viejos no se da nada por alcanzado
            return False
        return max(abs(a - b) for a, b in zip(self.q, self.secuencia.puntos[self.i])) < TOLERANCIA

    def _siguiente(self):
        self.i += 1
        if self.i < len(self.secuencia):
            self._enviar_punto()
        else:
            print("Secuencia terminada")
            self.i = None
            self.fase = LIBRE

    def _parar_robot(self):
        """Intenta frenar el robot (stopj). Devuelve True si la orden salio. Si no, lo dice muy claro y devuelve False."""
        try:
            self.robot.stopj(self.aceleracion)
            return True
        except ur.ErrorUR as e:
            print("*** NO SE HA PODIDO ENVIAR LA PARADA ({}): el robot puede seguir moviendose hasta el punto {}. "
                  "PARALO CON EL BOTON DEL PENDANT ***".format(e, (self.i or 0) + 1))
            return False

    def _fallar(self, motivo):
        print("*** FALLO DE LA SECUENCIA: {}".format(motivo))
        if self._parar_robot():
            print("Robot detenido.")
        self.fase = PARADA
        print("Escribe 'r' para reanudar desde el punto {} o 'c' para cancelar".format((self.i or 0) + 1))
