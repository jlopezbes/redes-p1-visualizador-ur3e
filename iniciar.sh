#!/usr/bin/env bash
# Practica 1 (visualizador UR3e) en Linux: equivalente a iniciar.bat. Se lanza desde una terminal:  bash iniciar.sh
# Las IP de los robots estan en datos/robots.json (opcion 4 del menu).
# Tambien se puede lanzar directo, sin menu:  bash iniciar.sh primaria | tiempo_real | ensenar | copiar [grabador ejecutor]
#
# La primera vez crea el entorno (entorno-linux/) con la carpeta linux/ de esta practica (uv, un Python 3.11 y las
# librerias ya descargadas): no hace falta internet, ni sudo, ni compilador, ni que el Python del sistema sea el
# adecuado (pybullet solo tiene binarios para Linux hasta Python 3.11 y Ubuntu nuevo trae 3.14). Las siguientes
# veces no instala nada.
# Sin linux/ (p. ej. un clon del repo), usa uv del sistema y descarga todo de internet.
cd "$(dirname "$0")" || exit 1

PY=entorno-linux/bin/python
if [ ! -x "$PY" ]; then
    if [ -f linux/uv ]; then
        echo "Primera vez: creando entorno-linux/ con el kit de linux/ (sin internet, unos segundos)..."
        chmod +x linux/uv
        export UV_PYTHON_DOWNLOADS=never
        rm -rf entorno-linux linux/python
        mkdir -p linux/python \
            && tar -xzf linux/cpython-*-install_only.tar.gz -C linux/python \
            && linux/uv venv --python linux/python/python/bin/python3 entorno-linux \
            && linux/uv pip install --python "$PY" --no-deps --no-index --find-links linux/wheels -r requirements-linux.txt \
            || { echo "No se pudo crear el entorno (mira el error de arriba)."; rm -rf entorno-linux; exit 1; }
    elif command -v uv > /dev/null 2>&1; then
        echo "Primera vez: creando entorno-linux/ con Python 3.11 e instalando dependencias (hace falta internet)..."
        rm -rf entorno-linux
        uv venv --python 3.11 entorno-linux \
            && uv pip install --python "$PY" --no-deps -r requirements-linux.txt \
            || { echo "No se pudo crear el entorno (mira el error de arriba)."; rm -rf entorno-linux; exit 1; }
    else
        echo "Falta la carpeta linux/ (el kit con uv, Python 3.11 y las ruedas, no incluido en esta entrega)"
        echo "y tampoco hay 'uv' instalado. Instala uv con:  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

lanzar() {                      # $1 = primaria | tiempo_real | ensenar | copiar; el resto se pasa al script
    "$PY" -u -B "src/$1.py" "${@:2}"
    codigo=$?
    echo
    echo "El programa ha terminado (codigo $codigo; 0 = normal, 1 = error explicado arriba)."
}

confirmar_ensenar() {
    read -r -p "ensenar ENVIA movej al robot. Robot libre y zona despejada? (s/n): " r
    [ "$r" = "s" ] || [ "$r" = "S" ]
}

confirmar_copiar() {
    read -r -p "copiar ENVIA movej al EJECUTOR (1er robot de robots.json; el 2o solo se lee). Ejecutor libre y zona despejada? (s/n): " r
    [ "$r" = "s" ] || [ "$r" = "S" ]
}

case "$1" in
    primaria|tiempo_real) lanzar "$1"; exit ;;
    ensenar) confirmar_ensenar && lanzar ensenar; exit ;;
    copiar) confirmar_copiar && lanzar "$@"; exit ;;
esac

while true; do
    echo "============================================================"
    echo "  PRACTICA 1 - visualizador de robots UR3e"
    echo "============================================================"
    echo "  1  Primaria     visualiza 1 o varios robots (puerto 30001)"
    echo "  2  Tiempo real  visualiza 1 o varios robots (puerto 30003)"
    echo "  3  Ensenar      guarda y reproduce puntos desde la consola"
    echo "                  ENVIA movej: solo con el robot libre y zona despejada"
    echo "  6  Copiar       graba puntos en el 2o robot y los ejecuta en el 1o"
    echo "                  ENVIA movej al 1o: solo con ese robot libre y zona despejada"
    echo "  4  Cambiar las IP de los robots (datos/robots.json)"
    echo "  5  Salir"
    read -r -p "Elige una opcion (1-6): " op
    case "$op" in
        1) lanzar primaria ;;
        2) lanzar tiempo_real ;;
        3) confirmar_ensenar && lanzar ensenar ;;
        4) "${EDITOR:-nano}" datos/robots.json ;;
        5) exit 0 ;;
        6) confirmar_copiar && lanzar copiar ;;
    esac
    echo
done
