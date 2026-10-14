"""
Capa de red: una conexion TCP cliente con timeouts. No sabe nada del protocolo del UR.

    with ConexionTCP("127.0.0.1", 30001) as red:
        red.enviar(b"hola\n")
        datos = red.recibir()

Todos los fallos de red salen como OSError (ConnectionError y socket.timeout lo son).
"""
import socket


class ConexionTCP:
    def __init__(self, ip, puerto, timeout_conexion=5.0, timeout_lectura=2.0):
        self.ip = ip
        self.puerto = puerto
        self.timeout_conexion = timeout_conexion    # s: maximo para establecer la conexion
        self.timeout_lectura = timeout_lectura      # s: recibir() falla si no llega nada en este tiempo
        self._socket = None

    @property
    def abierta(self):
        return self._socket is not None

    def abrir(self):
        self._socket = socket.create_connection((self.ip, self.puerto), timeout=self.timeout_conexion)
        self._socket.settimeout(self.timeout_lectura)

    def cerrar(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def enviar(self, datos):
        """Envia todos los bytes. datos: bytes."""
        if not self.abierta:
            raise ConnectionError("la conexion no esta abierta")
        self._socket.sendall(datos)

    def recibir(self, maximo=4096):
        """Devuelve entre 1 y `maximo` bytes. Espera como mucho timeout_lectura s (socket.timeout).
        Si el otro extremo cierra lanza ConnectionError: recv() devolveria b"" y no seria un dato."""
        if not self.abierta:
            raise ConnectionError("la conexion no esta abierta")
        datos = self._socket.recv(maximo)
        if not datos:
            raise ConnectionError("{}:{} ha cerrado la conexion".format(self.ip, self.puerto))
        return datos

    def __enter__(self):
        self.abrir()
        return self

    def __exit__(self, *_):
        self.cerrar()
