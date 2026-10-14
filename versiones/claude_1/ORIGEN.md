# Origen: versión Claude 1

Versión archivada como historia; no se edita. Procedencia: carpeta `practica 1_claude\` de la copia de Drive del 2026-10-13 (commit `eec5574`, etiqueta `p1-origen`).

| Campo | Valor |
|---|---|
| Archivos de código | 8 `.py` (≈ 28 KB): `ur_primary.py` (módulo con `recv_exact` y el hilo `LectorUR`), `ejercicio1…5`, `gemelo.py`, `simulador_ur.py` (robot falso) |
| Documentación | `README.md` y `docs/` (`01_contexto_y_objetivo` … `07_pendiente_y_siguientes_pasos`, ≈ 40 KB) |
| Última modificación | 2026-10-08 12:06–16:39 (fecha de los archivos) |
| Quién la escribió | Claude Code (VS Code) |
| Prompts | **Pendiente de Josu.** La ficha del núcleo recoge (Josu, 2026-10-10) que la hecha con un solo prompt es la sin enunciado, es decir esta. |
| Enunciado | **no** (su documentación dice «no visto») |
| Qué se probó y con qué | Con 2 URSim en VirtualBox el 2026-10-08: ver `docs/05_pruebas_y_resultados.md`. La Pi, el 2026-10-13, con `LectorUR` y `formatear_estado` contra el robot falso: ✅ articulaciones en rad y `modo: running`. Gemelo 3D, `--metodo rtde` y `--arrancar`: ❌ sin verificar. |

## Cambios respecto al original

- `docs/02_protocolo_interfaz_primaria.md` pasó a [docs/ur-referencia.md](../../../../docs/ur-referencia.md) y `docs/04_entorno_y_reproduccion.md` a [docs/entorno.md](../../../../docs/entorno.md): valen para cualquier versión. Los demás `docs/` se quedan: describen esta versión y no la final.
- Se quitó `UR3e_rg2-0.1.tar.gz`: idéntico (SHA256) al de `a_mano`, está en [fuentes/librerias/](../../../../fuentes/librerias/).
- `URSim_VIRTUAL-5.12.6…rar` y `virtualbox-7.1…deb` (≈ 850 MB) están fuera de git, en `recursos-grandes/` (raíz de `Redes\`, ignorada; antes estuvo en `Josu\recursos-grandes\`).
- Los README y docs de esta versión citan rutas anteriores a la reorganización (`practica 1_claude\`, `docs\02_…`): son históricas.

## Pendiente de Josu

- [ ] Prompts usados (cuántos y cuáles) y fecha real de la sesión.
