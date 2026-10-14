"""
Capa de red: una conexion TCP cliente con timeouts. No sabe nada del protocolo del UR.

    with ConexionTCP("127.0.0.1", 30001) as red:
        red.enviar(b"hola\n")
        datos = red.recibir()

Los fallos de red salen SIEMPRE como ErrorRed (o ErrorRedTimeout, que es un ErrorRed): ninguna capa de arriba
necesita conocer socket ni OSError. Argumentos absurdos (IP o puerto mal escritos, timeouts <= 0) salen como
ValueError al crear el objeto, antes de tocar la red.
"""
import ipaddress
import socket

MAX_RECIBIR = 1048576       # bytes: tope de recibir(maximo)
MAX_TIMEOUT = 3600.0        # s: un timeout mayor es casi seguro un error (y 'inf'/'nan' se rechazan)


class ErrorRed(Exception):
    """Fallo de la conexion (rechazada, cortada, cerrada por el otro lado...). El mensaje dice con quien y por que."""


class ErrorRedTimeout(ErrorRed):
    """No contesta nadie dentro del plazo. Si ocurre en recibir(), la conexion sigue abierta y se puede reintentar."""


class ConexionTCP:
    def __init__(self, ip, puerto, timeout_conexion=5.0, timeout_lectura=2.0):
        # Se valida todo aqui: es el unico sitio por el que pasan IP y puertos (CLI, robots.json, pruebas).
        try:
            ipaddress.ip_address(ip.strip())            # solo IPs literales: un nombre obligaria a esperar al DNS
        except (AttributeError, ValueError):
            raise ValueError("IP no valida: {!r} (debe ser una IP como 192.168.0.10)".format(ip)) from None
        if isinstance(puerto, bool) or not isinstance(puerto, int) or not 1 <= puerto <= 65535:
            raise ValueError("puerto no valido: {!r} (debe ser un entero entre 1 y 65535)".format(puerto))
        for nombre, valor in (("timeout_conexion", timeout_conexion), ("timeout_lectura", timeout_lectura)):
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 < valor <= MAX_TIMEOUT:
                raise ValueError("{} no valido: {!r} (segundos, mayor que 0 y como mucho {})".format(
                    nombre, valor, MAX_TIMEOUT))
        self.ip = ip.strip()
        self.puerto = puerto
        self.destino = "{}:{}".format(self.ip, self.puerto)     # para los mensajes de error
        self.timeout_conexion = timeout_conexion    # s: maximo para establecer la conexion
        self.timeout_lectura = timeout_lectura      # s: recibir() falla si no llega nada en este tiempo
        self._socket = None

    @property
    def abierta(self):
        return self._socket is not None

    def abrir(self):
        self.cerrar()                               # un objeto = una conexion: no se deja un socket suelto
        try:
            sock = socket.create_connection((self.ip, self.puerto), timeout=self.timeout_conexion)
        except socket.timeout:
            raise ErrorRedTimeout("{} no contesta en {} s (robot apagado o IP de otra red?)".format(
                self.destino, self.timeout_conexion)) from None
        except OSError as e:
            raise ErrorRed("no se puede conectar con {}: {}".format(self.destino, e)) from e
        sock.settimeout(self.timeout_lectura)
        self._socket = sock

    def cerrar(self):
        """Cierra la conexion. Se puede llamar varias veces y desde otro hilo (el hilo que lee recibe ErrorRed)."""
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass                                # ya estaba rota: da igual

    def _perdida(self, causa):
        """La conexion ya no sirve: se cierra y se devuelve el ErrorRed que hay que lanzar."""
        self.cerrar()
        return ErrorRed("conexion con {} perdida o cerrada: {}".format(self.destino, causa))

    def _socket_abierto(self):
        sock = self._socket                         # copia local: otro hilo puede poner self._socket a None
        if sock is None:
            raise ErrorRed("la conexion con {} no esta abierta".format(self.destino))
        return sock

    def enviar(self, datos):
        """Envia todos los bytes. datos: bytes. Un fallo cierra la conexion (no se sabe cuanto salio).
        Ojo: si el otro lado ya cerro, el primer envio puede no fallar; fallara el siguiente o el recibir()."""
        if not isinstance(datos, (bytes, bytearray)):
            raise TypeError("enviar() necesita bytes, no {}".format(type(datos).__name__))
        sock = self._socket_abierto()
        try:
            sock.sendall(datos)
        except OSError as e:                        # incluye el timeout: tras un envio a medias el flujo no vale
            raise self._perdida(e) from e

    def recibir(self, maximo=4096):
        """Devuelve entre 1 y `maximo` bytes. Espera como mucho timeout_lectura s (ErrorRedTimeout, sigue abierta).
        Si el otro extremo cierra lanza ErrorRed: recv() devolveria b"" y no seria un dato."""
        if not 1 <= maximo <= MAX_RECIBIR:
            raise ValueError("maximo debe estar entre 1 y {} bytes, no {}".format(MAX_RECIBIR, maximo))
        sock = self._socket_abierto()
        try:
            datos = sock.recv(maximo)
        except socket.timeout:
            raise ErrorRedTimeout("{} no ha enviado nada en {} s".format(self.destino, self.timeout_lectura)) from None
        except OSError as e:
            raise self._perdida(e) from e
        if not datos:
            raise self._perdida("el otro extremo ha cerrado")
        return datos

    def __enter__(self):
        self.abrir()
        return self

    def __exit__(self, *_):
        self.cerrar()
