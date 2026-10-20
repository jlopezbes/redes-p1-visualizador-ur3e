"""
Capa de red: una conexion TCP cliente con timeouts. No sabe nada del protocolo del UR.

    red = ConexionTCP("127.0.0.1", 30001)
    red.conectar()
    red.enviar(b"hola\\n")
    datos = red.recibir()
    red.desconectar()

Los fallos de red salen SIEMPRE como ErrorRed: ninguna capa de arriba necesita conocer socket ni OSError, y el mensaje
dice con quien y por que. ErrorRedTimeout (que es un ErrorRed) significa "nadie contesta a tiempo". Una IP o un puerto
mal escritos salen como ValueError al crear el objeto, antes de tocar la red.
"""
import encodings.idna  # noqa: F401  Python lo carga al primer connect(); si dos hilos conectan a la vez (un hilo por robot) uno falla con "unknown encoding: idna"
import ipaddress
import socket

TIMEOUT_CONEXION = 5.0      # s: maximo para establecer la conexion
TIMEOUT_LECTURA = 2.0       # s: recibir() falla si no llega nada en este tiempo


class ErrorRed(Exception):
    """Fallo de la conexion (rechazada, cortada, cerrada por el otro lado...). El mensaje dice con quien y por que."""


class ErrorRedTimeout(ErrorRed):
    """No contesta nadie dentro del plazo. Si ocurre en recibir(), la conexion sigue abierta y se puede reintentar."""


class ConexionTCP:
    def __init__(self, ip, puerto):
        try:
            ipaddress.ip_address(ip.strip())            # solo IPs literales: un nombre obligaria a esperar al DNS
        except (AttributeError, ValueError):
            raise ValueError("IP no valida: {!r} (debe ser una IP como 192.168.0.10)".format(ip)) from None
        if not 1 <= puerto <= 65535:
            raise ValueError("puerto no valido: {!r} (debe ser un entero entre 1 y 65535)".format(puerto))
        self.ip = ip.strip()
        self.puerto = puerto
        self.destino = "{}:{}".format(self.ip, self.puerto)     # para los mensajes de error
        self._socket = None

    def conectar(self):
        self.desconectar()                              # un objeto = una conexion: no se deja un socket suelto
        try:
            sock = socket.create_connection((self.ip, self.puerto), timeout=TIMEOUT_CONEXION)
        except socket.timeout:
            raise ErrorRedTimeout("{} no contesta en {} s (robot apagado o IP de otra red?)".format(
                self.destino, TIMEOUT_CONEXION)) from None
        except OSError as e:
            raise ErrorRed("no se puede conectar con {}: {} (robot apagado, puerto equivocado o URSim cerrado?)".format(
                self.destino, e)) from e
        sock.settimeout(TIMEOUT_LECTURA)
        self._socket = sock

    def desconectar(self):
        """Cierra la conexion. Se puede llamar varias veces y desde otro hilo (el hilo que lee recibe ErrorRed)."""
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)         # en Linux close() no despierta a un recv() de otro hilo; shutdown() si
            except OSError:                             # ya cerrado por el otro lado
                pass
            sock.close()

    def enviar(self, datos):
        """Envia todos los bytes. Un fallo cierra la conexion (no se sabe cuanto salio).
        Ojo: si el otro lado ya cerro, el primer envio puede no fallar; fallara el siguiente o el recibir()."""
        sock = self._socket                             # copia local: otro hilo puede poner self._socket a None
        if sock is None:
            raise ErrorRed("la conexion con {} no esta abierta".format(self.destino))
        try:
            sock.sendall(datos)
        except OSError as e:                            # incluye el timeout: tras un envio a medias el flujo no vale
            self.desconectar()
            raise ErrorRed("conexion con {} perdida al enviar: {}".format(self.destino, e)) from e

    def recibir(self):
        """Devuelve los bytes que haya (hasta 65536). Espera como mucho TIMEOUT_LECTURA s (ErrorRedTimeout, sigue abierta).
        Si el otro extremo cierra lanza ErrorRed: recv() devolveria b"" y no seria un dato."""
        sock = self._socket
        if sock is None:
            raise ErrorRed("la conexion con {} no esta abierta".format(self.destino))
        try:
            datos = sock.recv(65536)
        except socket.timeout:
            raise ErrorRedTimeout("{} no ha enviado nada en {} s (robot parado o puerto equivocado?)".format(
                self.destino, TIMEOUT_LECTURA)) from None
        except OSError as e:
            self.desconectar()
            raise ErrorRed("conexion con {} perdida al recibir: {}".format(self.destino, e)) from e
        if not datos:
            self.desconectar()
            raise ErrorRed("conexion con {} cerrada por el otro extremo (robot apagado o reiniciado?)".format(self.destino))
        return datos
