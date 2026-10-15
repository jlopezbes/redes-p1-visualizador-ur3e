"""
Comunicacion con un robot UR por sockets TCP, encima de red.ConexionTCP.

    UrPrimaria    interfaz primaria (puerto 30001): estado, errores y envio de ordenes URScript
    UrTiempoReal  interfaz de tiempo real (puerto 30003): solo el estado, a 500 Hz
    LectorUR      hilo que lee un robot y guarda solo el ultimo q

De este modulo hacia arriba solo sale ErrorUR (red caida, mensajes que no se entienden, robot sin enviar nada...).
ValueError solo significa "argumento mal puesto" (p. ej. un movej fuera de limites).

Estado fresco: un q solo vale si se recibio hace menos de PLAZO_ESTADO s. ClienteUR.estado_fresco() es el UNICO
sitio que lo decide: lo usan LectorUR.ultimo_q() (no entrega un q viejo) y UrPrimaria.movej() (no mueve a ciegas).

Formatos (todo big-endian):
  Primaria:
    mensaje      = [longitud int32][tipo uint8][cuerpo]        la longitud incluye la cabecera (5 bytes)
    tipo 16      = estado del robot; el cuerpo son subpaquetes con el mismo formato [longitud][tipo][datos]
    subpaquete 0 = modo del robot; subpaquete 1 = articulaciones: 6 x ">dddffffB" (41 bytes), q_actual primero
    tipo 20      = mensaje del robot (version, errores...)
  Tiempo real:
    paquete      = [longitud int32][time double][...], q_actual empieza siempre en el byte 252
"""
import math
import struct
import threading
import time

from red import ConexionTCP, ErrorRed

# ---- Primaria ----
CABECERA = 5            # int32 (longitud) + uint8 (tipo)
MAX_LONGITUD = 65536    # un mensaje mas largo significa que el buffer esta desalineado
TIPO_ROBOT_MESSAGE = 20
TIPO_ESTADO = 16
SUB_MODO = 0
SUB_JOINTS = 1
TAM_SUB_JOINTS = 251    # 5 + 6 * 41 (NO verificado con un robot real: si el robot manda otro tamano, ErrorUR)
BYTES_JOINT = 41

# ---- Tiempo real ----
CABECERA_TR = 4         # solo la longitud (int32)
OFFSET_Q_ACTUAL = 252   # 4 + 8 + 5 bloques de 6 doubles (q_target, qd_target, qdd_target, I_target, M_target)

# ---- Limites obligatorios en robot real ----
VELOCIDAD_MAX = 0.3     # rad/s
ACELERACION_MAX = 0.5   # rad/s2
MINIMO = 0.001          # rad/s y rad/s2: por debajo Python escribiria 1e-05 y no se sabe si URScript lo admite
LIMITE_Q_LECTURA = 2 * math.pi + 0.2    # rad: lo usa simulador.py (se revisa en la capa 4)

REINTENTO = 2.0         # s entre intentos de reconexion
PLAZO_ESTADO = 2.0      # s: sin un estado nuevo pasado este tiempo, el q ya no es actual y no se mueve el robot


class ErrorUR(Exception):
    """Fallo hablando con el robot. El mensaje dice con quien y que ha pasado."""


# ============ Funciones de decodificacion (sin red: se pueden probar con bytes) ============

def leer_estado(mensaje):
    """Mensaje tipo 16 -> dict con 'q' (6 q_actual) y, si vienen, 'ejecutando', 'protegido', 'emergencia', 'modo'.
    Lanza ErrorUR si el mensaje esta cortado o mal formado."""
    estado = {}
    pos = CABECERA
    try:
        while pos < len(mensaje):                       # subpaquetes: [longitud int32][tipo uint8][datos]
            tam, tipo = struct.unpack(">iB", mensaje[pos:pos + CABECERA])
            if tam < CABECERA or pos + tam > len(mensaje):
                raise ErrorUR("subpaquete {} se sale del mensaje".format(tipo))
            datos = mensaje[pos + CABECERA:pos + tam]
            if tipo == SUB_JOINTS:
                if len(datos) + CABECERA != TAM_SUB_JOINTS:
                    raise ErrorUR("subpaquete de articulaciones de {} bytes y se esperaban {}: otra version del robot? "
                                  "(ajusta TAM_SUB_JOINTS)".format(len(datos) + CABECERA, TAM_SUB_JOINTS))
                estado["q"] = [struct.unpack(">d", datos[BYTES_JOINT * j:BYTES_JOINT * j + 8])[0] for j in range(6)]
            elif tipo == SUB_MODO:
                _, _, _, _, emergencia, protegido, ejecutando, _, modo = struct.unpack(">Q???????B", datos[:16])
                estado.update(ejecutando=ejecutando, protegido=protegido, emergencia=emergencia, modo=modo)
            pos += tam
    except struct.error as e:
        raise ErrorUR("mensaje de estado mal formado: {}".format(e)) from e
    return estado


def leer_error(mensaje):
    """Mensaje tipo 20 -> texto si es un error (robotMessageType 6 o 10), o None para cualquier otro.
    Cualquier error o excepcion del robot cuenta, sea cual sea su reportLevel (parar es lo seguro).
    Lanza ErrorUR si el mensaje esta cortado."""
    # cabecera 5 + timestamp 8 + source 1 + robotMessageType 1 = 15
    if len(mensaje) < 15 or mensaje[14] not in (6, 10):
        return None
    try:
        numero = struct.unpack(">i", mensaje[15:19])[0]
    except struct.error as e:
        raise ErrorUR("mensaje de error del robot cortado: {}".format(e)) from e
    if mensaje[14] == 6:       # error code: code, argument, reportLevel, dataType, data (5 x int32) y texto
        return "error del robot (codigo {}): {}".format(numero, mensaje[35:].decode("ascii", "replace"))
    # excepcion de programa: linea, columna (2 x int32) y texto
    return "excepcion de programa (linea {}): {}".format(numero, mensaje[23:].decode("ascii", "replace"))


def es_punto_valido(q):
    """6 angulos en radianes entre -2*pi y 2*pi (evita enviar grados por error). Un q raro (None, texto...) no es valido."""
    try:
        return len(q) == 6 and all(abs(a) <= 2 * math.pi for a in q)
    except TypeError:
        return False


# ============ Clases ============

class ClienteUR:
    """Conexion con un UR: junta los bytes que llegan en un buffer y los corta en paquetes completos.
    Cada interfaz dice en _extraer() como se corta un paquete."""

    PUERTO = None

    def __init__(self, ip, puerto=None):
        self.red = ConexionTCP(ip, self.PUERTO if puerto is None else puerto)
        self._buffer = bytearray()
        self._t_estado = None       # time.monotonic() del ultimo estado valido de ESTA conexion

    def conectar(self):
        self._buffer.clear()        # lo que quedara de una conexion anterior no vale
        self._t_estado = None
        try:
            self.red.abrir()
        except ErrorRed as e:
            raise ErrorUR(str(e)) from e

    def cerrar(self):
        self.red.cerrar()

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, *_):
        self.cerrar()

    def estado_fresco(self):
        """True si llego un estado valido hace menos de PLAZO_ESTADO s. Es la unica definicion de 'datos actuales'."""
        return self._t_estado is not None and time.monotonic() - self._t_estado <= PLAZO_ESTADO

    def _extraer(self, buffer):
        raise NotImplementedError

    def _paquetes(self):
        """Generador de paquetes completos. Lanza ErrorUR si la red falla, si el robot calla o si el buffer se desalinea."""
        while True:
            try:
                self._buffer += self.red.recibir(65536)
            except ErrorRed as e:
                raise ErrorUR(str(e)) from e
            paquete = self._extraer(self._buffer)
            while paquete is not None:
                yield paquete
                paquete = self._extraer(self._buffer)


class UrPrimaria(ClienteUR):
    PUERTO = 30001

    def _extraer(self, buffer):
        """Corta un mensaje completo del buffer y devuelve (tipo, mensaje), o None si todavia no ha llegado entero."""
        if len(buffer) < CABECERA:
            return None
        longitud, tipo = struct.unpack(">iB", buffer[:CABECERA])
        if not CABECERA <= longitud <= MAX_LONGITUD:
            raise ErrorUR("{}: longitud imposible ({}): buffer desalineado".format(self.red.destino, longitud))
        if len(buffer) < longitud:
            return None
        mensaje = bytes(buffer[:longitud])
        del buffer[:longitud]
        return tipo, mensaje

    def mensajes(self):
        """Generador de (tipo, mensaje) de cada mensaje completo que llega. Los de estado se comprueban antes."""
        for tipo, mensaje in self._paquetes():
            if tipo == TIPO_ESTADO and "q" in leer_estado(mensaje):
                self._t_estado = time.monotonic()
            yield tipo, mensaje

    def estados(self):
        """Generador del q (6 angulos, rad) de cada mensaje de estado; el resto de mensajes se ignora."""
        for tipo, mensaje in self.mensajes():
            if tipo == TIPO_ESTADO:
                q = leer_estado(mensaje).get("q")
                if q:
                    yield q

    def enviar_script(self, texto):
        """Envia una linea de URScript. El salto de linea al final es obligatorio (lo anade esta funcion)."""
        try:
            self.red.enviar((texto + "\n").encode("utf-8"))
        except ErrorRed as e:
            raise ErrorUR(str(e)) from e

    def movej(self, q, *, velocidad, aceleracion):
        """Mueve las 6 articulaciones a q (rad). velocidad en rad/s, aceleracion en rad/s2.
        Se niega (ValueError) a enviar angulos fuera de [-2pi, 2pi] o velocidades por encima de los limites del robot
        real, y (ErrorUR) si no hay un estado fresco del robot: ante la duda, no mover.
        Los argumentos son solo por nombre para no mezclar velocidad y aceleracion (URScript: a=, v=)."""
        if not es_punto_valido(q):
            raise ValueError("angulos fuera de [-2pi, 2pi] (rad), o no son 6: {}".format(q))
        if not MINIMO <= velocidad <= VELOCIDAD_MAX:
            raise ValueError("velocidad {} rad/s fuera de [{}, {}]".format(velocidad, MINIMO, VELOCIDAD_MAX))
        if not MINIMO <= aceleracion <= ACELERACION_MAX:
            raise ValueError("aceleracion {} rad/s2 fuera de [{}, {}]".format(aceleracion, MINIMO, ACELERACION_MAX))
        if not self.estado_fresco():
            raise ErrorUR("{}: no se envia el movej porque no hay un estado del robot de hace menos de {} s".format(
                self.red.destino, PLAZO_ESTADO))
        self.enviar_script("movej([{}], a={}, v={})".format(
            ", ".join("{:.5f}".format(a) for a in q), aceleracion, velocidad))

    def stopj(self, aceleracion):
        """Frena las articulaciones con la deceleracion dada (rad/s2). No exige estado fresco: parar siempre se intenta."""
        self.enviar_script("stopj({})".format(aceleracion))


class UrTiempoReal(ClienteUR):
    PUERTO = 30003

    def _extraer(self, buffer):
        """Corta un paquete completo del buffer, o devuelve None si todavia no ha llegado entero."""
        if len(buffer) < CABECERA_TR:
            return None
        longitud = struct.unpack(">i", buffer[:CABECERA_TR])[0]
        if not OFFSET_Q_ACTUAL + 48 <= longitud <= MAX_LONGITUD:
            raise ErrorUR("{}: longitud imposible ({}): buffer desalineado".format(self.red.destino, longitud))
        if len(buffer) < longitud:
            return None
        paquete = bytes(buffer[:longitud])
        del buffer[:longitud]
        return paquete

    def estados(self):
        """Generador del q (6 angulos, rad) de cada paquete (unos 500 por segundo)."""
        for paquete in self._paquetes():
            self._t_estado = time.monotonic()
            yield list(struct.unpack(">6d", paquete[OFFSET_Q_ACTUAL:OFFSET_Q_ACTUAL + 48]))


class LectorUR(threading.Thread):
    """Hilo que lee un robot y guarda solo el ultimo q. Si la conexion se cae, reintenta cada REINTENTO s.
    `cliente` es una UrPrimaria o una UrTiempoReal sin conectar.
    El resto del programa pregunta con ultimo_q() y nunca toca el socket. Tambien puede mirar `recibidos` (estados
    recibidos en total) y `ultimo_error` (por que no hay datos, o None si todo va bien)."""

    def __init__(self, nombre, cliente):
        super().__init__(daemon=True)
        self.nombre = nombre
        self.cliente = cliente
        self.recibidos = 0
        self.ultimo_error = None
        self._q = None
        self._parar = threading.Event()

    def run(self):
        while not self._parar.is_set():
            try:
                with self.cliente:
                    for q in self.cliente.estados():
                        if self._q is None:
                            print("[{}] recibiendo estados de {}".format(self.nombre, self.cliente.red.destino))
                        self._q = q
                        self.ultimo_error = None
                        self.recibidos += 1
            except ErrorUR as e:
                if not self._parar.is_set():            # si nos han parado, el cierre del socket es normal
                    if str(e) != self.ultimo_error:     # una sola linea por motivo, no una por reintento
                        print("[{}] DESCONECTADO ({}). Reintentando en {} s...".format(self.nombre, e, REINTENTO))
                    self.ultimo_error = str(e)
                    self._q = None
            self._parar.wait(REINTENTO)

    def detener(self):
        """Pide parar y cierra el socket (sirve desde otro hilo): el hilo sale enseguida. Espera hasta 3 s a que acabe."""
        self._parar.set()
        self.cliente.cerrar()
        if self.is_alive():
            self.join(3.0)

    def ultimo_q(self):
        """Ultimo q recibido (6 angulos, rad), o None si no hay conexion o el estado no es fresco (ver estado_fresco)."""
        q = self._q                 # copia local: el hilo lector puede poner self._q a None entre la comprobacion y el uso
        return q if q is not None and self.cliente.estado_fresco() else None
