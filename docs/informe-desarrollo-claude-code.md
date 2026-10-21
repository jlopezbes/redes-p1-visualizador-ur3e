# Informe: desarrollar la Práctica 1 con Claude Code

*Qué cambió, por qué cambió y qué enseña sobre trabajar con un agente de código.*

| | |
|---|---|
| **Práctica** | 1 · visualizador de un UR3e por TCP/IP (Redes de comunicación industriales, MUAECI) |
| **Periodo** | 2026-10-08 (primera versión) a 2026-10-21 (informe); defensa con el UR3e el 2026-10-20 |
| **Fuentes** | `git log` (85 commits), `depuración.md` (F1–F31), `decisiones.md` (D1–D31), `pruebas.md` (T1–T31), las cronologías de `docs/cronologia/`, `ORIGEN.md` de las tres versiones de partida y la memoria del agente |
| **Qué NO hice** | No he ejecutado el código ni las pruebas para este informe. Las cifras de pruebas salen de `pruebas.md`; las de líneas las he contado yo sobre git (ver «Método» en la sección 3) |

---

## 1. Resumen

La práctica pasó por **cinco ciclos** y el código se movió así: se generó rápido, se endureció de más, se podó con criterio humano, se amplió y, al final, se contrastó con el robot real.

1. **Generar** (14-oct). Claude Code escribe `src/` modular a partir de la mejor de tres versiones de partida: 663 líneas y 84 pruebas, todo contra robots falsos.
2. **Endurecer** (14-oct). Un agente auditor y otro corrector encuentran 14 fallos de robustez (F7–F20). El código crece un **50 %** (663 → 995 líneas) y llega a 149 pruebas.
3. **Podar** (15–16-oct). Josu pide soluciones más básicas y dicta sus criterios. El código baja un **29 %** (995 → 709). La poda quita justo dos protecciones necesarias (F22, F23) y hay que devolverlas.
4. **Ampliar** (17–19-oct). Un script por nivel, rutas relativas, una web de control que se escribe y se **retira en dos días**, entorno portable, Linux y `Lock`.
5. **Contrastar con la realidad** (20-oct). El UR3e real revela un fallo que **223 pruebas en verde no veían** (F31) y el profesor pide una función nueva en directo (`copiar.py`).

**Las cinco lecciones principales** (con su evidencia en las secciones 5 y 6):

1. El agente, sin límite de alcance, **sobre-ingenia**: añadió +50 % de código «por si acaso» a una persona que tiene que explicar cada línea.
2. **El robot falso refleja lo que el agente cree del protocolo**, no el protocolo. F31 pasó todas las pruebas porque prueba y código compartían el mismo error (el texto del error empezaba en el byte 32, no en el 35).
3. **Podar también rompe**: 4 de los 31 fallos son regresiones de una corrección o de una limpieza.
4. Lo que mantuvo el proyecto entendible fue **escribir**: casos de depuración numerados, decisiones con «Hoy», cronología por sesión y una lista viva de criterios de Josu.
5. **Dónde se trabaja importa**: lo hecho en otro PC sin git (la defensa) costó una fusión por hash y dejó `Commit: —` en los registros.

### Cifras de un vistazo

| Medida | Valor |
|---|---|
| Commits (todo el repo) / con prefijo `p1:` | 85 / 52 |
| Commits del 14-oct (estructura, fase 1 y auditoría) | 42 |
| Código `src/` (líneas no vacías) | 663 → 995 → 709 → 973 |
| Pruebas | 84 → 149 → 122 → 223 → 181 → 201 |
| Casos de depuración / decisiones / pruebas documentadas | 31 / 31 / 31 |
| Decisiones revisadas o retiradas después (líneas «Hoy») | 14 de 31 |
| Tamaño en bytes: código / pruebas / docs de la práctica | ≈ 54 KB / ≈ 142 KB / ≈ 158 KB |

---

## 2. Línea de versiones

| # | Versión | Fecha | Cómo se hizo | Resultado |
|---|---|---|---|---|
| V0 | `versiones/a_mano` | 9-oct | Josu, sin IA, con el enunciado. 1 archivo, 1 537 B | ❌ no imprime nada: lee la cabecera del subpaquete 0 pero no su cuerpo (F5) |
| V1 | `versiones/claude_1` | 8-oct | Claude Code, **sin el enunciado**. 8 `.py` (≈ 28 KB) y 8 `.md` (≈ 40 KB) | ✅ lectura contra 2 URSim. Mucho código de apoyo (5 ejercicios, gemelo 3D, robot falso) y la mejor documentación de entorno |
| V2 | `versiones/claude_2` | 9-oct | Claude Code, **con el enunciado**. 5 `.py` (≈ 30 KB) y un README | ✅ contra robot falso. Buffer con longitud validada, 4 niveles. Nunca probado con URSim |
| V3 | `src/` fase 1 | 14-oct | Claude Code a partir de V2, con ideas de V1 (hilo lector, robot falso). Módulos `red → ur → simulador/secuencia → tareas → main` | ⚠️ 84 pruebas, 663 líneas. Todo contra robots falsos |
| V4 | `src/` auditado | 14-oct | Auditor y corrector (agentes) por capas | ⚠️ 149 pruebas, 995 líneas (+50 %) |
| V5 | `src/` podado | 15–16-oct | Limpieza por capas con criterios de Josu | ⚠️ 122 pruebas, 709 líneas (−29 %) |
| V6 | por niveles | 17–19-oct | Prototipo preparado por la Pi y aplicado por Josu: `primaria.py`, `tiempo_real.py`, `ensenar.py`, `librerias/` | ✅ 223 pruebas en Windows con Python 3.7.5; probado con 2 URSim |
| V7 | portable + Linux | 19-oct | `iniciar.bat/.sh`, Python embebido, kit `uv` | ✅ Windows; ⚠️ Ubuntu («funciona», dato de Josu) |
| V8 | **defendida** (`p1-defensa`) | 20-oct | En el laboratorio, con el profesor, y fusionada después | ✅ UR3e: F31 corregido y `copiar.py` «funcionó a la primera» (dato de Josu, sin log) |

**Qué se tomó de cada versión de partida** (decisión D1–D5, propuesta de la Pi): de V2, el buffer con longitud validada y el módulo importable; de V1, el hilo lector, el robot falso y la documentación de entorno; de V0, nada de código, solo el caso de depuración F5, que es de los que el profesor pide saber explicar.

**Dato que falta:** los `ORIGEN.md` de V1 y V2 dicen «Prompts: pendiente de Josu». Nunca se registró cuántos prompts hubo ni cuáles. Es la única medida de «esfuerzo humano por versión» que habría permitido comparar enfoques, y no se puede reconstruir.

---

## 3. La evolución en números

### Líneas de `src/` (no vacías) a lo largo del tiempo

```
                                       líneas  pruebas
fase 1 (800dd7d)           █████████████  663      84
auditoría (ac99d04)        ████████████████████  995     149     ← +50 %
poda (7c6ec6d)             ██████████████  709     122     ← −29 %
+ robots.json (4f21b21)    ███████████████  729     125
reorg. + web (a50cd0d)     ██████████████████  904     223
web retirada (681aac4)     ███████████████  757     181     ← −662 líneas en src
+ Lock (8f9ea86)           ███████████████  763     181
defensa (eeff5de)          ███████████████████  973     201     ← incluye copiar.py (187)
                           (cada █ ≈ 50 líneas)
```

**Método.** Líneas no vacías de `src/*.py` en cada commit, contadas con `git show | Measure-Object -Line`. Los documentos hablan de 1176 → 817 líneas porque cuentan también las vacías y los docstrings; el porcentaje es el mismo (−31 % frente a mi −29 %). Las pruebas de 84 y 122 vienen de `pruebas.md`; el resto, también (T10–T31). En la fase 1 la ruta era `practicas/` (antes del renombrado), de ahí que el comando directo no la encuentre.

### Qué dicen los números

- **El mismo alcance cuesta ≈ 19 % más que la fase 1.** Sin `copiar.py` (la única función nueva), el final tiene 786 líneas frente a 663, y esas 123 líneas incluyen lo que se conservó del endurecimiento (límites del robot, parada por protección o emergencia, aviso del `stopj`, aviso de puerto equivocado), el rechazo C210 y los cambios de estructura (`ajustar`, consola, rutas). No he desglosado cuánto es de cada cosa.
- **Las pruebas pesan 2,4 veces el código** (2 339 contra 973 líneas). Tres de los 31 fallos (F6, F24, F28) eran pruebas mal planteadas, no código.
- **La documentación de la práctica pesa 2,9 veces el código** (≈ 158 KB contra ≈ 54 KB), con `decisiones.md` y `depuración.md` de ≈ 47 KB cada una. Es útil para la defensa, pero la memoria que se entrega tiene un tope de 6 páginas: el valor está en seleccionar, no en la cantidad.
- **Una funcionalidad entera pasó por el repo en dos días.** La web de control (D24, 17-oct) entró con ≈ 115 líneas de Python más `hmi.html`; se retiró el 19-oct (D27) borrando 662 líneas de `src/` y 42 pruebas. Josu la pidió, la vio y decidió que no la podía defender línea a línea.

---

## 4. Las correcciones, clasificadas

Los 31 casos de `depuración.md`, por causa principal (cada caso en una sola categoría):

| Categoría | Casos | n |
|---|---|---|
| Entorno e instalación | F1, F2, F3, F4, F30 | 5 |
| Defecto de la versión de partida | F5 | 1 |
| Robustez no cubierta (la encontró la auditoría) | F7, F9, F10, F11, F12, F13, F14, F15, F16, F18, F19, F20 | 12 |
| **Regresión** de un arreglo o de una limpieza | F17, F21, F22, F23 | 4 |
| Concurrencia o plataforma (Windows, Linux, Python embebido) | F8, F27, F29 | 3 |
| Pruebas mal planteadas (tiempos, carreras de la prueba) | F6, F24, F28 | 3 |
| Web y consola | F25, F26 | 2 |
| **Robot real** | F31 | 1 |

### Quién o qué encontró cada fallo

| Canal | Casos | n |
|---|---|---|
| Instalar y arrancar el entorno | F1–F4 | 4 |
| Traza de la Pi sobre el código de partida | F5 | 1 |
| **Auditor agente sin contexto** (con experimentos propios) | F7–F20 | 14 |
| Ejecutar la suite o el humo (Windows, ventana real) | F6, F21, F23, F24, F27, F28 | 6 |
| Ejecutar la web o la consola en la Pi | F25, F26 | 2 |
| Razonado, sin ejecutar | F22 | 1 |
| **Uso real por Josu** (`iniciar.bat`, Ubuntu, laboratorio) | F29, F30, F31 | 3 |

Tres lecturas:

1. **El auditor encontró mucho, pero de poco impacto real.** De sus 14 hallazgos (F7–F20), la propia tabla de `depuración.md` marca **11** (F10–F20) como casos que describen código que la poda cambió después. Cuando el modelo revisa en abstracto, detecta lo que *podría* pasar; Josu necesitaba lo que *pasa*.
2. **Lo que ocurre en la realidad llegó por uso, no por revisión.** F29 (el robot 2 inmóvil), F30 (Ubuntu con Python 3.14) y F31 (error C210) los encontró Josu usando el programa. F29 no tenía traza en la salida normal: el hilo moría en silencio y la consola decía «sin datos».
3. **Las regresiones son un coste fijo de cambiar.** F17 es una regresión del arreglo de F12; F21, del orden de las líneas al tocar `tareas.py`; F22 y F23, de la poda. Tres de los cuatro (F17, F21, F23) se vieron al **ejecutar**; F22 solo se detectó razonando, y se arregló sin haber visto el fallo. En ningún caso lo detectó la lectura del cambio.

### Casos ejemplares (síntoma → causa → lección)

**F5 · `a_mano` mudo (13-oct).** El programa no imprimía nada. La traza de cada cabecera de subpaquete mostró `sub 47 0` seguido de `sub 417 53`: tras leer la cabecera, el código no leía el cuerpo y la siguiente lectura caía en mitad de los datos. *Lección:* TCP es un flujo de bytes; el caso se usa de plantilla porque se explica en un minuto con una traza de 4 líneas.

**F31 · el robot real rechaza el `movej` (20-oct).** El UR3e devolvió «error del robot (codigo 210)» con texto vacío, luego otro 210 por el `stopj` y un «Robot detenido» falso. Dos causas, con distinto nivel de certeza: el robot decide al **abrir** el socket si la conexión es de solo lectura (una conexión abierta en Local sigue rechazando órdenes aunque se pase a remoto: *comprobado por Josu con el robot*), y `_leer_error` leía el texto desde el byte 35 en vez del 32 (*comprobado por la estructura de la trama*, según F31; no con una captura del robot). *Lección:* las 223 pruebas pasaban porque el robot falso y el código compartían la misma suposición. Un robot falso es una opinión sobre el protocolo, no una medida; ver recomendación R3. Primero se supuso «modo Local», y era falso: en el segundo intento ya estaba en remoto y fallaba igual.

**F29 · el robot 2 no se movía (19-oct).** Con el Python portable, dos hilos conectando a la vez fallaban a ratos con `LookupError: unknown encoding: idna`; el hilo moría con el traceback solo en `stderr`. Aislado con un script de 8 líneas sin robots (3 fallos de 120 en el portable, 0 de 40 en el Python del PC). Arreglo: `import encodings.idna` en `red.py` (0 de 120). *Lección:* algo que falla solo en un entorno es a menudo una carrera que el otro entorno esconde.

**F21 · `ensenar` mudo con la ventana real (14-oct).** Las 149 pruebas pasaban porque usaban un simulador falso sin ventana. Con la real, un `input()` ya bloqueado en otro hilo impedía abrir la ventana de PyBullet. La causa fue un reordenamiento hecho en la auditoría. *Lección:* ejecutar el humo con la ventana real **al cerrar cada capa**, no al final; hoy una línea de comentario en [ensenar.py:114](../src/ensenar.py#L114) guarda el motivo.

**F22 / F23 · la poda quita una protección (15–16-oct).** Al simplificar `ur.py`, desaparecieron dos guardas: la que avisa de un puerto de otro formato (`primaria --puerto 30003` conectaba y callaba) y la que mira `_parar` tras `conectar()` (`detener()` tardaba 2 s). F23 lo delató una prueba; F22, solo el razonamiento. *Lección:* antes de borrar una comprobación, preguntar **qué fallo del usuario la hacía falta** y dejar una prueba de esa carrera.

**F24 / F28 · pruebas escritas en Linux, ejecutadas en Windows (16 y 19-oct).** Un puerto cerrado en Windows tarda 1–2 s en rechazarse, y `time.sleep(0.4)` puede medir 0,39 s. Las pruebas de tiempo con márgenes ajustados fallan por el entorno, no por el código.

---

## 5. Las decisiones y su vida

De las 31 decisiones, **14 tienen una línea «Hoy»** (D3, D4, D6, D8, D9, D10, D11, D12, D13, D14, D15, D16, D22 y D24, esta última «retirada»). Las siete de la auditoría (D10–D16) fueron todas recortadas después.

| Decisión | Se tomó | Qué pasó |
|---|---|---|
| **D12** estado fresco + `PLAZO_ESTADO` | auditoría | **Sustituida por D20**: bastaba el timeout de lectura |
| **D14** fase `ESPERANDO_ESTADO` | auditoría | Quitada; se conservó solo lo que protege al robot (protección y emergencia, aviso del `stopj`) |
| **D15** topes de fichero + guardado atómico | auditoría | Eliminados; se mantiene la validación de 6 ángulos |
| **D10** una excepción por módulo | auditoría | Colapsada a `ErrorRed`; Josu **conservó** las otras tres «porque ayudan a entender el tipo de error» (D19) |
| **D3 / D29** `Lock` en el hilo lector | fase 1 | Quitado en la poda (D17); **vuelve** por decisión de Josu porque el enunciado lo recomienda |
| **D8** `main.py` + `tareas.py` | fase 1 | Desaparecen (D23): un script por nivel, sin `argparse` |
| **D24** web de control | 17-oct | Retirada en D27 |
| **D30** `copiar.py` | defensa | Nuevo script duplicando parte de `ensenar.py` a propósito (no tocar lo ya defendido) |

**Patrón:** las decisiones que sobrevivieron intactas son las que dan seguridad con el robot y las que Josu dictó con una razón concreta (límites de 0,3 rad/s y 0,5 rad/s², `es_punto_valido`, `stopj` siempre, ficheros en `datos/`). Las que cayeron son las que añadía el agente por completitud.

---

## 6. Lo que funcionó y lo que no

### Funcionó

1. **Casos de depuración numerados** con síntoma, aislamiento, causa, arreglo y lección, y marca de qué se ejecutó (✅ ⚠️ ❌). Hicieron posible preparar la defensa y detectar a tiempo lo no verificado. Ejemplo: F31 distingue lo comprobado con el robot de lo solo supuesto.
2. **Criterios de Josu escritos como lista viva** (12 puntos en `feedback-criterios-limpieza.md`). Cada corrección se convirtió en regla para la pasada siguiente, y por eso la poda convergió en vez de oscilar.
3. **Revisión por capas con una rama por capa**: Josu leía, retocaba y solo entonces se bajaba a la siguiente. Entre capas, revisión estática; ejecución al final.
4. **Agentes con roles separados** (auditor sin contexto, corrector con una prueba por arreglo, un commit de código y otro de docs por capa): reproducibles y trazables.
5. **Robot falso propio con tramas reales** y humo con la ventana real: permitieron trabajar sin hardware hasta la primera prueba con URSim (5 días después de la fase 1). Funcionaron hasta donde alcanza lo que el agente sabe del protocolo.
6. **Estructura de carpetas y de scripts**: el profesor la valoró «mucho» en la defensa (dato de Josu). Merece conservarse como plantilla de la Práctica 2.
7. **Continuidad entre sesiones y PCs** con `CLAUDE.md`, memoria del agente y cronología: la fusión de la copia del pendrive se hizo comparando por hash y por líneas, sin perder nada.

### No funcionó, o costó caro

1. **Sin presupuesto de alcance, el agente añade.** La auditoría pidió robustez y devolvió +50 % de código con validaciones de `nan`, tipos internos y timeouts que nunca ocurren en uso real. Josu: «no seas tan fino. Hay formas mucho más básicas de resolver cosas».
2. **El oráculo de las pruebas es el mismo agente.** F31 es el ejemplo; la sección «Aviso general» de `pruebas.md` ya lo decía y por eso las pruebas con robot falso llevan ⚠️.
3. **Cambios fuera de git.** En la defensa se trabajó en otro PC sin repositorio: F31 dice «Commit: — (el proyecto no es un repositorio git)», y el repo tuvo que reconstruirse por comparación. El código de las dos copias era distinto.
4. **Deriva documental.** D23–D31 siguen con «Commit: pendiente» aunque hay commits; `depuración.md` tiene en la cabecera solapes de qué caso es de qué sesión (lo reconoce la cronología del 20-oct); `Redes\CLAUDE.md` (de la Pi) seguía mencionando la web retirada. Con documentos que pesan casi 3 veces el código, la deriva es inevitable si no hay una revisión al cerrar cada sesión.
5. **Poda sin red.** F22 se detectó razonando y F23 con una prueba que alguien tuvo que escribir antes. La limpieza se hizo «sin ejecutar entre capas» por decisión de proceso, y ahí se pierde la alarma temprana.
6. **El enunciado llegó de segunda mano.** V1 no lo tuvo; en la fase 1 el PDF no se pudo leer (falta `pdftoppm`) y el resumen del README era indirecto. La lectura del enunciado debe ser lo primero que verifique el agente.
7. **Git no distingue la autoría.** Los 85 commits van con la identidad de Josu y sin trailer `IA:` (decisión de Josu del 14-oct). Es coherente con el régimen «EJECUTA», pero toda la trazabilidad de la IA descansa en cronologías y decisiones, no en git.

---

## 7. Recomendaciones: una receta para el siguiente trabajo

Son propuestas mías a partir de lo anterior, no hechos del repo. Las he ordenado por el momento en que se aplican. **Convertidas en normas, viven en la [guía común](../../../docs/guia-programar-con-ia.md)**, que es la que se aplica a todas las prácticas; este informe queda como evidencia.

### Al empezar

- **R1. Alcance y criterios desde el primer prompt.** Poner en `CLAUDE.md` los 12 criterios de la poda **antes** de generar, con un presupuesto («≤ 800 líneas en `src/`, ninguna función de uso único, ninguna validación de argumentos internos»). Habría evitado el ciclo endurecer → podar completo (≈ 330 líneas añadidas y quitadas).
- **R2. Verificar la lectura del enunciado.** Que el agente cite los apartados que cumple; si el PDF no se lee, resolverlo antes (V1 y la fase 1 trabajaron a ciegas).

### Durante

- **R3. Trazas reales como patrón de oro.** Grabar una vez los bytes de URSim y del UR3e (primaria, tiempo real, un mensaje de error) y construir los robots falsos y las pruebas de decodificación **a partir de esas capturas**, no de la descripción del protocolo. Es la corrección que mejor habría atrapado F31 (byte 32 contra 35).
- **R4. Auditoría con filtro de realismo.** Pedirle al auditor, para cada hallazgo, «¿ocurre con un robot, una red y un fichero normales?» y un coste en líneas. Aplicar solo lo que ocurra; lo hipotético, a una lista aparte. Así F7–F20 habrían sido 3 o 4 cambios, no 14.
- **R5. Antes de quitar, anotar la protección.** Para cada comprobación que se elimine, una línea: «protegía contra X; prueba Y». F22 y F23 son exactamente este hueco.
- **R6. Humo real al cerrar cada capa**, no al final (F21), y pruebas de tiempo con margen holgado y sin igualdad (F24, F28).
- **R7. Un solo canal de cambios.** Aunque se trabaje en el PC del laboratorio: `git init` en la copia, o al menos un `git diff` guardado. Hoy lo salvó la fusión por hash, pero el historial de la defensa quedó en un solo commit.

### Al cerrar cada sesión

- **R8. Un paso de coherencia**: marcar los `Commit: pendiente` con su hash, repasar la cabecera de `depuración.md`, comprobar que `CLAUDE.md`, `README.md` y las tablas de pruebas dicen lo mismo. El skill `/close` ya hace casi todo; este punto es la comprobación cruzada.
- **R9. Registrar los prompts relevantes** (aunque sea el primero de cada ciclo y cada corrección de Josu). Es lo único que no se pudo reconstruir (`ORIGEN.md` de V1 y V2) y alimenta directamente la sección «Uso de la IA» de la memoria.

---

## 8. Estado final del código

Revisé a fondo `ur.py` y `ensenar.py`; el resto lo conozco por los documentos y por las cifras de git. No he revisado `copiar.py` línea a línea.

**Lo que está bien resuelto**

- Docstring de cabecera con el **formato de los mensajes** y la separación de errores ([ur.py:1-18](../src/librerias/ur.py#L1-L18)): se puede defender sin abrir el PDF.
- **Constantes con nombre y unidad** ([ur.py:27-53](../src/librerias/ur.py#L27-L53)), `movej` con argumentos solo por nombre para no mezclar velocidad y aceleración ([ur.py:205](../src/librerias/ur.py#L205)).
- **Los comentarios explican el porqué** y guardan la historia de los fallos: [ensenar.py:114](../src/ensenar.py#L114) (F21), [ur.py:249](../src/librerias/ur.py#L249) (F23), el orden de los campos de la trama de error ([ur.py:186](../src/librerias/ur.py#L186), F31).
- Cada script se ejecuta solo, con rutas relativas a sí mismo ([ensenar.py:21-24](../src/ensenar.py#L21-L24)).

**Lo que se podría pulir** (no es urgente y Josu decide qué se toca antes de entregar)

| Dónde | Observación |
|---|---|
| [ur.py:51](../src/librerias/ur.py#L51) | `CODIGO_SIN_REMOTO` tiene un comentario de ≈ 150 caracteres y el nombre sugiere una causa («sin remoto») más estrecha de la confirmada. `decisiones.md` ya lo marca como limpieza pendiente |
| [ur.py:64-89](../src/librerias/ur.py#L64-L89) | `leer_robots` y `elegir_robots` (JSON e `input`) viven en el módulo del protocolo. Josu los dejó como funciones sueltas a propósito; es una concesión de ubicación |
| [ur.py:182-202](../src/librerias/ur.py#L182-L202) | `_leer_error` decodifica y a la vez decide una política (`rechazada`). Funciona, pero mezcla dos responsabilidades |
| [ensenar.py:117-131](../src/ensenar.py#L117-L131) | Bucle doble y una bandera `rep.reconectar` que el llamador consulta y repone. Es lo más difícil de explicar en un cambio en caliente |
| [ensenar.py:21-29](../src/ensenar.py#L21-L29) | El arranque (`sys.path` y `# noqa: E402`) se repite en cada script (D23 lo aceptó). Con 4 scripts es tolerable; con más, pediría un helper |
| [ensenar.py:2](../src/ensenar.py#L2) | Docstring con tildes y `¡`, mientras `ur.py` y los textos de consola van en ASCII. Inconsistente, sin consecuencia en el funcionamiento |
| `copiar.py` | Repite `_leer_consola`, `_ruta` y `_comando` de `ensenar.py`: duplicación aceptada para no tocar lo ya defendido (D30) |

---

## 9. Anexos

### A. Fases del historial (85 commits, 14 a 21-oct)

| Fase | Commits (primero … último) | Contenido |
|---|---|---|
| Estructura y git | `eec5574` … `785c99e` | Repo inicial, tres versiones archivadas, `fuentes/`, docs, `.gitattributes` |
| Fase 1 de código | `5c1248d` … `6a47cb4` | Un módulo por commit con sus pruebas: `red`, `ur`, `simulador`, `secuencia`, `tareas`/`main`, humo y docs |
| Auditoría por capas | `e639b91` … `ac99d04` | Cuatro pares «capa N» + «documenta la capa N»; F7–F21 |
| Limpieza por capas | `e5ef55b` … `7c6ec6d`, `4a56083`, `4f21b21` | Cinco capas, tests adaptados, robot desde JSON (D22) |
| Reorganización | `58d3e9c`, `a50cd0d`, `2c55291` | Scripts por nivel, `librerias/`, web (D23–D25), F27 |
| Portable y Linux | `96f2855` … `7c42362` | `iniciar.bat`, `iniciar.sh`, kit `uv`; F28–F30; web retirada (`681aac4`) |
| Lock y mediciones | `8f9ea86`, `19bc459` | D29, T25–T27 |
| Defensa | `eeff5de`, `a91def0` (`p1-defensa`) | F31, D30, D31, `copiar.py`, T28–T31 |

### B. Tabla completa de fallos

| F | Fecha | Qué pasó | Categoría | Lo encontró |
|---|---|---|---|---|
| F1 | 8-oct | `pybullet` no instala en Windows con Python 3.7 | entorno | instalar |
| F2 | 8-oct | `pip install ur_rtde` falla por permisos | entorno | instalar |
| F3 | 8-oct | `UR3e_rg2` no instala con 3.7 | entorno | instalar |
| F4 | 8-oct | Segundo URSim: NAT frente a puente y placeholders en PowerShell | entorno | uso de Josu |
| F5 | 13-oct | `a_mano` no lee el cuerpo del subpaquete 0 | partida | traza de la Pi |
| F6 | 14-oct | Prueba intermitente: el `stopj` aún no ha llegado | prueba | repetir la suite |
| F7 | 14-oct | Puerto fuera de 0–65535 conecta a otro | robustez | auditor |
| F8 | 14-oct | `cerrar()` desde otro hilo da `OSError` crudo | concurrencia | auditor |
| F9 | 14-oct | Errores de socket crudos y `abierta` obsoleta | robustez | auditor |
| F10 | 14-oct | `timeout_lectura` a `None`/`0` | robustez | auditor |
| F11 | 14-oct | `ultimo_q()` entrega `q` viejo; el hilo muere callado | robustez | auditor |
| F12 | 14-oct | `movej` sin saber si el robot sigue | robustez | auditor |
| F13 | 14-oct | Mensaje cortado, `nan`, texto raro | robustez | auditor |
| F14 | 14-oct | `parar()` lento, `puerto=0`, `stopj` sin validar | robustez | auditor |
| F15 | 14-oct | `stopj` no sale y se decía «detenida» | robustez | auditor |
| F16 | 14-oct | `movej` con protección activa; `reanudar` tras borrar | robustez | auditor |
| F17 | 14-oct | `e` falla tras una vista previa larga (regresión de F12) | regresión | auditor |
| F18 | 14-oct | Ficheros de secuencia malos; guardado destructivo | robustez | auditor |
| F19 | 14-oct | Simulador cae con errores de la librería | robustez | auditor |
| F20 | 14-oct | Configuración mala, Ctrl+C y EOF acaban en traceback | robustez | auditor |
| F21 | 14-oct | `ensenar` mudo con la ventana real | regresión | humo con ventana |
| F22 | 16-oct | `--puerto` de la otra interfaz conecta y calla | regresión | razonado |
| F23 | 16-oct | `detener()` tarda 2 s si llega mientras conecta | regresión | suite |
| F24 | 16-oct | Pruebas nuevas fallan por Windows y por un cliente falso | prueba | suite en Windows |
| F25 | 17-oct | La web salía vacía al abrirse | web | Firefox sin cabeza |
| F26 | 17-oct | `Fatal Python error` al salir con `q` (3.11) | consola | humo en la Pi |
| F27 | 19-oct | El servidor web no leía el cuerpo del POST: RST en Windows | plataforma | suite, Python portable |
| F28 | 19-oct | Tres pruebas fallan por tiempos de Windows | prueba | suite en Windows |
| F29 | 19-oct | Robot 2 inmóvil: carrera del códec `idna` | plataforma | Josu + humo |
| F30 | 19-oct | Ubuntu con Python 3.14: `pybullet` sin binarios | entorno | Josu en Ubuntu |
| F31 | 20-oct | UR3e rechaza el `movej` (C210) y el texto se leía mal | robot real | Josu en el laboratorio |

### C. Límites de este informe

- **No he ejecutado nada.** Las pruebas y sus números son los de `pruebas.md`; los resultados con URSim y UR3e son los que ahí constan, algunos (T29, T30) solo de palabra de Josu y sin log.
- **No puedo atribuir autoría línea a línea**: git no distingue entre lo escrito por Claude Code, por la Pi, por los agentes o por Josu. Las proporciones de «humano contra agente» no se pueden calcular; sí cuándo intervino Josu (criterios, poda, web, `Lock`, estructura).
- **Hechos recibidos de palabra**: «funcionó a la primera», «funciona en Ubuntu» y el comentario del profesor sobre la estructura son datos de Josu.
- **Cifras mías**: las líneas por commit y el porcentaje (+50 %, −29 %, +19 %); los tamaños en bytes, de la lista de archivos del día del informe.
- La clasificación de los 31 casos en categorías y canales es **mía**; con otros criterios algunos casos podrían cambiar de columna (por ejemplo F23, que es a la vez regresión y carrera).
