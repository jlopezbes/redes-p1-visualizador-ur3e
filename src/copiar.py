"""
Practica 1, sobresaliente: GRABAR puntos en un robot y EJECUTARLOS en otro, con la interfaz primaria (puerto 30001).

    python -u src\\copiar.py                       grabador = 2o robot de datos\\robots.json, ejecutor = 1o (como ensenar)
    python -u src\\copiar.py robot1 robot2         grabador = robot1, ejecutor = robot2 (nombres de robots.json)

El GRABADOR solo se lee: nunca recibe una orden. Se le lleva a mano a cada posicion y con 'g' se guarda su q.
El EJECUTOR es el unico que se mueve: 'e' le envia un movej por punto.
¡ENVIA movej al ejecutor! Solo con ese robot encendido y con los frenos liberados (robotMode = 7), en URSim con
Control remoto activado y, en un robot real, con el profesor delante, zona despejada y velocidades bajas.
El ejecutor, en Control remoto ANTES de arrancar: si no, el primer 'e' se rechaza (C210), se reconecta y se sigue con 'r'.

Es ensenar.py con la lectura y el movimiento en robots distintos. Mismos comandos (ver AYUDA) y mismos ficheros en
datos\\secuencias\\. Parar con Ctrl+C o con 'q'.
Fallos: el programa explica la causa y sale con codigo 1 (0 con Ctrl+C o 'q').

Hilos: el principal atiende al ejecutor, las ordenes y dibuja (PyBullet solo se toca desde aqui); HiloLectorUR lee el
grabador y guarda su ultimo q; otro hilo lee la consola y solo mete lineas de texto en una cola.
"""
import os
import queue
import sys
import threading
import time

AQUI = os.path.dirname(os.path.abspath(__file__))                       # carpeta src
sys.path.insert(0, os.path.join(AQUI, "librerias"))
ROBOTS = os.path.normpath(os.path.join(AQUI, "..", "datos", "robots.json"))        # rutas relativas a este script,
SECUENCIAS = os.path.normpath(os.path.join(AQUI, "..", "datos", "secuencias"))    # no a donde se lance

import ur  # noqa: E402
from red import ErrorRed  # noqa: E402
from secuencia import LIBRE, ErrorSecuencia, Reproductor, Secuencia  # noqa: E402
from simulador import ErrorSimulador, Simulador  # noqa: E402

VELOCIDAD = 0.1         # rad/s al arrancar; se cambia con 'ajustar' (maximo 0,3: ver ur.py)
ACELERACION = 0.2       # rad/s2 al arrancar; se cambia con 'ajustar' (maximo 0,5)

AYUDA = ("Comandos: g (guardar punto del grabador), v (previsualizar), e (ejecutar en el ejecutor), c (cancelar), "
         "r (reanudar), s/l [fichero] (salvar/cargar), b (borrar), ajustar <v rad/s> <a rad/s2>, q (salir)")


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


def _elegir_robots(robots, argumentos):
    """(grabador, ejecutor) a partir de robots.json y los argumentos de la linea de comandos (nada o dos nombres).
    Lanza ValueError si faltan robots, un nombre no existe o los dos son el mismo robot (mismo nombre o misma IP)."""
    if not argumentos:
        if len(robots) < 2:
            raise ValueError("{}: hacen falta al menos 2 robots (grabador y ejecutor)".format(ROBOTS))
        ejecutor, grabador = list(robots)[:2]          # el que se mueve es el primero, como en ensenar.py
    elif len(argumentos) == 2:
        grabador, ejecutor = argumentos
    else:
        raise ValueError("uso: copiar.py [grabador ejecutor]")
    for nombre in (grabador, ejecutor):
        if nombre not in robots:
            raise ValueError("no hay ningun robot llamado {} en {} (hay: {})".format(nombre, ROBOTS, ", ".join(robots)))
    if grabador == ejecutor or robots[grabador] == robots[ejecutor]:
        raise ValueError("el grabador y el ejecutor son el mismo robot ({})".format(robots[grabador]))
    return grabador, ejecutor


def _guardar_punto(secuencia, lector):
    """Añade a la secuencia el ultimo q del grabador (lo lee el hilo lector, no el Reproductor del ejecutor)."""
    with lector.cerrojo:
        q = lector.q
    if q is None:
        print("Todavia no se ha recibido la posicion del grabador {} ({})".format(lector.nombre, lector.ultimo_error or "sin datos"))
    elif not ur.es_punto_valido(q):
        print("No se guarda: el grabador da angulos fuera de [-2pi, 2pi] rad ({})".format(q))
    else:
        secuencia.append(list(q))
        print("Punto {} guardado".format(len(secuencia)))


def _comando(linea, rep, lector, simulador, ejecutor):
    """Ejecuta una linea de la consola. Devuelve True si hay que salir."""
    orden, _, argumento = linea.partition(" ")
    if orden == "q":
        return True
    if orden == "c":
        rep.cancelar()
    elif rep.fase != LIBRE and orden != "r":
        print("Secuencia en marcha o parada: solo 'c' (cancelar), 'r' (reanudar) o 'q'")
    elif orden == "g":
        _guardar_punto(rep.secuencia, lector)
    elif orden == "b":
        rep.secuencia.clear()
        print("Secuencia borrada")
    elif orden == "v":
        if not rep.secuencia or rep.q is None:
            print("Nada que previsualizar")
        else:
            print("Previsualizando {} puntos con el ejecutor en la ventana (ningun robot real se mueve)...".format(len(rep.secuencia)))
            simulador.previsualizar(ejecutor, rep.q, rep.secuencia)
            print("Previsualizacion terminada")
    elif orden == "e":
        rep.ejecutar()
    elif orden == "r":
        rep.reanudar()
    elif orden == "ajustar":
        try:
            velocidad, aceleracion = (float(x) for x in argumento.split())
        except ValueError:
            print("Uso: ajustar <velocidad rad/s> <aceleracion rad/s2>")
        else:
            rep.ajustar(velocidad, aceleracion)
    elif orden == "s":
        ruta = _ruta(argumento)
        try:
            os.makedirs(SECUENCIAS, exist_ok=True)
            rep.secuencia.guardar(ruta)
            print("{} puntos guardados en {}".format(len(rep.secuencia), os.path.basename(ruta)))
        except (ErrorSecuencia, OSError) as e:
            print("No se pudo guardar: {}".format(e))
    elif orden == "l":
        ruta = _ruta(argumento)
        try:
            rep.secuencia.cargar(ruta)
            print("{} puntos cargados de {}".format(len(rep.secuencia), os.path.basename(ruta)))
        except ErrorSecuencia as e:
            print("No se pudo cargar: {}".format(e))
    else:
        print(AYUDA)
    return False


def _dibujar_grabador(simulador, lector):
    """Pone el grabador simulado en el ultimo q leido (si hay conexion)."""
    with lector.cerrojo:
        q = lector.q
    if q:
        simulador.mover(lector.nombre, q)


def main(argumentos=()):
    """argumentos: los de la linea de comandos (nada o 'grabador ejecutor')."""
    robots = ur.leer_robots(ROBOTS)
    grabador, ejecutor = _elegir_robots(robots, list(argumentos))
    lector = ur.HiloLectorUR(grabador, ur.ClienteUR(robots[grabador]))      # solo lee: este cliente nunca envia ordenes
    robot = ur.ClienteUR(robots[ejecutor])
    rep = Reproductor(robot, Secuencia(), VELOCIDAD, ACELERACION)           # mueve y supervisa al ejecutor
    comandos = queue.Queue()
    simulador = Simulador()
    try:
        simulador.agregar_robot(grabador)
        simulador.agregar_robot(ejecutor)
        lector.start()
        # La consola se lee DESPUES de abrir la ventana: un input() ya bloqueado impide que PyBullet termine de abrirla.
        threading.Thread(target=_leer_consola, args=(comandos,), daemon=True).start()
        print("Grabador (solo lectura): {} ({}). Ejecutor (se mueve): {} ({})".format(
            grabador, robots[grabador], ejecutor, robots[ejecutor]))
        salir = False
        while not salir:                # si se cae la conexion con el ejecutor se vuelve a intentar
            try:
                robot.conectar()
                print("Conectado a {}. {}".format(robot.destino, AYUDA))
                for datos in robot.mensajes():
                    rep.procesar(datos)
                    if rep.reconectar:          # orden rechazada: la conexion vieja puede ser de solo lectura
                        rep.reconectar = False
                        break
                    if rep.q:
                        simulador.mover(ejecutor, rep.q)
                    _dibujar_grabador(simulador, lector)
                    while not comandos.empty() and not salir:
                        salir = _comando(comandos.get(), rep, lector, simulador, ejecutor)
                    if salir:
                        break
            except ErrorRed as e:       # red caida, robot que cierra o calla, mensajes que no se entienden
                print("Conexion perdida ({}). Reintentando en {} s...".format(e, ur.REINTENTO))
                rep.conexion_perdida()
                fin = time.monotonic() + ur.REINTENTO
                while not salir and time.monotonic() < fin:     # mientras espera, la consola y el dibujo siguen atendidos
                    _dibujar_grabador(simulador, lector)
                    try:
                        salir = _comando(comandos.get(timeout=0.1), rep, lector, simulador, ejecutor)
                    except queue.Empty:
                        pass
    finally:                            # q, Ctrl+C, ventana cerrada o un bug: el ejecutor se frena antes de cerrar nada
        if rep.ocupado:
            rep.cancelar()
        robot.desconectar()
        lector.detener()
        simulador.cerrar()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:           # es la forma normal de parar
        pass
    except (ValueError, ErrorSimulador) as e:       # ValueError: robots.json, una IP o los argumentos mal puestos
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    # Cualquier otra excepcion es un fallo del programa: Python imprime el traceback y sale con codigo 1
