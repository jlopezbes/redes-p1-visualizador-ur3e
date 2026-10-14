# Origen: versión a mano

Versión archivada como historia; no se edita. Procedencia: carpeta `practica1\` de la copia de Drive del 2026-10-13 (commit `eec5574`, etiqueta `p1-origen`).

| Campo | Valor |
|---|---|
| Archivos de código | `main.py` (1 537 B) |
| Última modificación | 2026-10-09 19:06 (fecha de los archivos) |
| Quién la escribió | Josu, a mano |
| Prompts | ninguno (sin IA) |
| Enunciado | sí (el PDF de la práctica guiada) |
| Qué se probó y con qué | La Pi, el 2026-10-13, con una copia con IP y puerto cambiados contra el robot falso de `claude_1/simulador_ur.py` en `127.0.0.1`: ❌ no imprime nada en 6 s. Causa en [docs/desde-pi/comparacion-versiones-p1.md](../../../../docs/desde-pi/comparacion-versiones-p1.md): tras leer la cabecera del subpaquete 0 no lee su cuerpo (42 B) y la siguiente lectura de 5 B cae en mitad de los datos. Contra URSim o un robot real: ❌ no probado. |

## Cambios respecto al original

- Se quitó `UR3e_rg2-0.1.tar.gz`: era idéntico (SHA256) al de `claude_1` y está ahora en [fuentes/librerias/](../../../../fuentes/librerias/).

## Pendiente de Josu

- [ ] Confirmar la fecha real de escritura y cualquier cosa que falte (¿qué se probó a mano?).
