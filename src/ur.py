"""
Comunicacion con un robot UR por sockets TCP, encima de red.ConexionTCP.

    UrPrimaria    interfaz primaria (puerto 30001): estado, errores y envio de ordenes URScript
    UrTiempoReal  interfaz de tiempo real (puerto 30003): solo el estado, a 500 Hz
    LectorUR      hilo que lee un robot y guarda solo el ultimo q

Errores: de este modulo hacia arriba solo sale ErrorUR (red caida, mensajes que no se entienden, robot sin
enviar estados...). ErrorRed, struct.error y los ValueError de decodificacion se convierten aqui, con
`raise ... from e`. ValueError/TypeError solo significan "argumento mal puesto" (p. ej. un movej fuera de limites).

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
import traceback

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
MAX_TEXTO_ERROR = 300   # caracteres del texto de un error del robot que se conservan

# ---- Tiempo real ----
CABECERA_TR = 4         # solo la longitud (int32)
OFFSET_Q_ACTUAL = 252   # 4 + 8 + 5 bloques de 6 doubles (q_target, qd_target, qdd_target, I_target, M_target)

# ---- Limites obligatorios en robot real ----
VELOCIDAD_MAX = 0.3     # rad/s
ACELERACION_MAX = 0.5   # rad/s2
LIMITE_Q_ENVIO = 2 * math.pi            # rad: es_punto_valido() no deja ENVIAR angulos fuera de +-2*pi
LIMITE_Q_LECTURA = 2 * math.pi + 0.2    # rad: al LEER se admite un margen, por si el robot esta en el tope de una articulacion

REINTENTO = 2.0         # s entre intentos de reconexion
PLAZO_ESTADO = 2.0      # s: sin un estado nuevo pasado este tiempo, el q ya no es actual y no se mueve el robot


class ErrorUR(Exception):
    """Fallo hablando con el robot. El mensaje dice con quien y que ha pasado."""


# ============ Funciones de decodificacion (sin red: se pueden probar con bytes) ============
# Las funciones sueltas pueden lanzar struct.error o ValueError con bytes cortados o absurdos; leer_estado,
# leer_error y ClienteUR los convierten en ErrorUR antes de que salgan del modulo.

def extraer_mensaje(buffer):
    """Si el buffer (bytearray) empieza por un mensaje completo, lo corta y devuelve (tipo, mensaje).
    Si todavia no ha llegado entero devuelve None. Lanza ValueError si la longitud es imposible."""
    if len(buffer) < CABECERA:
        return None
    longitud, tipo = struct.unpack(">iB", buffer[:CABECERA])
    if longitud < CABECERA or longitud > MAX_LONGITUD:
        raise ValueError("longitud imposible ({}): buffer desalineado".format(longitud))
    if len(buffer) < longitud:
        return None
    mensaje = bytes(buffer[:longitud])
    del buffer[:longitud]
    return tipo, mensaje


def subpaquetes(mensaje):
    """Recorre un mensaje de estado (tipo 16) y devuelve [(tipo, datos), ...] de sus subpaquetes."""
    resultado = []
    pos = CABECERA
    while pos < len(mensaje):
        tam, tipo = struct.unpack(">iB", mensaje[pos:pos + CABECERA])
        if tam < CABECERA or pos + tam > len(mensaje):
            raise ValueError("subpaquete {} se sale del mensaje".format(tipo))
        resultado.append((tipo, mensaje[pos + CABECERA:pos + tam]))
        pos += tam
    return resultado


def _q_valido(q):
    """Devuelve q si los 6 angulos son finitos y estan en +-LIMITE_Q_LECTURA; si no, ErrorUR."""
    if not all(abs(a) <= LIMITE_Q_LECTURA for a in q):      # nan e inf tambien incumplen la comparacion
        raise ErrorUR("posicion del robot no valida (rad): {}".format(q))
    return q


def leer_q_actual(datos):
    """Datos del subpaquete 1 -> lista con los 6 q_actual (rad)."""
    if len(datos) + CABECERA != TAM_SUB_JOINTS:
        raise ErrorUR("subpaquete de articulaciones de {} bytes y se esperaban {}: otra version del robot? "
                      "(ajusta TAM_SUB_JOINTS)".format(len(datos) + CABECERA, TAM_SUB_JOINTS))
    return _q_valido([struct.unpack(">d", datos[BYTES_JOINT * j:BYTES_JOINT * j + 8])[0] for j in range(6)])


def leer_modo(datos):
    """Datos del subpaquete 0 -> (isProgramRunning, isProtectiveStopped, isEmergencyStopped, robotMode)."""
    (_, _, _, _, emergencia, protegido, ejecutando, _, modo
     ) = struct.unpack(">Q???????B", datos[:16])
    return ejecutando, protegido, emergencia, modo


def leer_estado(mensaje):
    """Mensaje tipo 16 -> dict con 'q' (6 q_actual) y, si vienen, 'ejecutando', 'protegido', 'emergencia', 'modo'.
    Lanza ErrorUR si el mensaje esta cortado, mal formado o trae una posicion no valida."""
    estado = {}
    try:
        for tipo, datos in subpaquetes(mensaje):
            if tipo == SUB_JOINTS:
                estado["q"] = leer_q_actual(datos)
            elif tipo == SUB_MODO:
                estado["ejecutando"], estado["protegido"], estado["emergencia"], estado["modo"] = leer_modo(datos)
    except (struct.error, ValueError) as e:
        raise ErrorUR("mensaje de estado mal formado: {}".format(e)) from e
    return estado


def _texto_seguro(datos):
    """Texto que manda el robot -> solo ASCII imprimible y como mucho MAX_TEXTO_ERROR caracteres (puede venir cualquier cosa)."""
    return "".join(chr(b) if 32 <= b < 127 else "?" for b in datos[:MAX_TEXTO_ERROR])


def leer_error(mensaje):
    """Mensaje tipo 20 -> texto si es un error (robotMessageType 6 o 10), o None para cualquier otro.
    Cualquier error o excepcion del robot cuenta, sea cual sea su reportLevel (parar es lo seguro).
    Lanza ErrorUR si el mensaje esta cortado."""
    # cabecera 5 + timestamp 8 + source 1 + robotMessageType 1 = 15
    if len(mensaje) < 15:
        return None
    subtipo = mensaje[14]
    try:
        if subtipo == 6:       # error code: code, argument, reportLevel, dataType, data (5 x int32) y texto
            return "error del robot (codigo {}): {}".format(
                struct.unpack(">i", mensaje[15:19])[0], _texto_seguro(mensaje[35:]))
        if subtipo == 10:      # excepcion de programa: linea, columna (2 x int32) y texto
            return "excepcion de programa (linea {}): {}".format(
                struct.unpack(">i", mensaje[15:19])[0], _texto_seguro(mensaje[23:]))
    except struct.error as e:
        raise ErrorUR("mensaje de error del robot cortado: {}".format(e)) from e
    return None


def extraer_paquete(buffer):
    """Tiempo real: si el buffer (bytearray) empieza por un paquete completo, lo corta y lo devuelve; si no, None.
    Lanza ValueError si la longitud es imposible."""
    if len(buffer) < CABECERA_TR:
        return None
    longitud = struct.unpack(">i", buffer[:CABECERA_TR])[0]
    if longitud < OFFSET_Q_ACTUAL + 48 or longitud > MAX_LONGITUD:
        raise ValueError("longitud imposible ({}): buffer desalineado".format(longitud))
    if len(buffer) < longitud:
        return None
    paquete = bytes(buffer[:longitud])
    del buffer[:longitud]
    return paquete


def leer_q_tiempo_real(paquete):
    """Paquete de tiempo real (ya cortado por extraer_paquete) -> lista con los 6 q_actual (rad)."""
    return _q_valido(list(struct.unpack(">6d", paquete[OFFSET_Q_ACTUAL:OFFSET_Q_ACTUAL + 48])))


def es_punto_valido(q):
    """6 angulos en radianes entre -2*pi y 2*pi (evita enviar grados por error). Un q raro (None, texto...) no es valido."""
    try:
        return len(q) == 6 and all(abs(a) <= LIMITE_Q_ENVIO for a in q)
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

    def marcar_estado(self):
        """Se llama cada vez que llega un estado valido (con su q)."""
        self._t_estado = time.monotonic()

    def estado_fresco(self):
        """True si llego un estado valido hace menos de PLAZO_ESTADO s. Es la unica definicion de 'datos actuales'."""
        return self._t_estado is not None and time.monotonic() - self._t_estado <= PLAZO_ESTADO

    def _extraer(self, buffer):
        raise NotImplementedError

    def _paquetes(self):
        """Generador de paquetes completos. Lanza ErrorUR si la red falla, si el buffer se desalinea o si pasan
        PLAZO_ESTADO s sin un estado (aunque lleguen otros bytes: un robot que gotea no mantiene la conexion 'viva')."""
        inicio = time.monotonic()
        while True:
            try:
                self._buffer += self.red.recibir(65536)
            except ErrorRed as e:
                raise ErrorUR(str(e)) from e
            while True:
                try:
                    paquete = self._extraer(self._buffer)
                except ValueError as e:
                    raise ErrorUR("{}: {}".format(self.red.destino, e)) from e
                if paquete is None:
                    break
                yield paquete
            if time.monotonic() - max(inicio, self._t_estado or 0.0) > PLAZO_ESTADO:   # tras vaciar el buffer
                raise ErrorUR("{} no envia estados desde hace mas de {} s".format(self.red.destino, PLAZO_ESTADO))


class UrPrimaria(ClienteUR):
    PUERTO = 30001

    def _extraer(self, buffer):
        return extraer_mensaje(buffer)

    def mensajes(self):
        """Generador de (tipo, mensaje) de cada mensaje completo que llega. Los de estado se comprueban antes."""
        for tipo, mensaje in self._paquetes():
            if tipo == TIPO_ESTADO and "q" in leer_estado(mensaje):
                self.marcar_estado()
            yield tipo, mensaje

    def estados(self):
        """Generador del q (6 angulos, rad) de cada mensaje de estado; el resto de mensajes se ignora."""
        for tipo, mensaje in self._paquetes():
            if tipo == TIPO_ESTADO:
                q = leer_estado(mensaje).get("q")
                if q:
                    self.marcar_estado()
                    yield q

    def enviar_script(self, texto):
        """Envia una linea de URScript. El salto de linea al final es obligatorio (lo anade esta funcion)."""
        if "\n" in texto or "\r" in texto:
            raise ValueError("una orden URScript es una sola linea")
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
        if not (isinstance(velocidad, (int, float)) and 0 < velocidad <= VELOCIDAD_MAX):
            raise ValueError("velocidad {} rad/s fuera de (0, {}]".format(velocidad, VELOCIDAD_MAX))
        if not (isinstance(aceleracion, (int, float)) and 0 < aceleracion <= ACELERACION_MAX):
            raise ValueError("aceleracion {} rad/s2 fuera de (0, {}]".format(aceleracion, ACELERACION_MAX))
        if not self.estado_fresco():
            raise ErrorUR("{}: no se envia el movej porque no hay un estado del robot de hace menos de {} s".format(
                self.red.destino, PLAZO_ESTADO))
        self.enviar_script("movej([{}], a={}, v={})".format(
            ", ".join("{:.5f}".format(a) for a in q), aceleracion, velocidad))

    def stopj(self, aceleracion):
        """Frena las articulaciones con la deceleracion dada (rad/s2). Un valor mal puesto (nan, negativo, mayor que
        ACELERACION_MAX...) nunca impide frenar: se usa ACELERACION_MAX. Tampoco exige estado fresco."""
        if not (isinstance(aceleracion, (int, float)) and 0 < aceleracion <= ACELERACION_MAX):
            aceleracion = ACELERACION_MAX
        self.enviar_script("stopj({})".format(aceleracion))


class UrTiempoReal(ClienteUR):
    PUERTO = 30003

    def _extraer(self, buffer):
        return extraer_paquete(buffer)

    def estados(self):
        """Generador del q (6 angulos, rad) de cada paquete (unos 500 por segundo)."""
        for paquete in self._paquetes():
            q = leer_q_tiempo_real(paquete)
            self.marcar_estado()
            yield q


class LectorUR(threading.Thread):
    """Hilo que lee un robot y guarda solo el ultimo q. Si la conexion se cae, reintenta cada REINTENTO s.
    `cliente` es una UrPrimaria o una UrTiempoReal sin conectar.
    El resto del programa pregunta con ultimo_q() y nunca toca el socket. Tambien puede mirar `vivo`
    (el hilo sigue en marcha) y `ultimo_error` (por que no hay datos, o None si todo va bien)."""

    def __init__(self, nombre, cliente):
        super().__init__(daemon=True)
        self.nombre = nombre
        self.cliente = cliente
        self._lock = threading.Lock()
        self._q = None
        self._error = None
        self._recibidos = 0
        self._parar = threading.Event()

    def run(self):
        try:
            while not self._parar.is_set():
                try:
                    self._leer()
                except ErrorUR as e:
                    if not self._parar.is_set():            # si nos han parado, el cierre del socket es normal
                        self._fallo(str(e))
                except Exception as e:                      # ultima defensa: un bug no mata el hilo en silencio
                    self._fallo("error inesperado en el hilo lector: {!r}".format(e), traceback.format_exc())
                self._parar.wait(REINTENTO)
        finally:
            with self._lock:
                self._q = None

    def _leer(self):
        """Una conexion: lee estados hasta que falle (ErrorUR) o alguien llame a parar()."""
        with self.cliente:
            if self._parar.is_set():            # parar() llego mientras se conectaba: su cerrar() no vio ningun socket
                return
            for q in self.cliente.estados():
                with self._lock:
                    primero = self._q is None
                    self._q = q
                    self._error = None
                    self._recibidos += 1
                if primero:
                    print("[{}] recibiendo estados de {}".format(self.nombre, self.cliente.red.destino))
                if self._parar.is_set():
                    return

    def _fallo(self, motivo, detalle=""):
        """Anota el motivo, deja sin q, y lo escribe solo si es distinto del anterior (no una linea por reintento)."""
        with self._lock:
            nuevo = motivo != self._error
            self._error = motivo
            self._q = None
        if nuevo:
            print("[{}] DESCONECTADO ({}). Reintentando en {} s...".format(self.nombre, motivo, REINTENTO))
            if detalle:
                print(detalle)

    def parar(self):
        """Pide parar y cierra el socket (seguro desde otro hilo): el hilo sale enseguida, no tras el timeout de lectura."""
        self._parar.set()
        self.cliente.cerrar()

    def detener(self, timeout=3.0):
        """parar() y espera (como mucho `timeout` s) a que el hilo termine."""
        self.parar()
        if self.is_alive():
            self.join(timeout)

    @property
    def vivo(self):
        return self.is_alive()

    @property
    def ultimo_error(self):
        with self._lock:
            return self._error

    def ultimo_q(self):
        """Ultimo q recibido (6 angulos, rad), o None si no hay conexion o el estado no es fresco (ver estado_fresco)."""
        with self._lock:
            return list(self._q) if self._q is not None and self.cliente.estado_fresco() else None

    @property
    def recibidos(self):
        """Cuantos estados se han recibido en total (sirve para calcular estados por segundo)."""
        with self._lock:
            return self._recibidos
