"""
Las cuatro tareas de la practica, como funciones que juntan los controladores:
    ur.ClienteUR / ur.HiloLectorUR                  hablan con el robot
    simulador.Simulador                             dibuja en PyBullet
    secuencia.Secuencia / secuencia.Reproductor     enseñar y reproducir

    visualizar(clientes)                    uno o varios robots, un hilo por robot   -> aprobado (uno) y notable (varios)
    cargar_robots(ruta)                     los clientes de los robots de un JSON de IPs
    ensenar_reproducir(ip, puerto, v, a)    enseñar puntos y reproducirlos           -> sobresaliente

PyBullet solo se toca desde el hilo que llama a estas funciones; los hilos de ur.HiloLectorUR solo leen sockets.
Orden en todas: primero se crean los clientes (validan IP y puerto, ValueError, sin abrir red) y despues el
simulador, dentro de `with`: asi un argumento malo falla antes de abrir la ventana y la ventana se cierra siempre.
Los errores de las capas de abajo (ErrorRed, ErrorSimulador, ErrorSecuencia) los muestra main.py.
"""
import json
import math
import queue
import threading
import time

import ur
from red import ErrorRed
from secuencia import LIBRE, ErrorSecuencia, Reproductor, Secuencia
from simulador import Simulador


def visualizar(clientes):
    """clientes: {nombre: ClienteUR sin conectar}. Mueve cada robot simulado a su ultimo q y escribe una linea por
    robot cada segundo. Termina con Ctrl+C. Al salir, por lo que sea, detiene los hilos lectores. Un robot desconectado no se mueve."""
    lectores = [ur.HiloLectorUR(nombre, cliente) for nombre, cliente in clientes.items()]
    contados = {l.nombre: 0 for l in lectores}
    with Simulador() as simulador:
        for lector in lectores:
            simulador.agregar_robot(lector.nombre)
        try:
            for lector in lectores:
                lector.start()
            t_info = time.time()
            while True:
                for lector in lectores:
                    q = lector.q
                    if q:
                        simulador.mover(lector.nombre, q)
                ahora = time.time()
                if ahora - t_info >= 1.0:
                    for lector in lectores:
                        q = lector.q
                        por_segundo = (lector.recibidos - contados[lector.nombre]) / (ahora - t_info)
                        contados[lector.nombre] = lector.recibidos
                        print("[{}] {:.0f} estados/s | q (grados): {}".format(
                            lector.nombre, por_segundo,
                            [round(math.degrees(a), 1) for a in q] if q else (lector.ultimo_error or "sin datos")))
                    t_info = ahora
                time.sleep(1 / 30)              # 30 redibujados por segundo
        finally:
            for lector in lectores:
                lector.detener()


def cargar_robots(ruta):
    """JSON [{"nombre": "robot1", "ip": "10.172.18.74"}, ...] -> {nombre: ClienteUR} (primaria, puerto 30001).
    Lanza ValueError si no se puede leer o le falta algo."""
    try:
        with open(ruta, encoding="utf-8-sig") as f:         # utf-8-sig: tolera el BOM que anade el Bloc de notas
            robots = json.load(f)
        clientes = {r["nombre"]: ur.ClienteUR(r["ip"]) for r in robots}
    except (OSError, ValueError, KeyError, TypeError) as e:     # fichero, JSON, campo que falta, IP mala
        raise ValueError("{}: {}: {}".format(ruta, type(e).__name__, e)) from e
    if not clientes:
        raise ValueError("{}: no hay ningun robot".format(ruta))
    return clientes


# ---------- enseñar y reproducir ----------

AYUDA = ("Comandos: g (guardar punto), v (previsualizar), e (ejecutar), c (cancelar), r (reanudar), "
         "s/l [fichero] (salvar/cargar), b (borrar), q (salir)")


def _leer_consola(comandos):
    """Hilo: pasa cada linea escrita a la cola. Solo el hilo principal actua sobre ella."""
    while True:
        try:
            comandos.put(input().strip())
        except EOFError:                # Ctrl+Z o entrada cerrada: salida ordenada, como un 'q'
            comandos.put("q")
            return


def _comando(linea, rep, simulador):
    """Ejecuta una linea de la consola. Devuelve True si hay que salir."""
    orden, _, argumento = linea.partition(" ")
    fichero = argumento.strip() or "secuencia.json"
    if orden == "q":
        return True
    if orden == "c":
        rep.cancelar()
    elif rep.fase != LIBRE and orden != "r":
        print("Secuencia en marcha o parada: solo 'c' (cancelar), 'r' (reanudar) o 'q'")
    elif orden == "g":
        rep.guardar_punto()
    elif orden == "b":
        rep.secuencia.clear()
        print("Secuencia borrada")
    elif orden == "v":
        if not rep.secuencia or rep.q is None:
            print("Nada que previsualizar")
        else:
            simulador.previsualizar("robot", rep.q, rep.secuencia)
    elif orden == "e":
        rep.ejecutar()
    elif orden == "r":
        rep.reanudar()
    elif orden == "s":
        try:
            rep.secuencia.guardar(fichero)
            print("{} puntos guardados en {}".format(len(rep.secuencia), fichero))
        except ErrorSecuencia as e:
            print("No se pudo guardar: {}".format(e))
    elif orden == "l":
        try:
            rep.secuencia.cargar(fichero)
            print("{} puntos cargados de {}".format(len(rep.secuencia), fichero))
        except ErrorSecuencia as e:
            print("No se pudo cargar: {}".format(e))
    else:
        print(AYUDA)
    return False


def ensenar_reproducir(ip, puerto, velocidad, aceleracion):
    """Enseñar y reproducir con la interfaz primaria. El estado se lee y las ordenes se envian por el MISMO socket.
    velocidad en rad/s y aceleracion en rad/s2 de cada movej (maximo 0,3 y 0,5: ver ur.py)."""
    robot = ur.ClienteUR(ip, puerto)
    rep = Reproductor(robot, Secuencia(), velocidad, aceleracion)
    comandos = queue.Queue()
    try:
        with Simulador() as simulador:
            simulador.agregar_robot("robot")
            # La consola se lee DESPUES de abrir la ventana: un input() ya bloqueado impide que PyBullet termine de abrirla.
            threading.Thread(target=_leer_consola, args=(comandos,), daemon=True).start()
            salir = False
            while not salir:                     # si se cae la conexion se vuelve a intentar
                try:
                    robot.conectar()
                    print("Conectado a {}:{}. {}".format(ip, puerto, AYUDA))
                    for datos in robot.mensajes():
                        rep.procesar(datos)
                        if rep.q:
                            simulador.mover("robot", rep.q)
                        while not comandos.empty() and not salir:
                            salir = _comando(comandos.get(), rep, simulador)
                        if salir:
                            break
                except ErrorRed as e:       # red caida, robot que cierra o calla, mensajes que no se entienden
                    print("Conexion perdida ({}). Reintentando en {} s...".format(e, ur.REINTENTO))
                    rep.conexion_perdida()
                    try:                    # mientras espera, la consola sigue atendida: con 'q' se sale al instante
                        salir = _comando(comandos.get(timeout=ur.REINTENTO), rep, simulador)
                    except queue.Empty:
                        pass
    finally:                                # q, Ctrl+C, ventana cerrada o un bug: el robot no se queda en marcha
        if rep.ocupado:
            rep.cancelar()
        robot.desconectar()
