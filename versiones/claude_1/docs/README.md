# Documentación – Práctica 1 (comunicación con robots UR)

> **Si eres un agente que retoma este trabajo, lee primero este archivo y luego `07_pendiente_y_siguientes_pasos.md`.**
> Todo lo demás es referencia.

Fecha de cierre de esta fase: **2026-10-08**. Idioma de trabajo con el usuario: **español**. Plataforma: **Windows 11, PowerShell, Python 3.7.5**.

## Estado en una página

| Etapa pedida por el usuario | Estado | Archivo |
|---|---|---|
| 1. Leer un robot (URSim) y printear sus posiciones | ✅ hecho y probado con URSim real | `ejercicio1_leer_un_robot.py` |
| 2. Leer varios UR a la vez | ✅ hecho y probado con 2 URSim reales | `ejercicio2_varios_robots.py` |
| 3. Mover los robots | ✅ hecho y probado con 2 URSim reales (método `socket`) | `ejercicio3_mover.py` |
| Extra: leer uno y mover otro (espejo) | ✅ hecho y probado con 2 URSim reales (método `speed`) | `ejercicio4_espejo.py` |
| Extra: espejo bidireccional (primario/secundario) | ⚠️ escrito y con sintaxis comprobada; **sin probar contra robots** | `ejercicio5_bidireccional.py` |
| Gemelo 3D (PyBullet) | ⚠️ instalado y arranca; **no verificado visualmente** | `gemelo.py` + flag `--gemelo` |
| Método `rtde` (ur_rtde) | ⚠️ instalado, **nunca ejecutado contra un robot** | flags `--metodo rtde` |
| Robots físicos del laboratorio | ⏳ **no empezado** (el usuario dijo "primero las instancias, luego los del laboratorio") | – |
| Enunciado oficial de este año | ⏳ **no visto**; el usuario dijo "con el enunciado ya afinaremos" | – |

El usuario cerró la fase con "Perfecto. Buen trabajo, terminado" y no pidió nada más.

## Índice de documentos

| Archivo | Contenido |
|---|---|
| [01_contexto_y_objetivo.md](01_contexto_y_objetivo.md) | Qué se pidió, de dónde se partió (proyecto del año pasado), preferencias del usuario |
| [02_protocolo_interfaz_primaria.md](02_protocolo_interfaz_primaria.md) | Formato binario de los paquetes del UR (puerto 30001), con los `struct` exactos |
| [03_arquitectura_codigo.md](03_arquitectura_codigo.md) | Qué hace cada archivo, funciones, flags y ejemplos de salida |
| [04_entorno_y_reproduccion.md](04_entorno_y_reproduccion.md) | Cómo reproducir el entorno desde cero: VMs, puertos, Python, pybullet, ur_rtde |
| [05_pruebas_y_resultados.md](05_pruebas_y_resultados.md) | Qué se probó, cómo, con qué resultados numéricos, y qué NO se probó |
| [06_problemas_y_decisiones.md](06_problemas_y_decisiones.md) | Bugs del código antiguo, problemas encontrados, decisiones y por qué |
| [07_pendiente_y_siguientes_pasos.md](07_pendiente_y_siguientes_pasos.md) | Qué falta, riesgos conocidos, sugerencias para el siguiente agente |

## Mapa de carpetas

```
c:\Users\Estudiante\Josu\Redes\
├── practica 1\                          <- ESTE TRABAJO (código nuevo)
│   ├── README.md                        resumen rápido y comandos
│   ├── ur_primary.py                    parser de la interfaz primaria + hilo LectorUR
│   ├── gemelo.py                        wrapper del visualizador 3D (import perezoso)
│   ├── ejercicio1_leer_un_robot.py
│   ├── ejercicio2_varios_robots.py
│   ├── ejercicio3_mover.py
│   ├── ejercicio4_espejo.py
│   ├── simulador_ur.py                  robot FALSO para pruebas sin URSim
│   └── docs\                            <- ESTA DOCUMENTACIÓN
│
├── VIEJO COMUNICACIONES\                <- material del año pasado (SOLO LECTURA, no tocar)
│   ├── UR3e_rg2-0.1.tar.gz              librería del gemelo 3D (PyBullet)
│   ├── URSim_VIRTUAL-5.12.6.1102099.rar imagen de VirtualBox con URSim
│   ├── virtualbox-7.1_...deb            instalador de VirtualBox para Ubuntu (no sirve en Windows)
│   ├── Prácticas\Práctica1_JosuLópez\   ProyectoUR.py + PDF de la práctica 1 del año pasado
│   ├── Prácticas\Práctica2_JosuLópez\   Modbus (no relacionado con esta fase)
│   ├── Prácticas\Práctica3_JosuLópez\   OPC UA (no relacionado con esta fase)
│   └── ProyectoFinalCI\                 proyecto final: practica1_Asier_Burgos.py, cliente_serverV1.8_def.zip, memoria, presentación
│
└── (otras carpetas de prácticas genéricas de sockets: loopback_*, tiempo_*, multi_*; no usadas)
```

## Reglas de seguridad aprendidas (importante)

1. **Los robots URSim del usuario son reales para el usuario**: cualquier script que envíe `movej`/`speedj` los mueve. En una prueba temprana se movió el URSim del usuario **sin avisar** (ver `06_problemas_y_decisiones.md`, incidente nº 1). Avisa siempre antes de mover.
2. **No ejecutes `simulador_ur.py` mientras URSim esté abierto** con los mismos puertos: VirtualBox escucha en `127.0.0.1:30001` y el simulador en `0.0.0.0:30001`; ambos conviven y el cliente puede acabar hablando con el equivocado.
3. **No modifiques `VIEJO COMUNICACIONES\`**; es material de referencia. Las extracciones se hicieron en `%TEMP%`.
