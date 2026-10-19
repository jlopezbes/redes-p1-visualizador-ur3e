"""
Practica 1, sobresaliente: ENSEÑAR y reproducir puntos con la interfaz primaria (puerto 30001), desde la consola.

    python -u src\\ensenar.py

¡ENVIA movej al robot! Solo con el robot encendido y con los frenos liberados (robotMode = 7), en URSim con
Control remoto activado y, en un robot real, con el profesor delante, zona despejada y velocidades bajas.

Usa el PRIMER robot de datos\\robots.json. Se maneja escribiendo comandos (ver AYUDA). Los puntos se guardan en
datos\\secuencias\\. Parar con Ctrl+C o con 'q'.
Fallos: el programa explica la causa y sale con codigo 1 (0 con Ctrl+C o 'q').

Hilos: el principal lee el robot, atiende las ordenes y dibuja (PyBullet solo se toca desde aqui) y otro lee la consola
y solo mete lineas de texto en una cola.
"""
import os
import queue
import sys
import threading

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
    """Ejecuta una linea de la consola. Devuelve True si hay que salir."""
    orden, _, argumento = linea.partition(" ")
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
            print("Previsualizando {} puntos en la ventana (el robot real no se mueve)...".format(len(rep.secuencia)))
            simulador.previsualizar(nombre, rep.q, rep.secuencia)
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


def main():
    nombre, ip = next(iter(ur.leer_robots(ROBOTS).items()))     # el primer robot de datos\robots.json
    robot = ur.ClienteUR(ip)
    rep = Reproductor(robot, Secuencia(), VELOCIDAD, ACELERACION)
    comandos = queue.Queue()
    simulador = Simulador()
    try:
        simulador.agregar_robot(nombre)
        # La consola se lee DESPUES de abrir la ventana: un input() ya bloqueado impide que PyBullet termine de abrirla.
        threading.Thread(target=_leer_consola, args=(comandos,), daemon=True).start()
        salir = False
        while not salir:                # si se cae la conexion se vuelve a intentar
            try:
                robot.conectar()
                print("Conectado a {}. {}".format(robot.destino, AYUDA))
                for datos in robot.mensajes():
                    rep.procesar(datos)
                    if rep.q:
                        simulador.mover(nombre, rep.q)
                    while not comandos.empty() and not salir:
                        salir = _comando(comandos.get(), rep, simulador, nombre)
                    if salir:
                        break
            except ErrorRed as e:       # red caida, robot que cierra o calla, mensajes que no se entienden
                print("Conexion perdida ({}). Reintentando en {} s...".format(e, ur.REINTENTO))
                rep.conexion_perdida()
                try:                    # mientras espera, la consola sigue atendida: con 'q' se sale al instante
                    salir = _comando(comandos.get(timeout=ur.REINTENTO), rep, simulador, nombre)
                except queue.Empty:
                    pass
    finally:                            # q, Ctrl+C, ventana cerrada o un bug: el robot se frena antes de cerrar nada
        if rep.ocupado:
            rep.cancelar()
        robot.desconectar()
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
