"""
Comunicacion con un robot UR por sockets TCP, encima de red.ConexionTCP.

    UrPrimaria    interfaz primaria (puerto 30001): estado, errores y envio de ordenes URScript
    UrTiempoReal  interfaz de tiempo real (puerto 30003): solo el estado, a 500 Hz
    LectorUR      hilo que lee un robot y guarda solo el ultimo q

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

from red import ConexionTCP

# ---- Primaria ----
CABECERA = 5            # int32 (longitud) + uint8 (tipo)
MAX_LONGITUD = 65536    # un mensaje mas largo significa que el buffer esta desalineado
TIPO_ROBOT_MESSAGE = 20
TIPO_ESTADO = 16
SUB_MODO = 0
SUB_JOINTS = 1
TAM_SUB_JOINTS = 251    # 5 + 6 * 41
BYTES_JOINT = 41

# ---- Tiempo real ----
CABECERA_TR = 4         # solo la longitud (int32)
OFFSET_Q_ACTUAL = 252   # 4 + 8 + 5 bloques de 6 doubles (q_target, qd_target, qdd_target, I_target, M_target)

# ---- Limites obligatorios en robot real ----
VELOCIDAD_MAX = 0.3     # rad/s
ACELERACION_MAX = 0.5   # rad/s2

REINTENTO = 2.0         # s entre intentos de reconexion


# ============ Funciones de decodificacion (sin red: se pueden probar con bytes) ============

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


def leer_q_actual(datos):
    """Datos del subpaquete 1 -> lista con los 6 q_actual (rad)."""
    if len(datos) + CABECERA != TAM_SUB_JOINTS:
        print("Aviso: subpaquete de articulaciones de {} bytes (se esperaban {}); version distinta?".format(
            len(datos) + CABECERA, TAM_SUB_JOINTS))
    return [struct.unpack(">d", datos[BYTES_JOINT * j:BYTES_JOINT * j + 8])[0] for j in range(6)]


def leer_modo(datos):
    """Datos del subpaquete 0 -> (isProgramRunning, isProtectiveStopped, isEmergencyStopped, robotMode)."""
    (_, _, _, _, emergencia, protegido, ejecutando, _, modo
     ) = struct.unpack(">Q???????B", datos[:16])
    return ejecutando, protegido, emergencia, modo


def leer_estado(mensaje):
    """Mensaje tipo 16 -> dict con 'q' (6 q_actual) y, si vienen, 'ejecutando', 'protegido', 'emergencia', 'modo'."""
    estado = {}
    for tipo, datos in subpaquetes(mensaje):
        if tipo == SUB_JOINTS:
            estado["q"] = leer_q_actual(datos)
        elif tipo == SUB_MODO:
            estado["ejecutando"], estado["protegido"], estado["emergencia"], estado["modo"] = leer_modo(datos)
    return estado


def leer_error(mensaje):
    """Mensaje tipo 20 -> texto si es un error (robotMessageType 6 o 10), o None para cualquier otro."""
    # cabecera 5 + timestamp 8 + source 1 + robotMessageType 1 = 15
    if len(mensaje) < 15:
        return None
    subtipo = mensaje[14]
    if subtipo == 6:       # error code: code, argument, reportLevel, dataType, data (5 x int32) y texto
        return "error del robot (codigo {}): {}".format(
            struct.unpack(">i", mensaje[15:19])[0], mensaje[35:].decode("utf-8", "replace"))
    if subtipo == 10:      # excepcion de programa: linea, columna (2 x int32) y texto
        return "excepcion de programa (linea {}): {}".format(
            struct.unpack(">i", mensaje[15:19])[0], mensaje[23:].decode("utf-8", "replace"))
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
    """Paquete de tiempo real -> lista con los 6 q_actual (rad)."""
    return list(struct.unpack(">6d", paquete[OFFSET_Q_ACTUAL:OFFSET_Q_ACTUAL + 48]))


def es_punto_valido(q):
    """6 angulos en radianes entre -2*pi y 2*pi (evita enviar grados por error)."""
    return len(q) == 6 and all(abs(a) <= 2 * math.pi for a in q)


# ============ Clases ============

class ClienteUR:
    """Conexion con un UR: junta los bytes que llegan en un buffer y los corta en paquetes completos.
    Cada interfaz dice en _extraer() como se corta un paquete."""

    PUERTO = None

    def __init__(self, ip, puerto=None):
        self.red = ConexionTCP(ip, puerto or self.PUERTO)
        self._buffer = bytearray()

    def conectar(self):
        self._buffer.clear()        # lo que quedara de una conexion anterior no vale
        self.red.abrir()

    def cerrar(self):
        self.red.cerrar()

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, *_):
        self.cerrar()

    def _extraer(self, buffer):
        raise NotImplementedError

    def _paquetes(self):
        """Generador de paquetes completos. Lanza OSError (red) o ValueError (buffer desalineado)."""
        while True:
            self._buffer += self.red.recibir(65536)
            while True:
                paquete = self._extraer(self._buffer)
                if paquete is None:
                    break
                yield paquete


class UrPrimaria(ClienteUR):
    PUERTO = 30001

    def _extraer(self, buffer):
        return extraer_mensaje(buffer)

    def mensajes(self):
        """Generador de (tipo, mensaje) de cada mensaje completo que llega."""
        return self._paquetes()

    def estados(self):
        """Generador del q (6 angulos, rad) de cada mensaje de estado; el resto de mensajes se ignora."""
        for tipo, mensaje in self._paquetes():
            if tipo == TIPO_ESTADO:
                q = leer_estado(mensaje).get("q")
                if q:
                    yield q

    def enviar_script(self, texto):
        """Envia una linea de URScript. El salto de linea al final es obligatorio."""
        self.red.enviar((texto + "\n").encode("utf-8"))

    def movej(self, q, *, velocidad, aceleracion):
        """Mueve las 6 articulaciones a q (rad). velocidad en rad/s, aceleracion en rad/s2.
        Se niega a enviar angulos fuera de [-2pi, 2pi] o velocidades por encima de los limites del robot real.
        Los argumentos son solo por nombre para no mezclar velocidad y aceleracion (URScript: a=, v=)."""
        if not es_punto_valido(q):
            raise ValueError("angulos fuera de [-2pi, 2pi] (rad), o no son 6: {}".format(q))
        if not 0 < velocidad <= VELOCIDAD_MAX:
            raise ValueError("velocidad {} rad/s fuera de (0, {}]".format(velocidad, VELOCIDAD_MAX))
        if not 0 < aceleracion <= ACELERACION_MAX:
            raise ValueError("aceleracion {} rad/s2 fuera de (0, {}]".format(aceleracion, ACELERACION_MAX))
        self.enviar_script("movej([{}], a={}, v={})".format(
            ", ".join("{:.5f}".format(a) for a in q), aceleracion, velocidad))

    def stopj(self, aceleracion):
        """Frena las articulaciones con la deceleracion dada (rad/s2)."""
        self.enviar_script("stopj({})".format(aceleracion))


class UrTiempoReal(ClienteUR):
    PUERTO = 30003

    def _extraer(self, buffer):
        return extraer_paquete(buffer)

    def estados(self):
        """Generador del q (6 angulos, rad) de cada paquete (unos 500 por segundo)."""
        for paquete in self._paquetes():
            yield leer_q_tiempo_real(paquete)


class LectorUR(threading.Thread):
    """Hilo que lee un robot y guarda solo el ultimo q. Si la conexion se cae, reintenta cada REINTENTO s.
    `cliente` es una UrPrimaria o una UrTiempoReal sin conectar.
    El resto del programa pregunta con ultimo_q() y nunca toca el socket."""

    def __init__(self, nombre, cliente):
        super().__init__(daemon=True)
        self.nombre = nombre
        self.cliente = cliente
        self._lock = threading.Lock()
        self._q = None
        self._conectado = False
        self._recibidos = 0
        self._parar = threading.Event()

    def run(self):
        while not self._parar.is_set():
            try:
                with self.cliente:
                    print("[{}] conectado a {}:{}".format(self.nombre, self.cliente.red.ip, self.cliente.red.puerto))
                    for q in self.cliente.estados():
                        with self._lock:
                            self._q = q
                            self._conectado = True
                            self._recibidos += 1
                        if self._parar.is_set():
                            break
            except (OSError, ValueError, struct.error) as e:
                print("[{}] DESCONECTADO ({}). Reintentando en {} s...".format(self.nombre, e, REINTENTO))
            with self._lock:
                self._conectado = False
            self._parar.wait(REINTENTO)

    def parar(self):
        self._parar.set()

    def ultimo_q(self):
        """Ultimo q recibido (6 angulos, rad), o None si el robot no esta conectado."""
        with self._lock:
            return list(self._q) if self._conectado else None

    @property
    def recibidos(self):
        """Cuantos estados se han recibido en total (sirve para calcular estados por segundo)."""
        with self._lock:
            return self._recibidos
