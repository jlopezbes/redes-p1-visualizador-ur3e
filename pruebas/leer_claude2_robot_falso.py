"""
Prueba V2 de docs/pruebas.md: lee 3 estados con las funciones de versiones/claude_2/primaria.py.
Solo lectura. No usa primaria.main() porque abre PyBullet.

Antes hay que tener el robot falso en marcha (puerto 31001, no el de URSim):
    python -B -u practicas\\Practica1_visualizador_UR3e\\versiones\\claude_1\\simulador_ur.py 31001
Despues, desde la raiz del repo:
    python -B -u practicas\\Practica1_visualizador_UR3e\\pruebas\\leer_claude2_robot_falso.py [puerto]
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "versiones", "claude_2"))

import primaria  # noqa: E402  (se importa tras ajustar sys.path)

PUERTO = int(sys.argv[1]) if len(sys.argv) > 1 else 31001
ESTADOS = 3

n = 0
with primaria.conectar("127.0.0.1", PUERTO) as s:
    for tipo, mensaje in primaria.mensajes(s):
        if tipo != primaria.TIPO_ESTADO:
            print("mensaje tipo", tipo, "ignorado")
            continue
        n += 1
        estado = primaria.leer_estado(mensaje)
        print("estado", n, "q (rad) =", [round(x, 2) for x in estado["q"]], "modo =", estado["modo"])
        if n == ESTADOS:
            break
