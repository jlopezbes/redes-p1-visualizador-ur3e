# 01 – Contexto y objetivo

## Petición original del usuario (resumida, en sus palabras)

> "En VIEJO COMUNICACIONES verás un proyecto del año pasado donde comunicamos con un UR. Quiero volver a hacerlo pero para este año. Al final es leer un gemelo con el URSim y printear sus posiciones. Luego irá leer el de varios UR y luego moverlos. ¿Puedes ponerte a prototipar el código copiando donde puedas? Cualquier duda me preguntas. En una carpeta nueva de nombre `practica 1`."

El ejemplo de referencia está repartido entre la **práctica 1**, la **práctica 3** y el **proyecto final** del año pasado. (La práctica 3 es OPC UA y no aportó nada a esta fase.)

- "Gemelo" = el **URSim** (simulador oficial de Universal Robots, que hace de gemelo digital del robot). Existe además un visualizador 3D (`UR3e_rg2`, PyBullet) usado el año pasado; el usuario dijo que su uso "aún no está claro, como sea más fácil, con el enunciado ya afinaremos". Se dejó **opcional** (`--gemelo`).
- Orden de trabajo acordado: **primero con instancias de URSim, luego con los robots del laboratorio**.

## Qué se partió (código del año pasado)

| Archivo antiguo | Qué aportó |
|---|---|
| `Prácticas\Práctica1_JosuLópez\ProyectoUR.py` | Lectura por socket del puerto 30001, subpaquetes 0 y 1, hilos por robot, uso de `UR3eRG2` |
| `Prácticas\Práctica1_JosuLópez\Práctica1_JosuLópez.pdf` | Memoria: solo se implementaron los 3 primeros ejercicios; **los dos últimos (mover el robot) no se hicieron** |
| `ProyectoFinalCI\practica1_Asier_Burgos.py` | Versión más limpia (recv_exact, extract_subpacket) y las dos formas de mover: socket con `movej` URScript, y `rtde_control.moveJ` |
| `ProyectoFinalCI\cliente_serverV1.8_def.zip` → `mover_robot\controladorUR3_TCP.py` | Clase `ControladorUR3`; pinza RG2 vía `xmlrpc http://IP:41414 rg_grip` (no usada ahora, útil si se pide la pinza) |
| `UR3e_rg2-0.1.tar.gz` | Librería del gemelo 3D: clase `UR3eRG2` (`spawn_robot`, `move_robot`, `move_gripper`) |
| `URSim_VIRTUAL-5.12.6.1102099.rar` | Imagen VirtualBox de URSim 5.12.6 |

IPs de los robots reales del año pasado (laboratorio): `10.172.21.203`, `10.172.21.206` (y `10.172.21.202`, `.204` aparecen en comentarios). Posición "home" usada entonces:
`[0.005337, -1.571745, -0.002806, -1.574434, 0.004911, 0.001310]` ≈ `[0, -π/2, 0, -π/2, 0, 0]`.

## Preferencias y forma de trabajar del usuario (observadas)

- Habla **español**, directo y breve. Pide explicaciones **paso a paso** cuando es algo operativo (abrir VirtualBox, etc.).
- Ejecuta él mismo los pasos en VirtualBox y pega salidas de terminal cuando algo falla.
- Prefiere **lo más sencillo**: ante "IP distinta vs. localhost con otro puerto" eligió localhost con puertos distintos.
- Respondió a las dudas del asistente numeradas (1–4) y aprobó instalar dependencias.
- Aceptó que el asistente ejecutara comandos en su máquina (instalar pip, compilar pybullet, cambiar la red de la VM2 con `VBoxManage`), pero **no** que se muevan sus robots sin que lo sepa.
- Sus datos de contexto: usuario `josuulpz@gmail.com`; carpeta de trabajo `c:\Users\Estudiante\Josu\Redes`; no es un repositorio git.

## Interpretación de la petición y entregables

| Etapa | Entregable |
|---|---|
| "leer un gemelo con el URSim y printear sus posiciones" | `ejercicio1_leer_un_robot.py` |
| "leer el de varios UR" | `ejercicio2_varios_robots.py` |
| "y luego moverlos" | `ejercicio3_mover.py` |
| "leer uno y mover otro" (petición posterior; el usuario aclaró que quería que mover un robot de la VM mueva al otro de la otra VM, **no** el simulador PyBullet) | `ejercicio4_espejo.py` |
| Probar sin URSim | `simulador_ur.py` (robot falso) |
