"""
HMI web minima para ensenar.py: una pagina en http://127.0.0.1:<puerto> que muestra el estado del robot y manda
ordenes (guardar punto, ejecutar, cancelar...). Solo libreria estandar: http.server en un hilo aparte.

    web = HMI(comandos)                 comandos: la queue.Queue de lineas que ya lee ensenar.py (la misma que la consola)
    url = web.iniciar()                 arranca el servidor; devuelve la URL (lleva un token)
    web.publicar(estado)                el hilo principal, con cada mensaje del robot: un dict de datos simples
    web.detener()

Reparto de hilos (igual que HiloLectorUR): el hilo principal PUBLICA y los hilos del servidor solo LEEN, asi que
el estado compartido va con un Lock. Las ordenes no se ejecutan aqui: se meten en `comandos` y las atiende el hilo
principal, como si se hubieran escrito en la consola.

Seguridad (por esto manda ordenes a un robot): solo escucha en 127.0.0.1; todas las peticiones llevan un token
aleatorio que se genera al arrancar (y que solo conoce quien vea la consola o la URL que abre el programa);
se rechaza una cabecera Host que no sea 127.0.0.1 o localhost y un POST que no sea JSON. La seta del pendant
sigue siendo la parada real: esto es software.
"""
import collections
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VENTANA = 60.0          # s de historial de q que se envian a la pagina
MAX_ORDEN = 100         # caracteres maximos de una orden
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hmi.html")      # al lado de este fichero


class HMI:
    def __init__(self, comandos, puerto=8080):
        self.comandos = comandos
        self.puerto = puerto                    # si esta ocupado se usa otro libre
        self.token = secrets.token_urlsafe(8)
        self._lock = threading.Lock()
        self._estado = {}
        self._historial = collections.deque()   # [t, q1..q6]: t en s desde el arranque, q en rad
        self._t0 = time.monotonic()
        self._servidor = None

    def publicar(self, estado):
        """Hilo principal. `estado`: dict con datos simples (numeros, textos, listas), ya copiado: no se toca despues."""
        ahora = time.monotonic() - self._t0
        with self._lock:
            self._estado = estado
            if estado.get("q"):
                self._historial.append([round(ahora, 2)] + [round(a, 4) for a in estado["q"]])
            while self._historial and self._historial[0][0] < ahora - VENTANA:
                self._historial.popleft()

    def _instantanea(self):
        with self._lock:
            return dict(self._estado, t=round(time.monotonic() - self._t0, 2), historial=list(self._historial))

    def iniciar(self):
        """Arranca el servidor en un hilo aparte y devuelve la URL con el token. OSError si no hay ningun puerto libre."""
        manejador = _crear_manejador(self)
        try:
            self._servidor = ThreadingHTTPServer(("127.0.0.1", self.puerto), manejador)
        except OSError:                         # el puerto esta ocupado: uno libre cualquiera
            self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), manejador)
        threading.Thread(target=self._servidor.serve_forever, daemon=True).start()
        return "http://127.0.0.1:{}/?t={}".format(self._servidor.server_address[1], self.token)

    def detener(self):
        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
            self._servidor = None


def _crear_manejador(hmi):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):           # sin una linea por peticion: la pagina pregunta 5 veces por segundo
            pass

        def _responder(self, codigo, tipo, cuerpo):
            if isinstance(cuerpo, str):
                cuerpo = cuerpo.encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _autorizado(self):
            host = self.headers.get("Host", "").rsplit(":", 1)[0]
            token = parse_qs(urlparse(self.path).query).get("t", [""])[0]
            if host in ("127.0.0.1", "localhost") and secrets.compare_digest(token, hmi.token):
                return True
            self._responder(403, "text/plain; charset=utf-8", "Prohibido: usa la URL que escribe el programa (lleva un token).")
            return False

        def do_GET(self):
            if not self._autorizado():
                return
            ruta = urlparse(self.path).path
            if ruta == "/":
                with open(HTML, encoding="utf-8") as f:
                    pagina = f.read()
                inicial = json.dumps(hmi._instantanea()).replace("<", "\\u003c")      # sin "<": un texto no puede cerrar el <script>
                self._responder(200, "text/html; charset=utf-8", pagina.replace("__INICIAL__", inicial))
            elif ruta == "/estado":
                self._responder(200, "application/json", json.dumps(hmi._instantanea()))
            else:
                self._responder(404, "text/plain; charset=utf-8", "No existe")

        def do_POST(self):
            try:
                largo = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                largo = 0
            cuerpo = self.rfile.read(max(0, min(largo, 1000)))      # se lee SIEMPRE, antes de responder: si se cierra con
            if not self._autorizado():                              # datos sin leer, Windows reinicia la conexion y el cliente pierde la respuesta
                return
            if urlparse(self.path).path != "/orden":
                self._responder(404, "text/plain; charset=utf-8", "No existe")
            elif not self.headers.get("Content-Type", "").startswith("application/json"):
                self._responder(415, "text/plain; charset=utf-8", "Solo application/json")
            else:
                try:
                    linea = json.loads(cuerpo.decode("utf-8"))["linea"]
                    if not isinstance(linea, str) or not linea.strip() or len(linea) > MAX_ORDEN or "\n" in linea:
                        raise ValueError("orden no valida")
                except (ValueError, KeyError, TypeError):
                    self._responder(400, "text/plain; charset=utf-8", "Orden no valida")
                    return
                hmi.comandos.put(linea.strip())
                self._responder(200, "application/json", '{"ok": true}')

    return Manejador
