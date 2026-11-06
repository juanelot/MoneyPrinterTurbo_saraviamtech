# Saraviamtech Studio

Estudio de creación de video con IA desarrollado por **[Saraviamtech](https://github.com/juanelot)**.
Va del tema o el guion al video final montado, con voz, escenas y prompts para Google Flow, subtítulos animados, edición con efectos y miniatura.

Claude hace todo el trabajo de texto e imagen a través de **Claude CLI**, con tu suscripción de Claude y sin API key. El montaje se hace con ffmpeg en tu máquina o en tu VPS. En la máquina local, las imágenes de cada escena también se pueden generar **gratis y solas en Google Flow** (Nano Banana).

El repositorio contiene dos aplicaciones sobre el mismo motor (MoneyPrinterTurbo):

| App | Para qué | Dónde |
|---|---|---|
| **Estudio** (`estudio-ui`) | Videos por pasos con Claude: guion, voz, escenas, contenido, edición y miniatura | `localhost:3100` · https://studio.saraviamtech.com |
| **Virales** (`mpt-ui`) | Videos rápidos de un solo formulario con clips de stock o locales | `localhost:3000` · https://virales.saraviamtech.com |

---

## Índice

1. [Cómo se trabaja: los pasos](#cómo-se-trabaja-los-pasos)
2. [Funciones](#funciones)
3. [Imágenes automáticas con Google Flow (solo local)](#imágenes-automáticas-con-google-flow-solo-local)
4. [Conexión con Claude CLI (local y VPS)](#conexión-con-claude-cli)
5. [Instalación local](#instalación-local)
6. [Despliegue en VPS](#despliegue-en-vps)
7. [Automatización por terminal](#automatización-por-terminal)
8. [App Virales (mpt-ui)](#app-virales-mpt-ui)
9. [Estructura del proyecto](#estructura-del-proyecto)
10. [Estado actual y pendientes](#estado-actual-y-pendientes)
11. [Historial](#historial)

---

## Cómo se trabaja: los pasos

Cada video es un **proyecto** que avanza por pasos. Puedes ir en orden o volver a cualquier paso: solo se rehace lo que depende de lo que cambiaste.

| Paso | Qué haces | Quién trabaja |
|---|---|---|
| **Material** | Pegas el tema, notas o fuentes; eliges la duración (hasta 3 h) y el idioma. | Tú |
| **Guion** | Claude redacta la locución, o pegas tu guion tal cual. | Claude CLI |
| **Voz** | Voces de Microsoft, tu propio audio ("Mi audio") o sin voz. | TTS / Whisper |
| **Escenas** | Eliges el formato (16:9, 9:16 o 1:1) y el estilo; Claude corta el guion en escenas y escribe el prompt de imagen (y de video) de cada una. | Claude CLI |
| **Contenido** | En local, pulsas **Generar en Flow** y las imágenes se crean solas. Si no, subes lo que generaste en Flow, la carpeta de la extensión, un ZIP o tus propios recursos. | Flow automático / tú |
| **Ajuste** | Revisas qué imagen o clip va en cada plano y fijas a mano lo que quieras. | Claude CLI / tú |
| **Editor** (opcional) | Editor multipista con vista previa: cortes y clips de la pista principal, capas de fotos y videos encima, textos, audios, música e intro antes de la voz. | Tú |
| **Video** | Eliges el estilo de edición (Clásico, Editorial o Intenso) y la música, y montas el video. | ffmpeg |
| **Miniatura** | Claude propone conceptos y prompts para la miniatura; subes la final. | Claude CLI |

```
material → guion → voz → escenas + prompts ─┐   ← contenido generado en Flow (automático en local) o subido por ti
                    recursos (tus archivos) ─┴→ ajuste → video → miniatura
```

**Por etapas y con firma.** Cada etapa guarda la firma de sus entradas. Por ejemplo, otra música solo rehace el acabado, fijar un plano rehace ese clip y editar el guion rehace la voz y lo que viene después. Las respuestas de Claude se guardan en caché, así que repetir un paso sin cambios no lo vuelve a llamar.

---

## Funciones

### Guion
- Claude lo redacta a partir de tu material, con la duración pedida (de segundos a 3 horas). Si sale corto, hace una segunda pasada para ampliarlo.
- También puedes pegar tu propio guion y se usa tal cual.

### Voz
- **Microsoft:** más de 300 voces neuronales en muchos idiomas, con el tiempo exacto de cada palabra.
- **Mi audio:** subes una narración ya grabada (tu voz o la de otro programa) en WAV, MP3, M4A, OGG o FLAC, y se sincroniza sola.
  - Whisper saca el tiempo de cada palabra; si el guion coincide con lo que se oye, los subtítulos usan el texto del guion.
  - Tarda unos 8 s por minuto de audio en CPU (14,5 min en menos de 2 min).
  - **Quitar silencios largos:** acorta las pausas que pasen de 1 s, 0,6 s o 0,35 s antes de sincronizar, y el video queda más ágil.
- **Sin voz:** para estilos sin narración (ASMR, por ejemplo). Cada escena dura lo que su tramo o su clip, suena el audio de los propios clips y se recortan sus silencios.
- La narración se corta en **planos** según sus pausas; cada plano lleva una imagen o clip.
- **Aviso de versión:** antes de sintetizar con Microsoft se hace una prueba de ~1 s. Si Microsoft rechaza la versión instalada de `edge-tts` (error 403, pasa cuando cambian su servicio), el paso falla al momento y explica cómo actualizar, en lugar de esperar 3 × 120 s.

### Escenas y prompts para Flow
- **Formato:** se elige aquí y es el mismo para las imágenes y para el video final (16:9 por defecto). Se le pasa a Claude en todos los lotes, sin excepción.
- Claude agrupa las frases en escenas de la duración que elijas y escribe para cada una:
  - un **prompt de imagen**, que describe una imagen fija, sin movimiento, cámara ni tiempos;
  - y, si lo pides, un **prompt de video** (image-to-video), que es donde va el movimiento.
- Todos los lotes reciben el mismo contexto: guion completo, estilo visual, indicaciones (personajes fijos, época…), formato e idioma, más las últimas escenas ya escritas para mantener la continuidad.
- **La narración de cada escena es el texto exacto del guion, con su puntuación.** Se corta en código; Claude no la reescribe.
- **Validación automática** antes de guardar:
  - el formato es correcto (en 16:9 ningún prompt dice "9:16", "vertical" ni "portrait", y al revés);
  - la narración unida es idéntica al guion;
  - las imágenes no describen movimiento;
  - las escenas son consecutivas.

  Las escenas que fallan se rehacen solas; si alguna sigue fallando, aparece un aviso con su número.
- Puedes descargar `script.json` (formato de la extensión "AI Content Generator") o `prompts.txt`, copiar los prompts y corregir cualquiera a mano.

### Contenido y ajuste
- Subes la carpeta de la extensión (`images/` y `videos/`), un ZIP o archivos sueltos. Cada archivo va a su escena por el número de su nombre (`1.png`, `scene_2.mp4`); si una escena tiene imagen y video, se usa el video.
- **Con tus propios recursos** (sin escenas), Claude mira una miniatura de cada imagen o video, lo describe y elige qué recurso va en cada plano. Cualquier plano se puede fijar a mano.
- **En local**, las imágenes de las escenas se pueden generar solas con **Generar en Flow** (ver [Imágenes automáticas con Google Flow](#imágenes-automáticas-con-google-flow-solo-local)).
- **Escenas por clip:** si los clips ya están hechos (por ejemplo, las partes de una serie) y la voz es una sola pista, el guion se reparte entre los clips por su nombre (`4.8` = parte 4, clip 8; `1`, `scene_12` = una sola parte). El texto no cambia ni una palabra.
- El botón **último fotograma** saca el último cuadro de un clip para encadenar segmentos en Flow.
- **Liberar espacio:** borra solo lo que el Estudio puede rehacer (caché de clips e intermedios del montaje), de un proyecto o de todos. Nunca toca lo subido, el guion, la voz ni el video final.

### Editor
Paso propio entre **Ajuste** y **Video**, a pantalla ancha y **multipista**, al estilo de un editor de video. Es opcional: **Todo hasta el video** no se detiene aquí, pero lo que se edite es exactamente lo que se monta.

- **Vista previa sin montar:** voz, clips en el segundo justo, zoom de las imágenes, subtítulos por palabra, capas, textos, audios y música elegida. Es una aproximación: los efectos de los estilos Editorial e Intenso solo se ven en el video montado.
- **Medios** (izquierda): fotos, videos y audios (los del proyecto, que se suben ahí mismo, y las canciones de la biblioteca), con buscador y cuántas veces se usa cada archivo.
- **Pistas** (abajo), todas sobre el mismo eje de tiempo:
  - **Capas** de video: fotos o videos encima de la pista principal, a pantalla completa o en ventana (tamaño y posición), con su volumen. Siempre hay una pista vacía arriba para soltar más.
  - **Textos** propios (títulos, rótulos): texto, tamaño, color, posición y caja oscura. Se añaden con **Texto** o la tecla `T`.
  - **Principal**: los planos de Ajuste. Se mueve entera desde su **asa** (⋮, a la izquierda). Arrastrar la raya entre dos planos mueve el corte (con **imán** al hueco entre palabras); arrastrar un clip **entre dos planos** lo lleva allí (los de en medio se corren un lugar) y soltarlo **en el centro** de otro los intercambia; los cortes no se mueven, siguen a la voz. Soltar un archivo encima cambia ese clip.
  - **Voz**: va **por su lado**. Con la voz elegida, `S` la parte en el cabezal y cada trozo se mueve (una pausa, una intro), se recorta por sus bordes o se borra (`Supr`).
  - **Subtítulos**: también van por su lado y por trozos, igual que la voz (`S`, mover, recortar, borrar; «Igual que la voz» los vuelve a alinear con ella).
    Un **clic en una frase** permite corregir su texto (o quitarla con `Supr`): los tiempos siguen a la voz y, si cambia el número de palabras, se reparten dentro de la frase. Las marcas de Claude no se vuelven a pedir.
  - El botón **Juntas** mueve la principal, la voz y los subtítulos a la vez (como antes); «Alinear las tres» las vuelve a poner juntas y enteras. Lo que quede **después** del final alarga el video.
  - **Audios**: efectos o sonidos, con su volumen y su punto de entrada.
  - **Música**: un bloque que se mueve y se recorta; también se elige la canción, el volumen y por qué segundo entra.
- **Gráficos animados** (botón **Gráfico**): título de impacto (las palabras entran una a una; las marcadas con `*asteriscos*` van en color), cifra que cuenta, rótulo inferior y «Suscríbete»; y además frase cinética (una palabra o grupo cada vez), comparar en barras, anillo de porcentaje, línea de tiempo, lista con checks, A contra B, cita con rotulador, sello («FALSO», «MITO»…) y notificación del móvil. Estas nueve salen de ideas de los videos de [awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos), que solo trae prompts, y están escritas desde cero. En barras, línea de tiempo y lista va una fila por renglón («Etiqueta: valor»). Con **Ideas de Claude** (dentro de Gráfico), Claude lee lo que dice la voz y propone gráficos para todo el video (plantilla, textos y momento, solo con datos que se dicen; puedes decirle qué buscar); marcas los que te gusten y se crean y se ponen de una vez en la línea de tiempo (un deshacer los quita). Las ideas quedan guardadas en `graficos/ideas.json` del proyecto. Eliges la plantilla, los textos, el color, la posición y la duración, y se pone en el cabezal como una capa más: se mueve, se recorta y se ve en la vista previa. Las plantillas son propias (HTML + GSAP en `MoneyPrinterTurbo/motion/plantillas/`) y las renderiza [HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0) en un WebM transparente, unos 30 s cada uno; el mismo gráfico con los mismos textos no se vuelve a renderizar. Necesita Node 22 y, una vez, `npm install` en `MoneyPrinterTurbo/motion` (descarga su propio Chrome). La telemetría de HyperFrames va apagada.
- **Cambiar lo que dice un plano** (panel del plano): escribes otro texto o pides **ideas a Claude** (tres textos que caben en ese hueco, con un pedido opcional como «más gancho»), y **Grabar y poner** regraba solo esa parte con la voz del proyecto (la de Microsoft). El retoque se encaja en el mismo hueco: si es un poco largo se acelera hasta un 30 % y, si es más corto, el resto queda en silencio. Así no se mueve nada más (clips, cortes, subtítulos, capas) ni se vuelve a llamar a Claude para asignar. Los subtítulos de ese hueco toman el texto nuevo y la pista de voz lo marca como «regrabado»; «Volver a la voz original» lo deshace. No se puede con una narración propia.
- **En la pantalla** (vista previa) se arrastran las fotos y videos encima, los textos y los subtítulos para colocarlos donde quieras; la esquina del objeto elegido cambia su tamaño y al pasar por el centro aparecen guías que lo pegan. Una capa a pantalla completa que se mueve pasa a ventana.
- Todo bloque se **mueve** (también a otra pista del mismo tipo) y se **recorta** por sus bordes; el imán pega a bordes, cabezal, cortes y huecos entre palabras (`Alt` lo suelta).
- El **cabezal** (línea roja) se agarra y se arrastra; también se puede arrastrar sobre la regla o cualquier hueco de la línea de tiempo, y la vista previa lo sigue.
- **Dividir** (`S`), **borrar** (`Supr`), **duplicar** (`Ctrl+D`), **deshacer** (`Ctrl+Z`), **rehacer** (`Ctrl+Y`), zoom (`+`/`−`, `Ctrl` + rueda o el deslizador) y fotograma a fotograma (`Shift` + flechas).
- Los cambios de la pista principal se aplican solos en un segundo, sin volver a llamar a Claude; las capas, textos, audios y música se guardan al momento. Si se rehace la voz, los cortes viejos se descartan.
- Las capas, textos y audios necesitan el acabado **Rápido** (ffmpeg con libass), que es el de por defecto.

### Video: montaje y estilos de edición
El montaje se hace con ffmpeg: un clip por plano, en caché, y el acabado (voz, música y subtítulos) en una sola pasada. Hay tres estilos:

- **Clásico:** subtítulos por frase, sin efectos.
- **Editorial:** efectos sobrios de documental, cada uno activable por separado:
  - subtítulos palabra por palabra con la palabra clave en color;
  - rótulos de cifras, fechas y nombres;
  - whoosh en los cortes, golpe grave en las revelaciones y música que baja sola bajo la voz;
  - ritmo de entrada y zoom en las revelaciones;
  - color unificado (natural, cálido, cine o frío) y gancho en los primeros 2 s;
  - momentos clave, como mucho uno cada 20 s: cita destacada, pausa dramática, destello y blanco y negro para el pasado.
- **Intenso:** el estilo para redes, lleno de efectos. Usa lo mismo que el editorial con más densidad y añade:
  - subtítulos en mayúsculas en los que crece la palabra que suena;
  - la palabra clave gigante con temblor y desfase de color en las revelaciones;
  - flash en los cambios de imagen;
  - barra de progreso;
  - franjas de cine en las citas;
  - un "pop" en los rótulos y una subida de tensión antes de cada revelación.

**Sonido de los clips (con narración):** cuando el video lleva voz, en el paso Video eliges cómo suena cada clip de video bajo la narración:
- **Completo:** el audio entero del clip.
- **Solo fuertes:** solo los picos (golpes, gritos, efectos); la música de fondo del clip queda fuera.
- **Silencio:** solo la narración (es el modo por defecto, así los videos que ya tenías no cambian).

Hay un modo por defecto y otro por clip (con el clip para verlo y oírlo), un volumen propio y la opción de que el sonido de los clips baje solo mientras habla la voz. Si un clip se ralentiza por la voz de corrido, su audio también; si se congela su último fotograma, queda en silencio.

Claude marca las palabras clave, los datos y los momentos fuertes en una sola pasada y siempre escribe esos textos en el idioma de la narración. Puedes poner tus propios efectos de sonido en `MoneyPrinterTurbo/resource/sfx/` (`whoosh`, `golpe`); si no los hay, se generan solos.

### Publicar y herramientas
Con el video montado, el paso **Video** trae una tarjeta **Publicar** (Claude CLI, una llamada por herramienta; lo generado se guarda en el proyecto):

- **Título y descripción:** 3 títulos, la descripción lista para pegar y hashtags para YouTube, TikTok o Instagram Reels (en YouTube también las etiquetas), cada uno con su botón **Copiar**.
- **Capítulos de YouTube:** `0:00 …` con los tiempos del video montado. Sigue las reglas de YouTube: al menos 3 capítulos de 10 s o más y el primero en 0:00.
- **Subtítulos:** descarga el SRT del video (con los tiempos finales y las frases corregidas) y tradúcelo al inglés, portugués, francés, italiano, alemán o español para subirlo como subtítulos.
- **Gancho:** nota del 1 al 10 de los primeros segundos, qué funciona y qué falla, y 3 ganchos alternativos que caben en el primer plano. **Regrabar el inicio con este** usa el retoque del editor: el primer plano pasa a decir el gancho nuevo y sale marcado como «regrabado».

En el paso Video, **Sonido → Mejorar la voz** (Suave o Fuerte) quita los graves de fondo, suaviza las «s», comprime y empareja el volumen a −16 LUFS; «Fuerte» además limpia el ruido de una grabación casera. Es local (ffmpeg) y solo se oye en el video montado.

### Clip Studio (video largo → shorts)
Página propia en la barra de arriba. Subes un video largo (podcast, entrevista, directo) en MP4, MOV, MKV o WEBM y:

1. **Whisper lo transcribe** en la máquina, con el tiempo de cada palabra, y lo parte en frases (entre 15 y 40 s por minuto de video en un PC normal).
2. **Claude propone los mejores momentos** (cuántos, de 15–35, 30–60 o 55–90 s, y opcionalmente qué buscar): título y gancho en el idioma del video, nota del 1 al 10 y por qué funciona. Siempre de frase completa a frase completa; en videos largos lee por tramos y se queda con los mejores sin que se pisen.
3. **Ajustas cada clip:** **Ver** reproduce solo ese tramo; el inicio y el final se mueven de frase en frase o en pasos de 0,5 s; también hay **Clip desde aquí** para uno a mano. La transcripción se puede abrir y saltar a cualquier frase.
4. **Haces el short** en 1080×1920: recortado a vertical por la parte que elijas (un recuadro sobre el video lo muestra) o entero sobre un fondo desenfocado, con subtítulos palabra por palabra en el color que elijas, el gancho arriba los primeros 3 s y el volumen emparejado. Los shorts quedan en la página para verlos y descargarlos.

Se guarda todo en `storage/estudio/clips/<id>/`.

### Fábrica (videos enteros desde un tema)
Página propia en la barra de arriba. Escribes un tema y sale el video terminado, sin modelos de video ni créditos: todo se dibuja con código (HyperFrames + GSAP).

1. **Guion por escenas:** Claude elige el tipo de cada escena según el nicho y marca la palabra en la que pasa cada animación.
2. **Voz:** de Microsoft (con el tiempo de cada palabra) o una grabación tuya (Whisper la escucha y Claude reparte tu texto sin cambiarlo).
3. **Escenas dibujadas** justo cuando se dicen: mapas que se mueven (países, ríos, rutas, medidas, satélite, banderas con ojos, pegatinas), cifras que cuentan, barras, listas, versus, líneas de tiempo e ilustraciones a pantalla completa.
4. **Montaje** con música (baja sola cuando habla la voz) y efectos de sonido, en 9:16, 16:9 y 1:1.

- **Nichos:** mapas e historia, datos y comparaciones, curiosidades, finanzas y economía. Cada uno tiene su estructura y sus escenas.
- **Estilos** con galería de muestras: papel antiguo, keynote oscuro, documental, periódico, pizarra, cuaderno, minimal, pop cómic, neón, terminal, explicador, **Retro TV** (siluetas blancas sobre negro, cabecera con contador y acabado de tele vieja) y **Thriller** (historia de suspense dibujada, portada en sombra). Cada estilo tiene sus colores, letras (OFL), textura y forma de entrar, y su familia de dibujos (muñecos de madera, plano, grabado, stickman, Retro TV o Thriller; las dos últimas se dibujan en Flow con imágenes de referencia para no perder el estilo).
- **Biblioteca de dibujos:** pegatinas e ilustraciones hechas con Nano Banana en Flow (`motion/fabrica/datos/hacer_pegatinas.py` y `hacer_estilos.py`, retomables). Puedes crear las tuyas (solo en local) o subirlas. Si a Claude le falta una, la pide y se dibuja al hacer el guion.
- **Varios videos:** marca "uno por línea" y cada línea del tema es un video con las mismas opciones; se hacen de uno en uno.
- **Sagas por temporadas:** el botón *Siguiente episodio* de un video pide cuántos episodios (1-10), qué pasa (opcional) y si el último cierra la historia. Claude planea la tanda en una llamada corta; primero escribe todos los guiones en orden (cada uno lee los anteriores) y luego hace la voz y el render de uno en uno. Con *Hacer todo sin parar* cada episodio sale montado aunque el molde tenga revisión o clips. El último guarda hacia dónde puede seguir la historia, y la siguiente tanda arranca de ahí. Si una tanda quedó esperando revisión, *Montar toda la saga* los monta en orden.
- **Duración:** si el guion se aleja más de un 10 % de las palabras pedidas, Claude lo corrige una vez.
- **Abrir en el editor:** el botón del lápiz junto a cada video crea un proyecto del Estudio con esa voz y un clip por escena, listo para retocar en el editor (música, textos, capas…).
- Rehacer con otro estilo o formato solo vuelve a dibujar; las escenas que no cambian salen de la caché.

Se guarda en `storage/estudio/fabrica/<id>/`; las muestras de la galería, en `storage/estudio/fabrica_muestras/`.

### Miniatura
- Claude propone de 1 a 5 conceptos, cada uno con su texto y el prompt para Flow, con y sin texto (para Canva).
- Se basa en el guion, el estilo, las imágenes del proyecto y, si la subes, una miniatura de referencia (copia el estilo, no el contenido).
- La miniatura final queda como portada en Mis videos.

### Prompts maestros, creaciones y series
- **Biblioteca de prompts maestros** (menú superior): subes un prompt maestro (.docx, .txt, .md o texto) y Claude lo desglosa en una ficha con sus pasos, preguntas, entregables, formato y reglas.
- **Crear contenido:** Claude ejecuta el maestro paso a paso con botones, o en modo automático. Al final ordena los entregables: guion, escenas con sus prompts, miniaturas y `script.json`.
- **Hojas de referencia** de personajes y lugares, **series** con biblia compartida y episodios.
- **Crear video:** convierte una creación en un proyecto del Estudio ya relleno, con cuatro opciones de narración: su guion, guion demostración, guion libre o sin voz.

### Mis videos
- Cada tarjeta tiene portada y las acciones Ver, Descargar, Editar, Duplicar, Renombrar y Borrar.
- Mis videos, la Fábrica y Clip Studio muestran 12 videos por página.

---

## Imágenes automáticas con Google Flow (solo local)

Automatiza el único paso manual del modo escenas. Genera **una imagen por escena** con Nano Banana en la web de Google Flow, que es gratis con tu cuenta de Google, y la deja directamente en el proyecto:

```
Antes:  Escenas → bajar script.json → extensión en Flow → bajar images/ → subirlas → Video
Ahora:  Escenas → Contenido: "Generar en Flow" (automático, retomable)              → Video
```

- **Solo imágenes.** Los videos en Flow gastan créditos (Veo), así que no se automatizan.
- **Solo en la máquina local.** Hace falta un Chrome con tu sesión de Google. En el VPS queda desactivado y el Estudio se ve como siempre.

### Cómo se usa
1. En **Escenas**, elige *"Una imagen por escena (Flow automático o subidas)"* y genera los prompts de imagen.
2. En **Contenido** aparece la tarjeta **Generar en Google Flow**. Pulsa **Generar en Flow (N pendientes · M listas)**.
3. La cuadrícula muestra cada escena: ✓ lista, ✗ fallida (pasa el ratón para ver el motivo), girando = en curso, número = pendiente. Las imágenes aparecen en la lista de archivos según se crean.
4. **Detener** termina la imagen en curso y para (**Cortar ya** la abandona). **Continuar** genera solo lo que falta.
5. Cuando estén todas, pasa a **Video**.

Tarda unos 30 s por imagen: 200 escenas son unas 2 h. Salen a 1K completo (768×1376 en 9:16).

### Cómo se comporta
Imita a la extensión "AI Content Generator":

| Qué | Comportamiento |
|---|---|
| Escena hecha | La que tiene una imagen con su número en `recursos/` (en `images/` o suelta). **El archivo manda**: no hay otro estado que pueda perderse. |
| Al empezar | Solo las pendientes. Lo ya generado o subido a mano no se repite. |
| Intentos | 4 por escena, hasta 2 min cada uno. Pausa de 4 s tras una imagen y de 4,5 s tras un fallo. |
| Fallidas | Al final de la vuelta se repasan solas, hasta 2 veces más. Las que sigan fallando quedan pendientes para la próxima corrida. |
| Límite de Flow | Si Flow avisa de cuota o límite, el lote se **pausa** sin gastar intentos. |
| Apagar o reiniciar | No se pierde nada. Cada imagen se escribe como `.part` y se renombra al terminar. |
| Concurrencia | Una sola generación a la vez en toda la máquina (lock entre procesos). |
| Idioma de Flow | Nada depende de los textos de la web (botones por icono, ajustes por valor, éxito y error por elementos), salvo el aviso de límite: sus frases en es, en, pt, fr, it y de están en `tools/flow/textos.js`. |

### Instalación (una vez por máquina)
1. Node.js 18+ y Google Chrome.
2. `npm install` en `tools/flow/`.
3. En `MoneyPrinterTurbo/config.toml`:
   ```toml
   estudio_flow_habilitado = true    # false (o sin poner) en el VPS
   estudio_flow_dir = ""             # ruta a tools/flow (vacío = la del repo)
   estudio_flow_modelo = "2"         # pro | 2 | lite  (Nano Banana Pro, 2.1, 2 Lite)
   estudio_flow_pasadas_extra = 2    # repasos automáticos de las fallidas
   ```
4. Reinicia el backend. En Contenido pulsa **Conectar Flow** e inicia sesión con tu cuenta de Google en el Chrome que se abre (perfil propio en `%LOCALAPPDATA%\FlowImageChrome`). Solo hace falta una vez.

### Piezas
- `tools/flow/`: generador en Node con Playwright, que se conecta por CDP a un Chrome dedicado (puerto 9333). Está basado en srzGoogleFlowMCP.
  - `lote.js`: el lote. Escribe su progreso en líneas JSON.
  - `cli.js`: abre el Chrome (`chrome`) y comprueba la sesión (`sesion`).
  - `flow.js`: maneja la web de Flow.
  - `textos.js`: las frases de límite.
  - Se puede usar sin el Estudio (ver su `README.md`).
- Backend: `app/services/estudio/flow_gen.py` lanza el lote, lee su progreso y lo guarda en `proyectos/<id>/flow/estado.json`.
- Rutas: `GET /estudio/flow`, `POST /estudio/flow/conectar`, y `GET`, `POST …/flow/generar` y `POST …/flow/detener` bajo `/estudio/proyectos/{id}`. Con Flow desactivado responden 404.
- Interfaz: `estudio-ui/components/paneles/GenerarFlow.tsx`.

---

## Conexión con Claude CLI

### Cómo funciona

El Estudio **no usa la API de Anthropic ni una API key**. Cada vez que necesita a Claude (guion, escenas, catálogo visual, asignación, edición, miniatura, prompts maestros, Fábrica), el backend lanza el programa **Claude Code** en modo no interactivo:

```
claude -p --model <haiku|sonnet|opus> --effort <low|medium|high> --output-format json
```

- La instrucción va por la entrada estándar y la respuesta vuelve en JSON.
- Usa la **sesión de tu cuenta de Claude** (Pro o Max) guardada en la máquina donde corre el backend, así que el consumo cuenta contra tu suscripción.
- Para que nunca salga de la suscripción, el backend quita del proceso hijo `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL` y las variables de Bedrock/Vertex. Aunque tengas una API key en el sistema, no se usa.
- Por seguridad se lanza sin MCP (`--strict-mcp-config`) y con las herramientas desactivadas. Solo se permite `Read`, dentro de la carpeta del proyecto, cuando Claude tiene que mirar imágenes.
- El modelo y el esfuerzo se eligen en cada paso de la interfaz. `low` es lo más rápido; `medium` y `high` piensan más y tardan más.

Código: `MoneyPrinterTurbo/app/services/claude_cli.py`.

### En local (Windows, macOS o Linux)

1. **Instala Claude Code** en la misma máquina donde corre el backend.

   ```powershell
   # Windows (PowerShell)
   irm https://claude.ai/install.ps1 | iex
   ```
   ```bash
   # macOS / Linux
   curl -fsSL https://claude.ai/install.sh | bash
   ```
   También sirve `npm install -g @anthropic-ai/claude-code`.

2. **Inicia sesión** con tu cuenta de Claude: ejecuta `claude`, escribe `/login`, elige *Claude account (Pro/Max)* y completa el login en el navegador. La sesión queda guardada en tu usuario (`%USERPROFILE%\.claude` en Windows, `~/.claude` en macOS/Linux).

3. **Comprueba que responde** sin abrir el modo interactivo:

   ```bash
   claude -p "responde solo: ok" --model haiku
   ```
   Si contesta `ok`, el Estudio ya puede usarlo.

4. **Arranca el backend con el mismo usuario** con el que hiciste el login. El backend busca `claude` en el PATH. Si lo arrancas desde otro sitio (un servicio, una tarea programada o un PATH distinto) y no lo encuentra, pon la ruta completa en `config.toml`:

   ```toml
   [app]
   claude_cli_path = "C:/Users/<tu-usuario>/.local/bin/claude.exe"   # Windows (instalador nativo)
   # claude_cli_path = "/home/<usuario>/.local/bin/claude"            # Linux
   ```

### En el VPS (Docker Swarm)

La imagen del backend (`MoneyPrinterTurbo/Dockerfile`) ya instala Claude Code. Solo falta darle una sesión, que se guarda fuera del contenedor para que no se pierda al actualizar.

1. **Volumen de sesión.** Ya está en `docker-stack.yml`, en el servicio `api`:

   ```yaml
   volumes:
     - /root/mpt-data/claude:/root/.claude
   environment:
     - CLAUDE_CONFIG_DIR=/root/.claude
   ```
   Crea la carpeta una vez: `mkdir -p /root/mpt-data/claude`.

2. **Inicia sesión**, una sola vez. Elige una de estas dos formas:

   - **A. Login dentro del contenedor:**
     ```bash
     docker exec -it $(docker ps -qf name=mpt_api) claude
     # dentro: /login → elige "Claude account" → abre la URL en tu navegador,
     # autoriza y pega el código que te da. Sal con /exit.
     ```
     La sesión queda en `/root/mpt-data/claude` y sobrevive a reinicios y actualizaciones.

   - **B. Token de larga duración**, sin login interactivo:
     ```bash
     # En tu PC (con sesión iniciada):
     claude setup-token
     # Copia el token (sk-ant-oat01-...)
     ```
     En Portainer, añade al servicio `api` la variable `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...` y vuelve a desplegar el stack. Trata ese token como una contraseña.

3. **Comprueba** desde el VPS:

   ```bash
   docker exec -it $(docker ps -qf name=mpt_api) claude -p "responde solo: ok" --model haiku
   ```

### Ajustes en `config.toml`

```toml
[app]
claude_cli_model = "sonnet"   # por defecto cuando un paso no indica modelo: haiku | sonnet | opus
claude_cli_effort = "low"     # low | medium | high | xhigh | max
claude_cli_timeout = 0        # segundos; 0 = automático según modelo y esfuerzo
claude_cli_path = ""          # vacío = buscar `claude` en el PATH
```

### Problemas frecuentes

| Mensaje | Causa | Solución |
|---|---|---|
| `no se encontro el CLI claude` | Claude Code no está instalado o no está en el PATH del backend | Instálalo o pon `claude_cli_path` |
| `Not logged in` / `Please run /login` | No hay sesión, o expiró | Repite el login (local: `claude` → `/login`; VPS: forma A o B) |
| `cupo de la suscripcion agotado` | Llegaste al límite de uso de tu plan | Espera a que se renueve y vuelve a lanzar el paso. Las etapas ya terminadas no se repiten |
| `sin respuesta en N s` | Tarea muy larga con esfuerzo alto | Baja el esfuerzo a `low` o `medium`, o sube `claude_cli_timeout` |
| La sesión desaparece al actualizar el VPS | Falta el volumen `/root/mpt-data/claude` | Revisa el volumen y `CLAUDE_CONFIG_DIR` en `docker-stack.yml` |

### Otros problemas frecuentes

| Mensaje | Causa | Solución |
|---|---|---|
| `Microsoft rechazo la conexion de voz (403)…` (o la voz tarda minutos y falla) | Microsoft cambió su servicio y la versión de `edge-tts` quedó vieja. Pasó en octubre de 2026 con la 7.2.7. | Local: `uv pip install --python .venv/Scripts/python.exe -U edge-tts`, pon la versión en `requirements.txt` y reinicia el backend. VPS: reconstruye la imagen `mpt-api`. |
| `falta instalar el generador: ejecuta npm install…` | Flow habilitado sin dependencias | `npm install` en `tools/flow/` |
| Generar en Flow: "no tiene sesión de Google" | El Chrome de Flow no tiene sesión iniciada | **Conectar Flow**, inicia sesión y pulsa **Continuar** |
| Generar en Flow: "Flow avisó de un límite de uso" | Cuota de Flow agotada por ahora | Espera y pulsa **Continuar**. Lo hecho no se pierde |

---

## Instalación local

### Requisitos
- Python 3.10 o superior, y Node.js 18 o superior.
- **ffmpeg con libass** en el PATH. El build de gyan.dev en Windows y el de apt o Docker en Linux lo traen.
- **Claude Code** con sesión iniciada (ver [Conexión con Claude CLI](#conexión-con-claude-cli)).
- **Git LFS**, porque la música y las fuentes van por LFS: `git lfs install` antes de clonar.

### Pasos

```bash
git clone https://github.com/juanelot/Saraviamtech_Studio.git
cd Saraviamtech_Studio

# Backend (motor + API del Estudio) → http://localhost:8080
cd MoneyPrinterTurbo
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp config.example.toml config.toml
python main.py

# Estudio (otra terminal) → http://localhost:3100
cd estudio-ui
npm install
npm run dev
```

Opciones del Estudio en `config.toml` (`[app]`):

```toml
estudio_carpetas_permitidas = []   # carpetas del servidor que el Estudio puede leer como recursos
estudio_flow_habilitado = false    # true para generar las imágenes en Google Flow (ver su sección)
```

**Opcional, Google Flow:** `cd tools/flow && npm install`, y luego `estudio_flow_habilitado = true` (ver [Imágenes automáticas con Google Flow](#imágenes-automáticas-con-google-flow-solo-local)).

La primera vez que uses **Mi audio**, Whisper descarga su modelo (unos 150 MB). Hace falta internet solo esa vez.

> El backend no recarga el código solo: después de actualizar, reinicia `python main.py`.

---

## Despliegue en VPS

La guía completa está en **[DEPLOY.md](DEPLOY.md)** (Portainer + Traefik + Docker Swarm). Resumen del Estudio:

```bash
mkdir -p /root/mpt-data/claude /root/mpt-data/recursos
docker build -t mpt-api:latest ./MoneyPrinterTurbo
docker build -t estudio-ui:latest --build-arg MPT_API_URL=http://api:8080 ./estudio-ui
docker stack deploy -c docker-stack.yml mpt
```

- **Dominio:** `studio.saraviamtech.com` (label `Host(...)` del servicio `estudio`), con auth básica de Traefik.
- **Sesión de Claude:** ver [En el VPS](#en-el-vps-docker-swarm).
- **Datos persistentes:** proyectos en `/root/mpt-data/storage/estudio/`, recursos del servidor en `/root/mpt-data/recursos` (dentro del contenedor, `/recursos`).
- **Stack real:** Portainer, stack `mpt` con los servicios `api` (motor compartido), `ui` (Virales) y `estudio`. El código está en `/root/saraviamtech-studio`, clonado de este repo (`main`). Se actualiza desde el editor de Portainer, no con `docker stack deploy`.
- **Actualizar:**
  ```bash
  cd /root/saraviamtech-studio && git pull
  docker tag mpt-api:latest mpt-api:backup-$(date +%Y%m%d)        # respaldo para volver atrás
  docker tag estudio-ui:latest estudio-ui:backup-$(date +%Y%m%d)
  docker build -t mpt-api:latest ./MoneyPrinterTurbo
  docker build -t estudio-ui:latest --build-arg MPT_API_URL=http://api:8080 ./estudio-ui
  docker service update --force mpt_api mpt_estudio
  ```
  Antes de actualizar, comprueba que no haya nada renderizando: reiniciar `api` corta los trabajos en curso.
- **Google Flow:** en el VPS queda desactivado (`estudio_flow_habilitado` sin poner o en `false`).

---

## Automatización por terminal

Varios CLIs para que Hermes, n8n o un cron trabajen sin abrir el navegador. Usan la API del Estudio:

```bash
# Contra el VPS (por defecto): https://studio.saraviamtech.com/api/motor
export MPT_BASIC_AUTH="usuario:password"          # la auth básica de Traefik
# En local:
export MPT_API_BASE="http://localhost:8080/api/v1"
```

**`estudio_cli.py`** crea o continúa proyectos:

```bash
python estudio_cli.py --titulo "Rockefeller" --material-archivo notas.txt --minutos 12 \
    --recursos-dir ./mis_recursos --formato 16:9 --out ./videos
python estudio_cli.py --titulo "X" --guion-archivo guion.txt --asignacion escenas \
    --generar imagenes --hasta escenas --exportar-json ./flow/script.json
python estudio_cli.py --proyecto <id> --contenido-dir ./flow --out ./videos   # sube lo de Flow y monta
```

Imprime `PROYECTO=<id>` al empezar y sale con código 0 si todo va bien y 1 si falla. Hay un perfil de ejemplo en `estudio_perfil.example.json`.

**`maestros_cli.py`** trabaja con los prompts maestros:

```bash
python maestros_cli.py listar
python maestros_cli.py crear --maestro "paper craft" --tema "un faro en una isla" --sin-paradas --out ./flow/faro
python maestros_cli.py video --maestro "paper craft" --creacion <id> --narracion demostracion
```

Sale con código 0 si está listo, 1 si hay un error y 2 si el flujo espera una respuesta (contéstala con `responder`).

**`fabrica_cli.py`** hace videos de la Fábrica, uno o un lote, y los descarga:

```bash
python fabrica_cli.py --catalogo                                                   # nichos, estilos y formatos
python fabrica_cli.py --tema "Por qué Bolivia no tiene mar" --estilo papel --out ./videos
python fabrica_cli.py --temas-archivo temas.txt --nicho finanzas --estilo minimal --formatos 9:16,16:9
python fabrica_cli.py --perfil fabrica_perfil.json --tema "..." --editor           # y lo abre en el editor
python fabrica_cli.py --seguir <id>,<id> --out ./videos                            # retomar videos ya creados
python fabrica_cli.py --siguiente <id> --episodios 5 --idea "buscan un barco"     # temporada de una saga (--final la cierra)
```

Imprime `FABRICA=<id>` por video al empezar, `VIDEO=<ruta>` por cada MP4 bajado (con un `.txt` al lado con el título y la descripción) y `PROYECTO=<id>` si se pide `--editor`. Sale con código 0 si todos terminan bien y 1 si alguno falla. Hay un perfil de ejemplo en `fabrica_perfil.example.json`.

---

## App Virales (mpt-ui)

Es la primera app del repositorio: un formulario para sacar videos rápido con el motor de MoneyPrinterTurbo, sin pasos. Corre en `localhost:3000` (`cd mpt-ui && npm install && npm run dev`) y en https://virales.saraviamtech.com. La interfaz está en español e inglés.

- **Crear video:** tema o guion → voz → clips de Pexels, Pixabay o locales → subtítulos, música y montaje.
- **Música propia:** subir, elegir y escuchar MP3. Se guardan en un volumen persistente en el VPS.
- **Mis videos:** biblioteca con reproductor y descarga.

Un render de 1080×1920 con subtítulos tarda de 5 a 15 min en CPU. Si el navegador avisa de un *timeout* a los 40 min, el backend sigue trabajando: no relances el video.

---

## Estructura del proyecto

```
Saraviamtech_Studio/
├── estudio-ui/                     # Interfaz del Estudio (Next.js 16, puerto 3100)
│   ├── app/                        # Páginas: inicio, proyecto (/p/<id>), maestros
│   ├── components/paneles/         # Un panel por paso (Guion, Voz, Escenas, Video…)
│   └── lib/                        # API, marca (marca.ts), voces
├── MoneyPrinterTurbo/              # Backend (FastAPI, puerto 8080): motor de video + API
│   ├── app/services/estudio/       # Una etapa por archivo; el grafo de etapas en grafo.py
│   │   ├── flow_gen.py             # Generar en Google Flow (lanza tools/flow/lote.js)
│   │   └── componentes.py          # Prueba rápida de edge-tts (aviso de versión)
│   ├── app/services/claude_cli.py  # Conexión con Claude CLI
│   ├── app/controllers/v1/estudio.py   # Rutas /api/v1/estudio/*
│   ├── storage/estudio/            # Proyectos, maestros, catálogo
│   └── config.toml                 # Privado (fuera de git); plantilla en config.example.toml
├── tools/flow/                     # Generador de Google Flow (Node + Playwright, solo local)
├── mpt-ui/                         # App Virales (Next.js, puerto 3000)
├── prompts_maestros/               # Prompts maestros de ejemplo
├── estudio_cli.py · fabrica_cli.py · maestros_cli.py   # Automatización por terminal
├── docker-stack.yml · DEPLOY.md        # Despliegue en VPS
└── PLAN_FLOW_LOCAL.md              # Diseño de la integración con Flow
```

---

## Estado actual y pendientes

*Al 23 de octubre de 2026.*

**Funcionando**
- Estudio completo en local y en el VPS (studio.saraviamtech.com, actualizado el 19-10-2026 con `edge-tts` 7.3.1): todos los pasos, prompts maestros, series, Mi audio, Sin voz, escenas por clip, sonido de los clips bajo la narración, editor con línea de tiempo y los tres estilos de edición.
- Generar en Google Flow en local. Se probó de punta a punta: 4 escenas, detener a mitad, continuar (solo generó las que faltaban) y montaje del video.
- App Virales con clips de stock o locales.

**Pendiente**
- **Flow en inglés:** repetir la prueba de 5 escenas con la cuenta de Google en inglés.
- **Flow, detección de fallos:** comprobar con un fallo real que se detecta la tesela de error (`flow-error-tile`). La de "generando" ya está verificada.
- **Pantalla "Conectar Claude"** en el Estudio, para iniciar sesión de Claude desde la web.
- **VPS:** la RAM va justa al renderizar (~3 GB libres en los picos).

---

## Historial

| Fecha | Cambio |
|---|---|
| 2026-06-04 | Primera versión: MoneyPrinterTurbo, edición Saraviamtech (app Virales), música y fuentes por Git LFS |
| 2026-06-11 | Despliegue en VPS (Portainer + Traefik + Swarm) e interfaz en español e inglés |
| 2026-06 | Video de imágenes estilo Zenn con Kie AI y `zenn_cli.py` (modos kie, local y video) |
| 2026-07-18 | Música propia (subir, elegir y escuchar), mejoras de subtítulos y latido en el CLI |
| 2026-09-29 | **Estudio por etapas** con Claude CLI: escenas y prompts para Flow, voz clonada, miniatura, edición editorial, asistente, prompts maestros y creaciones |
| 2026-09-30 | Hojas de referencia, segmentos encadenados, series con biblia y `maestros_cli.py` |
| 2026-10-04 | Estilo de edición Intenso, textos en el idioma del video y Mi audio con Whisper |
| 2026-10-07 | Claude CLI en modo ligero: de unos 14.000 a unos 200 tokens fijos por llamada |
| 2026-10-10 | Estudio desplegado en studio.saraviamtech.com, zoom suave y escenas exactas |
| 2026-10-12 | Sin voz (suena el audio de los clips, con recorte de silencios) y maestro Stickman |
| 2026-10-13 | Botón Liberar espacio |
| 2026-10-17 | Voz de corrido en escenas de prompt maestro, escenas por clip y borrar música |
| 2026-10-19 | **Generar en Google Flow** (solo local), aviso de versión de `edge-tts` y paso a `edge-tts` 7.3.1 |
| 2026-10-21 | Exportar e importar prompts maestros y Stickman con los estilos 4 y 5 |
| 2026-10-23 | **Sonido de los clips** bajo la narración: completo, solo fuertes o silencio, por clip |
| 2026-11-05 | Fábrica: estilos Retro TV y Thriller, duración ajustada, **sagas por temporadas** y páginas en las listas. Se quitan Blender, el video de imágenes de Kie (Zenn), la voz clonada, el asistente y las familias foto, acuarela, cómic y recortes |
| 2026-10-23 | **Editor multipista** como paso propio: vista previa sin montar, Medios, capas de fotos y videos, textos, audios, música movible, intro antes de la voz, dividir, borrar, deshacer y rehacer |

---

## Licencia

© Saraviamtech. Todos los derechos reservados sobre el Estudio, sus interfaces y la marca.
Incluye componentes de código abierto bajo licencia MIT; sus avisos están en `MoneyPrinterTurbo/LICENSE`.

---

*Desarrollado por [Saraviamtech](https://github.com/juanelot)*
