"""
Fabrica: videos enteros desde un tema, sin modelos de video (todo se dibuja con codigo).

  1. GUION: Claude escribe el guion partido en ESCENAS (portada, mapa, cifra...) segun el
     nicho. Cada escena trae su trozo de narracion y sus datos; lo que tiene que pasar AL
     DECIR una palabra lleva esa "palabra". guion.json.
  2. VOZ: el TTS de MPT (edge-tts da el tiempo de cada palabra) o tu grabacion.
     voz/voz.mp3 y voz/palabras.json (una entrada por palabra del guion).
  3. PLAN: cada escena empieza cuando se dice su primera palabra; las palabras se cambian
     por segundos de la escena y los mapas se encadenan (la camara sigue donde acabo).
     plan.json.
  4. RENDER: cada escena es una pagina (motion/fabrica: base.html + nucleo.js + la piel del
     estilo + escenas/<tipo>.js) que HyperFrames convierte en video, en cada formato pedido.
     Se cachea por contenido: cambiar una escena solo vuelve a renderizar esa.
  5. MONTAJE: escenas una tras otra + voz + musica (baja sola cuando habla la voz).
     videos/<formato>.mp4 y descripcion.txt.

Todo vive en storage/estudio/fabrica/<id>/. Un trabajo por sesion, en un hilo; la interfaz
consulta el estado (como Clip Studio). Los estilos son pieles (motion/fabrica/estilos.css) y
las escenas son las mismas para todos: un estilo o un nicho nuevo no obliga a tocar las escenas.
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unicodedata
import uuid

from loguru import logger

from app.services import claude_cli, voice
from app.services.estudio import acabado, almacen, biblioteca, componentes, edicion, flow_gen, grafo, graficos, medios, satelite
from app.services.estudio import banco, clonar, presentadores
from app.services.estudio import voz as etapa_voz

DIR_FABRICA = os.path.join(graficos.DIR_MOTION, "fabrica")
FPS = 30
COLA_S = 0.9          # segundos de imagen despues de la ultima palabra
ADELANTO_S = 0.12     # cada escena entra un pelin antes de su primera palabra
MARCA_S = 1.4         # segundos de mas al final para el cierre de marca (solo si se pide)
DERIVA = 0.05         # igual que en mapa.js: la camara se sigue acercando al llegar (zoom por segundo)
_candado = threading.RLock()
_render = threading.Lock()   # un Chrome cada vez
_trabajos = {}

FORMATOS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
BANDERAS = os.path.join(graficos.DIR_MOTION, "node_modules", "country-flag-icons", "3x2")
NUEVOS_MAX = 4        # dibujos nuevos (Nano Banana) como mucho por video: ~45 s cada uno
NUEVOS_MAX_UNICOS = 8 # fuera de mapas cada escena lleva su propia imagen: hacen falta mas
PROTA_MAX = 2         # fuera de mapas, escenas 'protagonista' como mucho (el resto pasan a ilustraciones nuevas)
RECIENTES = 12        # videos anteriores cuyas ilustraciones no se repiten
DIR_AUDIOS = almacen.raiz("fabrica_audios")   # narraciones grabadas que se suben (compartidas entre videos)
IDIOMAS_CLON = {"espanol": "es", "ingles": "en", "portugues": "pt", "frances": "fr", "italiano": "it", "aleman": "de"}

# familia: de donde salen las pegatinas e ilustraciones (biblioteca.FAMILIAS; sin familia, los munecos de madera)
ESTILOS = {
    "papel": {"nombre": "Papel antiguo", "descripcion": "Mapa de libro de historia: sepia, tinta y letra de imprenta."},
    "oscuro": {"nombre": "Keynote oscuro", "descripcion": "Fondo casi negro, color brillante y letra gruesa."},
    "documental": {"nombre": "Documental", "descripcion": "Negro y oro de cine, letra alta y estrecha, grano de pelicula."},
    "periodico": {"nombre": "Periodico", "descripcion": "Papel de diario, titulares con serifa y grabados antiguos.", "familia": "grabado"},
    "pizarra": {"nombre": "Pizarra", "descripcion": "Pizarra verde con tiza de colores y letra a mano.", "familia": "plano"},
    "cuaderno": {"nombre": "Cuaderno", "descripcion": "Hoja de libreta con rayas, boli azul y rotulador.", "familia": "plano"},
    "minimal": {"nombre": "Minimal", "descripcion": "Blanco limpio, mucho aire y un solo color de acento.", "familia": "plano"},
    "pop": {"nombre": "Pop comic", "descripcion": "Amarillo de comic, puntos de imprenta y letra de vineta.", "familia": "plano"},
    "neon": {"nombre": "Neon", "descripcion": "Noche synthwave: morado, rosa y cian que brillan.", "familia": "plano"},
    "terminal": {"nombre": "Terminal", "descripcion": "Pantalla de ordenador antigua: verde fosforo y letra de maquina.", "familia": "plano"},
    "explicador": {"nombre": "Explicador", "descripcion": "Papel crema, tinta y rojo, tarjetas con sombra de puntos. Ideal con presentador.",
                   "familia": "plano"},
    # B3 y B4 de stickman-video-director (kaomei, MIT). guia = reglas extra del guion; escenas = tipos permitidos
    # (si falta, los del nicho); palabras = por escena; nuevas = dibujos nuevos como mucho (videos cortos).
    "retrotv": {"nombre": "Retro TV", "familia": "retrotv", "palabras": "8-14", "segundos": "3-5", "nuevas": 12,
                "descripcion": "Campo oscuro, siluetas blancas, cabecera con contador y acabado de tele vieja.",
                "guia": "ESTILO 'Retro TV' (explicador de siluetas blancas sobre negro, como una emision analogica): cada "
                        "escena muestra UNA idea con un sujeto claro y mucho espacio vacio. Las ilustraciones 'nueva' "
                        "describen en ingles una escena sencilla: personas como stickman blanco sin cara, animales "
                        "simpaticos, pocos objetos, nada de texto; varia el plano (general, detalle, comparacion lado a "
                        "lado, pantalla de camara de vigilancia, diagrama con flechas) y que la imagen ENSENE lo que dice "
                        "la frase (si dice que se acerca, se ve acercandose). Mezcla con listas, versus y cifras para ordenar "
                        "ideas. Usa 'sello' con 'FALSO' o 'NO' para tachar una idea equivocada. Pon en la raiz \"cabecera\": "
                        "\"TEMA / SUBTEMA\" (2-4 palabras, sale arriba en cada escena). La portada lleva \"nueva\": "
                        "descripcion EN INGLES de la primera imagen (el sujeto del gancho)."},
    "thriller": {"nombre": "Thriller", "familia": "thriller", "palabras": "5-9", "segundos": "2-3", "nuevas": 20,
                 "escenas": ["portada", "ilustracion"],
                 "descripcion": "Historia de suspense dibujada a color, guantes blancos, planos cortos y portada en sombra.",
                 "guia": "ESTILO 'Thriller' (historia corta de supervivencia o suspense, contada en planos dibujados): "
                         "una historia con protagonista, situacion, amenaza que escala y giro final; la narracion en "
                         "frases cortas que crean tension. Los 3 primeros segundos ya muestran el peligro o lo raro. "
                         "Casi todo son escenas 'ilustracion' de 2-3 s (UNA frase corta cada una) con \"nueva\" en ingles: "
                         "un plano distinto cada vez (general, primer plano de la cara, detalle de la mano o del objeto, "
                         "contrapicado, desde lejos), con la amenaza VISIBLE en el dibujo y quien es quien claro (el "
                         "protagonista siempre con el mismo peinado o accesorio, descrito igual en cada 'nueva'). Nada de "
                         "sangre ni gore. La portada lleva \"nueva\": descripcion EN INGLES del momento mas inquietante, "
                         "y su titulo es una pregunta corta. El final puede dejar una pregunta al que mira (sin pedir likes)."},
}

# Presentador (motion/fabrica/presentador.js): un personaje plano abajo a la derecha que habla todo el video; la
# boca sigue el volumen de la voz. aspecto = colores y forma; los subtitulos pasan arriba a la izquierda.
PRESENTADORES = {
    "leo": {"nombre": "Leo", "descripcion": "Gafas, pelo corto y sudadera azul.",
            "aspecto": {"piel": "#f1c7a3", "pelo": "#3a2a22", "ropa": "#2f5d8a", "ropa2": "#24496e", "peinado": "corto", "gafas": True}},
    "ana": {"nombre": "Ana", "descripcion": "Pelo largo castano y sudadera roja.",
            "aspecto": {"piel": "#e9b48f", "pelo": "#5a3420", "ropa": "#c8463b", "ropa2": "#9e352c", "peinado": "largo", "gafas": False}},
    "max": {"nombre": "Max", "descripcion": "Pelo rizado, barba y sudadera verde.",
            "aspecto": {"piel": "#b9825c", "pelo": "#1f1712", "ropa": "#3f7d4e", "ropa2": "#2f5f3b", "peinado": "rizado", "gafas": False, "barba": True}},
    "sol": {"nombre": "Sol", "descripcion": "Coleta rubia, gafas y sudadera morada.",
            "aspecto": {"piel": "#f6d2b5", "pelo": "#d9a441", "ropa": "#6a4f8a", "ropa2": "#523c6c", "peinado": "coleta", "gafas": True}},
}
BOCA_DB = (-42.0, -16.0)   # volumen (dB) de boca cerrada y de boca muy abierta
BOCA_SUELTA = 0.55         # al bajar el volumen la boca se cierra multiplicando por esto cada fotograma
# Escenas: lo que Claude puede pedir (campos) y lo que necesita el motor (scripts extra).
ESCENAS = {
    "portada": {
        "descripcion": "El gancho del principio: el titulo grande (ya visible en el primer fotograma). Siempre la primera.",
        "campos": '"titulo": la pregunta o idea en pocas palabras, con *asteriscos* en la palabra clave (un nombre o un dato, nunca un verbo); '
                  '"antetitulo"?: 2-4 palabras encima; "paises"?: ["ISO3"] para poner su mapa de fondo (se pintan); '
                  '"lugar"?: {"lon", "lat", "zoom"} si el video va de una PARTE de un pais o de un sitio (Alaska, Crimea, '
                  'Gibraltar, el canal de Panama): el fondo encuadra eso en vez del pais entero; '
                  '"vista"?: "satelite" o "mapa" (como en las escenas de mapa); '
                  '"protagonista"?: {"id": pegatina de la biblioteca, "nueva"?: "descripcion EN INGLES"} '
                  '(de quien o de que va el video: el animal, el objeto, la persona; grande junto al titulo; '
                  'OBLIGATORIO si no hay paises)',
        "scripts": ["paises.js", "mapa.js", "graficas.js"],
    },
    "mapa": {
        "descripcion": "Mapa que se mueve: la camara vuela a paises o sitios, se pintan paises de color, rotulos y un dato grande.",
        "campos": '"paises": [{"iso": "ISO3", "color": COLOR, "palabra": "...", "hasta"?: "..."}]; '
                  '"etiquetas"?: [{"texto": "NOMBRE", "iso"?: "ISO3" o "lon"/"lat", "palabra": "...", "punto"?: true si es una ciudad}]; '
                  '"rotulo"?: {"texto": "1879", "palabra": "..."} (fecha o cifra corta, grande arriba); '
                  '"camara"?: [{"paises": ["ISO3"] o "lugar": {"lon", "lat", "zoom"}, "palabra": "..."}] '
                  '(si no la pones, encuadra lo que sale en la escena; zoom: 1 continente, 2.5 pais grande, 4 pais pequeno, '
                  '5-6 una ciudad en el mapa dibujado; con satelite: 7 una region, 9 una ciudad entera (Moscu, Paris), '
                  '10-11 un sitio muy pequeno como Gibraltar o un puerto); '
                  '"vista"?: "satelite" (foto real: sitios concretos, costas, estrechos, ciudades, el presente) o "mapa" '
                  '(dibujado: historia, muchos paises, fronteras; es lo normal); '
                  '"banderas"?: [{"iso": "ISO3", "palabra": "...", "ojos"?: true para personificar al pais (protagonista, el que se queja o quiere algo), '
                  '"lon"/"lat"?: si va en otro sitio que el centro de su pais (la bandera britanica sobre Gibraltar)}] '
                  '(la bandera tiene que verse con la camara de ese momento); '
                  '"pegatinas"?: [{"id": el de la biblioteca mas parecido, "nueva"?: "descripcion EN INGLES" si ninguno sirve bien, '
                  '"clase"?: "personaje" u "objeto", "iso" o "lon"/"lat" (donde se pone), "palabra": "..."}] '
                  '(personaje u objeto de juguete encima del mapa: el rey, el barco, el canon, el mono de Gibraltar...); '
                  '"rios"?: [{"nombre": en ingles como en Natural Earth ("Nile", "White Nile", "Blue Nile", "Amazon", "Danube"), '
                  '"palabra": "...", "color"?: COLOR}] (un rio se dibuja asi, NUNCA pintando un pais); '
                  '"medida"?: {"desde": {"lon", "lat"}, "hasta": {"lon", "lat"}, "texto": "14 km", "palabra": "..."} '
                  '(una DISTANCIA entre dos puntos que se ven, p. ej. de orilla a orilla de un estrecho; nunca un area); '
                  '"ruta"?: {"desde": {"lon", "lat"}, "hasta": {"lon", "lat"}, "palabra": "...", "pegatina"?: id que viaja (barco, avion...)}; '
                  '"circulo"?: {"lon", "lat", "palabra"} (rodea un sitio pequeno); '
                  '"golpe"?: {"texto": "PARA SIEMPRE" (2-3 palabras de impacto), "palabra": "..."} (no junto con rotulo); '
                  '"foco"?: true si la escena va de un sitio a otro (al pintarse un pais, los de antes de OTRO color se apagan '
                  'y solo brilla aquel del que se habla); no lo pongas cuando se comparan o se enfrentan a la vez',
        "scripts": ["paises.js", "rios.js", "mapa.js", "piezas.js"],
    },
    "cifra": {
        "descripcion": "Un numero enorme que cuenta desde 0 al decirlo, con lo que significa.",
        "campos": '"numero": "400" (solo cifras), "antes"?: "$", "despues"?: " km", "etiqueta": "de costa perdida", '
                  '"contexto"?: frase corta encima, "palabra": la palabra del numero tal cual se dice',
        "scripts": [],
    },
    "ilustracion": {
        "descripcion": "Una escena dibujada a pantalla completa (en el estilo de dibujo del video) para lo que no se ve en un mapa: "
                       "personas y momentos (un rey enfermo, la firma de un tratado, una batalla, un mercado). 1-3 por video, nunca seguidas.",
        "campos": '"imagen": id de la biblioteca de ilustraciones (la mas parecida), "nueva"?: "descripcion EN INGLES de la escena" '
                  'si ninguna sirve bien; "golpe"?: {"texto", "palabra"}; "rotulo"?: {"texto": "1713", "palabra"}',
        "scripts": ["piezas.js"],
    },
    "protagonista": {
        "descripcion": "El protagonista del video (el de la portada) grande en el centro, que CAMBIA DE ESTADO justo al "
                       "decir la palabra: es el hilo del video y lo que mas engancha. 1-3 por video, nunca seguidas.",
        "campos": '"inicio"?: ESTADO con el que aparece (si no lo pones, como acabo la vez anterior); '
                  '"cambios": [{"estado": ESTADO, "palabra": "..."}] (1-3, en orden); '
                  '"golpe"?: {"texto": 2-3 palabras de impacto, "palabra"}; "rotulo"?: {"texto": "2 años", "palabra"}',
        "scripts": ["graficas.js", "piezas.js"],
    },
    "barras": {
        "descripcion": "Comparar 2-6 cantidades de lo mismo (PIB, poblacion, precios, alturas): cada barra crece al nombrarla.",
        "campos": '"titulo"?: que se compara, con la unidad ("Deuda publica, % del PIB"); '
                  '"barras": [{"etiqueta": "Japon", "valor": 255 (numero), "texto"?: "255 %" (como se lee la cifra), '
                  '"color"?: COLOR, ICONO, "palabra": "..."}] (en el orden en que se nombran)',
        "scripts": ["graficas.js"],
    },
    "lista": {
        "descripcion": "Un top o una enumeracion de 2-5 cosas (motivos, pasos, los mas grandes): cada fila entra al nombrarla.",
        "campos": '"titulo"?: "3 motivos..."; "numerar"?: true si es un top o pasos; '
                  '"items": [{"texto": "frase muy corta (2-6 palabras)", ICONO, "palabra": "..."}]',
        "scripts": ["graficas.js"],
    },
    "versus": {
        "descripcion": "Dos cosas frente a frente (dos paises, dos empresas, antes y ahora) con un dato de cada una.",
        "campos": '"titulo"?: "..."; "lados": [{"nombre": "Coca-Cola", "dato"?: "dato corto", "color"?: COLOR, ICONO, '
                  '"palabra": "..."}, {...}] (exactamente 2); "palabra_vs"?: la palabra donde se enfrentan',
        "scripts": ["graficas.js"],
    },
    "captura": {
        "descripcion": "Algo de una pantalla que todos reconocen, como si fuera una captura: un tuit, el titular de una "
                       "noticia, notificaciones del movil, un chat de WhatsApp o una busqueda en Google. Para citas, "
                       "titulares, lo que alguien dijo o lo que la gente busca. 0-2 por video.",
        "campos": '"forma": "tuit" | "noticia" | "notificacion" | "chat" | "busqueda"; "nombre": quien lo publica, el '
                  'medio, la app o el contacto del chat; "usuario"?: @ del tuit; "contenido": el texto del tuit, el '
                  'titular o lo que se busca (corto, max 120 letras); "cifra"?: likes del tuit ("48000"); '
                  '"mensajes"?: [{"texto": "...", "mio"?: true si es el de la derecha en un chat, "palabra": "..."}] '
                  '(chat 2-5, notificacion 1-3); "palabra": donde pasa lo principal (se subraya el titular, acaba '
                  'de escribirse la busqueda, cuentan los likes). Nunca inventes que una persona o medio real dijo '
                  'algo: si no es una cita real, usa un nombre generico ("Un usuario", "Noticias")',
        "scripts": ["graficas.js"],
    },
    "linea_tiempo": {
        "descripcion": "De 2 a 5 fechas en orden sobre una linea que se va dibujando (una historia, una evolucion).",
        "campos": '"titulo"?: "..."; "hitos": [{"fecha": "1929", "texto": "2-6 palabras", ICONO, "palabra": la fecha o '
                  'palabra que se dice}] (en orden)',
        "scripts": ["graficas.js"],
    },
}

# Estados del protagonista (motion/fabrica/graficas.js): los de color y tamano duran; los demas son un momento.
ESTADOS = {
    "normal": "como es (vuelve a su color y tamano)", "gris": "sin color", "apagado": "gris y medio transparente",
    "brillante": "brilla con el color del estilo", "grande": "crece", "pequeno": "encoge",
    "salta": "da un salto (alegria, sorpresa)", "tiembla": "tiembla (miedo, peligro, frio)",
    "muchos": "aparecen 2 copias a los lados (se multiplica, mas de uno)", "se_va": "desaparece (muere, se pierde, se acaba)",
}
ESTADOS_FIJOS = ("gris", "apagado", "brillante")   # los que puede llevar un icono quieto
# ICONO en las fichas de arriba (lo que se dibuja al lado de un elemento)
ICONO = ('"pegatina"?: id de la biblioteca (con "nueva"?: "descripcion EN INGLES" si ninguna es eso; '
         f'"estado"?: {" | ".join(ESTADOS_FIJOS)} para verla asi, p. ej. el protagonista gris frente al de color), '
         'o "iso"?: ISO3 para su bandera (uno de los dos o ninguno)')
for _e in ESCENAS.values():
    _e["campos"] = _e["campos"].replace("ICONO", ICONO).replace(
        "ESTADO", "uno de " + ", ".join(f"{k} ({d})" for k, d in ESTADOS.items()), 1).replace("ESTADO", "uno de esos estados")

FORMAS_CAPTURA = ("tuit", "noticia", "notificacion", "chat", "busqueda")
COLORES = ("rojo", "azul", "verde", "amarillo", "naranja", "morado", "gris", "acento")

NICHOS = {
    "mapas": {
        "nombre": "Mapas e historia",
        "descripcion": "Por que un territorio es de quien es, fronteras raras, guerras que cambiaron el mapa.",
        "escenas": ["portada", "mapa", "cifra", "ilustracion", "protagonista", "captura"],
        "guia": "Video de geografia e historia con mapas. Estructura: gancho con una pregunta curiosa -> contexto -> "
                "el hecho clave (fecha, guerra, tratado, venta) -> consecuencia hoy -> cierre que responde la pregunta. "
                "Casi todo son escenas de mapa: la camara nunca se para y cada pais o sitio se ve CUANDO se nombra. "
                "Dale vida al mapa como un short de mapas de los buenos: banderas sobre los paises que hablan, pegatinas "
                "(personajes y objetos) donde pasa la accion, rutas de barcos o ejercitos, medidas de distancias, satelite "
                "para sitios concretos y alguna ilustracion para los momentos con personas.",
    },
    "datos": {
        "nombre": "Datos y comparaciones",
        "descripcion": "Rankings, cifras que sorprenden y comparaciones entre paises, empresas o epocas.",
        "escenas": ["portada", "cifra", "barras", "lista", "versus", "linea_tiempo", "protagonista", "mapa", "ilustracion", "captura"],
        "guia": "Video de datos para redes. Estructura: gancho con la cifra o la comparacion mas sorprendente -> el contexto "
                "minimo -> los datos que lo explican (barras, versus, listas) -> el giro o el dato final que nadie espera -> "
                "cierre que responde al gancho. Cada escena muestra UN dato claro; varia el tipo de escena (nunca 2 iguales "
                "seguidas). Datos reales con su fecha o año; redondea para que se lean bien. Un mapa solo si importa donde.",
    },
    "curiosidades": {
        "nombre": "Curiosidades",
        "descripcion": "Cosas que casi nadie sabe: historia, ciencia, animales, objetos de todos los dias.",
        "escenas": ["portada", "protagonista", "ilustracion", "cifra", "lista", "versus", "linea_tiempo", "mapa", "captura"],
        "guia": "Video de curiosidades. Estructura: gancho con una pregunta o un hecho increible -> por que pasa -> el detalle "
                "que lo hace aun mas raro -> cierre con la respuesta. Tono cercano y con ritmo. Usa ilustraciones para lo que "
                "tiene personas o momentos, cifras para los numeros y alguna lista o versus para ordenar ideas; nunca 2 "
                "escenas iguales seguidas.",
    },
    "finanzas": {
        "nombre": "Finanzas y economia",
        "descripcion": "Dinero, inflacion, empresas, inversiones y por que las cosas cuestan lo que cuestan.",
        "escenas": ["portada", "cifra", "barras", "linea_tiempo", "versus", "lista", "protagonista", "ilustracion", "mapa", "captura"],
        "guia": "Video de finanzas personales y economia, claro para cualquiera. Estructura: gancho con una cifra o una pregunta "
                "sobre dinero -> explicacion sencilla con un ejemplo -> los datos (barras, cifras, linea de tiempo) -> lo que "
                "significa para quien lo ve -> cierre. Nada de consejos de inversion personalizados ni promesas de ganar "
                "dinero. Pegatinas de dinero, graficos, monedas, hucha... en barras, listas y versus; nunca 2 escenas iguales seguidas.",
    },
    "historia": {
        "nombre": "Historia y personajes",
        "descripcion": "Reyes, batallas, inventores y momentos que cambiaron todo, contados como una historia.",
        "escenas": ["portada", "protagonista", "ilustracion", "linea_tiempo", "cifra", "versus", "mapa", "lista", "captura"],
        "guia": "Video de historia contada como un relato. Estructura: gancho con el momento mas sorprendente -> quien era y "
                "que queria -> el conflicto -> el giro que nadie esperaba -> como acabo y que queda hoy. El personaje es el "
                "protagonista (escenas 'protagonista' que cambian de estado con lo que le pasa); ilustraciones para los "
                "momentos clave, linea de tiempo para las fechas y un mapa solo si importa donde. Fechas y nombres reales.",
    },
    "ciencia": {
        "nombre": "Ciencia y espacio",
        "descripcion": "El universo, el cuerpo humano y la fisica de todos los dias, con cifras que cuesta creer.",
        "escenas": ["portada", "cifra", "versus", "protagonista", "ilustracion", "barras", "lista", "linea_tiempo", "captura"],
        "guia": "Video de divulgacion cientifica para cualquiera. Estructura: gancho con una pregunta o una cifra imposible "
                "-> la explicacion con una comparacion de la vida diaria (si la Tierra fuera una canica...) -> el dato que "
                "lo hace aun mas raro -> que significa para nosotros. Cifras enormes con 'cifra' y comparaciones con "
                "'versus' o 'barras'; nunca 2 escenas iguales seguidas. Solo ciencia aceptada; si algo se discute, dilo.",
    },
    "animales": {
        "nombre": "Animales y naturaleza",
        "descripcion": "Animales con poderes increibles, records de la naturaleza y fenomenos que parecen inventados.",
        "escenas": ["portada", "protagonista", "ilustracion", "cifra", "versus", "barras", "lista", "mapa", "captura"],
        "guia": "Video de animales y naturaleza. Estructura: gancho con la habilidad o el record mas increible -> como lo "
                "hace -> la comparacion con un humano o un objeto conocido (versus, barras) -> el detalle que nadie sabe -> "
                "cierre. El animal es el protagonista y cambia de estado con la historia (crece, se multiplica, se va); un "
                "mapa solo para donde vive. Datos de fuentes cientificas, sin exagerar.",
    },
    "tecnologia": {
        "nombre": "Tecnologia y empresas",
        "descripcion": "Como nacio una marca, inventos que cambiaron todo, IA y las guerras entre gigantes.",
        "escenas": ["portada", "linea_tiempo", "barras", "versus", "cifra", "protagonista", "ilustracion", "lista", "captura"],
        "guia": "Video de tecnologia y empresas. Estructura: gancho con la cifra o el giro mas fuerte -> el origen (quien, "
                "donde, cuando) -> la decision clave o el error -> los numeros de hoy (barras, versus entre empresas) -> la "
                "leccion. Cifras con su ano; nada de rumores. Nunca 2 escenas iguales seguidas.",
    },
    "misterios": {
        "nombre": "Misterios sin resolver",
        "descripcion": "Desapariciones, lugares extranos y enigmas reales que nadie ha podido explicar.",
        "escenas": ["portada", "ilustracion", "mapa", "linea_tiempo", "cifra", "lista", "protagonista", "versus", "captura"],
        "guia": "Video de misterios REALES y documentados, con suspense. Estructura: gancho con el hecho inexplicable -> "
                "donde y cuando (mapa, linea de tiempo) -> lo que se sabe -> las teorias (lista; separa los hechos de las "
                "teorias y nunca presentes una teoria como cierta) -> la pregunta que sigue abierta. Tono intrigante pero "
                "serio; sin morbo con victimas reales.",
    },
}

# Series de formato: la misma estructura reconocible video tras video (sirve con cualquier nicho). "antetitulo" sale
# siempre encima del titulo de la portada, asi quien la ve sabe de que serie es.
SERIES = {
    "mitos": {
        "nombre": "Mito o verdad", "antetitulo": "Mito o verdad",
        "descripcion": "Una creencia que casi todos repiten, puesta a prueba con datos.",
        "guia": "SERIE 'Mito o verdad': la portada plantea la creencia tal como la dice la gente, en pregunta. Luego de "
                "donde sale, que dicen los datos y el veredicto. La ultima escena lleva un 'golpe' con el veredicto "
                "(MITO, VERDAD o A MEDIAS) y la frase que lo resume.",
    },
    "abuela": {
        "nombre": "Explicado facil", "antetitulo": "Explicado facil",
        "descripcion": "Un tema complicado contado como a tu abuela: comparaciones de casa, sin tecnicismos.",
        "guia": "SERIE 'Explicado facil': cuentalo como a una abuela lista que no sabe del tema. Cada idea con una "
                "comparacion de la vida diaria (la cocina, el mercado, la familia); cero palabras tecnicas sin explicar; "
                "frases muy cortas. El cierre resume todo en una frase que se pueda repetir en la cena.",
    },
    "estafas": {
        "nombre": "Que no te pase", "antetitulo": "Que no te pase",
        "descripcion": "Como funciona un engano conocido, como detectarlo y que hacer (para protegerse).",
        "guia": "SERIE 'Que no te pase' (para protegerse, nunca para ensenar a estafar): la portada dice el engano "
                "y a quien le cae. Luego como empieza, la trampa (sin dar detalles que sirvan para copiarla), las "
                "senales para detectarlo en una 'lista' y que hacer si ya te paso. Cifras reales de cuanta gente cae.",
    },
    "historias": {
        "nombre": "Historias reales", "antetitulo": "Historia real",
        "descripcion": "Un caso real y documentado contado como una historia, con su giro final.",
        "guia": "SERIE 'Historia real': un caso REAL y documentado contado como una historia de las que se leen en "
                "foros: protagonista, situacion, problema, giro y final. Tension en cada escena; el giro casi al final. "
                "Nada inventado: nombres, lugares y fechas reales.",
    },
    "noticias": {
        "nombre": "La noticia en 1 minuto", "antetitulo": "En 1 minuto",
        "descripcion": "Que paso, por que importa y que viene ahora.",
        "guia": "SERIE 'La noticia en 1 minuto': que paso (con fecha), por que importa a quien lo ve, el contexto "
                "minimo y que puede venir ahora. Solo hechos que estan en el tema; si algo no lo sabes seguro, no lo digas.",
    },
    "explicador": {
        "nombre": "Explicado en puntos", "antetitulo": "",
        "descripcion": "Un problema, la promesa y 3-7 puntos que lo resuelven (va muy bien con presentador).",
        "guia": "SERIE 'Explicado en puntos' (formato de presentador que explica): la portada dice el PROBLEMA en menos "
                "de 6 palabras y la primera frase de la narracion lo dice igual; la segunda frase PROMETE lo que se va a "
                "llevar quien mire hasta el final. Luego 3-7 puntos: cada punto empieza en una escena con un extra "
                "'sello' con su numero ('#1', '#2'...) en la palabra donde empieza, y se explica con cifras, listas, "
                "versus, barras o una captura de busqueda que se escribe sola. El cierre cumple la promesa y repite la "
                "idea de la portada (el video acaba como empieza, para que se vea en bucle). Frases cortas, unas 3 "
                "palabras por segundo, tono de alguien que te lo explica a ti. Sin emojis.",
    },
    "top": {
        "nombre": "Top 5", "antetitulo": "Top 5",
        "descripcion": "Un ranking de 5 que va del 5 al 1, con el mejor dato al final.",
        "guia": "SERIE 'Top 5': un ranking que se cuenta del 5 al 1 (una escena o dos por puesto, el numero del puesto "
                "en un 'rotulo' o en un 'golpe'), dejando lo mas sorprendente para el numero 1. Una 'lista' numerada al "
                "final repasa los 5.",
    },
}


# ------------------------------------------------------------------ almacen

def _dir(fid, *partes, crear=False):
    almacen.validar_id(fid)
    ruta = almacen.raiz("fabrica", fid, *partes)
    if crear:
        os.makedirs(ruta if not os.path.splitext(ruta)[1] else os.path.dirname(ruta), exist_ok=True)
    return ruta


def _leer(fid):
    s = almacen.leer_json(_dir(fid, "sesion.json"))
    if s is None:
        raise FileNotFoundError("ese video de la Fabrica no existe")
    return _interrumpido(fid, s)


TRABAJANDO = ("en cola", "guion", "voz", "render", "montaje")


def _interrumpido(fid, s):
    """Un video "en proceso" sin hilo en este servidor se corto (se reinicio el servidor a medias): pasa a error con
    el aviso de Rehacer (sigue donde iba: lo ya dibujado sale de la cache), en vez de quedarse pegado para siempre."""
    if s.get("estado") in TRABAJANDO and fid not in _trabajos and time.time() - (s.get("actualizado") or 0) > 30:
        etapa = {"render": "render", "montaje": "render", "voz": "voz"}.get(s["estado"], "guion")
        s = {**s, "estado": "error", "mensaje": "",
             "error": f"Se corto a medias (se reinicio el servidor). Dale a Rehacer desde {etapa}: sigue donde iba."}
        almacen.escribir_json(_dir(fid, "sesion.json"), s)
    return s


def _guardar(fid, **cambios):
    with _candado:
        s = _leer(fid)
        s.update(cambios)
        s["actualizado"] = time.time()
        almacen.escribir_json(_dir(fid, "sesion.json"), s)
        return s


def catalogo():
    return {"nichos": [{"id": k, "nombre": n["nombre"], "descripcion": n["descripcion"]} for k, n in NICHOS.items()],
            "series": [{"id": k, "nombre": s["nombre"], "descripcion": s["descripcion"]} for k, s in SERIES.items()],
            "presentadores": [{"id": k, "nombre": x["nombre"], "descripcion": x["descripcion"]} for k, x in PRESENTADORES.items()]
            + [{"id": "propio:" + f["id"], "nombre": f["nombre"], "descripcion": f.get("descripcion") or "propio", "propio": True}
               for f in presentadores.listar()],
            "visuales": [{"id": k, "nombre": n} for k, n in biblioteca.NOMBRES_FAMILIA.items()],
            "estilos": [{"id": k, **e} for k, e in ESTILOS.items()],
            "formatos": list(FORMATOS), "falta": graficos.disponible()}


def listar():
    base = almacen.raiz("fabrica")
    if not os.path.isdir(base):
        return []
    salida = []
    for f in os.listdir(base):
        s = almacen.leer_json(os.path.join(base, f, "sesion.json"))
        if s:
            s = _interrumpido(f, s)
        if s:   # con sus videos para las tarjetas (se pueden ver mientras se rehace otro)
            videos = almacen.leer_json(os.path.join(base, f, "videos.json"), []) or []
            salida.append({**s, "videos": [v for v in videos if os.path.isfile(os.path.join(base, f, "videos", v["archivo"]))],
                           "trabajando": bool(f in _trabajos and _trabajos[f].is_alive())})
    return sorted(salida, key=lambda s: s.get("creado", 0), reverse=True)


def renombrar(fid, titulo):
    titulo = str(titulo or "").strip()[:120]
    if not titulo:
        raise ValueError("escribe un titulo")
    _leer(fid)
    _guardar(fid, titulo=titulo)
    return _leer(fid)


def duplicar(fid):
    """Copia entera (guion, voz, escenas ya dibujadas y videos) para probar otra version sin perder esta."""
    s = _leer(fid)
    with _candado:
        if fid in _trabajos and _trabajos[fid].is_alive():
            raise RuntimeError("esta trabajando: espera a que termine")
        nuevo = uuid.uuid4().hex[:12]
        shutil.copytree(_dir(fid), _dir(nuevo))
    _guardar(nuevo, id=nuevo, titulo=f"{s['titulo']} (copia)"[:120], creado=time.time())
    return _leer(nuevo)


def ver(fid):
    s = _leer(fid)
    return {**s, "guion": _con_estilo_video(almacen.leer_json(_dir(fid, "guion.json")), s["opciones"]), "clips": clips(fid),
            "videos": almacen.leer_json(_dir(fid, "videos.json"), []) or []}


def _con_estilo_video(guion, o):
    """Los prompts de video llevan al final el aspecto de los dibujos (stickman, grabado...): sin la imagen de
    partida, Seedance o Veo harian personas reales."""
    if not guion:
        return guion
    familia = _familia(o)
    plantilla = biblioteca.FAMILIAS[familia]["escena"] if familia else biblioteca.ESCENA
    antes, despues = plantilla.split("{}")
    estilo = (f"Visual style: {antes.strip().removesuffix(' of').strip()}, "
              + despues.strip(", ").replace(", vertical composition", "") + ".")
    for e in guion.get("escenas") or []:
        if isinstance(e.get("video_prompt"), str) and e["video_prompt"] and "Visual style:" not in e["video_prompt"]:
            e["video_prompt"] = e["video_prompt"].rstrip(". ") + ". " + estilo
    return guion


def ruta_video(fid, formato):
    if formato not in FORMATOS:
        raise ValueError("formato no valido")
    ruta = _dir(fid, "videos", formato.replace(":", "x") + ".mp4")
    if not os.path.isfile(ruta):
        raise FileNotFoundError("ese video aun no esta hecho")
    return ruta


def borrar(fid):
    with _candado:
        if fid in _trabajos and _trabajos[fid].is_alive():
            raise RuntimeError("esta trabajando: espera a que termine")
        shutil.rmtree(_dir(fid), ignore_errors=True)


def _tam(ruta):
    total = 0
    for raiz, _dirs, archivos in os.walk(ruta):
        for n in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, n))
            except OSError:
                pass
    return total


def espacio(fid):
    """{"total": bytes del video, "liberable": la cache de escenas ya dibujadas (se redibujan si hacen falta)}."""
    return {"total": _tam(_dir(fid)), "liberable": _tam(_dir(fid, "escenas"))}


def liberar(fid):
    """Borra la cache de escenas. Los videos hechos, el guion, la voz y los clips subidos no se tocan; al
    rehacer o abrir en el editor las escenas se vuelven a dibujar. Devuelve los bytes liberados."""
    _leer(fid)
    with _candado:
        if fid in _trabajos and _trabajos[fid].is_alive():
            raise RuntimeError("esta trabajando: espera a que termine")
        antes = _tam(_dir(fid, "escenas"))
        shutil.rmtree(_dir(fid, "escenas"), ignore_errors=True)   # en uso (Windows): queda para la proxima
        return antes - _tam(_dir(fid, "escenas"))


def resumen_espacio():
    base = almacen.raiz("fabrica")
    ids = [f for f in os.listdir(base) if os.path.isfile(os.path.join(base, f, "sesion.json"))] if os.path.isdir(base) else []
    return [{"id": f, **espacio(f)} for f in sorted(ids)]


def _opciones(o, base=None):
    """Limpia lo que pide la persona (tema, nicho, estilo, formatos, voz...)."""
    o = {**(base or {}), **{k: v for k, v in (o or {}).items() if v is not None}}
    nicho = o.get("nicho") if o.get("nicho") in NICHOS else "mapas"
    estilo = o.get("estilo") if o.get("estilo") in ESTILOS else next(iter(ESTILOS))
    formatos = [f for f in (o.get("formatos") or ["9:16"]) if f in FORMATOS] or ["9:16"]
    # musica: "random", "" (sin musica) o el nombre de una cancion de resource/songs (antes era un bool)
    musica = o.get("musica", "random")
    musica = ("random" if musica else "") if isinstance(musica, bool) else os.path.basename(str(musica or ""))[:200]
    return {"tema": str(o.get("tema") or "").strip()[:400], "nicho": nicho, "estilo": estilo,
            "formatos": list(dict.fromkeys(formatos)), "voz": str(o.get("voz") or etapa_voz.DEFECTOS["voz"])[:120],
            "velocidad": min(1.5, max(0.7, float(o.get("velocidad") or 1.0))),
            "duracion": min(600, max(20, int(o.get("duracion") or 55))),   # hasta 10 min (largos: por capitulos)
            "musica": musica, "musica_volumen": min(1.0, max(0.0, float(o.get("musica_volumen") or 0.16))),
            "subtitulos": bool(o.get("subtitulos", True)),
            "efectos": bool(o.get("efectos", True)), "nuevos": bool(o.get("nuevos", True)),
            "foco": bool(o.get("foco", True)),
            "serie": o.get("serie") if o.get("serie") in SERIES else "",
            # clonar: la receta (id de clonar.py) cuya estructura sigue el guion; clips: ademas de la foto, Claude escribe
            # el prompt de video de cada ilustracion para hacerlo aparte (Seedance, Veo...) y subirlo
            "receta": o.get("receta") if re.fullmatch(r"[0-9a-f]{12}", str(o.get("receta") or "")) else "",
            "clips": bool(o.get("clips", False)),
            # banco de clips: videos cortados en planos (banco.py) cuyos clips Claude pone detras de las ilustraciones
            "banco": [b for b in dict.fromkeys(o.get("banco") or []) if re.fullmatch(r"[0-9a-f]{12}", str(b))][:6]
            if isinstance(o.get("banco"), list) else [],
            "banco_modo": o.get("banco_modo") if o.get("banco_modo") in banco.MODOS else "insertos",
            # revisar: se para tras el guion y las imagenes (estado "revision") para subir clips, tu voz o elegir
            # la musica; luego montar() sigue. Con clips se para siempre (hay que subirlos antes de montar)
            "revisar": bool(o.get("revisar", False)) or bool(o.get("clips", False)),
            # aspecto de los dibujos: "" (el del estilo), "madera" o una familia (plano, grabado, stickman...)
            "visual": o.get("visual") if o.get("visual") == "madera" or o.get("visual") in biblioteca.FAMILIAS else "",
            # cierre de marca: el nombre del canal sale al final de cada video ("" = sin cierre)
            "marca": str(o.get("marca") or "").strip()[:40],
            # uno de PRESENTADORES o "propio:<id>" (presentadores.py: hecho con Nano Banana o subido)
            "presentador": o.get("presentador") if o.get("presentador") in PRESENTADORES
            or presentadores.aspecto(str(o.get("presentador") or "").removeprefix("propio:")) else "",
            "idioma": str(o.get("idioma") or "espanol")[:30],
            # saga: el video del que este es la continuacion (Dia 1 -> Dia 2...) y su numero de episodio
            "continua": o.get("continua") if re.fullmatch(r"[0-9a-f]{12}", str(o.get("continua") or "")) else "",
            "episodio": max(1, int(o.get("episodio") or 1)),
            # temporada: lo que pasa en este episodio segun el plan que hizo Claude para toda la tanda
            "rumbo": str(o.get("rumbo") or "").strip()[:700]}


def crear(opciones):
    o = _opciones(opciones)
    if _propia(o):
        _audio_subido(o["voz"])   # falla ya si no esta
    elif not o["tema"]:
        raise ValueError("escribe el tema del video")
    fid = uuid.uuid4().hex[:12]
    os.makedirs(_dir(fid), exist_ok=True)
    almacen.escribir_json(_dir(fid, "sesion.json"), {
        "id": fid, "titulo": o["tema"][:120], "opciones": o, "creado": time.time(), "actualizado": time.time(),
        "estado": "en cola", "progreso": 0, "mensaje": "en cola", "error": None})
    _usar_idea(o)
    _lanzar(fid, _producir, fid, "voz" if _propia(o) else "guion")
    return _leer(fid)


def siguiente_episodio(fid, idea=""):
    """Video nuevo que sigue la historia de este (saga): mismas opciones, y el guion continua donde quedo."""
    s = _leer(fid)
    if not almacen.leer_json(_dir(fid, "guion.json")):
        raise ValueError("este video aun no tiene guion: espera a que termine")
    o = s["opciones"]
    n = int(o.get("episodio") or 1) + 1
    idea = str(idea or "").strip()
    tema = f"Episodio {n} de «{s['titulo']}»" + (f": {idea}" if idea else "")
    # la voz grabada era de aquel video: el nuevo se narra con la voz por defecto
    voz = etapa_voz.DEFECTOS["voz"] if _propia(o) else o["voz"]
    nuevo = crear({**o, "tema": tema, "voz": voz, "continua": fid, "episodio": n, "rumbo": ""})
    if s.get("saga"):   # sigue en la misma saga (y lo que quedaba pendiente pasa a este)
        _guardar(nuevo["id"], saga=s["saga"], saga_nombre=s.get("saga_nombre") or "", saga_despues=s.get("saga_despues") or "")
    return _leer(nuevo["id"])


def montar_saga(sid):
    """Monta, de uno en uno y por orden de episodio, los episodios de una saga que esperan en revision."""
    fids = sorted((s for s in listar() if s.get("saga") == sid and s.get("estado") == "revision"),
                  key=lambda s: s["opciones"].get("episodio") or 1)
    fids = [s["id"] for s in fids]
    if not fids:
        raise ValueError("no hay episodios de esta saga esperando a montar")
    for n, fid in enumerate(fids, 1):
        _guardar(fid, estado="en cola", progreso=0, error=None, mensaje=f"en cola: montar saga ({n} de {len(fids)})")

    def correr():
        for fid in fids:
            try:
                _producir(fid, "voz")
            except Exception as e:  # noqa: BLE001 -- se ve en su tarjeta; sigue el siguiente
                logger.exception(f"fabrica {fid} (montar saga {sid})")
                _guardar(fid, estado="error", error=str(e)[:500], mensaje="")

    hilo = threading.Thread(target=correr, daemon=True, name=f"fabrica-montar-{sid}")
    with _candado:
        for fid in fids:
            _trabajos[fid] = hilo
    hilo.start()
    return {"videos": [_leer(f) for f in fids]}


TEMPORADA_MAX = 10   # episodios por tanda


def temporada(desde=None, opciones=None, cuantos=3, idea="", final=False, sin_parar=True):
    """Varios episodios de una saga de una vez. Claude planea la tanda en una llamada corta (que pasa en cada uno y
    hacia donde sigue despues); luego se hacen en orden: primero todos los guiones (cada uno ve los anteriores) y
    despues voz y render, de uno en uno. desde = el ultimo episodio ya hecho (sigue de ahi) o None (saga nueva
    con opciones["tema"]). final: la tanda cierra la historia; si no, el ultimo deja la puerta abierta.
    sin_parar: en masa no se para a revisar ni a esperar clips: cada episodio sale montado."""
    cuantos = min(TEMPORADA_MAX, max(1, int(cuantos or 3)))
    idea = str(idea or "").strip()[:600]
    if desde:
        s = _leer(desde)
        if not almacen.leer_json(_dir(desde, "guion.json")):
            raise ValueError("este video aun no tiene guion: espera a que termine")
        o = {**s["opciones"], "rumbo": ""}
        if _propia(o) or o["voz"].startswith(NARRADA):   # la grabacion era de aquel video
            o["voz"] = etapa_voz.DEFECTOS["voz"]
        n0 = int(o.get("episodio") or 1) + 1
        sid, nombre = s.get("saga") or desde, s.get("saga_nombre") or ""   # sin nombre: el que proponga Claude
        antes, pendiente = _anteriores(desde), s.get("saga_despues") or ""
    else:
        o = _opciones(opciones)
        if _propia(o):
            raise ValueError("una temporada no puede usar una grabacion propia (es de un solo video)")
        if not o["tema"]:
            raise ValueError("escribe de que va la saga")
        n0, sid, nombre, antes, pendiente = 1, uuid.uuid4().hex[:12], "", [], ""
    if sin_parar:   # los prompts de video (clips) se siguen escribiendo; solo no se espera a subirlos
        o = {**o, "revisar": False}
    nicho = NICHOS[o["nicho"]]
    prompt = (
        f"Eres el guionista de una saga de videos cortos por entregas (nicho: {nicho['nombre']}, {o['idioma']}, "
        f"unos {o['duracion']} s por episodio).\n"
        + (f"La saga: {o['tema']}\n" if not antes else "Lo que ya se conto:\n" + "\n".join(antes) + "\n")
        + (f"Lo que quedo pendiente para despues: {pendiente}\n" if pendiente else "")
        + (f"Lo que quiere la persona para esta tanda: {idea}\n" if idea else "")
        + f"Planea los episodios {n0} a {n0 + cuantos - 1} ({cuantos}). Cada uno: una situacion nueva que avanza la "
        "historia (sin repetir lo ya contado), un peligro o problema que escala, y un final que deja intriga para el "
        "siguiente. El mismo protagonista y las mismas reglas del mundo. "
        + ("El ULTIMO episodio cierra la historia con un final claro." if final else
           "El ultimo episodio NO cierra: deja la historia abierta para otra tanda.")
        + "\nResponde SOLO con JSON: {\"saga\": \"nombre corto de la saga (2-5 palabras)\", \"episodios\": "
        "[{\"titulo\": \"titulo del episodio (sigue la numeracion si la hay: Dia 3, Parte 2...)\", \"pasa\": \"que pasa, "
        "2-3 frases: como empieza, que se complica y como acaba\"}], \"despues\": \"hacia donde puede seguir la historia "
        "despues de esta tanda, 1-2 frases\"}")
    plan = _objeto_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=240)) or {}
    eps = [e for e in plan.get("episodios") or [] if isinstance(e, dict) and _txt(e.get("pasa"))][:cuantos]
    if not eps:
        raise RuntimeError("Claude no devolvio el plan de la temporada: prueba otra vez")
    nombre = nombre or _txt(plan.get("saga"), 60) or o["tema"][:60]
    despues = "" if final else _txt(plan.get("despues"), 400)
    fids, previo = [], desde or ""
    for k, e in enumerate(eps):
        n = n0 + k
        titulo = _txt(e.get("titulo"), 90) or f"Episodio {n}"
        oe = _opciones({**o, "tema": f"{nombre} — Episodio {n}: {titulo}", "continua": previo, "episodio": n,
                        "rumbo": f"{titulo}. {_txt(e.get('pasa'), 600)}"})
        if sin_parar:
            oe["revisar"] = False   # _opciones lo vuelve a encender si hay clips
        fid = sid if not desde and k == 0 else uuid.uuid4().hex[:12]   # la saga se llama como su primer video
        os.makedirs(_dir(fid), exist_ok=True)
        almacen.escribir_json(_dir(fid, "sesion.json"), {
            "id": fid, "titulo": oe["tema"][:120], "opciones": oe, "creado": time.time() + k * 0.001,
            "actualizado": time.time(), "estado": "en cola", "progreso": 0,
            "mensaje": f"en cola: episodio {n} ({k + 1} de {len(eps)})", "error": None,
            "saga": sid, "saga_nombre": nombre, "saga_despues": despues if k == len(eps) - 1 else ""})
        fids.append(fid)
        previo = fid
    if desde:
        _guardar(desde, saga=sid, saga_nombre=nombre)

    def correr():
        hechos = []
        for k, fid in enumerate(fids):   # 1) los guiones, en orden (cada uno lee el anterior)
            try:
                _guion(fid)
                hechos.append(fid)
                _guardar(fid, estado="revision" if o.get("revisar") else "en cola", progreso=12,
                         mensaje="guion e imagenes listos: revisa y dale a Montar" if o.get("revisar")
                         else "guion listo: espera su turno para la voz y el render")
            except Exception as e:  # noqa: BLE001 -- sin este guion los siguientes no saben como sigue
                logger.exception(f"fabrica {fid} (temporada {sid})")
                _guardar(fid, estado="error", error=str(e)[:500], mensaje="")
                for resto in fids[k + 1:]:
                    _guardar(resto, estado="error", mensaje="",
                             error="El episodio anterior fallo: rehazlo y luego dale a Rehacer desde guion a este.")
                break
        if o.get("revisar"):
            return
        for fid in hechos:   # 2) voz, escenas y montaje
            try:
                _producir(fid, "voz")
            except Exception as e:  # noqa: BLE001 -- se ve en su tarjeta; sigue el siguiente
                logger.exception(f"fabrica {fid} (temporada {sid})")
                _guardar(fid, estado="error", error=str(e)[:500], mensaje="")

    hilo = threading.Thread(target=correr, daemon=True, name=f"fabrica-temporada-{sid}")
    with _candado:
        for fid in fids:
            _trabajos[fid] = hilo
    hilo.start()
    return {"saga": sid, "nombre": nombre, "despues": despues, "videos": [_leer(f) for f in fids]}


# ------------------------------------------------------------------ moldes
# Las opciones de un video que funciono (estilo, formato, duracion, efectos, receta...) guardadas con un nombre:
# al usarlo se rellena todo y solo se cambia el tema, la musica o la voz.
RUTA_MOLDES = almacen.raiz("fabrica_moldes.json")
MOLDE_FUERA = ("tema", "continua", "episodio", "rumbo")   # lo que es de cada video, no del molde


def moldes():
    return almacen.leer_json(RUTA_MOLDES, []) or []


def guardar_molde(nombre, opciones=None, desde=None):
    nombre = str(nombre or "").strip()[:60]
    if not nombre:
        raise ValueError("ponle un nombre al molde")
    o = _opciones(_leer(desde)["opciones"] if desde else opciones)
    if o["voz"].startswith((etapa_voz.PROPIA, NARRADA)):   # la grabacion era de aquel video
        o["voz"] = etapa_voz.DEFECTOS["voz"]
    molde = {"id": uuid.uuid4().hex[:12], "nombre": nombre, "creado": time.time(),
             "opciones": {k: v for k, v in o.items() if k not in MOLDE_FUERA}}
    with _candado:
        lista = [m for m in moldes() if m["nombre"].lower() != nombre.lower()]   # mismo nombre: se reemplaza
        almacen.escribir_json(RUTA_MOLDES, [molde, *lista])
    return molde


def borrar_molde(mid):
    with _candado:
        almacen.escribir_json(RUTA_MOLDES, [m for m in moldes() if m["id"] != mid])
    return {"ok": True}


SAGA_MAX = 6   # episodios anteriores que ve Claude (el ultimo entero, los demas resumidos)


def _saga(o):
    """Lo que Claude necesita para seguir la historia: los episodios anteriores (del mas viejo al ultimo) y, en una
    temporada, lo que el plan dice que pasa en este."""
    rumbo = (f"Lo que pasa en ESTE episodio (plan de la temporada, cuentalo con detalle): {o['rumbo']}\n"
             if o.get("rumbo") else "")
    if not o.get("continua"):
        return (f"SAGA: este video es el EPISODIO {o['episodio']} de una historia por entregas. " + rumbo
                + "Presenta al protagonista y su mundo con claridad y cierra dejando intriga para el siguiente.\n\n"
                if rumbo else "")
    partes, ultimo = _anteriores(o["continua"], con_guion=True)
    prota = next((e.get("protagonista") for e in ultimo.get("escenas") or [] if e.get("tipo") == "portada" and e.get("protagonista")), None)
    return (
        f"SAGA: este video es el EPISODIO {o['episodio']} de una historia por entregas. Lo que ya se conto:\n"
        + "\n".join(partes) + "\n" + rumbo +
        "Sigue la historia JUSTO donde termino el ultimo episodio: el mismo protagonista, el mismo mundo y sus reglas, "
        "y lo que ya paso cuenta (no lo repitas ni lo contradigas). Si los titulos llevan numeracion (Dia 1, Parte 1, "
        "Regla #3...), sigue con la siguiente; si no, la portada dice el episodio. Abre con una frase que recuerde donde "
        "nos quedamos y cierra dejando intriga para el siguiente episodio. Mismo tono, mismo tipo de gancho, mismo ritmo.\n"
        + (f"La portada lleva el mismo protagonista: {json.dumps(prota, ensure_ascii=False)}.\n" if prota else "")
        + "\n")


def _anteriores(fid, con_guion=False):
    """Los episodios hasta fid (incluido), del mas viejo al ultimo: el ultimo entero, los demas resumidos."""
    cadena = []
    while fid and len(cadena) < SAGA_MAX:
        try:
            s = _leer(fid)
        except FileNotFoundError:
            break
        g = almacen.leer_json(_dir(fid, "guion.json")) or {}
        cadena.append((s, g))
        fid = s["opciones"].get("continua")
    cadena.reverse()
    partes = []
    for k, (s, g) in enumerate(cadena):
        texto = " ".join(str(e.get("texto") or "") for e in g.get("escenas") or [])
        if k < len(cadena) - 1:
            texto = texto[:400] + ("…" if len(texto) > 400 else "")
        partes.append(f"- Episodio {s['opciones'].get('episodio') or 1}: «{g.get('titulo') or s['titulo']}»\n  {texto}")
    ultimo = cadena[-1][1] if cadena else {}
    return (partes, ultimo) if con_guion else partes


LOTE_MAX = 30


def lote(temas, opciones):
    """Varios videos con las mismas opciones: temas = ["tema", ...] o [{"tema", "estilo"?, "nicho"?...}, ...].
    Quedan todos en cola y se hacen de uno en uno (Claude, la voz y Chrome no se pisan); si uno falla, sigue el siguiente."""
    filas = [t if isinstance(t, dict) else {"tema": t} for t in (temas or []) if t]
    filas = [f for f in filas if str(f.get("tema") or "").strip()]
    if not filas:
        raise ValueError("escribe al menos un tema")
    if len(filas) > LOTE_MAX:
        raise ValueError(f"como mucho {LOTE_MAX} videos por lote")
    todas = [_opciones({**(opciones or {}), **f}) for f in filas]
    if any(_propia(o) for o in todas):
        raise ValueError("un lote no puede usar una grabacion propia (es de un solo video)")
    lid = uuid.uuid4().hex[:8]
    fids = []
    for n, o in enumerate(todas, 1):
        fid = uuid.uuid4().hex[:12]
        os.makedirs(_dir(fid), exist_ok=True)
        almacen.escribir_json(_dir(fid, "sesion.json"), {
            "id": fid, "titulo": o["tema"][:120], "opciones": o, "creado": time.time() + n * 0.001, "actualizado": time.time(),
            "estado": "en cola", "progreso": 0, "mensaje": f"en cola: lote de {len(todas)} ({n} de {len(todas)})",
            "error": None, "lote": lid})
        fids.append(fid)
        _usar_idea(o)

    def correr():
        for fid in fids:
            try:
                _producir(fid, "guion")
            except Exception as e:  # noqa: BLE001 -- se ve en su tarjeta; el lote sigue
                logger.exception(f"fabrica {fid} (lote {lid})")
                _guardar(fid, estado="error", error=str(e)[:500], mensaje="")

    hilo = threading.Thread(target=correr, daemon=True, name=f"fabrica-lote-{lid}")
    with _candado:
        for fid in fids:
            _trabajos[fid] = hilo
    hilo.start()
    return {"lote": lid, "videos": [_leer(f) for f in fids]}


def _familia(o):
    """De que familia salen los dibujos: la que se eligio en "visual" (madera = la base, sin familia) o la del estilo."""
    v = o.get("visual") or ""
    if v == "madera":
        return None
    return v if v in biblioteca.FAMILIAS else ESTILOS.get(o["estilo"], {}).get("familia")


VERSIONES_MAX = 14   # dibujos que un video puede pasar a otra familia (cada uno ~45 s en Flow)


def _versiones(fid, guion):
    """Con un aspecto elegido (stickman, grabado...), los dibujos del guion que aun no lo tienen se generan en ese
    aspecto con Nano Banana (solo local) y quedan para los siguientes videos. Sin Flow se usan los que haya."""
    o = _leer(fid)["opciones"]
    familia = _familia(o)
    if not familia or not o.get("visual") or not flow_gen.habilitado():
        return
    usados = []
    for e in guion["escenas"]:
        if e["tipo"] == "portada" and e.get("protagonista"):
            usados.append(("pegatinas", e["protagonista"]))
        if e["tipo"] == "protagonista" and e.get("id"):
            usados.append(("pegatinas", e["id"]))
        if e["tipo"] == "ilustracion" and e.get("imagen"):
            usados.append(("ilustraciones", e["imagen"]))
        if e["tipo"] == "mapa":
            usados += [("pegatinas", p["id"]) for p in e.get("pegatinas") or []]
            if (e.get("ruta") or {}).get("pegatina"):
                usados.append(("pegatinas", e["ruta"]["pegatina"]))
        for c in ("barras", "items", "lados", "hitos"):
            usados += [("pegatinas", x["pegatina"]) for x in e.get(c) or [] if x.get("pegatina")]
    faltan = [u for u in dict.fromkeys(usados) if not biblioteca.tiene_version(u[0], u[1], familia)][:VERSIONES_MAX]
    nombre = biblioteca.NOMBRES_FAMILIA.get(familia, familia).lower()
    for n, (tipo, clave) in enumerate(faltan):
        _guardar(fid, progreso=9 + round(5 * n / max(1, len(faltan))),
                 mensaje=f"Nano Banana pasa los dibujos a {nombre} ({n + 1} de {len(faltan)}): {clave}")
        try:
            biblioteca.version_familia(tipo, clave, familia)
        except flow_gen.NoHabilitado:
            return
        except Exception as e:  # noqa: BLE001 -- sin esa version se usa la que haya
            logger.warning(f"fabrica {fid}: no se pudo pasar {clave} a {familia}: {e}")
            if "sesion" in str(e):
                return   # sin sesion en Flow fallarian todos


def _usar_idea(o):
    """El tema sale del banco de ideas si venia de ahi."""
    if o["tema"] and any(i["tema"].strip() == o["tema"] for i in ideas(o["nicho"])):
        quitar_idea(o["nicho"], o["tema"])


NARRADA = "narrada:"   # grabacion propia leyendo el guion ya escrito (al reves que "propia:")


def _propia(o):
    return str(o.get("voz") or "").startswith(etapa_voz.PROPIA)


def _audio_subido(voz):
    nombre = voz.split(":", 1)[1] if ":" in voz else ""
    ruta = os.path.join(DIR_AUDIOS, nombre)
    if not nombre or os.path.basename(nombre) != nombre or not os.path.isfile(ruta):
        raise FileNotFoundError("no esta la grabacion subida: vuelve a subirla")
    return ruta


def subir_audio(datos, nombre_archivo):
    """Guarda una narracion grabada (para que el guion se adapte a ella) y dice como pedirla: voz = "propia:<archivo>"."""
    ext = os.path.splitext(nombre_archivo or "")[1].lower()
    if ext not in (".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".webm", ".mp4"):
        raise ValueError("sube un audio (mp3, wav, m4a, ogg...)")
    os.makedirs(DIR_AUDIOS, exist_ok=True)
    nombre = hashlib.sha1(datos).hexdigest()[:16] + ext
    ruta = os.path.join(DIR_AUDIOS, nombre)
    if not os.path.isfile(ruta):
        with open(ruta, "wb") as f:
            f.write(datos)
    duracion = float(medios.sondear(ruta).get("duracion") or 0)
    if duracion <= 0:
        os.remove(ruta)
        raise ValueError("no se pudo leer el audio")
    if duracion > 600:
        raise ValueError("la grabacion es muy larga: hasta 10 minutos")
    return {"voz": etapa_voz.PROPIA + nombre, "duracion": round(duracion, 1)}


def rehacer(fid, desde="guion", opciones=None):
    """Vuelve a hacer el video desde una etapa (guion, voz o render), con opciones nuevas si se dan
    (otro estilo o formatos solo necesitan render; otra voz, desde voz)."""
    s = _leer(fid)
    if desde not in ("guion", "voz", "render"):
        raise ValueError("desde: guion, voz o render")
    if desde != "guion" and not os.path.isfile(_dir(fid, "guion.json")):
        desde = "guion"
    if desde == "render" and not os.path.isfile(_dir(fid, "voz", "palabras.json")):
        desde = "voz"
    o = _opciones(opciones, s["opciones"])
    if _propia(o) and desde == "guion" and not os.path.isfile(_dir(fid, "voz", "palabras.json")):
        desde = "voz"   # con grabacion el guion sale de la transcripcion
    _guardar(fid, opciones=o, estado="en cola", progreso=0, mensaje="en cola", error=None)
    _lanzar(fid, _producir, fid, desde)
    return _leer(fid)


def guardar_guion(fid, guion):
    """El guion editado a mano: se valida y se rehace desde la voz."""
    s = _leer(fid)
    guion = _validar(guion, s["opciones"]["nicho"], None, s["opciones"].get("banco"))
    if s.get("estado") == "revision":   # aun no hay voz: se guarda y sigue esperando a Montar
        almacen.escribir_json(_dir(fid, "guion.json"), guion)
        return _leer(fid)
    if _propia(s["opciones"]):
        # la voz ya esta grabada: se corrigen palabras que Whisper oyo mal, se unen o separan ("delitoral" ->
        # "del litoral") o se mueve el corte entre escenas; los tiempos se reparten sobre lo grabado
        voz = almacen.leer_json(_dir(fid, "voz", "palabras.json"))
        nuevas = [w for e in guion["escenas"] for w in e["texto"].split()]
        voz["palabras"] = _realinear(voz["palabras"], nuevas)
        almacen.escribir_json(_dir(fid, "voz", "palabras.json"), voz)
        almacen.escribir_json(_dir(fid, "guion.json"), guion)
        return rehacer(fid, "render")
    almacen.escribir_json(_dir(fid, "guion.json"), guion)
    return rehacer(fid, "voz")


def _realinear(viejas, nuevas):
    """Tiempos para el texto corregido de una grabacion: las palabras que siguen igual conservan su segundo y cada
    trozo cambiado ocupa el tramo de lo que sustituye, repartido segun el largo de cada palabra. Si casi nada
    coincide, el texto ya no es lo grabado."""
    sm = difflib.SequenceMatcher(None, [_norm(w[2]) for w in viejas], [_norm(w) for w in nuevas], autojunk=False)
    if sm.ratio() < 0.6:
        raise ValueError("el texto ya no se parece a la grabacion: corrige palabras, no cambies lo que se dice "
                         "(para eso, graba de nuevo)")
    salida = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            salida += [[viejas[i][0], viejas[i][1], nuevas[j]] for i, j in zip(range(i1, i2), range(j1, j2))]
        elif j2 > j1:   # sustituye, une, separa o anade
            if i2 > i1:
                a, b = viejas[i1][0], viejas[i2 - 1][1]
            else:       # anadida entre dos palabras: el hueco que haya (o comparte el final de la anterior)
                a = salida[-1][1] if salida else (viejas[0][0] if viejas else 0.0)
                b = viejas[i1][0] if i1 < len(viejas) else a + 0.3
                if b - a < 0.15 and salida:
                    a = (salida[-1][0] + salida[-1][1]) / 2
                    salida[-1][1] = a
            pesos = [max(1, len(w)) for w in nuevas[j1:j2]]
            t = a
            for w, p in zip(nuevas[j1:j2], pesos):
                fin = t + (b - a) * p / sum(pesos)
                salida.append([round(t, 3), round(fin, 3), w])
                t = fin
    return salida


def _lanzar(fid, fn, *args):
    with _candado:
        if fid in _trabajos and _trabajos[fid].is_alive():
            raise RuntimeError("ya esta trabajando: espera a que termine")

        def correr():
            try:
                fn(*args)
            except Exception as e:  # noqa: BLE001 -- se ve en la interfaz
                logger.exception(f"fabrica {fid}")
                _guardar(fid, estado="error", error=str(e)[:500], mensaje="")
        hilo = threading.Thread(target=correr, daemon=True, name=f"fabrica-{fid}")
        _trabajos[fid] = hilo
        hilo.start()


def _producir(fid, desde):
    # con una grabacion subida primero se escucha (Whisper) y despues Claude parte ESE texto en escenas
    etapas = ["voz", "guion", "render"] if _propia(_leer(fid)["opciones"]) else ["guion", "voz", "render"]
    for etapa in etapas[etapas.index(desde):]:
        {"guion": _guion, "voz": _voz, "render": _render_y_montar}[etapa](fid)
        if etapa == "guion" and _leer(fid)["opciones"].get("revisar"):
            _guardar(fid, estado="revision", progreso=12,
                     mensaje="guion e imagenes listos: sube los clips, tu voz o elige la musica y dale a Montar")
            return
    _guardar(fid, estado="listo", progreso=100, mensaje="video listo")


def montar(fid, opciones=None):
    """Sigue un video parado en revision: voz (la elegida o tu grabacion del guion), dibujos y montaje."""
    if _leer(fid).get("estado") != "revision":
        raise ValueError("este video no esta esperando: usa Rehacer")
    return rehacer(fid, "voz", opciones)


# ------------------------------------------------------------------ 1. guion

def _paises():
    ruta = os.path.join(DIR_FABRICA, "datos", "paises.json")
    if not hasattr(_paises, "datos"):
        with open(ruta, encoding="utf-8") as f:
            _paises.datos = json.load(f)
    return _paises.datos


def _rios():
    if not hasattr(_rios, "datos"):
        with open(os.path.join(DIR_FABRICA, "datos", "rios.json"), encoding="utf-8") as f:
            _rios.datos = json.load(f)
    return _rios.datos


def _rio(nombre):
    """Clave de rios.json para un nombre ("Nile", "White Nile", "Nilo Blanco"), o None."""
    clave = biblioteca.clave_de(nombre)
    rios = _rios()
    if clave in rios:
        return clave
    return next((k for k, r in rios.items() if clave in {biblioteca.clave_de(n) for n in r["nombres"]}), None)


def _clave_tema(texto):
    """Palabras con contenido de un tema (sin tildes ni palabras vacias) para comparar temas entre si."""
    vacias = {"por", "que", "como", "cual", "los", "las", "del", "una", "uno", "con", "sin", "para", "mas", "muy", "este",
              "esta", "the", "and", "why", "how", "what", "nunca", "siempre", "tiene", "tienen", "hay", "fue", "son", "es"}
    plano = "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")
    return {w for w in re.findall(r"[a-z0-9]+", plano) if len(w) > 2 and w not in vacias}


def _hechos(nicho, salvo=None, cuantos=25):
    """Titulos (o temas) de los ultimos videos del nicho: Claude los ve para no repetirse."""
    filas = [s for s in listar() if s["id"] != salvo and s.get("opciones", {}).get("nicho") == nicho and s.get("estado") != "error"]
    return [_txt(s.get("titulo") or s["opciones"].get("tema"), 120) for s in filas[:cuantos]]


def parecido(tema, nicho=None):
    """El video ya hecho mas parecido a un tema (para avisar antes de repetir) o None."""
    clave = _clave_tema(tema)
    if len(clave) < 2:
        return None
    mejor, valor = None, 0.0
    for s in listar():
        if nicho and s.get("opciones", {}).get("nicho") != nicho:
            continue
        otra = _clave_tema(f"{s.get('titulo', '')} {s.get('opciones', {}).get('tema', '')}")
        if otra:
            v = len(clave & otra) / len(clave)
            if v > valor:
                mejor, valor = s, v
    return {"id": mejor["id"], "titulo": mejor["titulo"], "parecido": round(valor, 2)} if mejor and valor >= 0.6 else None


# Banco de temas: ideas que Claude propone por nicho (sin repetir lo hecho); al usar una sale del banco.
IDEAS = almacen.raiz("fabrica_ideas.json")


def ideas(nicho):
    return (almacen.leer_json(IDEAS, {}) or {}).get(nicho, [])


def sugerir_temas(nicho, serie="", cuantos=10):
    if nicho not in NICHOS:
        raise ValueError("nicho no valido")
    s = SERIES.get(serie or "")
    banco = ideas(nicho)
    ya = _hechos(nicho, cuantos=60) + [i["tema"] for i in banco]
    prompt = (
        f"Eres el productor de un canal de videos cortos. Nicho: {NICHOS[nicho]['nombre']} "
        f"({NICHOS[nicho]['descripcion']}).\n" + (f"Formato de serie: {s['nombre']} ({s['descripcion']}).\n" if s else "")
        + f"Propon {cuantos} temas NUEVOS con potencial viral: concretos (con nombre propio, lugar o cifra), que despierten "
        "una pregunta, y que se puedan contar con datos reales en menos de un minuto. Variados entre si.\n"
        + ("No repitas ni se parezcan a estos (ya hechos o ya en la lista):\n" + "\n".join(f"- {t}" for t in ya) + "\n" if ya else "")
        + 'Responde SOLO con JSON: [{"tema": "el tema en una frase", "gancho": "la primera frase del video, maximo 12 palabras"}]')
    crudo = claude_cli.extraer_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=180))
    nuevas = [{"tema": _txt(x.get("tema"), 200), "gancho": _txt(x.get("gancho"), 120), "serie": serie or "", "creado": time.time()}
              for x in (crudo if isinstance(crudo, list) else []) if isinstance(x, dict) and _txt(x.get("tema"))]
    return al_banco(nicho, nuevas, ya)


def al_banco(nicho, nuevas, ya=()):
    """Anade ideas al banco del nicho (arriba), sin las que repiten un tema ya hecho o ya en el banco."""
    vistas = [_clave_tema(t) for t in ya]
    limpias = []
    for x in nuevas:
        clave = _clave_tema(x["tema"])
        if clave and not any(clave == v for v in vistas):
            limpias.append(x)
            vistas.append(clave)
    with _candado:
        todo = almacen.leer_json(IDEAS, {}) or {}
        todo[nicho] = limpias + todo.get(nicho, [])
        almacen.escribir_json(IDEAS, todo)
    return todo[nicho]


def quitar_idea(nicho, tema):
    with _candado:
        todo = almacen.leer_json(IDEAS, {}) or {}
        todo[nicho] = [i for i in todo.get(nicho, []) if i["tema"].strip() != str(tema or "").strip()]
        almacen.escribir_json(IDEAS, todo)
        return todo[nicho]


LARGO_S = 120         # desde aqui el guion se escribe por capitulos (videos para YouTube)
CAPITULO_S = 50       # segundos de narracion por capitulo (una llamada a Claude cada uno)


def _nuevas_max(o):
    """Dibujos nuevos que puede pedir un video: pocos en mapas (se reusan pegatinas de sitios); fuera de mapas, mas,
    y en los largos uno cada ~10 s (con tope: cada uno son ~45 s en Flow)."""
    estilo = ESTILOS.get(o.get("estilo")) or {}
    if estilo.get("nuevas") and o["duracion"] <= LARGO_S:
        return estilo["nuevas"]
    if o["nicho"] == "mapas":
        return NUEVOS_MAX if o["duracion"] <= LARGO_S else min(12, o["duracion"] // 30)
    return NUEVOS_MAX_UNICOS if o["duracion"] <= LARGO_S else min(40, o["duracion"] // 10)


def _guion_largo(fid, o, cabeza, contexto, mensaje_txt):
    """Un video largo: primero el esquema (gancho, mensaje, capitulos) y luego cada capitulo por separado sabiendo lo
    ya contado (un solo JSON de 8 minutos se queda corto o se corta). Devuelve el guion en crudo, como uno corto."""
    n = max(2, round(o["duracion"] / CAPITULO_S))
    _guardar(fid, mensaje=f"Claude piensa el esquema ({n} capitulos)")
    esquema = _objeto_json(claude_cli.ejecutar(
        cabeza + f"Tema: {o['tema']}\nIdioma: {o['idioma']}.\nDuracion: unos {o['duracion'] // 60} minutos.\n\n" + mensaje_txt
        + f"Haz el ESQUEMA del video en {n} capitulos seguidos (el primero es la introduccion con el gancho, unos 30 s; "
        "el ultimo cierra respondiendo al gancho). Cada capitulo con su idea, 3-5 puntos concretos (datos reales con "
        "nombres, fechas y cifras) y un gancho final que obligue a seguir viendo. Sin repetir puntos entre capitulos.\n"
        'Responde SOLO con JSON: {"mensaje": "...", "titulo": "titulo para YouTube", "descripcion": "3-4 frases", '
        '"colores": {"rojo": "que significa", ...}, "capitulos": [{"titulo": "titulo corto", "puntos": ["..."], '
        '"intriga": "con que se queda el espectador para seguir"}]}',
        modelo="sonnet", esfuerzo="low", tiempo_max_s=300))
    capitulos = [c for c in esquema.get("capitulos") or [] if isinstance(c, dict) and _txt(c.get("titulo"))][:12]
    if len(capitulos) < 2:
        raise RuntimeError("Claude no devolvio el esquema del video largo (prueba otra vez)")
    por_cap = o["duracion"] / len(capitulos)
    resumen = "\n".join(f"{k + 1}. {c['titulo']}: " + "; ".join(map(str, c.get("puntos") or [])) for k, c in enumerate(capitulos))
    escenas, indicador = [], None
    for k, c in enumerate(capitulos):
        _guardar(fid, progreso=3 + round(6 * k / len(capitulos)),
                 mensaje=f"Claude escribe el capitulo {k + 1} de {len(capitulos)}: {_txt(c['titulo'], 60)}")
        segundos = 30 if k == 0 else por_cap
        primera = ("Es la INTRODUCCION: la primera escena es 'portada' con el gancho (reglas de la portada)."
                   if k == 0 else
                   f"NO hay portada en este capitulo: empieza con una escena que presente '{c['titulo']}' (con un 'rotulo' o "
                   "un 'golpe' con el titulo del capitulo) y recoja la intriga del capitulo anterior.")
        respuesta = claude_cli.ejecutar(
            cabeza + f"Tema del video: {o['tema']}\nIdioma de la narracion y los textos: {o['idioma']}.\n"
            f"Mensaje del video: {esquema.get('mensaje', '')}\nColores (un color = un significado): "
            f"{json.dumps(esquema.get('colores') or {}, ensure_ascii=False)}\n\nEsquema completo:\n{resumen}\n\n"
            f"Escribe SOLO el capitulo {k + 1} de {len(capitulos)}: '{c['titulo']}' (puntos: {'; '.join(map(str, c.get('puntos') or []))}; "
            f"termina con esta intriga: {c.get('intriga', '')}). Unos {round(segundos)} s: MINIMO {round(segundos * 2.3)} "
            f"palabras de narracion, en {max(3, round(segundos / 6))} escenas de 14-20 palabras. Cuenta las palabras antes "
            f"de responder: si te quedas corto, anade escenas con mas datos (no relleno). {primera} No repitas nada de los "
            "otros capitulos.\n\n" + contexto
            + ('Responde SOLO con JSON: {"escenas": [{"tipo": "...", "texto": "...", ...campos de su tipo}]'
               + (', "indicador"?: {"nombre", "antes"?, "despues"?}' if k == 0 else "") + "}"),
            modelo="sonnet", esfuerzo="low", tiempo_max_s=300)
        parte = _objeto_json(respuesta)
        nuevas = [e for e in parte.get("escenas") or [] if isinstance(e, dict)]
        if k and nuevas and nuevas[0].get("tipo") == "portada":
            nuevas = nuevas[1:]   # solo la introduccion lleva portada
        if nuevas:
            nuevas[0]["capitulo"] = _txt(c["titulo"], 80)
        escenas += nuevas
        indicador = indicador or parte.get("indicador")
    return {**{k: esquema.get(k) for k in ("mensaje", "titulo", "descripcion", "colores")},
            "indicador": indicador, "escenas": escenas}


def _guion(fid):
    o = _leer(fid)["opciones"]
    nicho = NICHOS[o["nicho"]]
    _guardar(fid, estado="guion", progreso=3, mensaje="Claude escribe el guion y las escenas")
    palabras = int(o["duracion"] * 2.2)  # Alvaro dice ~2,15 palabras/s
    estilo = ESTILOS.get(o.get("estilo")) or {}
    permitidas = estilo.get("escenas") or nicho["escenas"]
    catalogo_txt = "\n".join(f'- "{t}": {ESCENAS[t]["descripcion"]} Campos: {ESCENAS[t]["campos"]}' for t in permitidas)
    dibujos = biblioteca.para_claude(o["nicho"])
    grabada = almacen.leer_json(_dir(fid, "voz", "palabras.json")) if _propia(o) else None
    if grabada:
        oido = " ".join(w[2] for w in grabada["palabras"])
        encargo = (
            (f"Tema: {o['tema']}\n" if o["tema"] else "")
            + f"Idioma de los textos en pantalla: {o['idioma']}.\n"
            f"La narracion YA ESTA GRABADA ({grabada['duracion']:.0f} s). Este es su texto exacto:\n<<<\n{oido}\n>>>\n"
            f"Partelo en escenas seguidas (unas {max(3, round(grabada['duracion'] / 6))}, de 3-8 s): el 'texto' de cada escena "
            "es un trozo COPIADO TAL CUAL, sin cambiar, quitar ni anadir ninguna palabra, y entre todas cubren el texto entero "
            "en orden. La primera escena ('portada') lleva el comienzo del texto. Los rotulos y cifras salen de lo que dice. "
            "Las reglas sobre como escribir la narracion no aplican: ya esta escrita.\n\n")
    else:
        encargo = (
            f"Tema: {o['tema']}\nIdioma de la narracion y los textos: {o['idioma']}.\n"
            f"Duracion: unos {o['duracion']} s, o sea unas {palabras} palabras de narracion en total "
            f"(unas {max(4, round(palabras / _media(estilo.get('palabras', '12-20'))))} escenas de {estilo.get('palabras', '12-20')} "
            "palabras). Cuenta las palabras antes de responder: "
            "si te quedas corto, añade escenas con mas datos; no rellenes.\n\n")
    serie = SERIES.get(o.get("serie") or "")
    hechos = _hechos(o["nicho"], fid)
    # fuera de mapas cada escena lleva su propia imagen (si se pueden hacer: Flow en este PC)
    unicos = o["nicho"] != "mapas" and o["nuevos"] and flow_gen.habilitado()
    largo = not grabada and o["duracion"] > LARGO_S
    nuevas_max = _nuevas_max(o)
    cabeza = (
        (f"Eres guionista y director de videos largos para YouTube (se ven hasta el final si cada minuto deja una "
         f"intriga). {nicho['guia']}\n\n" if largo else f"Eres guionista y director de videos cortos para redes. {nicho['guia']}\n\n")
        + (f"{serie['guia']}\n\n" if serie else "")
        + (f"{estilo['guia']}\n\n" if estilo.get("guia") else "")
        + (clonar.para_guion(o["receta"]) if o.get("receta") else "")
        + _saga(o)
    )
    contexto = (
        (("Videos que YA hicimos en este canal (no repitas su gancho, su enfoque ni sus datos principales; si el tema "
          "se parece, busca otro angulo):\n" + "\n".join(f"- {t}" for t in hechos) + "\n\n") if hechos else "")
        + f"Escenas disponibles:\n{catalogo_txt}\n\n"
        "Indicador fijo (opcional, solo si el video gira alrededor de UNA cifra que cambia: km de costa perdidos, deuda, "
        "poblacion, anos que pasan...): en la raiz \"indicador\": {\"nombre\": \"Costa de Bolivia\", \"antes\"?: \"$\", "
        "\"despues\"?: \" km\"} y en las escenas donde cambia \"indicador\": {\"valor\": 400, \"palabra\": \"...\"}. Se queda "
        "visible en una esquina el resto del video y cuenta hasta el nuevo valor al decir la palabra.\n\n"
        + f"Biblioteca de pegatinas (id y que es): {dibujos['pegatinas'] or '(vacia)'}\n"
        + ("IMAGENES UNICAS: en este video cada escena 'ilustracion' lleva su PROPIA imagen nueva: pon siempre "
           "\"nueva\" con la descripcion EN INGLES de exactamente ese momento (encuadre y accion distintos en cada una: "
           "primer plano, plano general, detalle, desde arriba...) e \"imagen\": \"\". Nunca dos ilustraciones iguales. "
           f"Usa ilustraciones para la mayoria de momentos (hasta {nuevas_max} en todo el video); 'protagonista' como "
           f"mucho {PROTA_MAX} veces, y para enseñar al protagonista en otra situacion, una ilustracion nueva de el.\n\n"
           if unicos else f"Biblioteca de ilustraciones (id y que es): {dibujos['ilustraciones'] or '(vacia)'}\n\n")
        + banco.para_guion(o.get("banco") or [], o.get("banco_modo"))
    )
    reglas = (
        "Reglas:\n"
        f"- El guion se parte en escenas seguidas; cada una con su 'texto' (lo que dice la voz en esa escena, "
        f"{'una frase' if estilo.get('segundos') == '2-3' else '1-3 frases'}, {estilo.get('segundos', '3-8')} s). "
        "La narracion completa es la union de los textos, en orden.\n"
        + "- La primera escena es 'portada' y su texto es el gancho: lo que decide si siguen mirando o pasan, asi que "
        "lo fuerte va en los 3 primeros segundos (las 6-7 primeras palabras). Abre una pregunta que solo se cierra "
        "al final: un dato que choca, algo que contradice lo que todos creen, o una pregunta concreta con nombre "
        "propio o cifra. Maximo 12 palabras. Prohibido empezar con saludos, 'hoy te cuento', 'en este video', "
        "'sabias que' o 'te has preguntado'. El titulo de la portada dice lo mismo en menos palabras.\n"
        "- Cada escena deja una pequena duda que la siguiente resuelve (por que, pero, y entonces); nada de relleno ni repeticiones.\n"
        "- 'palabra' = una palabra (o dos seguidas) que aparece TAL CUAL en el texto de ESA escena: ahi pasa la animacion.\n"
        f"- Colores: {', '.join(COLORES)}. Paises: codigo ISO de 3 letras (ESP, BOL, CHL, USA, GBR...).\n"
        "- Un color = un significado en TODO el video (decidelo en 'colores': p. ej. rojo = lo que se pierde, verde = "
        "lo que se gana, gris = lo que no importa ahora). Cada pais o cosa lleva siempre el mismo color, y dos bandos "
        "distintos nunca comparten color. Pocos colores (2-3) se entienden mejor que muchos.\n"
        "- Escribe los numeros con cifras (1879, 400) para que la voz y la pantalla coincidan.\n"
        "- Pinta un pais SOLO cuando se habla de ese pais. Un rio va en 'rios', una ciudad o un sitio en 'etiquetas' "
        "o 'circulo', una zona que no es un pais con 'etiquetas' y 'camara'.\n"
        "- Pegatinas e ilustraciones: pon siempre un id de la biblioteca y, si ninguno ES de verdad lo que se cuenta, "
        f"pide 'nueva' (maximo {nuevas_max} nuevas en todo el video; repite la misma descripcion para reusar un dibujo). "
        "El protagonista del tema (el animal, el objeto, la persona) tiene que verse: si no esta en la biblioteca, "
        "pidelo 'nuevo' en la portada y reusalo en el resto. Hazlo el hilo del video: lo que se cuenta LE PASA a el "
        "(escenas 'protagonista' donde cambia de estado con la historia: nace gris y se vuelve rosa, crece, se "
        "multiplica, desaparece) y sale de icono con su estado en listas y versus (gris frente a color). Nunca un dibujo de otra cosa (una granja para hablar "
        "de flamencos): mejor una ilustracion 'nueva' de la escena. 'nueva' describe SOLO lo que se ve ('a pink "
        "flamingo standing on one leg'), sin estilo de dibujo (nada de wooden toy, cartoon, sticker): el estilo lo pone "
        "el video. Como mucho 2 pegatinas y 3 banderas por escena.\n"
        "- Extras (opcional, en cualquier escena menos la portada, como mucho 2 por escena y en 1 de cada 3 escenas): "
        "\"extras\": [{\"tipo\": \"emoji\", \"emoji\": \"😱\", \"palabra\": \"...\"} (una reaccion que salta en una esquina: "
        "sorpresa, dinero, peligro, risa), {\"tipo\": \"sello\", \"texto\": \"FALSO\", \"palabra\"} (2-3 palabras que caen "
        "como un sello: FALSO, RECORD, PROHIBIDO, CONFIRMADO), {\"tipo\": \"flecha\", \"texto\"?: \"mira esto\", \"palabra\"} "
        "(senala lo que hay en el centro)}]. Refuerzan un momento fuerte; no los pongas por poner.\n"
        "- Datos reales y comprobados; nada inventado. Frases cortas y naturales para leer en voz alta. "
        "El final responde al gancho y deja el mensaje en una frase que se recuerde (sin pedir likes ni suscripciones).\n"
        + ("- CLIPS DE VIDEO: cada escena 'ilustracion' lleva ademas \"video_prompt\": prompt EN INGLES para un modelo de "
           "video (Seedance, Veo) de ese mismo momento: sujeto y accion, movimiento de camara (push in, orbit, handheld, "
           "tracking...), luz y ambiente, 5-8 s, sin texto ni subtitulos en la imagen. La imagen ('nueva') es el primer "
           "fotograma de ese clip.\n" if o.get("clips") else "")
    )
    mensaje_txt = ("Antes de escribir, decide el 'mensaje': UNA sola idea que el que lo vea se lleve, en una frase. Todo "
                   "el video sirve a esa idea; un dato que no la empuja, fuera (aunque sea curioso). Nada de 3 temas en un video.\n\n")
    if largo:
        crudo = _guion_largo(fid, o, cabeza, contexto + reglas, mensaje_txt)
    else:
        prompt = (
            cabeza + encargo + contexto + mensaje_txt + reglas +
            'Responde SOLO con JSON: {"mensaje": "la idea unica, una frase", '
            '"colores": {"rojo": "que significa", ...solo los que uses}, "titulo": "titulo para publicar", '
            '"descripcion": "2-3 frases para la descripcion", '
            '"escenas": [{"tipo": "portada", "texto": "...", ...campos de su tipo}]}'
        )
        crudo = _objeto_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=300))
        if not grabada:
            crudo = _ajustar_largo(fid, crudo, palabras, o["duracion"])
    if o["nuevos"] and flow_gen.habilitado():
        if o["nicho"] != "mapas":
            _unicos(fid, crudo)
        _dibujos_nuevos(fid, crudo)
    guion = _validar(crudo, o["nicho"], permitidas, o.get("banco"))
    if estilo.get("guia") and _txt(crudo.get("cabecera")):
        guion["cabecera"] = _txt(crudo["cabecera"], 40)
    if grabada:
        guion = _encajar(guion, grabada["palabras"])
    almacen.escribir_json(_dir(fid, "guion.json"), guion)
    _guardar(fid, titulo=guion["titulo"] or o["tema"][:120] or "Video", progreso=26 if grabada else 12,
             mensaje=f"guion listo: {len(guion['escenas'])} escenas")


LARGO_TOLERANCIA = 0.10   # fuera de +-10 % de las palabras pedidas se pide a Claude que corrija (una vez)


def _media(rango):
    """'8-14' -> 11 (palabras por escena)."""
    a, _, b = str(rango).partition("-")
    return (int(a) + int(b or a)) / 2


def _palabras_de(crudo):
    return sum(len(str(e.get("texto") or "").split()) for e in (crudo.get("escenas") or []) if isinstance(e, dict))


def _ajustar_largo(fid, crudo, objetivo, duracion):
    """Claude suele quedarse corto (~70 % de lo pedido): si el guion se aleja de la duracion, una sola llamada
    mas para alargarlo o recortarlo. Solo cuesta cuando hace falta."""
    n = _palabras_de(crudo)
    if not n or abs(n - objetivo) <= objetivo * LARGO_TOLERANCIA:
        return crudo
    falta = objetivo - n
    _guardar(fid, mensaje=f"ajustando el guion a {duracion} s ({n} de {objetivo} palabras)")
    orden = (f"Le FALTAN unas {falta} palabras: anade escenas nuevas (con datos reales que empujen el mensaje, del mismo "
             "formato y campos) y alarga textos cortos; no rellenes ni repitas." if falta > 0 else
             f"Le SOBRAN unas {-falta} palabras: quita lo menos importante y acorta textos, sin perder el gancho ni el final.")
    prompt = (
        f"Este guion de video tiene {n} palabras de narracion (la suma de los 'texto' de las escenas), pero debe durar "
        f"{duracion} s = unas {objetivo} palabras. {orden} Mantén la portada, el mensaje, los colores, el estilo y las "
        "mismas reglas de campos ('palabra' debe aparecer tal cual en el texto de su escena). Cuenta las palabras antes "
        f"de responder: el total debe quedar entre {round(objetivo * 0.95)} y {round(objetivo * 1.05)}.\n\n"
        "Responde SOLO con el JSON completo corregido, mismo formato:\n" + json.dumps(crudo, ensure_ascii=False))
    try:
        nuevo = _objeto_json(claude_cli.ejecutar(prompt, modelo="sonnet", esfuerzo="low", tiempo_max_s=300))
    except Exception as ex:   # si falla, se sigue con el primero
        logger.warning(f"fabrica {fid}: no se pudo ajustar el largo: {ex}")
        return crudo
    m = _palabras_de(nuevo)
    if not nuevo.get("escenas") or abs(m - objetivo) >= abs(n - objetivo):
        return crudo
    logger.info(f"fabrica {fid}: guion ajustado {n} -> {m} palabras (objetivo {objetivo})")
    return nuevo


def _encajar(guion, oidas):
    """Con una grabacion, el texto de cada escena pasa a ser EXACTAMENTE su trozo de lo que se oye (Claude puede
    haber cambiado alguna palabra o un numero): se busca donde empieza cada escena en la transcripcion."""
    oido = [_norm(w[2]) for w in oidas]
    suyas, de_escena = [], []
    for i, e in enumerate(guion["escenas"]):
        for w in e["texto"].split():
            suyas.append(_norm(w))
            de_escena.append(i)
    # donde cae cada palabra de Claude en la transcripcion (las que no casan, en la siguiente que si)
    donde = [None] * len(suyas)
    sm = difflib.SequenceMatcher(None, suyas, oido, autojunk=False)
    for b in sm.get_matching_blocks():
        for k in range(b.size):
            donde[b.a + k] = b.b + k
    for k in range(len(donde) - 2, -1, -1):
        if donde[k] is None:
            donde[k] = donde[k + 1]
    n = len(guion["escenas"])
    cortes = [0] + [None] * (n - 1)
    for k, i in enumerate(de_escena):
        if i and cortes[i] is None:
            cortes[i] = donde[k] if donde[k] is not None else len(oidas)
    for i in range(1, n):   # siempre hacia delante
        cortes[i] = max(cortes[i] if cortes[i] is not None else len(oidas), cortes[i - 1])
    escenas = []
    for i, e in enumerate(guion["escenas"]):
        trozo = [w[2] for w in oidas[cortes[i]:cortes[i + 1] if i + 1 < n else len(oidas)]]
        if trozo:   # una escena sin voz se quita: su dibujo no tendria tiempo
            escenas.append({**e, "texto": " ".join(trozo)})
    if len(escenas) < 2:
        raise RuntimeError("no se pudo repartir la grabacion en escenas (prueba otra vez)")
    return {**guion, "escenas": escenas}


def _dibujos_nuevos(fid, guion):
    """Las pegatinas e ilustraciones que Claude pidio 'nueva' se hacen con Nano Banana (Flow, solo local) y se
    guardan en la biblioteca propia, dibujadas en la familia del estilo del video. Si falla alguna se queda la de
    la biblioteca que Claude eligio."""
    familia = _familia(_leer(fid)["opciones"])
    pedidos = []
    for e in guion.get("escenas") or []:
        if not isinstance(e, dict):
            continue
        if e.get("tipo") == "ilustracion" and _txt(e.get("nueva")) and not _txt(e.get("clip")):
            pedidos.append(("ilustraciones", e, "imagen", "personaje"))
        for p in (e.get("pegatinas") or []) if e.get("tipo") == "mapa" else []:
            if isinstance(p, dict) and _txt(p.get("nueva")):
                pedidos.append(("pegatinas", p, "id", "objeto" if p.get("clase") == "objeto" else "personaje"))
        if e.get("tipo") == "portada" and _txt(e.get("nueva")):   # su imagen de fondo (Retro TV, Thriller)
            pedidos.append(("ilustraciones", e, "imagen", "personaje"))
        p = e.get("protagonista")
        if e.get("tipo") == "portada" and isinstance(p, dict) and _txt(p.get("nueva")):
            pedidos.append(("pegatinas", p, "id", "personaje"))
        # iconos de barras, lista, versus y linea de tiempo
        for c in ("barras", "items", "lados", "hitos"):
            for p in e.get(c) or [] if isinstance(e.get(c), list) else []:
                if isinstance(p, dict) and _txt(p.get("nueva")):
                    pedidos.append(("pegatinas", p, "pegatina", "objeto"))
    hechos, sin_flow = {}, False
    maximo = _nuevas_max(_leer(fid)["opciones"])
    # las ilustraciones primero: sin ellas la escena se pierde; una pegatina que falta tiene la de la biblioteca
    pedidos.sort(key=lambda p: p[0] != "ilustraciones")
    total = min(len(pedidos), maximo)
    for n, (tipo, donde, campo, clase) in enumerate(pedidos[:maximo]):
        que = _txt(donde["nueva"], 300)
        if sin_flow:   # sin sesion en Flow los demas tambien fallarian (~45 s cada uno)
            hechos.setdefault((tipo, que), None)
        if (tipo, que) not in hechos:
            _guardar(fid, progreso=5 + n * 2, mensaje=f"Nano Banana dibuja {'una ilustracion' if tipo == 'ilustraciones' else 'una pegatina'} "
                                                   f"nueva ({n + 1} de {total}): {que[:60]}")
            try:
                hechos[(tipo, que)] = biblioteca.crear(tipo, que, nombre=que[:32], clase=clase, familia=familia)["id"]
            except Exception as e:  # noqa: BLE001 -- sin el dibujo nuevo vale el de la biblioteca
                logger.warning(f"fabrica {fid}: no se pudo crear '{que}': {e}")
                hechos[(tipo, que)] = None
                sin_flow = "sesion" in str(e)
        if hechos[(tipo, que)]:
            donde[campo] = hechos[(tipo, que)]


def _recientes(fid, cuantos=RECIENTES):
    """Ilustraciones usadas en los ultimos videos (de cualquier nicho), para no repetirlas."""
    usadas = set()
    for s in [x for x in listar() if x["id"] != fid][:cuantos]:
        g = almacen.leer_json(_dir(s["id"], "guion.json")) or {}
        usadas |= {e.get("imagen") for e in g.get("escenas") or [] if e.get("tipo") == "ilustracion" and e.get("imagen")}
    return usadas


def _unicos(fid, guion):
    """Fuera de mapas, cada escena con su propia imagen: ninguna ilustracion repetida en el video ni sacada de los
    ultimos videos (se pide nueva) y el protagonista como mucho en PROTA_MAX escenas (las demas pasan a ser una
    ilustracion nueva de el haciendo lo que dice esa escena). Se hace sobre lo que devolvio Claude, antes de dibujar."""
    escenas = [e for e in guion.get("escenas") or [] if isinstance(e, dict)]
    portada = next((e for e in escenas if e.get("tipo") == "portada"), {})
    prota = portada.get("protagonista") if isinstance(portada.get("protagonista"), dict) else {}
    quien = _txt(prota.get("nueva"), 200) or biblioteca.descripcion("pegatinas", _txt(prota.get("id"), 40).lower()) or ""
    vistas, recientes, n_prota = set(), _recientes(fid), 0
    for e in escenas:
        if e.get("tipo") == "protagonista":
            n_prota += 1
            if n_prota <= PROTA_MAX:
                continue
            # una escena mas del protagonista: mejor una imagen nueva de el en ese momento
            e["tipo"] = "ilustracion"
            e["nueva"] = f"{quien}, {_txt(e.get('texto'), 200)}" if quien else _txt(e.get("texto"), 240)
            e.pop("imagen", None)
        if e.get("tipo") != "ilustracion" or _txt(e.get("clip")):   # con clip del banco no hace falta imagen
            continue
        imagen = _txt(e.get("imagen"), 40).lower()
        if not _txt(e.get("nueva")) and (not imagen or imagen in vistas or imagen in recientes):
            e["nueva"] = _txt(e.get("texto"), 240)   # lo que se cuenta en esa escena (Nano Banana entiende espanol)
        vistas.add(imagen)


def _objeto_json(texto):
    """El objeto {...} de la respuesta (claude_cli.extraer_json prefiere listas y se quedaria con 'escenas')."""
    bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, re.DOTALL)
    texto = (bloque.group(1) if bloque else texto).strip()
    i, j = texto.find("{"), texto.rfind("}")
    if i != -1 and j > i:
        try:
            return json.loads(texto[i:j + 1])
        except json.JSONDecodeError:
            pass
    lista = claude_cli.extraer_json(texto)
    return {"escenas": lista} if isinstance(lista, list) else lista


def _txt(x, largo=200):
    return str(x or "").strip()[:largo]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _validar(guion, nicho, permitidas=None, bancos=None):
    """Deja solo lo que el motor sabe pintar: tipos del nicho (o los permitidos), ISO que existen, colores conocidos."""
    if not isinstance(guion, dict) or not isinstance(guion.get("escenas"), list):
        raise RuntimeError("Claude no devolvio un guion con escenas (prueba otra vez)")
    paises = _paises()
    permitidas = permitidas or NICHOS[nicho]["escenas"]
    iso = lambda x: str(x or "").upper().strip() if str(x or "").upper().strip() in paises else None
    color = lambda x: x if x in COLORES or re.fullmatch(r"#[0-9a-fA-F]{6}", str(x or "")) else "acento"
    vista = lambda x: "satelite" if x == "satelite" else "mapa"

    def punto(d):
        """(lon, lat) de un dict con lon/lat o iso, o None."""
        if not isinstance(d, dict):
            return None
        lon, lat = _num(d.get("lon")), _num(d.get("lat"))
        if (lon is None or lat is None) and iso(d.get("iso")):
            lon, lat = paises[iso(d.get("iso"))]["c"]
        return (lon, lat) if lon is not None and lat is not None and -180 <= lon <= 180 and -85 <= lat <= 85 else None

    def dibujo(tipo, clave):
        clave = _txt(clave, 40).lower()
        return clave if biblioteca.ruta(tipo, clave) else None

    def icono(d):
        """El icono de un elemento de barras, lista, versus o linea de tiempo: pegatina o bandera (o nada)."""
        clave = dibujo("pegatinas", d.get("pegatina"))
        if clave:
            return {"pegatina": clave, **({"estado": d["estado"]} if d.get("estado") in ESTADOS_FIJOS else {})}
        pais = iso(d.get("iso"))
        return {"iso": pais} if pais and paises[pais].get("a2") else {}

    escenas, sobra, prota = [], "", None
    for e in guion["escenas"]:
        if not isinstance(e, dict) or not _txt(e.get("texto"), 600):
            continue
        texto = _txt(e["texto"], 600)
        if e.get("tipo") not in permitidas:
            # lo que no se sabe pintar no se pierde: su narracion pasa a la escena de antes
            if escenas:
                escenas[-1]["texto"] = (escenas[-1]["texto"] + " " + texto)[:900]
            else:
                sobra = (sobra + " " + texto).strip()
            continue
        x = {"tipo": e["tipo"], "texto": texto}
        if _txt(e.get("capitulo")):
            x["capitulo"] = _txt(e["capitulo"], 80)   # primera escena de un capitulo (videos largos)
        ind = e.get("indicador")
        valor = _num(str(ind.get("valor")).replace(",", ".")) if isinstance(ind, dict) else None
        if valor is not None:
            x["indicador"] = {"valor": valor, "palabra": _txt(ind.get("palabra"), 40)}
        if x["tipo"] == "portada":
            x.update(titulo=_txt(e.get("titulo"), 120) or x["texto"], antetitulo=_txt(e.get("antetitulo"), 40),
                     paises=[p for p in map(iso, e.get("paises") or []) if p], vista=vista(e.get("vista")),
                     protagonista=dibujo("pegatinas", (e.get("protagonista") or {}).get("id"))
                     if isinstance(e.get("protagonista"), dict) else None)
            prota = x["protagonista"]
            if e.get("imagen"):   # Retro TV / Thriller: la primera ilustracion de fondo
                x["imagen"] = dibujo("ilustraciones", e.get("imagen"))
            lugar = e.get("lugar") if isinstance(e.get("lugar"), dict) else {}
            lon, lat = _num(lugar.get("lon")), _num(lugar.get("lat"))
            if lon is not None and lat is not None and -180 <= lon <= 180 and -85 <= lat <= 85:
                x["lugar"] = {"lon": lon, "lat": lat, "zoom": min(11, max(0.3, _num(lugar.get("zoom")) or 3))}
        elif x["tipo"] == "protagonista":
            x["id"] = prota
            x["inicio"] = e.get("inicio") if e.get("inicio") in ESTADOS else None
            x["cambios"] = [{"estado": c["estado"], "palabra": _txt(c.get("palabra"), 40)}
                            for c in (e.get("cambios") or [])[:4] if isinstance(c, dict) and c.get("estado") in ESTADOS]
            g, r = e.get("golpe"), e.get("rotulo")
            x["golpe"] = {"texto": _txt(g.get("texto"), 30), "palabra": _txt(g.get("palabra"), 40)} if isinstance(g, dict) and _txt(g.get("texto")) else None
            x["rotulo"] = {"texto": _txt(r.get("texto"), 24), "palabra": _txt(r.get("palabra"), 40)} if isinstance(r, dict) and _txt(r.get("texto")) else None
            if not prota:
                e = {**e, "tipo": "_sin_protagonista"}
        elif x["tipo"] == "ilustracion":
            x["imagen"] = dibujo("ilustraciones", e.get("imagen"))
            if bancos and banco.resolver(bancos, e.get("clip")):
                x["clip"] = _txt(e["clip"], 12).replace(" ", "")   # clip del banco ("k-n") detras de los textos
            if _txt(e.get("video_prompt")):
                x["video_prompt"] = _txt(e["video_prompt"], 800)   # para hacer el clip aparte y subirlo
            g, r = e.get("golpe"), e.get("rotulo")
            x["golpe"] = {"texto": _txt(g.get("texto"), 30), "palabra": _txt(g.get("palabra"), 40)} if isinstance(g, dict) and _txt(g.get("texto")) else None
            x["rotulo"] = {"texto": _txt(r.get("texto"), 24), "palabra": _txt(r.get("palabra"), 40)} if isinstance(r, dict) and _txt(r.get("texto")) else None
            if not x["imagen"] and not x.get("clip"):
                e = {**e, "tipo": "_sin_imagen"}
        elif x["tipo"] == "mapa":
            x["paises"] = [{"iso": iso(p.get("iso")), "color": color(p.get("color")), "palabra": _txt(p.get("palabra"), 40),
                            "hasta": _txt(p.get("hasta"), 40)} for p in e.get("paises") or [] if isinstance(p, dict) and iso(p.get("iso"))]
            x["etiquetas"] = []
            for t in e.get("etiquetas") or []:
                if not isinstance(t, dict) or not _txt(t.get("texto")):
                    continue
                lon, lat = _num(t.get("lon")), _num(t.get("lat"))
                if (lon is None or lat is None) and iso(t.get("iso")):
                    lon, lat = paises[iso(t.get("iso"))]["c"]
                if lon is not None and lat is not None and -180 <= lon <= 180 and -85 <= lat <= 85:
                    x["etiquetas"].append({"texto": _txt(t["texto"], 30), "lon": lon, "lat": lat,
                                           "palabra": _txt(t.get("palabra"), 40), "punto": bool(t.get("punto"))})
            r = e.get("rotulo")
            x["rotulo"] = {"texto": _txt(r.get("texto"), 24), "palabra": _txt(r.get("palabra"), 40)} if isinstance(r, dict) and _txt(r.get("texto")) else None
            x["camara"] = []
            for c in e.get("camara") or []:
                if not isinstance(c, dict):
                    continue
                lugar = c.get("lugar") if isinstance(c.get("lugar"), dict) else None
                isos = [p for p in map(iso, c.get("paises") or []) if p]
                if isos:
                    x["camara"].append({"paises": isos, "palabra": _txt(c.get("palabra"), 40)})
                elif lugar and _num(lugar.get("lon")) is not None and _num(lugar.get("lat")) is not None:
                    x["camara"].append({"lugar": {"lon": _num(lugar["lon"]), "lat": _num(lugar["lat"]),
                                                  "zoom": min(11, max(0.3, _num(lugar.get("zoom")) or 3))},
                                        "palabra": _txt(c.get("palabra"), 40)})
            x["vista"] = vista(e.get("vista"))
            x["foco"] = bool(e.get("foco"))
            x["banderas"] = []
            for b in (e.get("banderas") or [])[:4]:
                if isinstance(b, dict) and iso(b.get("iso")) and paises[iso(b.get("iso"))].get("a2"):
                    lon, lat = punto(b)   # su lon/lat si la trae; si no, el centro del pais
                    x["banderas"].append({"iso": iso(b["iso"]), "lon": lon, "lat": lat, "palabra": _txt(b.get("palabra"), 40),
                                          "ojos": bool(b.get("ojos"))})
            x["pegatinas"] = []
            for p in (e.get("pegatinas") or [])[:3]:
                donde, clave = punto(p), dibujo("pegatinas", (p or {}).get("id")) if isinstance(p, dict) else None
                if donde and clave:
                    x["pegatinas"].append({"id": clave, "lon": donde[0], "lat": donde[1], "palabra": _txt(p.get("palabra"), 40)})
            x["rios"] = []
            for r in e.get("rios") or []:
                clave = _rio(r.get("nombre")) if isinstance(r, dict) else None
                if clave:
                    x["rios"].append({"clave": clave, "color": color(r.get("color") or "azul"), "palabra": _txt(r.get("palabra"), 40)})
            m = e.get("medida")
            x["medida"] = {"desde": punto(m.get("desde")), "hasta": punto(m.get("hasta")), "texto": _txt(m.get("texto"), 20),
                           "palabra": _txt(m.get("palabra"), 40)} if isinstance(m, dict) and _txt(m.get("texto")) \
                and punto(m.get("desde")) and punto(m.get("hasta")) else None
            r = e.get("ruta")
            x["ruta"] = {"desde": punto(r.get("desde")), "hasta": punto(r.get("hasta")), "palabra": _txt(r.get("palabra"), 40),
                         "pegatina": dibujo("pegatinas", r.get("pegatina"))} if isinstance(r, dict) \
                and punto(r.get("desde")) and punto(r.get("hasta")) else None
            c = e.get("circulo")
            x["circulo"] = {"lon": punto(c)[0], "lat": punto(c)[1], "palabra": _txt(c.get("palabra"), 40)} if punto(c) else None
            g = e.get("golpe")
            x["golpe"] = {"texto": _txt(g.get("texto"), 30), "palabra": _txt(g.get("palabra"), 40)} \
                if isinstance(g, dict) and _txt(g.get("texto")) and not x["rotulo"] else None
            if not any(x[k] for k in ("paises", "camara", "etiquetas", "banderas", "pegatinas", "rios", "medida", "ruta", "circulo")):
                e = {**e, "tipo": "_vacio"}  # un mapa sin nada que mirar
        elif x["tipo"] == "cifra":
            numero = re.sub(r"[^\d.,]", "", str(e.get("numero") or ""))
            despues = _txt(e.get("despues"), 12)
            if despues[:1].isalpha():
                despues = " " + despues  # "400 km", pero "40%"
            x.update(numero=numero, antes=_txt(e.get("antes"), 6), despues=despues,
                     etiqueta=_txt(e.get("etiqueta"), 80), contexto=_txt(e.get("contexto"), 100), palabra=_txt(e.get("palabra"), 40))
            if not numero:
                e = {**e, "tipo": "_sin_numero"}
        elif x["tipo"] == "barras":
            x["titulo"] = _txt(e.get("titulo"), 80)
            x["barras"] = []
            for b in (e.get("barras") or [])[:6]:
                valor = _num(str(b.get("valor")).replace(",", ".")) if isinstance(b, dict) else None
                if valor is not None and valor >= 0 and _txt(b.get("etiqueta")):
                    x["barras"].append({"etiqueta": _txt(b["etiqueta"], 40), "valor": valor, "texto": _txt(b.get("texto"), 16),
                                        "color": color(b.get("color")), "palabra": _txt(b.get("palabra"), 40), **icono(b)})
            if len(x["barras"]) < 2:
                e = {**e, "tipo": "_sin_barras"}
        elif x["tipo"] == "lista":
            x["titulo"], x["numerar"] = _txt(e.get("titulo"), 80), bool(e.get("numerar"))
            x["items"] = [{"texto": _txt(t["texto"], 60), "palabra": _txt(t.get("palabra"), 40), **icono(t)}
                          for t in (e.get("items") or [])[:5] if isinstance(t, dict) and _txt(t.get("texto"))]
            if len(x["items"]) < 2:
                e = {**e, "tipo": "_sin_items"}
        elif x["tipo"] == "versus":
            x["titulo"], x["palabra_vs"] = _txt(e.get("titulo"), 80), _txt(e.get("palabra_vs"), 40)
            por_defecto = iter(("azul", "rojo"))
            x["lados"] = [{"nombre": _txt(l["nombre"], 30), "dato": _txt(l.get("dato"), 70), "palabra": _txt(l.get("palabra"), 40),
                           "color": color(l.get("color") or next(por_defecto)), **icono(l)}
                          for l in (e.get("lados") or [])[:2] if isinstance(l, dict) and _txt(l.get("nombre"))]
            if len(x["lados"]) < 2:
                e = {**e, "tipo": "_sin_lados"}
        elif x["tipo"] == "captura":
            x["forma"] = e.get("forma") if e.get("forma") in FORMAS_CAPTURA else "tuit"
            x.update(nombre=_txt(e.get("nombre"), 40), usuario=_txt(e.get("usuario"), 30), contenido=_txt(e.get("contenido"), 160),
                     cifra=re.sub(r"[^\d]", "", str(e.get("cifra") or ""))[:10], palabra=_txt(e.get("palabra"), 40))
            x["mensajes"] = [{"texto": _txt(m["texto"], 120), "mio": bool(m.get("mio")), "palabra": _txt(m.get("palabra"), 40)}
                             for m in (e.get("mensajes") or [])[:5] if isinstance(m, dict) and _txt(m.get("texto"))]
            if x["forma"] in ("chat", "notificacion") and not x["mensajes"] and x["contenido"]:
                x["mensajes"] = [{"texto": x["contenido"], "mio": False, "palabra": x["palabra"]}]
            if not (x["mensajes"] if x["forma"] in ("chat", "notificacion") else x["contenido"]):
                e = {**e, "tipo": "_sin_contenido"}
        elif x["tipo"] == "linea_tiempo":
            x["titulo"] = _txt(e.get("titulo"), 80)
            x["hitos"] = [{"fecha": _txt(h["fecha"], 16), "texto": _txt(h.get("texto"), 60), "palabra": _txt(h.get("palabra") or h["fecha"], 40),
                           **icono(h)} for h in (e.get("hitos") or [])[:5] if isinstance(h, dict) and _txt(h.get("fecha"))]
            if len(x["hitos"]) < 2:
                e = {**e, "tipo": "_sin_hitos"}
        extras = [_extra(t) for t in (e.get("extras") or [])[:2] if isinstance(t, dict)] \
            if x["tipo"] != "portada" else []
        if any(extras):
            x["extras"] = [t for t in extras if t]
        if e["tipo"] != x["tipo"]:
            # no se puede pintar: su narracion pasa a la escena de antes (o a la siguiente si es la primera)
            if escenas:
                escenas[-1]["texto"] = (escenas[-1]["texto"] + " " + x["texto"])[:900]
            else:
                sobra = (sobra + " " + x["texto"]).strip()
            continue
        if sobra:
            x["texto"], sobra = (sobra + " " + x["texto"])[:900], ""
        escenas.append(x)
    if len(escenas) < 2:
        raise RuntimeError("el guion se quedo sin escenas validas (prueba otra vez o cambia el tema)")
    _colores_fijos(escenas)
    leyenda = guion.get("colores") if isinstance(guion.get("colores"), dict) else {}
    ind = guion.get("indicador")
    indicador = {"nombre": _txt(ind.get("nombre"), 30), "antes": _txt(ind.get("antes"), 4), "despues": _txt(ind.get("despues"), 10)} \
        if isinstance(ind, dict) and _txt(ind.get("nombre")) and any("indicador" in e for e in escenas) else None
    if indicador and indicador["despues"][:1].isalpha():
        indicador["despues"] = " " + indicador["despues"]   # "400 km", pero "40%"
    return {"titulo": _txt(guion.get("titulo"), 120), "descripcion": _txt(guion.get("descripcion"), 800),
            "mensaje": _txt(guion.get("mensaje"), 200), "escenas": escenas, "indicador": indicador,
            "colores": {c: _txt(s, 60) for c, s in leyenda.items() if c in COLORES and _txt(s)}}


def _extra(t):
    """Un extra encima de la escena (nucleo.js, extras) ya limpio, o None."""
    tipo, palabra = t.get("tipo"), _txt(t.get("palabra"), 40)
    if tipo == "emoji":
        emoji = str(t.get("emoji") or "").strip()
        # solo el emoji (nada de letras ni numeros): 1-8 caracteres por los que llevan modificadores
        if 0 < len(emoji) <= 8 and not any(ch.isalnum() for ch in emoji):
            return {"tipo": "emoji", "emoji": emoji, "palabra": palabra}
    elif tipo in ("sello", "flecha") and _txt(t.get("texto")):
        return {"tipo": tipo, "texto": _txt(t["texto"], 18 if tipo == "sello" else 26), "palabra": palabra}
    elif tipo == "flecha":
        return {"tipo": "flecha", "texto": "", "palabra": palabra}
    return None


def _colores_fijos(escenas):
    """Un color = un significado: cada pais, rio o cosa (barra, lado de un versus) lleva en todo el video el color
    con que salio la primera vez, asi el que mira no tiene que volver a aprender quien es quien."""
    fijo = {}

    def fijar(clave, cosa, defecto="acento"):
        if cosa.get("color", defecto) == defecto and clave not in fijo:
            return   # sin color propio no marca nada (lo que se pinta despues decide)
        cosa["color"] = fijo.setdefault(clave, cosa.get("color", defecto))

    for e in escenas:
        for p in e.get("paises") if e["tipo"] == "mapa" else []:
            fijar("iso:" + p["iso"], p)
        for r in e.get("rios") or []:
            fijar("rio:" + r["clave"], r, "azul")
        for b in e.get("barras") or []:
            fijar("iso:" + b["iso"] if b.get("iso") else "cosa:" + _norm(b["etiqueta"]), b)
        for l in e.get("lados") or []:
            fijar("iso:" + l["iso"] if l.get("iso") else "cosa:" + _norm(l["nombre"]), l)
        lados = e.get("lados") or []
        if len(lados) == 2 and lados[0]["color"] == lados[1]["color"]:
            # dos bandos nunca con el mismo color: el segundo toma uno libre
            usados = set(fijo.values())
            libre = next((c for c in ("azul", "rojo", "verde", "naranja", "morado", "amarillo") if c not in usados), None)
            lados[1]["color"] = libre or next(c for c in ("azul", "rojo") if c != lados[0]["color"])


# ------------------------------------------------------------------ 2. voz

def _voz(fid):
    s = _leer(fid)
    o = s["opciones"]
    if _propia(o):
        return _voz_grabada(fid, o)
    guion = almacen.leer_json(_dir(fid, "guion.json"))
    texto = " ".join(e["texto"] for e in guion["escenas"])
    carpeta = _dir(fid, "voz", crear=True)
    audio = os.path.join(carpeta, "voz.mp3")
    if o["voz"].startswith(NARRADA):
        return _voz_narrada(fid, o, texto, audio)
    _guardar(fid, estado="voz", progreso=15, mensaje=f"sintetizando la voz ({o['voz']})")
    nombre = voice.parse_voice_name(o["voz"])
    if componentes.es_voz_microsoft(nombre):
        componentes.comprobar_edge_tts(nombre)
    sub_maker = voice.tts(text=texto, voice_name=nombre, voice_rate=o["velocidad"], voice_file=audio, voice_volume=1.0)
    if sub_maker is None or not os.path.isfile(audio):
        raise RuntimeError("el TTS no genero audio: revisa que la voz coincida con el idioma y la conexion")
    oidas = etapa_voz._guardar_palabras(sub_maker, os.path.join(carpeta, "oidas.json"))
    alineadas = etapa_voz.alinear(texto, oidas) if oidas else None
    if not alineadas:
        raise RuntimeError("la voz no trae el tiempo de cada palabra (usa una voz de Microsoft)")
    duracion = float(voice.get_audio_duration(sub_maker) or 0) or medios.sondear(audio)["duracion"]
    almacen.escribir_json(os.path.join(carpeta, "palabras.json"), {"duracion": round(duracion, 3), "palabras": alineadas[0]})
    _guardar(fid, progreso=22, mensaje=f"voz lista: {duracion:.1f} s")


_whisper_fino = None
_whisper_fino_candado = threading.Lock()


def _modelo_fino():
    """Whisper "small" para las grabaciones subidas: su texto va tal cual a los subtitulos ("base" confunde palabras)."""
    global _whisper_fino
    with _whisper_fino_candado:
        if _whisper_fino is None:
            from faster_whisper import WhisperModel
            _whisper_fino = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_fino


def _escuchar(fid, ruta, duracion, desde, hasta, idioma=None, fino=False):
    """Whisper: [(inicio, fin, palabra)] de lo que se oye en `ruta`."""
    _guardar(fid, mensaje="cargando Whisper")
    modelo = _modelo_fino() if fino else etapa_voz._modelo_whisper()
    segmentos, _info = modelo.transcribe(ruta, word_timestamps=True, vad_filter=True, beam_size=5 if fino else 1,
                                         language=IDIOMAS_CLON.get(idioma))
    oidas = []
    for s in segmentos:
        oidas += [(round(float(w.start), 3), round(float(w.end), 3), w.word.strip()) for w in (s.words or []) if w.word.strip()]
        _guardar(fid, progreso=int(desde + (hasta - desde) * min(1.0, s.end / max(duracion, 0.1))),
                 mensaje=f"escuchando la voz: {int(s.end)} de {int(duracion)} s")
    if not oidas:
        raise RuntimeError("Whisper no entendio ninguna palabra en el audio")
    return oidas


def _voz_grabada(fid, o):
    """Narracion subida: se pasa a mp3 y Whisper da cada palabra con su segundo (el guion sale despues de ella)."""
    carpeta = _dir(fid, "voz", crear=True)
    audio = os.path.join(carpeta, "voz.mp3")
    _guardar(fid, estado="voz", progreso=4, mensaje="preparando la grabacion")
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", _audio_subido(o["voz"]), "-vn",
                       "-c:a", "libmp3lame", "-q:a", "2", audio], timeout=900)
    if r.returncode != 0 or not os.path.isfile(audio):
        raise RuntimeError(f"ffmpeg no pudo leer la grabacion: {r.stderr[-300:]}")
    duracion = float(medios.sondear(audio).get("duracion") or 0)
    oidas = _escuchar(fid, audio, duracion, 6, 20, o["idioma"], fino=True)
    almacen.escribir_json(os.path.join(carpeta, "palabras.json"),
                          {"duracion": round(duracion, 3), "palabras": [list(w) for w in oidas]})
    _guardar(fid, progreso=22, mensaje=f"grabacion lista: {duracion:.1f} s, {len(oidas)} palabras")


def _voz_narrada(fid, o, texto, audio):
    """Tu grabacion leyendo el guion: Whisper oye cada palabra y el texto del guion toma esos tiempos."""
    _guardar(fid, estado="voz", progreso=14, mensaje="preparando tu grabacion")
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", _audio_subido(o["voz"]), "-vn",
                       "-c:a", "libmp3lame", "-q:a", "2", audio], timeout=900)
    if r.returncode != 0 or not os.path.isfile(audio):
        raise RuntimeError(f"ffmpeg no pudo leer la grabacion: {r.stderr[-300:]}")
    duracion = float(medios.sondear(audio).get("duracion") or 0)
    oidas = _escuchar(fid, audio, duracion, 15, 22, o["idioma"], fino=True)
    alineadas = etapa_voz.alinear(texto, [list(w) for w in oidas])
    if not alineadas:
        raise RuntimeError("tu grabacion no se parece al guion: lee el texto de las escenas tal cual (o corrige el guion)")
    almacen.escribir_json(os.path.join(_dir(fid, "voz"), "palabras.json"), {"duracion": round(duracion, 3), "palabras": alineadas[0]})
    _guardar(fid, progreso=22, mensaje=f"tu voz lista: {duracion:.1f} s")


# ------------------------------------------------------------------ 3. plan

def _norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return re.sub(r"[^\w%$€]+", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def _buscar(palabras, texto):
    """Indice de la primera palabra de `texto` (una o varias) dentro de `palabras` ([a, b, w]), o None."""
    objetivo = [_norm(w) for w in str(texto or "").split() if _norm(w)]
    lista = [_norm(w[2]) for w in palabras]
    for i in range(len(lista) - len(objetivo) + 1 if objetivo else 0):
        if lista[i:i + len(objetivo)] == objetivo:
            return i
    # si Claude puso la palabra con otra forma ("Bolivia" / "bolivianos"), vale el comienzo
    if objetivo:
        for i, w in enumerate(lista):
            if len(objetivo[0]) >= 4 and w.startswith(objetivo[0][:max(4, len(objetivo[0]) - 2)]):
                return i
    return None


def _cuadro(t):
    return round(t * FPS) / FPS


def _caja(isos):
    p = _paises()
    cajas = [p[i]["bbox"] for i in isos if i in p]
    return [min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas)] if cajas else None


# composiciones de cada tipo de escena (escenas/<tipo>.js las dibuja segun ESCENA.variante)
VARIANTES = {"cifra": 3, "lista": 3, "versus": 3, "ilustracion": 4, "barras": 2}
TRANSICIONES = ("zoom", "barrido", "destello", "giro")   # entrada de cada escena tras el corte (nucleo.js, ritmo)


def plan(fid):
    """Escenas con su inicio y duracion (en fotogramas exactos) y sus datos en segundos de la escena."""
    o = _leer(fid)["opciones"]
    familia = _familia(o)   # los dibujos salen de la familia elegida (o la del estilo)
    guion = almacen.leer_json(_dir(fid, "guion.json"))
    voz = almacen.leer_json(_dir(fid, "voz", "palabras.json"))
    palabras, total = voz["palabras"], voz["duracion"]
    # trozo de palabras de cada escena
    k, trozos = 0, []
    for e in guion["escenas"]:
        n = len(e["texto"].split())
        trozos.append(palabras[k:k + n])
        k += n
    inicios = [0.0] + [_cuadro(max(0.0, t[0][0] - ADELANTO_S)) if t else None for t in trozos[1:]]
    for i in range(1, len(inicios)):  # escenas sin palabras (no deberia pasar) pegadas a la anterior
        inicios[i] = max(inicios[i] if inicios[i] is not None else inicios[i - 1], inicios[i - 1] + 1 / FPS)
    # con cierre de marca, el video sigue un poco despues de la voz para que la marca salga sola
    fin = _cuadro(total + COLA_S + (MARCA_S if o.get("marca") else 0))
    salida, previa, pintados = [], None, set()   # pintados: paises que siguen de color al acabar la escena anterior
    sonidos = []                                  # (segundo del video, efecto)
    estado_prota = "normal"                       # como quedo el protagonista en su ultima escena
    indicador = None                              # ultimo valor del indicador fijo (None: aun no ha salido)
    semilla = int(fid[:6], 16) if re.fullmatch(r"[0-9a-f]{6,}", fid[:6]) else 0
    vistos = {}                                   # escenas de cada tipo ya repartidas (para rotar su composicion)
    presentador = None
    if o.get("presentador"):
        if o["presentador"] in PRESENTADORES:
            presentador = {"aspecto": PRESENTADORES[o["presentador"]]["aspecto"]}
        else:
            # propio: su imagen va a cada escena con un nombre que cambia si cambia la imagen (cache al dia)
            pid = o["presentador"].removeprefix("propio:")
            ruta_pres = presentadores.ruta_imagen(pid)
            if ruta_pres:
                with open(ruta_pres, "rb") as f_:
                    nombre_pres = f"pres_{hashlib.sha1(f_.read()).hexdigest()[:12]}.webp"
                presentador = {"aspecto": presentadores.aspecto(pid), "imagen": nombre_pres, "ruta": ruta_pres}
    boca = _niveles_boca(_dir(fid, "voz", "voz.mp3"), fin) if presentador else ""
    puntos = o.get("estilo") == "explicador" or o.get("serie") == "explicador"   # cortinilla de tinta en los cambios grandes
    for i, (e, trozo) in enumerate(zip(guion["escenas"], trozos)):
        a = inicios[i]
        archivos = {}                             # {nombre en la pagina: ruta} (banderas, dibujos)
        dur = round((inicios[i + 1] if i + 1 < len(inicios) else fin) - a, 4)
        rel = [[round(x - a, 3), round(y - a, 3), w] for x, y, w in trozo]

        def en(palabra, defecto=0.3):
            j = _buscar(trozo, palabra) if palabra else None
            return round(trozo[j][0] - a, 3) if j is not None else defecto

        d = {"subtitulos": rel if o["subtitulos"] else []}
        if o.get("estilo") == "retrotv":   # cabecera con el tema y el contador de escenas
            d["cabecera"] = {"texto": guion.get("cabecera") or guion.get("titulo") or "", "n": i + 1, "total": len(guion["escenas"])}
        if e["tipo"] == "portada":
            # en una serie, su nombre va siempre encima del titulo (asi se reconoce de un video a otro)
            serie = SERIES.get(o.get("serie") or "")
            d.update(titulo=e["titulo"], antetitulo=serie["antetitulo"] if serie else e.get("antetitulo") or "")
            lugar = e.get("lugar")
            if e.get("imagen") and not e.get("paises") and not lugar:
                d["fondo_img"] = _archivo(archivos, "ilustraciones", e["imagen"], familia)
            elif e.get("protagonista") and not e.get("paises") and not lugar:
                d["protagonista"] = _archivo(archivos, "pegatinas", e["protagonista"], familia)
            if e.get("paises") or lugar:
                # cada pais con el color que tendra en los mapas del video (asi no cambia de color al seguir)
                colores = {}
                for otra in guion["escenas"]:
                    if otra["tipo"] == "mapa":
                        for p in otra["paises"]:
                            colores.setdefault(p["iso"], p["color"])
                # una parte de un pais o un sitio (Alaska): se encuadra eso; si no, los paises enteros
                toma = {"lon": lugar["lon"], "lat": lugar["lat"], "z": lugar["zoom"]} if lugar else {"bbox": _caja(e["paises"])}
                d["mapa"] = {"toma": toma,
                             "paises": [{"iso": iso, "color": colores.get(iso, "acento")} for iso in e.get("paises") or []]}
                d["vista"] = e.get("vista") or "mapa"
                previa = {"toma": d["mapa"]["toma"], "dz": round(DERIVA * dur, 4), "zona": "portada", "vista": d["vista"]}
                pintados = set(e.get("paises") or [])
            else:
                previa, pintados = None, set()
            # el titulo ya dice lo mismo que la voz: sin subtitulos encima
            if len(set(map(_norm, e["titulo"].split())) & set(map(_norm, e["texto"].split()))) >= 0.6 * len(e["titulo"].split()):
                d["subtitulos"] = []
        elif e["tipo"] == "mapa":
            # los que ya venian pintados de la escena anterior siguen pintados (sin parpadeo)
            d["paises"] = [{"iso": p["iso"], "color": p["color"], "a": 0 if p["iso"] in pintados else en(p["palabra"]),
                            "b": en(p["hasta"], None) if p.get("hasta") else None} for p in e["paises"]]
            d["etiquetas"] = [{"texto": t["texto"], "lon": t["lon"], "lat": t["lat"], "a": en(t["palabra"]) + 0.15,
                               "punto": t["punto"]} for t in e["etiquetas"]]
            d["rotulos"] = [{"texto": e["rotulo"]["texto"], "a": en(e["rotulo"]["palabra"])}] if e.get("rotulo") else []
            d["golpe"] = {"texto": e["golpe"]["texto"], "a": en(e["golpe"]["palabra"])} if e.get("golpe") else None
            d["vista"] = e.get("vista") or "mapa"
            d["foco"] = o.get("foco", True) and bool(e.get("foco"))
            pais = _paises()
            # banderas en el centro de su pais; si hay pegatina en el mismo pais, la pegatina se aparta a un lado
            d["banderas"] = []
            for b in e.get("banderas") or []:
                a2 = pais[b["iso"]]["a2"]
                nombre = f"flag_{a2}.svg"
                archivos[nombre] = os.path.join(BANDERAS, f"{a2}.svg")
                lon, lat = (b["lon"], b["lat"]) if "lon" in b else pais[b["iso"]]["c"]
                d["banderas"].append({"src": nombre, "lon": lon, "lat": lat, "a": en(b["palabra"]), "ojos": b["ojos"]})
            d["pegatinas"] = []
            for p in e.get("pegatinas") or []:
                cerca = any(abs(p["lon"] - b["lon"]) < 1.5 and abs(p["lat"] - b["lat"]) < 1.5 for b in d["banderas"])
                d["pegatinas"].append({"src": _archivo(archivos, "pegatinas", p["id"], familia), "lon": p["lon"], "lat": p["lat"],
                                       "a": en(p["palabra"]), "dx": -0.11 if cerca else 0})
            # un rotulo en el mismo sitio que una bandera o pegatina baja un poco para no taparse
            for t in d["etiquetas"]:
                if any(abs(t["lon"] - q["lon"]) < 1.5 and abs(t["lat"] - q["lat"]) < 1.5 for q in d["banderas"] + d["pegatinas"]):
                    t["dy"] = 0.075
            d["rios"] = [{"clave": r["clave"], "color": r["color"], "a": en(r["palabra"])} for r in e.get("rios") or []]
            m = e.get("medida")
            d["medidas"] = [{"desde": m["desde"], "hasta": m["hasta"], "texto": m["texto"], "a": en(m["palabra"])}] if m else []
            r = e.get("ruta")
            d["rutas"] = [{"desde": r["desde"], "hasta": r["hasta"], "a": en(r["palabra"]),
                           "src": _archivo(archivos, "pegatinas", r["pegatina"], familia) if r.get("pegatina") else None}] if r else []
            c = e.get("circulo")
            d["circulos"] = [{"lon": c["lon"], "lat": c["lat"], "a": en(c["palabra"])}] if c else []
            tomas = []
            for c in e.get("camara") or []:
                toma = {"bbox": _caja(c["paises"])} if c.get("paises") else \
                    {"lon": c["lugar"]["lon"], "lat": c["lugar"]["lat"], "z": c["lugar"]["zoom"]}
                tomas.append({"t": max(0.6, en(c["palabra"], 0.8)), **toma})
            if not tomas:
                if d["paises"]:
                    # la camara se abre a medida que se nombran: cada pais nuevo entra en el encuadre
                    for p in sorted(d["paises"], key=lambda x: x["a"]):
                        caja = _caja([q["iso"] for q in d["paises"] if q["a"] <= p["a"]])
                        t = max(0.6, p["a"] + 0.2)
                        if tomas and t - tomas[-1]["t"] < 1.0:
                            tomas[-1]["bbox"] = caja  # dos nombres seguidos: un solo vuelo
                        elif not tomas or caja != tomas[-1]["bbox"]:
                            tomas.append({"t": t, "bbox": caja})
                else:
                    # sin paises: se encuadra todo lo que sale (rios, banderas, pegatinas, medidas, rotulos...)
                    puntos = [(q["lon"], q["lat"]) for q in d["etiquetas"] + d["banderas"] + d["pegatinas"] + d["circulos"]]
                    puntos += [tuple(x[k]) for x in d["medidas"] + d["rutas"] for k in ("desde", "hasta")]
                    for rr in d["rios"]:
                        o_, s_, e_, n_ = _rios()[rr["clave"]]["bbox"]
                        puntos += [(o_, s_), (e_, n_)]
                    xs, ys = [q[0] for q in puntos], [q[1] for q in puntos]
                    lado = max(max(xs) - min(xs), max(ys) - min(ys))
                    if lado < 0.5:   # un solo sitio: de cerca (mas aun con satelite)
                        tomas = [{"t": 0.8, "lon": xs[0], "lat": ys[0], "z": 9 if d["vista"] == "satelite" else 5}]
                    else:
                        tomas = [{"t": 0.8, "bbox": [min(xs), min(ys), max(xs), max(ys)]}]
            tomas.sort(key=lambda x: x["t"])
            d["tomas"] = tomas
            # de satelite a mapa dibujado (o al reves) no se sigue el encuadre: un primer plano de satelite en el
            # mapa dibujado es un fondo liso. Se corta y se empieza de un poco mas lejos.
            d["previa"] = previa if previa and previa.get("vista", "mapa") == d["vista"] else None
            ultima = {k: v for k, v in tomas[-1].items() if k != "t"}
            previa = {"toma": ultima, "dz": round(DERIVA * max(0.0, dur - tomas[-1]["t"]), 4),
                      "zona": "rotulo" if d["rotulos"] or d["golpe"] else "normal", "vista": d["vista"]}
            pintados = {p["iso"] for p in d["paises"] if p["b"] is None}
            for t_ in tomas:
                sonidos.append((a + max(0.0, t_["t"] - 0.95), "whoosh"))
            sonidos += [(a + q["a"], "pop") for q in d["banderas"] + d["pegatinas"]]
            sonidos += [(a + q["a"], "whoosh") for q in d["rutas"]]
            if d["golpe"]:
                sonidos.append((a + d["golpe"]["a"], "golpe"))
        elif e["tipo"] == "protagonista":
            d["src"] = _archivo(archivos, "pegatinas", e["id"], familia)
            # sigue como acabo la vez anterior (solo duran los estados de color y tamano)
            d["inicio"] = e.get("inicio") or estado_prota
            d["cambios"] = [{"estado": c["estado"], "a": min(en(c["palabra"], 0.6 + k * 0.9), round(max(0.0, dur - 0.5), 3))}
                            for k, c in enumerate(e["cambios"])]
            for c in [{"estado": d["inicio"]}] + d["cambios"]:
                if c["estado"] in ("normal", "gris", "apagado", "brillante", "grande", "pequeno"):
                    estado_prota = c["estado"]
                elif c["estado"] == "se_va":
                    estado_prota = "normal"
            d["golpe"] = {"texto": e["golpe"]["texto"], "a": en(e["golpe"]["palabra"])} if e.get("golpe") else None
            d["rotulo"] = {"texto": e["rotulo"]["texto"], "a": en(e["rotulo"]["palabra"])} if e.get("rotulo") else None
            previa, pintados = None, set()
            sonidos.append((a, "whoosh"))
            sonidos += [(a + c["a"], "golpe" if c["estado"] in ("muchos", "se_va") else "pop") for c in d["cambios"]]
            if d["golpe"]:
                sonidos.append((a + d["golpe"]["a"], "golpe"))
        elif e["tipo"] == "ilustracion":
            if e.get("clip"):
                _clip_banco(fid, i, e["clip"], dur, o)
            if e.get("imagen"):
                d["src"] = _archivo(archivos, "ilustraciones", e["imagen"], familia)
            if _ruta_clip(fid, i):
                d["clip"] = True   # hay un clip de video subido: la escena se dibuja sobre verde y el clip va detras
            d["golpe"] = {"texto": e["golpe"]["texto"], "a": en(e["golpe"]["palabra"])} if e.get("golpe") else None
            d["rotulo"] = {"texto": e["rotulo"]["texto"], "a": en(e["rotulo"]["palabra"])} if e.get("rotulo") else None
            previa, pintados = None, set()
            sonidos.append((a, "whoosh"))
            if d["golpe"]:
                sonidos.append((a + d["golpe"]["a"], "golpe"))
        elif e["tipo"] == "cifra":
            d.update(numero=e["numero"], antes=e["antes"], despues=e["despues"], etiqueta=e["etiqueta"],
                     contexto=e["contexto"], a=en(e["palabra"], 0.3))
            previa, pintados = None, set()
            sonidos.append((a + d["a"], "pop"))
        elif e["tipo"] in ("barras", "lista", "versus", "linea_tiempo"):
            previa, pintados = None, set()
            campo = {"barras": "barras", "lista": "items", "versus": "lados", "linea_tiempo": "hitos"}[e["tipo"]]
            d["titulo"] = e.get("titulo") or ""
            d["foco"] = o.get("foco", True)   # solo brilla lo que se esta nombrando
            d[campo] = []
            for k, x in enumerate(e[campo]):
                # sin palabra que se encuentre, uno tras otro desde el principio
                quitar = ("palabra", "pegatina", "iso")
                d[campo].append({**{c: v for c, v in x.items() if c not in quitar},
                                 "a": min(en(x.get("palabra"), 0.3 + k * 0.7), round(max(0.0, dur - 0.6), 3)),
                                 **_icono(x, archivos, familia)})
            if e["tipo"] == "lista":
                d["numerar"] = e.get("numerar", False)
            if e["tipo"] == "versus":
                d["vs"] = en(e.get("palabra_vs"), None) if e.get("palabra_vs") else None
                if d["vs"] is None:
                    d["vs"] = round(min(dur - 0.3, d["lados"][1]["a"] - 0.15) if len(d["lados"]) > 1 else 1.0, 3)
            sonidos.append((a, "whoosh"))
            sonidos += [(a + x["a"], "pop") for x in d[campo]]
            if e["tipo"] == "versus":
                sonidos.append((a + d["vs"], "golpe"))
        if e["tipo"] in VARIANTES:
            # composicion de la escena: cada video empieza en una distinta y las del mismo tipo van rotando
            n = vistos.get(e["tipo"], 0)
            vistos[e["tipo"]] = n + 1
            d["variante"] = e["variante"] if isinstance(e.get("variante"), int) else (semilla + n) % VARIANTES[e["tipo"]]
        if e["tipo"] == "captura":
            previa, pintados = None, set()
            d.update(forma=e["forma"], nombre=e["nombre"], usuario=e["usuario"], contenido=e["contenido"], cifra=e["cifra"],
                     a=en(e.get("palabra"), 0.6))
            d["mensajes"] = [{"texto": m["texto"], "mio": m["mio"], "a": min(en(m.get("palabra"), 0.3 + k * 0.9), round(max(0.0, dur - 0.5), 3))}
                             for k, m in enumerate(e["mensajes"])]
            sonidos += [(a + m["a"], "pop") for m in d["mensajes"]] or [(a + d["a"], "pop")]
        if e.get("extras"):
            d["extras"] = [{**t, "a": min(en(t.get("palabra"), 0.6 + k * 0.8), round(max(0.0, dur - 0.6), 3))}
                           for k, t in enumerate(e["extras"])]
            sonidos += [(a + t["a"], "golpe" if t["tipo"] == "sello" else "pop") for t in d["extras"]]
        # indicador fijo: desde que sale por primera vez se ve en todas las escenas (con su ultimo valor) y cuenta
        # hasta el nuevo cuando se dice su palabra
        if guion.get("indicador") and (indicador is not None or e.get("indicador")):
            nuevo = e.get("indicador")
            d["indicador"] = {**guion["indicador"], "desde": indicador, "hasta": nuevo["valor"] if nuevo else indicador,
                              "a": en(nuevo["palabra"], 0.4) if nuevo else 0}
            if nuevo:
                indicador = nuevo["valor"]
                sonidos.append((a + d["indicador"]["a"], "pop"))
        if i == len(guion["escenas"]) - 1 and o.get("marca"):
            # cierre de marca: el nombre del canal en los ultimos segundos del video
            d["marca"] = {"texto": o["marca"], "a": round(max(0.3, dur - MARCA_S - 0.4), 3)}
            sonidos.append((a + d["marca"]["a"], "whoosh"))
        if i and not d.get("previa") and not d.get("clip"):
            # entrada desde el corte (rotando, nunca dos iguales seguidas); el mapa que sigue al anterior no lleva:
            # su camara continua y un salto lo romperia. En el explicador, cortinilla de puntos tras la portada y
            # antes de la ultima escena (y solo zoom o barrido en el resto: nada de brillos)
            if puntos and i in (1, len(guion["escenas"]) - 1) and not salida[-1]["datos"].get("clip"):
                d["transicion"] = "puntos"
                salida[-1]["datos"]["salida"] = "puntos"
            elif puntos:
                d["transicion"] = ("zoom", "barrido")[(semilla + i) % 2]
            else:
                d["transicion"] = TRANSICIONES[(semilla + i) % len(TRANSICIONES)]
            d["lado"] = 1 if i % 2 else -1
            if d["transicion"] != "destello":
                sonidos.append((a, "whoosh"))
        # acercon + sacudida de la escena en sus golpes
        d["impactos"] = [round(t - a, 3) for t, nombre in sonidos if nombre == "golpe" and a <= t < a + dur]
        if presentador:
            # habla todo el video: su boca en estos fotogramas, cabecea cuando entra algo y alterna mano que senala
            # (escenas pares) y mano abierta (impares) al empezar cada escena
            f0 = round(a * FPS)
            momentos = sorted({round(t - a, 3) for t, nombre in sonidos if nombre in ("pop", "golpe") and a + 0.3 <= t < a + dur - 0.3})
            gesto = [round(min(0.35, max(0.0, dur - 1.8)), 3)] if dur >= 2.2 else []
            if presentador.get("imagen"):
                archivos[presentador["imagen"]] = presentador["ruta"]
            d["presentador"] = {"aspecto": presentador["aspecto"], **({"imagen": presentador["imagen"]} if presentador.get("imagen") else {}),
                                "t0": round(a, 3), "boca": boca[f0:f0 + round(dur * FPS) + 1],
                                "asentir": momentos[:6], "senalar": gesto if i % 2 == 0 else [], "palma": gesto if i % 2 else []}
        salida.append({"i": i, "tipo": e["tipo"], "inicio": a, "duracion": dur, "datos": d, "archivos": archivos})
    # efectos: nunca dos iguales casi a la vez
    efectos = []
    for t, nombre in sorted(sonidos):
        if t < fin and not any(n == nombre and t - u < 0.3 for u, n in efectos[-4:]):
            efectos.append((round(t, 3), nombre))
    almacen.escribir_json(_dir(fid, "plan.json"), {"duracion": fin, "escenas": salida, "efectos": efectos})
    return salida, fin


def _niveles_boca(audio, duracion):
    """Un digito por fotograma (0 boca cerrada - 9 muy abierta) desde el volumen de la voz: abre al momento y cierra
    poco a poco (BOCA_SUELTA por fotograma), como un ataque instantaneo con caida."""
    import numpy as np
    n = int(round(duracion * FPS)) + 2
    if not os.path.isfile(audio):
        return "0" * n
    sr = 16000
    r = subprocess.run([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", audio, "-ac", "1", "-ar", str(sr),
                        "-f", "s16le", "-"], capture_output=True, timeout=300)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    paso = sr // FPS
    salida, nivel = [], 0.0
    bajo, alto = BOCA_DB
    for k in range(n):
        trozo = x[k * paso:(k + 1) * paso]
        db = 20 * np.log10(np.sqrt(np.mean(trozo ** 2)) + 1e-9) if len(trozo) else -90.0
        objetivo = min(1.0, max(0.0, (db - bajo) / (alto - bajo)))
        nivel = objetivo if objetivo >= nivel else max(objetivo, nivel * BOCA_SUELTA)
        salida.append(str(min(9, int(round(nivel * 9)))))
    return "".join(salida)


def _icono(x, archivos, familia):
    """{"src": pegatina} o {"bandera": svg} del elemento de una escena de graficas (o {})."""
    if x.get("pegatina"):
        return {"src": _archivo(archivos, "pegatinas", x["pegatina"], familia)}
    if x.get("iso"):
        a2 = _paises()[x["iso"]]["a2"]
        archivos[f"flag_{a2}.svg"] = os.path.join(BANDERAS, f"{a2}.svg")
        return {"bandera": f"flag_{a2}.svg"}
    return {}


def _archivo(archivos, tipo, clave, familia=None):
    """Nombre con el que va un dibujo de la biblioteca en la pagina (cambia si cambia el dibujo: cache al dia)."""
    ruta = biblioteca.ruta(tipo, clave, familia)
    if not ruta:
        raise RuntimeError(f"falta el dibujo '{clave}' en la biblioteca ({tipo})")
    with open(ruta, "rb") as f:
        nombre = f"{tipo[:3]}_{hashlib.sha1(f.read()).hexdigest()[:12]}.webp"
    archivos[nombre] = ruta
    return nombre


# ------------------------------------------------------------------ 4. render

def _huella_motor():
    """Cambia si cambia cualquier archivo del motor (asi la cache no sirve escenas viejas)."""
    h = hashlib.sha1()
    for raiz, _dirs, archivos in os.walk(DIR_FABRICA):
        for a in sorted(archivos):
            if a.endswith((".js", ".css", ".html")) and a not in ("paises.js", "rios.js"):
                with open(os.path.join(raiz, a), "rb") as f:
                    h.update(a.encode() + f.read())
    return h.hexdigest()[:12]


def _textura(estilo, w, h):
    """Fondo pintado del estilo (motion/fabrica/texturas, hecho con datos/hacer_estilos.py) o None si no tiene."""
    ruta = os.path.join(DIR_FABRICA, "texturas", f"{estilo}_{'h' if w > h else 'v'}.webp")
    return ruta if os.path.isfile(ruta) else None


def _huella_escena(escena, estilo, w, h, motor):
    textura = _textura(estilo, w, h)
    return hashlib.sha1(json.dumps([motor, escena["tipo"], escena["datos"], escena["duracion"], estilo, w, h,
                                    textura and os.path.getmtime(textura)], sort_keys=True).encode()).hexdigest()[:16]


def renderizar_escena(escena, estilo, formato, destino_dir, motor=None):
    """Video (mp4, sin audio) de UNA escena. Devuelve la ruta (cacheada por contenido)."""
    w, h = FORMATOS[formato]
    motor = motor or _huella_motor()
    textura = _textura(estilo, w, h)
    huella = _huella_escena(escena, estilo, w, h, motor)
    os.makedirs(destino_dir, exist_ok=True)
    final = os.path.join(destino_dir, f"{huella}.mp4")
    if os.path.isfile(final):
        return final
    falta = graficos.disponible()
    if falta:
        raise RuntimeError(falta)
    with _render:
        if os.path.isfile(final):
            return final
        tmp = tempfile.mkdtemp(prefix="escena_", dir=destino_dir)
        try:
            tipo = escena["tipo"]
            scripts = ESCENAS[tipo]["scripts"]
            with open(os.path.join(DIR_FABRICA, "base.html"), encoding="utf-8") as f:
                html = (f.read().replace("__ANCHO__", str(w)).replace("__ALTO__", str(h))
                        .replace("__DURACION__", f"{escena['duracion']:g}").replace("__ESTILO__", estilo)
                        .replace("__SCRIPTS__", "\n".join(f'  <script src="{s}"></script>' for s in scripts)))
            with open(os.path.join(tmp, "index.html"), "w", encoding="utf-8") as f:
                f.write(html)
            with open(os.path.join(tmp, "datos.js"), "w", encoding="utf-8") as f:
                f.write("window.CFG=" + json.dumps({"W": w, "H": h, "D": escena["duracion"], "textura": bool(textura)}) + ";\n"
                        "window.ESCENA=" + json.dumps(escena["datos"], ensure_ascii=False) + ";\n")
            copiar = {"gsap.min.js": graficos.GSAP, "nucleo.js": os.path.join(DIR_FABRICA, "nucleo.js"),
                      "presentador.js": os.path.join(DIR_FABRICA, "presentador.js"),
                      "estilos.css": os.path.join(DIR_FABRICA, "estilos.css"),
                      "escena.js": os.path.join(DIR_FABRICA, "escenas", f"{tipo}.js")}
            for s in scripts:
                copiar[s] = os.path.join(DIR_FABRICA, "datos" if s in ("paises.js", "rios.js") else "", s)
            copiar.update(escena.get("archivos") or {})
            if textura:
                copiar["textura.webp"] = textura
            for fuente in os.listdir(os.path.join(DIR_FABRICA, "fuentes")):
                if fuente.endswith(".ttf"):
                    copiar[fuente] = os.path.join(DIR_FABRICA, "fuentes", fuente)
            for nombre, origen in copiar.items():
                shutil.copyfile(origen, os.path.join(tmp, nombre))
            salida = os.path.join(tmp, "escena.mp4")
            env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HYPERFRAMES_NO_UPDATE_CHECK": "1"}
            # HyperFrames da solo 5 s a "ffmpeg -version": si el equipo va cargado (o el antivirus revisa el exe)
            # falla con "FFmpeg cannot start" aunque ffmpeg este bien → se reintenta
            for intento in range(3):
                r = subprocess.run([shutil.which("node"), graficos.CLI, "render", tmp, "-o", salida, "--fps", str(FPS),
                                    "-w", "2", "--quiet"], cwd=graficos.DIR_MOTION, env=env, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=1800)
                if r.returncode == 0 or "FFmpeg cannot start" not in (r.stderr or "") + (r.stdout or ""):
                    break
                time.sleep(2)
            if r.returncode != 0 or not os.path.isfile(salida):
                raise RuntimeError(f"HyperFrames no pudo renderizar la escena {escena['i'] + 1} ({tipo}): {(r.stderr or r.stdout)[-500:]}")
            os.replace(salida, final)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return final


# ------------------------------------------------------------------ galeria de estilos

DIR_MUESTRAS = almacen.raiz("fabrica_muestras")
_muestras = {"hilo": None, "error": ""}


def _escenas_muestra(estilo):
    """Las dos escenas de la muestra de un estilo (portada y mapa con bandera, pegatina y rotulo), ya en segundos."""
    familia = ESTILOS[estilo].get("familia")
    lon, lat = _paises()["BOL"]["c"]
    archivos = {"flag_BO.svg": os.path.join(BANDERAS, "BO.svg")}
    pegatina = _archivo(archivos, "pegatinas", "barco_vela", familia)
    frase = [(0.15, 0.4, "En"), (0.45, 1.05, "1879"), (1.1, 1.75, "Bolivia"), (1.8, 2.3, "perdió"), (2.35, 2.5, "su"),
             (2.55, 3.1, "costa"), (3.15, 3.3, "en"), (3.35, 3.5, "la"), (3.55, 3.95, "guerra")]
    portada = {"i": 0, "tipo": "portada", "duracion": 2.4, "archivos": {}, "datos": {
        "subtitulos": [], "titulo": "¿Por qué *Bolivia* no tiene mar?", "antetitulo": "Historia en un minuto", "vista": "mapa",
        "mapa": {"toma": {"bbox": [-82, -56, -34, 13]}, "paises": [{"iso": "BOL", "color": "rojo"}]}}}
    mapa = {"i": 1, "tipo": "mapa", "duracion": 4.4, "archivos": archivos, "datos": {
        "subtitulos": [[a, b, w] for a, b, w in frase],
        "paises": [{"iso": "BOL", "color": "rojo", "a": 0.0, "b": None}, {"iso": "CHL", "color": "azul", "a": 2.55, "b": None},
                   {"iso": "PER", "color": "amarillo", "a": 3.55, "b": None}],
        "etiquetas": [], "rotulos": [{"texto": "1879", "a": 0.45}], "golpe": None, "vista": "mapa",
        "banderas": [{"src": "flag_BO.svg", "lon": lon, "lat": lat, "a": 1.1, "ojos": True}],
        "pegatinas": [{"src": pegatina, "lon": -73.5, "lat": -22.5, "a": 2.55}],
        "rios": [], "medidas": [], "rutas": [], "circulos": [], "tomas": [{"t": 0.3, "bbox": [-76, -28, -57, -9]}]}}
    return [portada, mapa]


MUESTRA_V = 1   # subirlo rehace las imagenes de muestra (p. ej. si cambia mucho un estilo)
_candado_muestras = threading.Lock()


def _ruta_muestra(estilo):
    """Imagen fija del estilo: NO depende del motor, asi tocar el motor no rehace las 10 muestras."""
    return os.path.join(DIR_MUESTRAS, f"{estilo}_v{MUESTRA_V}.jpg")


def _hacer_muestra(estilo):
    final = _ruta_muestra(estilo)
    with _candado_muestras:
        if os.path.isfile(final):
            return final
        # el mapa con rotulo, bandera, pegatina y subtitulos ensena todo el estilo: un fotograma y listo
        origen = renderizar_escena(_escenas_muestra(estilo)[1], estilo, "9:16", os.path.join(DIR_MUESTRAS, "escenas"))
        tmp = final + ".tmp.jpg"
        r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", "3.9", "-i", origen,
                           "-frames:v", "1", "-vf", "scale=360:-2,format=yuvj420p", "-q:v", "4", tmp], timeout=120)
        if r.returncode != 0 or not os.path.isfile(tmp):
            raise RuntimeError(f"no se pudo hacer la muestra de {estilo}: {r.stderr[-300:]}")
        os.replace(tmp, final)
        # los videos de muestra de antes y la escena ya no hacen falta
        for f in [origen] + [os.path.join(DIR_MUESTRAS, f) for f in os.listdir(DIR_MUESTRAS) if f.startswith(estilo + "_") and f.endswith(".mp4")]:
            try:
                os.remove(f)
            except OSError:
                pass
        return final


def estilos_galeria():
    """Los estilos con su muestra: si falta alguna, se hacen en segundo plano (la interfaz vuelve a preguntar)."""
    os.makedirs(DIR_MUESTRAS, exist_ok=True)
    # muestra: segundo en que se hizo (sirve de version para la cache del navegador) o 0 si falta
    filas = [{"id": k, **e, "muestra": int(os.path.getmtime(r)) if os.path.isfile(r := _ruta_muestra(k)) else 0}
             for k, e in ESTILOS.items()]
    falta = graficos.disponible()
    hilo = _muestras["hilo"]
    if not falta and any(not f["muestra"] for f in filas) and not (hilo and hilo.is_alive()):
        def trabajar():
            _muestras["error"] = ""
            for k in ESTILOS:
                try:
                    _hacer_muestra(k)
                except Exception as e:   # una que falla no para las demas
                    logger.exception(f"muestra del estilo {k}")
                    _muestras["error"] = str(e)[:300]
        _muestras["hilo"] = threading.Thread(target=trabajar, daemon=True, name="fabrica-muestras")
        _muestras["hilo"].start()
    return {"estilos": filas, "generando": bool(_muestras["hilo"] and _muestras["hilo"].is_alive()),
            "error": _muestras["error"] or falta}


def ruta_muestra(estilo):
    if estilo not in ESTILOS:
        raise FileNotFoundError("ese estilo no existe")
    ruta = _ruta_muestra(estilo)
    if not os.path.isfile(ruta):
        raise FileNotFoundError("la muestra de ese estilo todavia no esta hecha")
    return ruta


def _render_y_montar(fid):
    s = _leer(fid)
    o = s["opciones"]
    guion = almacen.leer_json(_dir(fid, "guion.json"))
    if o.get("nuevos", True):
        _versiones(fid, guion)   # con otro aspecto (stickman, grabado...), los dibujos que le falten
    escenas, total = plan(fid)
    motor = _huella_motor()
    pasos = len(escenas) * len(o["formatos"])
    videos = []
    for k, formato in enumerate(o["formatos"]):
        def avisar(n, mensaje, k=k):
            _guardar(fid, estado="render", progreso=int(25 + 65 * (k * len(escenas) + n) / pasos), mensaje=f"{formato}: {mensaje}")
        partes = _partes(fid, escenas, formato, o["estilo"], motor, avisar)
        _guardar(fid, estado="montaje", mensaje=f"{formato}: montando voz, musica y efectos")
        w, h = FORMATOS[formato]
        videos.append(_montar(fid, formato, partes, total, w, h, o))
    creditos = "Mapas: Natural Earth (dominio publico)."
    if any(e["datos"].get("vista") == "satelite" for e in escenas):
        creditos += "\n" + satelite.CREDITO
    # capitulos de YouTube (videos largos): "00:00 Introduccion" en la descripcion (el primero tiene que ser 00:00)
    capitulos = [(0.0 if not n else e["inicio"], guion["escenas"][e["i"]].get("capitulo"))
                 for n, e in enumerate(x for x in escenas if guion["escenas"][x["i"]].get("capitulo"))]
    lineas_cap = "\n".join(f"{int(t // 60):02d}:{int(t % 60):02d} {nombre}" for t, nombre in capitulos)
    _guardar(fid, capitulos=lineas_cap)
    with open(_dir(fid, "descripcion.txt"), "w", encoding="utf-8") as f:
        f.write(f"{guion['titulo']}\n\n{guion['descripcion']}\n\n" + (f"{lineas_cap}\n\n" if lineas_cap else "") + f"{creditos}\n")
    almacen.escribir_json(_dir(fid, "videos.json"), videos)


# ------------------------------------------------------------------ abrir en el editor del Estudio

def abrir_en_editor(fid, formato=None):
    """Convierte un video de la Fabrica en un proyecto del Estudio para retocarlo en el editor: la voz de la
    Fabrica como narracion propia, una escena fija por escena (con su texto) y su video ya dibujado (con los
    subtitulos de la Fabrica dentro, asi que el Estudio no pone los suyos). Lanza las etapas hasta la
    asignacion; la musica y los efectos se eligen en el Estudio."""
    s = _leer(fid)
    o = s["opciones"]
    if fid in _trabajos and _trabajos[fid].is_alive():
        raise RuntimeError("este video todavia se esta haciendo")
    formato = formato or (o["formatos"][0] if o["formatos"] else "9:16")
    if formato not in FORMATOS:
        raise ValueError("formato no valido")
    guion = almacen.leer_json(_dir(fid, "guion.json"))
    voz = _dir(fid, "voz", "voz.mp3")
    if not guion or not os.path.isfile(voz):
        raise RuntimeError("al video le falta el guion o la voz: hazlo primero")
    escenas, _total = plan(fid)
    # los clips con que se monto ese video; si no constan (videos de antes), se sacan de la cache o se dibujan
    hecho = next((v for v in almacen.leer_json(_dir(fid, "videos.json"), []) or [] if v["formato"] == formato), {})
    partes = [_dir(fid, "escenas", n) for n in hecho.get("escenas") or []]
    if len(partes) != len(escenas) or not all(os.path.isfile(p) for p in partes):
        partes = _partes(fid, escenas, formato, o["estilo"], _huella_motor())

    m = re.match(r"([a-z]{2})-[A-Z]{2}", o["voz"])
    idioma = m.group(1) if m else str(o.get("idioma") or "es")[:2].lower()
    textos = [e["texto"] for e in guion["escenas"]]
    proyecto = almacen.crear(s["titulo"])
    pid = proyecto["id"]
    carpeta_voz = almacen.dir_proyecto(pid, "voz_propia", crear=True)
    shutil.copyfile(voz, os.path.join(carpeta_voz, "fabrica.mp3"))
    carpeta_videos = almacen.dir_proyecto(pid, "recursos", "videos", crear=True)
    for n, parte in enumerate(partes, 1):
        shutil.copyfile(parte, os.path.join(carpeta_videos, f"scene_{n:04d}.mp4"))
    proyecto["params"] = {
        "guion": {"modo": "literal", "material": " ".join(textos), "idioma": idioma},
        "voz": {"voz": etapa_voz.PROPIA + "fabrica.mp3"},
        # sin narracion, el Estudio corta las escenas por su duracion: los mismos cortes que en la Fabrica
        # (por palabras cortaria entre dos palabras y las animaciones irian adelantadas)
        "escenas": {"generar": "no", "fijas": [{"n": n, "narracion": None, "duracion_s": e["duracion"]}
                                               for n, e in enumerate(escenas, 1)]},
        "recursos": {"vision": False},
        "asignacion": {"modo": "escenas", "preferir": "video"},
        "render": {"aspecto": formato, "subtitulos": False, "zoom": 0},
    }
    proyecto["origen"] = {"fabrica": fid, "formato": formato}
    almacen.guardar(proyecto)
    _guardar(fid, proyectos=(s.get("proyectos") or []) + [{"id": pid, "formato": formato, "t": time.time()}])
    grafo.lanzar(pid, "asignacion")
    return {"proyecto": pid}


def _partes(fid, escenas, formato, estilo, motor, avisar=lambda n, mensaje: None):
    """El video de cada escena en un formato (los que ya estan hechos salen de la cache)."""
    w, h = FORMATOS[formato]
    partes = []
    o = _leer(fid)["opciones"]
    for n, e in enumerate(escenas):
        if e["datos"].get("vista") == "satelite":
            avisar(n, f"escena {e['i'] + 1}: bajando la foto de satelite")
            e = _con_satelite(fid, e, w, h)
        avisar(n, f"escena {e['i'] + 1} de {len(escenas)} ({e['tipo']})")
        parte = renderizar_escena(e, estilo, formato, _dir(fid, "escenas"), motor)
        if e["datos"].get("clip") and _ruta_clip(fid, e["i"]):
            avisar(n, f"escena {e['i'] + 1}: poniendo tu clip de video detras")
            parte = _con_clip(fid, e, parte, w, h)
        partes.append(parte)
    return partes


# ------------------------------------------------------------------ clips de video (hechos aparte y subidos)

def _ruta_clip(fid, i):
    """El clip subido para la escena i (indice en el guion), o None."""
    ruta = _dir(fid, "clips", f"escena_{int(i):03d}.mp4")
    return ruta if os.path.isfile(ruta) else None


def clips(fid):
    return sorted(int(n[7:10]) for n in os.listdir(_dir(fid, "clips")) if re.fullmatch(r"escena_\d{3}\.mp4", n)) \
        if os.path.isdir(_dir(fid, "clips")) else []


def subir_clip(fid, i, datos, nombre_archivo):
    """Un clip hecho aparte (Seedance, Veo...) para una escena de ilustracion; se ve al redibujar."""
    guion = almacen.leer_json(_dir(fid, "guion.json")) or {}
    escenas = guion.get("escenas") or []
    if not 0 <= int(i) < len(escenas) or escenas[int(i)]["tipo"] != "ilustracion":
        raise ValueError("los clips van en escenas de ilustracion")
    tmp = _dir(fid, "clips", crear=True)
    entrada = os.path.join(tmp, f"subido_{int(i):03d}{os.path.splitext(nombre_archivo or '')[1].lower() or '.mp4'}")
    with open(entrada, "wb") as f:
        f.write(datos)
    destino = os.path.join(tmp, f"escena_{int(i):03d}.mp4")
    # se normaliza (sin audio, h264) para componerlo luego rapido
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", entrada, "-an", "-c:v", "libx264",
                       "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", destino], timeout=900)
    os.remove(entrada)
    if r.returncode != 0 or not os.path.isfile(destino):
        raise ValueError(f"no se pudo leer el clip: {r.stderr[-200:]}")
    return {"clips": clips(fid)}


def _clip_banco(fid, i, ref, dur, o):
    """El clip del banco que Claude puso en la escena i, alargado a su duracion, como si se hubiera subido. Uno
    subido a mano para esa escena manda; el del banco se rehace si cambia el clip o la escena dura mas."""
    marcas = almacen.leer_json(_dir(fid, "clips", "banco.json"), {}) or {}
    ruta = _ruta_clip(fid, i)
    if ruta and (str(i) not in marcas or (marcas[str(i)]["ref"] == ref and marcas[str(i)]["dur"] >= dur - 0.05)):
        return
    hallado = banco.resolver(o.get("banco") or [], ref)
    if not hallado:
        return
    destino = os.path.join(_dir(fid, "clips", crear=True), f"escena_{int(i):03d}.mp4")
    try:
        banco.armar(*hallado, dur, destino)
    except Exception as e:  # noqa: BLE001 -- sin el clip la escena se queda con su imagen (o verde si no tiene)
        logger.warning(f"fabrica {fid}: clip del banco {ref} para la escena {i}: {e}")
        return
    marcas[str(i)] = {"ref": ref, "dur": dur}
    almacen.escribir_json(_dir(fid, "clips", "banco.json"), marcas)


def borrar_clip(fid, i):
    ruta = _ruta_clip(fid, i)
    if ruta:
        os.remove(ruta)
    return {"clips": clips(fid)}


def _con_clip(fid, escena, parte, w, h, clip=None):
    """La escena (dibujada sobre verde croma) encima de su clip subido: el clip llena el
    cuadro, se repite si es corto y se corta a la duracion de la escena."""
    clip = clip or _ruta_clip(fid, escena["i"])
    dur = escena["duracion"]
    salida = parte[:-4] + f"_clip{hashlib.sha1(clip.encode()).hexdigest()[:6]}{int(os.path.getmtime(clip))}.mp4"
    if os.path.isfile(salida):
        return salida
    filtro = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={FPS},"
              f"trim=duration={dur},setpts=PTS-STARTPTS[fondo];[1:v]chromakey=0x00FF00:0.16:0.06[encima];"
              "[fondo][encima]overlay=shortest=1,format=yuv420p[v]")
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", clip,
                       "-i", parte, "-filter_complex", filtro, "-map", "[v]", "-t", str(dur), "-an", "-c:v", "libx264",
                       "-preset", "veryfast", "-crf", "18", salida], timeout=900)
    if r.returncode != 0 or not os.path.isfile(salida):
        logger.warning(f"fabrica {fid}: no se pudo poner el clip de la escena {escena['i']}: {r.stderr[-300:]}")
        return parte
    return salida


def _con_satelite(fid, escena, w, h):
    """La escena con sus mosaicos de satelite para este formato (lo que ve la camara depende del encuadre)."""
    d = escena["datos"]
    if escena["tipo"] == "portada":
        if not d.get("mapa"):
            return escena
        camaras = [satelite.encuadre(d["mapa"]["toma"], w, h, satelite.zona(w, h, "portada"))]
    else:
        zl = satelite.zona(w, h, "rotulo" if d.get("rotulos") or d.get("golpe") else "normal")
        camaras = [satelite.encuadre(t, w, h, zl) for t in d["tomas"]]
        if d.get("previa"):
            ini = satelite.encuadre(d["previa"]["toma"], w, h, satelite.zona(w, h, d["previa"]["zona"]))
            camaras.insert(0, {**ini, "z": ini["z"] + (d["previa"].get("dz") or 0)})
        else:
            camaras.insert(0, {**camaras[0], "z": camaras[0]["z"] - 0.9})
    lista, archivos = satelite.para_escena(camaras, w, h, _dir(fid, "sat", crear=True))
    return {**escena, "datos": {**d, "satelite": lista}, "archivos": {**(escena.get("archivos") or {}), **archivos}}


def _tele(fid, video, w):
    """Acabado de emision analogica de Retro TV sobre el video ya juntado: halo suave en lo blanco, un pelin de
    desfase de color siempre y un corte de senal corto (desfase fuerte + destello) en cada cambio de escena. Las
    lineas, el grano y la vineta ya los pinta el estilo. Si ffmpeg falla, se queda el video sin acabado."""
    escenas = (almacen.leer_json(_dir(fid, "plan.json"), {}) or {}).get("escenas") or []
    cortes = [round(e["inicio"], 3) for e in escenas[1:]]
    k = max(1, round(w / 540))
    corte = "+".join(f"between(t,{max(0, c - 0.04):.3f},{c + 0.12:.3f})" for c in cortes) or "0"
    filtro = (f"[0:v]split[a][b];[b]gblur=sigma={6 * k}[halo];[a][halo]blend=all_mode=screen:all_opacity=0.32,"
              f"rgbashift=rh=-{k}:bh={k},"
              f"rgbashift=rh=-{6 * k}:bh={6 * k}:rv={2 * k}:enable='{corte}',"
              f"eq=brightness=0.07:enable='{corte}',format=yuv420p[v]")
    salida = video[:-4] + "_tele.mp4"
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-filter_complex", filtro,
                       "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(FPS), salida], timeout=3600)
    if r.returncode != 0 or not os.path.isfile(salida):
        logger.warning(f"fabrica {fid}: sin acabado de tele: {r.stderr[-300:]}")
        return video
    os.replace(salida, video)
    return video


def _montar(fid, formato, partes, total, w, h, o):
    carpeta = _dir(fid, "videos", crear=True)
    lista = os.path.join(carpeta, f"lista_{formato.replace(':', 'x')}.txt")
    with open(lista, "w", encoding="utf-8") as f:
        f.writelines(f"file '{p.replace(os.sep, '/')}'\n" for p in partes)
    combinado = os.path.join(carpeta, f"escenas_{formato.replace(':', 'x')}.mp4")
    # HyperFrames entrega casi sin comprimir (~60 Mb/s): al juntar se comprime a un tamano normal para subir
    r = medios.correr([medios.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                       "-i", lista, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                       "-r", str(FPS), combinado], timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(f"no se pudieron juntar las escenas: {r.stderr[-400:]}")
    if o.get("estilo") == "retrotv":
        combinado = _tele(fid, combinado, w)
    destino = os.path.join(carpeta, formato.replace(":", "x") + ".mp4")
    musica = o["musica"] if isinstance(o["musica"], str) else ("random" if o["musica"] else "")   # sesiones viejas: bool
    p = {"volumen_voz": 1.0, "musica": musica, "musica_volumen": o.get("musica_volumen", 0.16), "sfx_volumen": 0.5}
    sfx = None
    efectos = (almacen.leer_json(_dir(fid, "plan.json"), {}) or {}).get("efectos") or []
    if o.get("efectos", True) and efectos:
        sfx = os.path.join(carpeta, "efectos.wav")
        edicion.pista_sfx(sfx, total, [tuple(x) for x in efectos])
    acabado.acabar(combinado, _dir(fid, "voz", "voz.mp3"), None, p, w, h, total, destino, sfx=sfx, ducking=True)
    for f in (lista, combinado) + ((sfx,) if sfx else ()):
        os.remove(f)
    return {"formato": formato, "archivo": os.path.basename(destino), "duracion": total, "ancho": w, "alto": h,
            "tam_mb": round(os.path.getsize(destino) / 1e6, 1), "creado": time.time(),
            "escenas": [os.path.basename(p) for p in partes]}   # los clips con que se monto (para abrir en el editor)
