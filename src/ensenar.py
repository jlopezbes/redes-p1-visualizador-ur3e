"""
Practica 1, sobresaliente: ENSEÑAR y reproducir puntos con la interfaz primaria (puerto 30001), con una web de control.

    python -u src\\ensenar.py

¡ENVIA movej al robot! Solo con el robot encendido y con los frenos liberados (robotMode = 7), en URSim con
Control remoto activado y, en un robot real, con el profesor delante, zona despejada y velocidades bajas.

Usa el PRIMER robot de datos\\robots.json. Se maneja desde la web (la abre el programa; si no, la URL sale en la consola)
o escribiendo en la consola. Los puntos se guardan en datos\\secuencias\\. Parar con Ctrl+C o con 'q'.
Fallos: el programa explica la causa y sale con codigo 1 (0 con Ctrl+C o 'q').

Hilos: el principal lee el robot, atiende las ordenes y dibuja (PyBullet solo se toca desde aqui); uno lee la consola
y el servidor web tiene los suyos. La consola y la web solo meten lineas de texto en la misma cola.
"""
import os
import queue
import sys
import threading
import webbrowser

AQUI = os.path.dirname(os.path.abspath(__file__))                       # carpeta src
sys.path.insert(0, os.path.join(AQUI, "librerias"))
ROBOTS = os.path.normpath(os.path.join(AQUI, "..", "datos", "robots.json"))        # rutas relativas a este script,
SECUENCIAS = os.path.normpath(os.path.join(AQUI, "..", "datos", "secuencias"))    # no a donde se lance

import ur  # noqa: E402
from hmi import HMI  # noqa: E402
from red import ErrorRed  # noqa: E402
from secuencia import LIBRE, ErrorSecuencia, Reproductor, Secuencia, avisar, mensajes  # noqa: E402
from simulador import ErrorSimulador, Simulador  # noqa: E402

VELOCIDAD = 0.1         # rad/s al arrancar; se cambia en la web (maximo 0,3: ver ur.py)
ACELERACION = 0.2       # rad/s2 al arrancar; se cambia en la web (maximo 0,5)

AYUDA = ("Comandos: g (guardar punto), v (previsualizar), e (ejecutar), c (cancelar), r (reanudar), "
         "s/l [fichero] (salvar/cargar), b (borrar), ajustar <v rad/s> <a rad/s2>, q (salir)")


def _leer_consola(comandos):
    """Hilo: pasa cada linea escrita a la cola. Solo el hilo principal actua sobre ella."""
    while True:
        try:
            comandos.put(input().strip())
        except EOFError:                # Ctrl+Z o entrada cerrada: salida ordenada, como un 'q'
            comandos.put("q")
            return


def _ruta(nombre):
    """Ruta en datos\\secuencias de un fichero: solo cuenta el nombre (sin carpetas) y se añade .json si falta."""
    nombre = os.path.basename(nombre.strip().replace("\\", "/")) or "secuencia"
    return os.path.join(SECUENCIAS, nombre if nombre.endswith(".json") else nombre + ".json")


def _comando(linea, rep, simulador, nombre):
    """Ejecuta una linea de la consola o de la web. Devuelve True si hay que salir."""
    orden, _, argumento = linea.partition(" ")
    if orden == "q":
        return True
    if orden == "c":
        rep.cancelar()
    elif rep.fase != LIBRE and orden != "r":
        avisar("Secuencia en marcha o parada: solo 'c' (cancelar), 'r' (reanudar) o 'q'")
    elif orden == "g":
        rep.guardar_punto()
    elif orden == "b":
        rep.secuencia.clear()
        avisar("Secuencia borrada")
    elif orden == "v":
        if not rep.secuencia or rep.q is None:
            avisar("Nada que previsualizar")
        else:
            simulador.previsualizar(nombre, rep.q, rep.secuencia)
    elif orden == "e":
        rep.ejecutar()
    elif orden == "r":
        rep.reanudar()
    elif orden == "ajustar":
        try:
            velocidad, aceleracion = (float(x) for x in argumento.split())
        except ValueError:
            avisar("Uso: ajustar <velocidad rad/s> <aceleracion rad/s2>")
        else:
            rep.ajustar(velocidad, aceleracion)
    elif orden == "s":
        ruta = _ruta(argumento)
        try:
            os.makedirs(SECUENCIAS, exist_ok=True)
            rep.secuencia.guardar(ruta)
            avisar("{} puntos guardados en {}".format(len(rep.secuencia), os.path.basename(ruta)))
        except (ErrorSecuencia, OSError) as e:
            avisar("No se pudo guardar: {}".format(e))
    elif orden == "l":
        ruta = _ruta(argumento)
        try:
            rep.secuencia.cargar(ruta)
            avisar("{} puntos cargados de {}".format(len(rep.secuencia), os.path.basename(ruta)))
        except ErrorSecuencia as e:
            avisar("No se pudo cargar: {}".format(e))
    else:
        avisar(AYUDA)
    return False


def _estado(rep, robot, conectado):
    """Lo que muestra la web, copiado: el servidor lo lee en otro hilo mientras este sigue cambiando `rep`."""
    try:
        ficheros = sorted(f for f in os.listdir(SECUENCIAS) if f.endswith(".json"))
    except OSError:
        ficheros = []
    return {
        "robot": robot.destino, "conectado": conectado,
        "q": list(rep.q) if rep.q else None,                    # rad
        "ejecutando": rep.ejecutando, "protegido": rep.protegido, "emergencia": rep.emergencia, "modo": rep.modo,
        "fase": rep.fase or "libre", "punto": None if rep.i is None else rep.i + 1,
        "puntos": [list(p) for p in rep.secuencia],             # rad
        "velocidad": rep.velocidad, "aceleracion": rep.aceleracion,                     # rad/s y rad/s2
        "limites": {"velocidad": [ur.MINIMO, ur.VELOCIDAD_MAX], "aceleracion": [ur.MINIMO, ur.ACELERACION_MAX]},
        "ficheros": ficheros, "mensajes": list(mensajes)[-30:],
    }


def main():
    nombre, ip = next(iter(ur.leer_robots(ROBOTS).items()))     # el primer robot de datos\robots.json
    robot = ur.ClienteUR(ip)
    rep = Reproductor(robot, Secuencia(), VELOCIDAD, ACELERACION)
    comandos = queue.Queue()
    web = HMI(comandos)
    simulador = Simulador()
    try:
        simulador.agregar_robot(nombre)
        # La consola se lee DESPUES de abrir la ventana: un input() ya bloqueado impide que PyBullet termine de abrirla.
        threading.Thread(target=_leer_consola, args=(comandos,), daemon=True).start()
        try:
            url = web.iniciar()
            print("Web de control: {}".format(url))
            webbrowser.open(url)
        except OSError as e:            # la web es un extra: sin ella se sigue con la consola
            print("La web no esta disponible ({}); se sigue con la consola".format(e))
        salir = False
        while not salir:                # si se cae la conexion se vuelve a intentar
            try:
                web.publicar(_estado(rep, robot, False))
                robot.conectar()
                avisar("Conectado a {}. {}".format(robot.destino, AYUDA))
                for datos in robot.mensajes():
                    rep.procesar(datos)
                    if rep.q:
                        simulador.mover(nombre, rep.q)
                    while not comandos.empty() and not salir:
                        salir = _comando(comandos.get(), rep, simulador, nombre)
                    web.publicar(_estado(rep, robot, True))
                    if salir:
                        break
            except ErrorRed as e:       # red caida, robot que cierra o calla, mensajes que no se entienden
                avisar("Conexion perdida ({}). Reintentando en {} s...".format(e, ur.REINTENTO))
                rep.conexion_perdida()
                web.publicar(_estado(rep, robot, False))
                try:                    # mientras espera, la consola y la web siguen atendidas: con 'q' se sale al instante
                    salir = _comando(comandos.get(timeout=ur.REINTENTO), rep, simulador, nombre)
                except queue.Empty:
                    pass
    finally:                            # q, Ctrl+C, ventana cerrada o un bug: el robot se frena antes de cerrar nada
        if rep.ocupado:
            rep.cancelar()
        robot.desconectar()
        web.detener()
        simulador.cerrar()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:           # es la forma normal de parar
        pass
    except (ValueError, ErrorSimulador) as e:       # ValueError: robots.json o una IP mal puestos
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    # Cualquier otra excepcion es un fallo del programa: Python imprime el traceback y sale con codigo 1
