# Origen: versión Claude 2

Versión archivada como historia; no se edita. Procedencia: carpeta `practica1_claude2\` de la copia de Drive del 2026-10-13 (commit `eec5574`, etiqueta `p1-origen`).

| Campo | Valor |
|---|---|
| Archivos de código | 5 `.py` (≈ 30 KB): `primaria.py` (módulo), `tiempo_real.py`, `varios_robots.py` + `robots.json`, `ensenar_reproducir.py` |
| Documentación | solo `README.md` |
| Última modificación | 2026-10-09 16:49–16:53 (fecha de los archivos) |
| Quién la escribió | Claude Code (VS Code) |
| Prompts | **Pendiente de Josu** (cuántos y cuáles). Se escribió ajustándose a los criterios del enunciado y a la simplicidad. |
| Enunciado | **sí** (el PDF de la práctica guiada; cita su apartado 8) |
| Qué se probó y con qué | La Pi, el 2026-10-13: ✅ `primaria.conectar` + `mensajes` + `leer_estado` contra el robot falso de `claude_1/simulador_ur.py` (5 mensajes tipo 16, `modo` = 7). En la sesión de escritura (2026-10-09), solo contra un robot y un visualizador falsos (buffer troceado, reconexión, varios robots, enseñar y reproducir con error y parada de protección). ❌ Nunca contra URSim ni robot real, ni se ha visto la ventana de PyBullet. Sin verificar: offsets de los mensajes tipo 20 (subtipos 6 y 10) y los 251 B del subpaquete 1. |

## Cambios respecto al original

- Se quitaron `ClientInterfaces_Primary.pdf` y `Práctica guiada visualizador de un UR3e por TCP IP.pdf`: idénticos (SHA256) a los de nivel superior; están en [fuentes/manuales/](../../../../fuentes/manuales/) y [fuentes/enunciados/](../../../../fuentes/enunciados/).
- `scriptmanualG5_.pdf` y `ur3e_rg2-0.1.0-py3-none-any.whl` se movieron a `fuentes/manuales/` y `fuentes/librerias/`.
- El `README.md` de esta versión cita rutas antiguas (`...\Redes\practica1`): es histórico.

## Pendiente de Josu

- [ ] Prompts usados (cuántos y cuáles) y fecha real de la sesión.
