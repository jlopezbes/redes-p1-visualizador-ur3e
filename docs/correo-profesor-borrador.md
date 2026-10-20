# Correo al profesor · cambios tras la defensa (borrador)

> **Borrador para cerrar con la Pi, no se envía tal cual.** `[JOSU]` = completa o corrige tú. Está escrito para el profesor: breve, sin jerga de la IA y con lo que cambió en el código. Los datos salen de F31, D30 y D31 (`docs/depuración.md` y `docs/decisiones.md`).

**Asunto:** Práctica 1 (UR3e por TCP/IP) · entrega con los cambios de la defensa

Buenos días, `[JOSU: nombre del profesor]`:

Le adjunto la memoria y la carpeta del programa de la Práctica 1 con los dos cambios que hicimos en la defensa del 20 de octubre con los UR3e del laboratorio:

**1. Fallo corregido: el robot rechazaba el `movej` (error 210).**
- *Qué pasaba:* si el programa abría la conexión con el pendant en modo Local, el robot rechazaba las órdenes aunque después se pasara a Control remoto; el programa mostraba un error sin texto y un «Robot detenido» falso, porque el `stopj` también era rechazado.
- *Causa:* el robot decide al abrir la conexión si es de solo lectura, y el texto del error se leía desde un byte equivocado (el 35 en vez del 32).
- *Arreglo:* el programa reconoce el error 210, explica que la orden no se ha ejecutado, no envía `stopj` y vuelve a conectar; la secuencia se conserva y se continúa con `r`. En `red.py` el cierre del socket hace ahora `shutdown()` antes de `close()`, necesario en Linux (`ur.py`, `secuencia.py`, `ensenar.py`, `red.py`).

**2. Funcionalidad nueva pedida en la defensa: `copiar.py`.**
Graba puntos moviendo a mano un robot (que solo se lee, nunca recibe órdenes) y los ejecuta en otro con los mismos límites de velocidad y aceleración. Se lanza con `iniciar.bat`/`iniciar.sh` (opción 6) o con `python src/copiar.py [grabador ejecutor]`. En la defensa funcionó a la primera con los UR3e.

**Otros cambios:** `datos/robots.json` queda con las IP del laboratorio (`10.172.21.205` y `.206`; para URSim hay que poner las del aula) y los menús de `iniciar.bat`/`iniciar.sh` tienen la opción nueva.

**Documentación:** el fallo está en `docs/depuración.md` (F31), las decisiones en `docs/decisiones.md` (D30 y D31), las pruebas en `docs/pruebas.md` (T28 a T31) y el resumen en el `README.md` de la práctica. La carpeta incluye 201 pruebas automáticas (con robots falsos), entre ellas las del error 210 y las de `copiar.py`.

`[JOSU: una frase propia, p. ej. qué aprendiste o qué harías distinto]`

Un saludo,
Josu `[apellidos]`
