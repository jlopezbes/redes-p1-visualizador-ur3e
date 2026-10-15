"""
Comunicacion con un robot UR por sockets TCP, encima de red.ConexionTCP.

    ClienteUR      portal entre la red y el robot: conecta, entrega lo que dice el robot ya decodificado y envia ordenes
    HiloLectorUR   hilo aparte que lee un robot sin parar y guarda solo el ultimo q

Los fallos (red caida, mensajes que no se entienden, robot que calla...) salen como red.ErrorRed.
ValueError solo significa "argumento mal puesto" (p. ej. un movej fuera de limites).

Formatos (todo big-endian). Los dos empiezan por la longitud del paquete (int32, cabecera incluida):
  Primaria (30001, unos 10 Hz):
    mensaje      = [longitud int32][tipo uint8][cuerpo]
    tipo 16      = estado del robot; el cuerpo son subpaquetes con el mismo formato [longitud][tipo][datos]
    subpaquete 0 = modo del robot; subpaquete 1 = articulaciones: 6 x ">dddffffB" (41 bytes), q_actual primero
    tipo 20      = mensaje del robot (version, errores...)
  Tiempo real (30003, unos 500 Hz):
    paquete      = [longitud int32][time double][...], q_actual empieza siempre en el byte 252
"""
import math
import struct
import threading

from red import ConexionTCP, ErrorRed

PUERTO_PRIMARIA = 30001
PUERTO_TIEMPO_REAL = 30003

# ---- Primaria ----
CABECERA = 5            # int32 (longitud) + uint8 (tipo)
TIPO_ROBOT_MESSAGE = 20
TIPO_ESTADO = 16
SUB_MODO = 0
SUB_JOINTS = 1
TAM_SUB_JOINTS = 251    # 5 + 6 * 41 (NO verificado con un robot real: si el robot manda otro tamano, ErrorRed)
BYTES_JOINT = 41

# ---- Tiempo real ----
OFFSET_Q_ACTUAL = 252   # 4 + 8 + 5 bloques de 6 doubles (q_target, qd_target, qdd_target, I_target, M_target)

MAX_LONGITUD = 65536    # un paquete mas largo significa que el buffer esta desalineado

# ---- Limites obligatorios en robot real ----
VELOCIDAD_MAX = 0.3     # rad/s
ACELERACION_MAX = 0.5   # rad/s2
MINIMO = 0.001          # rad/s y rad/s2: por debajo Python escribiria 1e-05 y no se sabe si URScript lo admite

MAX_IGNORADOS = 100     # paquetes seguidos sin ningun dato util: se supone puerto o interfaz equivocados

REINTENTO = 2.0         # s entre intentos de reconexion


def es_punto_valido(q):
    """6 angulos en radianes entre -2*pi y 2*pi (evita enviar grados por error). Un q raro (None, texto...) no es valido."""
    try:
        return len(q) == 6 and all(abs(a) <= 2 * math.pi for a in q)
    except TypeError:
        return False


class ClienteUR:
    """Portal entre la red y un UR: conecta, entrega lo que dice el robot ya decodificado (mensajes) y le envia
    ordenes (movej, stopj). Las dos interfaces del robot comparten todo el codigo salvo el formato de los bytes:
        tiempo_real=False   interfaz primaria (30001), unos 10 Hz: articulaciones, modo del robot y errores
        tiempo_real=True    interfaz de tiempo real (30003), unos 500 Hz: solo las articulaciones"""

    def __init__(self, ip, puerto=None, tiempo_real=False):
        if puerto is None:
            puerto = PUERTO_TIEMPO_REAL if tiempo_real else PUERTO_PRIMARIA
        self.tiempo_real = tiempo_real
        self.red = ConexionTCP(ip, puerto)
        self._buffer = bytearray()

    # ---------- conexion ----------
    def conectar(self):
        self._buffer.clear()        # lo que quedara de una conexion anterior no vale
        self.red.conectar()

    def desconectar(self):
        self.red.desconectar()

    # ---------- lo que dice el robot ----------
    def mensajes(self):
        """Generador de lo que dice el robot, un dict por mensaje: 'q' (6 q_actual, rad) y, solo en la primaria, 'ejecutando',
        'protegido', 'emergencia' y 'modo'; o {'error': texto} si el robot informa de un error. Lanza ErrorRed."""
        ignorados = 0
        while True:
            self._buffer += self.red.recibir()
            paquete = self._cortar()
            while paquete is not None:
                datos = self._decodificar(paquete)
                if datos:
                    ignorados = 0
                    yield datos
                else:                   # {} = un mensaje que no interesa
                    ignorados += 1
                    if ignorados > MAX_IGNORADOS:
                        raise ErrorRed("{}: llegan datos pero ninguno es un estado (puerto o interfaz equivocados? "
                                       "primaria = 30001, tiempo real = 30003)".format(self.red.destino))
                paquete = self._cortar()

    def _cortar(self):
        """Corta del buffer un paquete completo y lo devuelve, o devuelve None si todavia no ha llegado entero."""
        if len(self._buffer) < 4:
            return None
        longitud = struct.unpack(">i", self._buffer[:4])[0]
        minimo = OFFSET_Q_ACTUAL + 48 if self.tiempo_real else CABECERA
        if not minimo <= longitud <= MAX_LONGITUD:
            raise ErrorRed("{}: longitud imposible ({}): buffer desalineado".format(self.red.destino, longitud))
        if len(self._buffer) < longitud:
            return None
        paquete = bytes(self._buffer[:longitud])
        del self._buffer[:longitud]
        return paquete

    def _decodificar(self, paquete):
        """Paquete -> dict (ver mensajes), o {} si es un mensaje que no interesa."""
        if self.tiempo_real:
            return {"q": list(struct.unpack(">6d", paquete[OFFSET_Q_ACTUAL:OFFSET_Q_ACTUAL + 48]))}
        if paquete[4] == TIPO_ESTADO:
            return self._leer_estado(paquete)
        if paquete[4] == TIPO_ROBOT_MESSAGE:
            return self._leer_error(paquete)
        return {}

    def _leer_estado(self, paquete):
        """Mensaje tipo 16 -> dict con 'q' y, si vienen, 'ejecutando', 'protegido', 'emergencia', 'modo'."""
        estado = {}
        pos = CABECERA
        try:
            while pos < len(paquete):                   # subpaquetes: [longitud int32][tipo uint8][datos]
                tam, tipo = struct.unpack(">iB", paquete[pos:pos + CABECERA])
                if tam < CABECERA or pos + tam > len(paquete):
                    raise ErrorRed("subpaquete {} se sale del mensaje".format(tipo))
                datos = paquete[pos + CABECERA:pos + tam]
                if tipo == SUB_JOINTS:
                    if len(datos) + CABECERA != TAM_SUB_JOINTS:
                        raise ErrorRed("subpaquete de articulaciones de {} bytes y se esperaban {}: otra version del "
                                       "robot? (ajusta TAM_SUB_JOINTS)".format(len(datos) + CABECERA, TAM_SUB_JOINTS))
                    estado["q"] = [struct.unpack(">d", datos[BYTES_JOINT * j:BYTES_JOINT * j + 8])[0] for j in range(6)]
                elif tipo == SUB_MODO:
                    _, _, _, _, emergencia, protegido, ejecutando, _, modo = struct.unpack(">Q???????B", datos[:16])
                    estado.update(ejecutando=ejecutando, protegido=protegido, emergencia=emergencia, modo=modo)
                pos += tam
        except struct.error as e:
            raise ErrorRed("mensaje de estado mal formado: {}".format(e)) from e
        return estado

    def _leer_error(self, paquete):
        """Mensaje tipo 20 -> {'error': texto} si es un error (robotMessageType 6 o 10), o {} para cualquier otro.
        Cualquier error o excepcion del robot cuenta, sea cual sea su reportLevel (parar es lo seguro)."""
        # cabecera 5 + timestamp 8 + source 1 + robotMessageType 1 = 15
        if len(paquete) < 15 or paquete[14] not in (6, 10):
            return {}
        try:
            numero = struct.unpack(">i", paquete[15:19])[0]
        except struct.error as e:
            raise ErrorRed("mensaje de error del robot cortado: {}".format(e)) from e
        if paquete[14] == 6:       # error code: code, argument, reportLevel, dataType, data (5 x int32) y texto
            return {"error": "error del robot (codigo {}): {}".format(numero, paquete[35:].decode("ascii", "replace"))}
        # excepcion de programa: linea, columna (2 x int32) y texto
        return {"error": "excepcion de programa (linea {}): {}".format(numero, paquete[23:].decode("ascii", "replace"))}

    # ---------- ordenes al robot ----------
    def movej(self, q, *, velocidad, aceleracion):
        """Mueve las 6 articulaciones a q (rad). velocidad en rad/s, aceleracion en rad/s2.
        Se niega (ValueError) a enviar angulos fuera de [-2pi, 2pi] o velocidades por encima de los limites del robot real.
        Los argumentos son solo por nombre para no mezclar velocidad y aceleracion (URScript: a=, v=)."""
        if not es_punto_valido(q):
            raise ValueError("angulos fuera de [-2pi, 2pi] (rad), o no son 6: {}".format(q))
        if not MINIMO <= velocidad <= VELOCIDAD_MAX:
            raise ValueError("velocidad {} rad/s fuera de [{}, {}]".format(velocidad, MINIMO, VELOCIDAD_MAX))
        if not MINIMO <= aceleracion <= ACELERACION_MAX:
            raise ValueError("aceleracion {} rad/s2 fuera de [{}, {}]".format(aceleracion, MINIMO, ACELERACION_MAX))
        # el salto de linea al final de cada orden URScript es obligatorio
        self.red.enviar("movej([{}], a={}, v={})\n".format(
            ", ".join("{:.5f}".format(a) for a in q), aceleracion, velocidad).encode())

    def stopj(self, aceleracion):
        """Frena las articulaciones con la deceleracion dada (rad/s2)."""
        self.red.enviar("stopj({})\n".format(aceleracion).encode())


class HiloLectorUR(threading.Thread):
    """Hilo aparte que lee un robot sin parar y guarda solo el ultimo q. Asi el programa principal (que dibuja la
    ventana) nunca se queda esperando al socket: lee `q` cuando quiere, sin bloquearse, aunque haya varios robots.
    Si la conexion se cae, reintenta cada REINTENTO s. `cliente` es un ClienteUR sin conectar.

    Atributos que lee el programa principal (los escribe solo este hilo):
        q              ultimo q recibido (6 angulos, rad), o None si no hay conexion
        ultimo_error   por que no hay datos, o None si todo va bien
        recibidos      estados recibidos en total (sirve para calcular estados por segundo)"""

    def __init__(self, nombre, cliente):
        super().__init__(daemon=True)
        self.nombre = nombre
        self.cliente = cliente
        self.q = None
        self.ultimo_error = None
        self.recibidos = 0
        self._parar = threading.Event()

    def run(self):
        while not self._parar.is_set():
            try:
                self.cliente.conectar()
                for datos in self.cliente.mensajes():
                    if "q" in datos:
                        if self.q is None:
                            print("[{}] recibiendo estados de {}".format(self.nombre, self.cliente.red.destino))
                        self.q = datos["q"]
                        self.ultimo_error = None
                        self.recibidos += 1
            except ErrorRed as e:
                if not self._parar.is_set():            # si nos han parado, el cierre del socket es normal
                    if str(e) != self.ultimo_error:     # una sola linea por motivo, no una por reintento
                        print("[{}] DESCONECTADO ({}). Reintentando en {} s...".format(self.nombre, e, REINTENTO))
                    self.ultimo_error = str(e)
                    self.q = None
            finally:
                self.cliente.desconectar()
            self._parar.wait(REINTENTO)

    def detener(self):
        """Pide parar y cierra el socket (sirve desde otro hilo): el hilo sale enseguida. Espera hasta 3 s a que acabe."""
        self._parar.set()
        self.cliente.desconectar()
        if self.is_alive():
            self.join(3.0)
