"""
Las cuatro tareas de la practica, como funciones que juntan los controladores:
    ur.UrPrimaria / ur.UrTiempoReal / ur.LectorUR   hablan con el robot
    simulador.Simulador                             dibuja en PyBullet
    secuencia.Secuencia / secuencia.Reproductor     enseñar y reproducir

    visualizar_primaria(ip, puerto)         un robot, interfaz primaria (30001)      -> aprobado
    visualizar_tiempo_real(ip, puerto)      un robot, interfaz de tiempo real (30003) -> aprobado
    visualizar_varios(robots)               varios robots, un hilo por robot         -> notable
    ensenar_reproducir(ip, puerto, v, a)    enseñar puntos y reproducirlos           -> sobresaliente

PyBullet solo se toca desde el hilo que llama a estas funciones; los hilos de ur.LectorUR solo leen sockets.
"""
import json
import math
import queue
import threading
import time

import ur
from secuencia import Reproductor, Secuencia
from simulador import Simulador

HZ_DIBUJO = 30            # veces por segundo que se redibuja el simulador
PERIODO_INFO = 1.0        # s entre dos lineas de informacion por consola


def cargar_robots(ruta):
    """Lee el JSON de robots: [{"nombre", "ip", "puerto", "posicion": [x, y, z, roll, pitch, yaw]}, ...]."""
    with open(ruta, encoding="utf-8-sig") as f:         # utf-8-sig: tolera el BOM que anade el Bloc de notas
        robots = json.load(f)
    for r in robots:
        for campo in ("nombre", "ip", "puerto", "posicion"):
            if campo not in r:
                raise ValueError("al robot {} le falta el campo '{}'".format(r.get("nombre", "?"), campo))
    return robots


def _dibujar(simulador, lectores):
    """Bucle principal: mueve cada robot simulado a su ultimo q y escribe una linea por robot cada PERIODO_INFO s.
    Un robot desconectado no se mueve. Termina con Ctrl+C."""
    contados = {l.nombre: l.recibidos for l in lectores}
    t_info = time.time()
    try:
        while True:
            for lector in lectores:
                q = lector.ultimo_q()
                if q:
                    simulador.mover(lector.nombre, q)
            ahora = time.time()
            if ahora - t_info >= PERIODO_INFO:
                for lector in lectores:
                    q = lector.ultimo_q()
                    por_segundo = (lector.recibidos - contados[lector.nombre]) / (ahora - t_info)
                    contados[lector.nombre] = lector.recibidos
                    print("[{}] {:.0f} estados/s | q (grados): {}".format(
                        lector.nombre, por_segundo, [round(math.degrees(a), 1) for a in q] if q else "sin conexion"))
                t_info = ahora
            time.sleep(1.0 / HZ_DIBUJO)
    except KeyboardInterrupt:
        pass
    finally:
        for lector in lectores:
            lector.parar()


def visualizar_primaria(ip, puerto=ur.UrPrimaria.PUERTO):
    simulador = Simulador()
    simulador.agregar_robot("robot")
    lector = ur.LectorUR("robot", ur.UrPrimaria(ip, puerto))
    lector.start()
    _dibujar(simulador, [lector])


def visualizar_tiempo_real(ip, puerto=ur.UrTiempoReal.PUERTO):
    simulador = Simulador()
    simulador.agregar_robot("robot")
    lector = ur.LectorUR("robot", ur.UrTiempoReal(ip, puerto))
    lector.start()
    _dibujar(simulador, [lector])


def visualizar_varios(robots):
    """robots: lista de dicts como los de cargar_robots(). Todos por la interfaz primaria."""
    simulador = Simulador()
    lectores = []
    for r in robots:
        simulador.agregar_robot(r["nombre"], r["posicion"])
        lectores.append(ur.LectorUR(r["nombre"], ur.UrPrimaria(r["ip"], r["puerto"])))
    for lector in lectores:
        lector.start()
    _dibujar(simulador, lectores)


# ---------- enseñar y reproducir ----------

AYUDA = ("Comandos: g (guardar punto), v (previsualizar), e (ejecutar), c (cancelar), r (reanudar), "
         "s/l [fichero] (salvar/cargar), b (borrar), q (salir)")


def _leer_consola(comandos):
    """Hilo: pasa cada linea escrita a la cola. Solo el hilo principal actua sobre ella."""
    while True:
        try:
            comandos.put(input().strip())
        except EOFError:
            return


def _comando(linea, rep, simulador):
    """Ejecuta una linea de la consola. Devuelve True si hay que salir."""
    orden, _, argumento = linea.partition(" ")
    fichero = argumento.strip() or "secuencia.json"
    if orden == "q":
        return True
    if orden == "c":
        rep.cancelar()
    elif rep.ocupado:
        print("Robot en movimiento: solo 'c' (cancelar) o 'q'")
    elif orden == "g":
        rep.guardar_punto()
    elif orden == "b":
        rep.secuencia.borrar()
        print("Secuencia borrada")
    elif orden == "v":
        if not len(rep.secuencia) or rep.q is None:
            print("Nada que previsualizar")
        else:
            simulador.previsualizar("robot", rep.q, rep.secuencia.puntos)
    elif orden == "e":
        rep.ejecutar()
    elif orden == "r":
        rep.reanudar()
    elif orden == "s":
        try:
            rep.secuencia.guardar(fichero)
            print("{} puntos guardados en {}".format(len(rep.secuencia), fichero))
        except OSError as e:        # sin esto pareceria un fallo de conexion
            print("No se pudo guardar: {}".format(e))
    elif orden == "l":
        try:
            rep.secuencia.cargar(fichero)
            print("{} puntos cargados de {}".format(len(rep.secuencia), fichero))
        except (OSError, ValueError, TypeError) as e:
            print("No se pudo cargar: {}".format(e))
    else:
        print(AYUDA)
    return False


def ensenar_reproducir(ip, puerto=ur.UrPrimaria.PUERTO, velocidad=0.1, aceleracion=0.2):
    """Enseñar y reproducir con la interfaz primaria. El estado se lee y las ordenes se envian por el MISMO socket.
    velocidad en rad/s y aceleracion en rad/s2 de cada movej (maximo 0,3 y 0,5: ver ur.py)."""
    simulador = Simulador()
    simulador.agregar_robot("robot")
    robot = ur.UrPrimaria(ip, puerto)
    rep = Reproductor(robot, Secuencia(), velocidad, aceleracion)
    comandos = queue.Queue()
    threading.Thread(target=_leer_consola, args=(comandos,), daemon=True).start()

    salir = False
    while not salir:                         # si se cae la conexion se vuelve a intentar
        try:
            with robot:
                print("Conectado a {}:{}. {}".format(ip, puerto, AYUDA))
                try:
                    for tipo, mensaje in robot.mensajes():
                        rep.procesar(tipo, mensaje)
                        if rep.q:
                            simulador.mover("robot", rep.q)
                        while not comandos.empty() and not salir:
                            salir = _comando(comandos.get(), rep, simulador)
                        if salir:
                            break
                except KeyboardInterrupt:
                    salir = True
                if salir and rep.ocupado:
                    robot.stopj(rep.aceleracion)        # al salir no se deja el robot en marcha
        except ur.ErrorUR as e:         # red caida, robot que cierra o no envia estados, mensajes que no se entienden
            print("Conexion perdida ({}). Reintentando en {} s...".format(e, ur.REINTENTO))
            rep.conexion_perdida()
            time.sleep(ur.REINTENTO)
