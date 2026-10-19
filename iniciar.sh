#!/usr/bin/env bash
# Practica 1 (visualizador UR3e) en Linux: equivalente a iniciar.bat. Se lanza desde una terminal:  bash iniciar.sh
# Las IP de los robots estan en datos/robots.json (opcion 4 del menu).
# Tambien se puede lanzar directo, sin menu:  bash iniciar.sh primaria | tiempo_real | ensenar
#
# La primera vez crea el entorno (entorno/) con "uv", que descarga un Python 3.11 propio (no hace falta sudo, ni
# compilador, ni que el Python del sistema sea el adecuado: pybullet solo tiene binarios hasta Python 3.11) e instala
# lo de requirements-linux.txt. Necesita internet y uv. Las siguientes veces no instala nada.
cd "$(dirname "$0")" || exit 1

PY=entorno/bin/python
if [ ! -x "$PY" ]; then
    if ! command -v uv > /dev/null 2>&1; then
        echo "Falta 'uv' (instalador de entornos de Python). Instalalo una vez con:"
        echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo "y vuelve a lanzar este script en una terminal NUEVA (o antes:  source \$HOME/.local/bin/env)."
        exit 1
    fi
    echo "Primera vez: creando entorno/ con Python 3.11 e instalando dependencias (hace falta internet, tarda unos minutos)..."
    uv venv --python 3.11 entorno \
        && uv pip install --python "$PY" -r requirements-linux.txt \
        || { echo "No se pudo crear el entorno (mira el error de arriba)."; rm -rf entorno; exit 1; }
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
