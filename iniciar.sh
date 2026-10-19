#!/usr/bin/env bash
# Practica 1 (visualizador UR3e) en Linux: equivalente a iniciar.bat.
# Las IP de los robots estan en datos/robots.json (opcion 4 del menu).
# Tambien se puede lanzar directo, sin menu:  ./iniciar.sh primaria | tiempo_real | ensenar
# La primera vez crea el entorno (entorno/, un venv) e instala lo de requirements-linux.txt: necesita
# python3 (3.9 o superior) con el modulo venv e internet. Las siguientes veces no instala nada.
cd "$(dirname "$0")" || exit 1

PY=entorno/bin/python
if [ ! -x "$PY" ]; then
    echo "Primera vez: creando entorno/ e instalando dependencias (hace falta internet)..."
    python3 -m venv entorno \
        && "$PY" -m pip install --quiet --upgrade pip \
        && "$PY" -m pip install --quiet -r requirements-linux.txt \
        || { echo "No se pudo crear el entorno. Hace falta python3 >= 3.9 con venv (p. ej. sudo apt install python3-venv)."; rm -rf entorno; exit 1; }
fi

lanzar() {                      # $1 = primaria | tiempo_real | ensenar
    "$PY" -u -B "src/$1.py"
    codigo=$?
    echo
    echo "El programa ha terminado (codigo $codigo; 0 = normal, 1 = error explicado arriba)."
}

confirmar_ensenar() {
    read -r -p "ensenar ENVIA movej al robot. Robot libre y zona despejada? (s/n): " r
    [ "$r" = "s" ] || [ "$r" = "S" ]
}

case "$1" in
    primaria|tiempo_real) lanzar "$1"; exit ;;
    ensenar) confirmar_ensenar && lanzar ensenar; exit ;;
esac

while true; do
    echo "============================================================"
    echo "  PRACTICA 1 - visualizador de robots UR3e"
    echo "============================================================"
    echo "  1  Primaria     visualiza 1 o varios robots (puerto 30001)"
    echo "  2  Tiempo real  visualiza 1 o varios robots (puerto 30003)"
    echo "  3  Ensenar      guarda y reproduce puntos desde la consola"
    echo "                  ENVIA movej: solo con el robot libre y zona despejada"
    echo "  4  Cambiar las IP de los robots (datos/robots.json)"
    echo "  5  Salir"
    read -r -p "Elige una opcion (1-5): " op
    case "$op" in
        1) lanzar primaria ;;
        2) lanzar tiempo_real ;;
        3) confirmar_ensenar && lanzar ensenar ;;
        4) "${EDITOR:-nano}" datos/robots.json ;;
        5) exit 0 ;;
    esac
    echo
done
