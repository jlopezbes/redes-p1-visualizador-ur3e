"""
Lectura de la interfaz primaria de un UR (puerto 30001) y utilidades comunes.

El robot emite continuamente paquetes con esta estructura:
    [tamaño: int32][tipo: uint8][cuerpo...]          (todo big endian)
- tipo 20: mensaje de version (se descarta)
- tipo 16: estado del robot. El cuerpo son subpaquetes con el mismo formato
           [tamaño: int32][tipo: uint8][datos...] donde el tamaño incluye la cabecera.
    * subpaquete 0: RobotModeData
    * subpaquete 1: JointData  (6 articulaciones x 41 bytes)
    * subpaquete 4: CartesianInfo (pose del TCP)
"""
import socket
import threading
from struct import unpack, error as StructError

CABECERA = 5
TIPO_ESTADO_ROBOT = 16
SUB_MODO_ROBOT = 0
SUB_JOINTS = 1
SUB_CARTESIANO = 4
N_JOINTS = 6
BYTES_JOINT = 41   # ">dddffffB"

MODOS_ROBOT = {
    -1: "sin controlador", 0: "desconectado", 1: "confirmar seguridad", 2: "arrancando",
    3: "apagado", 4: "encendido", 5: "idle", 6: "backdrive", 7: "running", 8: "actualizando firmware",
}


def recv_exact(sock, num_bytes):
    """Recibe exactamente num_bytes (recv puede devolver menos de lo pedido)."""
    data = b""
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            raise ConnectionError("El robot cerro la conexion.")
        data += packet
    return data


def leer_paquete(sock):
    """Lee un paquete completo y devuelve (tipo, cuerpo)."""
    tamaño, tipo = unpack(">iB", recv_exact(sock, CABECERA))
    if tamaño < CABECERA:
        raise ValueError("Tamaño de paquete invalido: {}".format(tamaño))
    return tipo, recv_exact(sock, tamaño - CABECERA)


def separar_subpaquetes(cuerpo):
    """Divide el cuerpo de un paquete tipo 16 en {tipo_subpaquete: datos}."""
    subpaquetes = {}
    i = 0
    while i < len(cuerpo):
        tamaño, tipo = unpack(">iB", cuerpo[i:i + CABECERA])
        if tamaño < CABECERA:
            raise ValueError("Tamaño de subpaquete invalido: {}".format(tamaño))
        subpaquetes[tipo] = cuerpo[i + CABECERA:i + tamaño]
        i += tamaño
    return subpaquetes


def parsear_modo_robot(datos):
    (timestamp, conectado, habilitado, encendido, emergencia, protegido, programa_corriendo,
     programa_pausado, modo, modo_control, fraccion_vel, escalado_vel, limite_fraccion_vel
     ) = unpack(">Q???????BBddd", datos[:41])
    return {
        "timestamp": timestamp,
        "isRealRobotConnected": conectado,
        "isRealRobotEnabled": habilitado,
        "isRobotPowerOn": encendido,
        "isEmergencyStopped": emergencia,
        "isProtectiveStopped": protegido,
        "isProgramRunning": programa_corriendo,
        "isProgramPaused": programa_pausado,
        "robotMode": modo,
        "controlMode": modo_control,
        "targetSpeedFraction": fraccion_vel,
        "speedScaling": escalado_vel,
        "targetSpeedFractionLimit": limite_fraccion_vel,
    }


def parsear_joints(datos):
    """Devuelve un diccionario con una lista por variable (una posicion por articulacion)."""
    joints = {"q_actual": [], "q_target": [], "qd_actual": [], "I_actual": [],
              "V_actual": [], "T_motor": [], "T_micro": [], "jointMode": []}
    for i in range(N_JOINTS):
        q, q_t, qd, corriente, tension, t_motor, t_micro, modo = unpack(
            ">dddffffB", datos[BYTES_JOINT * i:BYTES_JOINT * (i + 1)])
        joints["q_actual"].append(q)
        joints["q_target"].append(q_t)
        joints["qd_actual"].append(qd)
        joints["I_actual"].append(corriente)
        joints["V_actual"].append(tension)
        joints["T_motor"].append(t_motor)
        joints["T_micro"].append(t_micro)
        joints["jointMode"].append(modo)
    return joints


def parsear_cartesiano(datos):
    """Pose del TCP: [x, y, z, rx, ry, rz] (m y vector de rotacion en rad)."""
    return list(unpack(">dddddd", datos[:48]))


def parsear_estado(cuerpo):
    """Convierte el cuerpo de un paquete tipo 16 en un diccionario (solo los subpaquetes conocidos)."""
    sub = separar_subpaquetes(cuerpo)
    estado = {}
    if SUB_MODO_ROBOT in sub:
        estado["modo"] = parsear_modo_robot(sub[SUB_MODO_ROBOT])
    if SUB_JOINTS in sub:
        estado["joints"] = parsear_joints(sub[SUB_JOINTS])
    if SUB_CARTESIANO in sub:
        estado["tcp"] = parsear_cartesiano(sub[SUB_CARTESIANO])
    return estado


def parsear_robot(texto, puerto_defecto=30001):
    """'192.168.0.5' o '192.168.0.5:30001' -> (ip, puerto)."""
    if ":" in texto:
        ip, puerto = texto.rsplit(":", 1)
        return ip, int(puerto)
    return texto, puerto_defecto


class LectorUR(threading.Thread):
    """Hilo que mantiene siempre disponible el ultimo estado recibido de un robot."""

    def __init__(self, nombre, ip, puerto=30001):
        super().__init__(daemon=True)
        self.nombre = nombre
        self.ip = ip
        self.puerto = puerto
        self._estado = None
        self._lock = threading.Lock()
        self._parar = threading.Event()

    def run(self):
        while not self._parar.is_set():
            try:
                with socket.create_connection((self.ip, self.puerto), timeout=5) as s:
                    s.settimeout(5)
                    print("[{}] conectado a {}:{}".format(self.nombre, self.ip, self.puerto))
                    while not self._parar.is_set():
                        tipo, cuerpo = leer_paquete(s)
                        if tipo != TIPO_ESTADO_ROBOT:
                            continue   # version u otros: se descartan
                        estado = parsear_estado(cuerpo)
                        with self._lock:
                            self._estado = estado
            except (OSError, ValueError, StructError) as e:
                print("[{}] error: {}. Reintentando en 2 s...".format(self.nombre, e))
                self._parar.wait(2)

    def ultimo_estado(self):
        """Ultimo estado recibido (dict) o None si todavia no ha llegado ninguno."""
        with self._lock:
            return self._estado

    def parar(self):
        self._parar.set()


def formatear_estado(nombre, estado):
    """Texto de una linea con las posiciones de un estado."""
    if not estado or "joints" not in estado:
        return "[{}] sin datos todavia".format(nombre)
    q = ", ".join("{:7.3f}".format(v) for v in estado["joints"]["q_actual"])
    texto = "[{}] joints (rad): [{}]".format(nombre, q)
    if "tcp" in estado:
        texto += " | TCP: [{}]".format(", ".join("{:6.3f}".format(v) for v in estado["tcp"]))
    if "modo" in estado:
        texto += " | modo: {}".format(MODOS_ROBOT.get(estado["modo"]["robotMode"], estado["modo"]["robotMode"]))
    return texto
