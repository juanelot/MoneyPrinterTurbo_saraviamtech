// Cliente del backend del Estudio (/api/v1/estudio via rewrite /api/estudio).

export type EtapaId = "guion" | "voz" | "escenas" | "recursos" | "asignacion" | "render";
export type EstadoEtapa = "ok" | "obsoleta" | "pendiente" | "error" | "ejecutando";

export interface Plano {
  i: number;
  inicio: number;
  fin: number;
  texto: string;
  recurso?: string;
  nombre?: string;
  tipo?: "imagen" | "video";
  offset?: number;
  motivo?: string;
  fijado?: boolean;
  escena?: number;
  dur_recurso?: number;
  ajuste?: AjusteClip;
  inicio_elegido?: boolean;
}

// Que hacer si el clip es mas corto que su plano (lo elige el editor).
export type AjusteClip = "repetir" | "congelar" | "lento";

export interface AudioProyecto { archivo: string; nombre: string; duracion: number }

// Lo que necesita el editor de la linea de tiempo: la voz por palabras y su forma de onda.
export interface DatosEditor {
  audio: string | null; duracion: number; sin_voz: boolean;
  palabras: [number, number, string][]; picos: number[]; picos_por_s: number;
  /** Las frases de los subtitulos (lineas del SRT de la voz). */
  lineas?: [number, number, string][];
}

// Clip Studio: de un video largo a shorts.
export type EstadoClips = "transcribiendo" | "listo" | "proponiendo" | "exportando" | "error";
export interface MomentoClip { id: string; inicio: number; fin: number; titulo: string; gancho: string; nota: number | null; motivo: string }
export interface ShortHecho { archivo: string; titulo: string; inicio: number; fin: number; creado: number; tam_mb: number }
export interface SesionClips {
  id: string; titulo: string; duracion: number; ancho: number; alto: number; creado: number;
  estado: EstadoClips; progreso: number; mensaje: string; error: string | null;
}
export interface DetalleClips extends SesionClips {
  frases: [number, number, string][]; propuestas: MomentoClip[]; exportados: ShortHecho[];
}
export interface OpcionesShort {
  inicio: number; fin: number; encuadre: "recortar" | "ajustar" | "documental"; encuadre_x: number; subtitulos: boolean;
  /** alto (0-0.35) de los subtitulos grabados del original que se quitan abajo */
  banda: number;
  /** planos de otras fuentes encima de algunas frases (Claude elige cuales); "" = todo del video */
  broll: "" | "pexels" | "banco" | "ambos";
  /** bancos de clips de la Fabrica para el B-roll (modo banco o ambos) */
  bancos: string[];
  gancho: string; titulo: string; color: string;
}
export const clipStudio = {
  listar: () => pedir<{ sesiones: SesionClips[] }>(`/clips`),
  subir: (archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return pedir<SesionClips>(`/clips`, { method: "POST", body: fd });
  },
  ver: (cid: string) => pedir<DetalleClips>(`/clips/${cid}`),
  borrar: (cid: string) => pedir<{ ok: boolean }>(`/clips/${cid}`, { method: "DELETE" }),
  proponer: (cid: string, body: { cuantos: number; duracion: string; pedido: string }) =>
    pedir<DetalleClips>(`/clips/${cid}/proponer`, { method: "POST", ...json(body) }),
  guardar: (cid: string, propuestas: MomentoClip[]) =>
    pedir<{ propuestas: MomentoClip[] }>(`/clips/${cid}/propuestas`, { method: "PUT", ...json({ propuestas }) }),
  exportar: (cid: string, o: OpcionesShort) => pedir<{ archivo: string }>(`/clips/${cid}/exportar`, { method: "POST", ...json(o) }),
  urlOriginal: (cid: string) => `${BASE}/clips/${cid}/original`,
  urlShort: (cid: string, archivo: string, descargar = false) => `${BASE}/clips/${cid}/shorts/${archivo}${descargar ? "?descargar=true" : ""}`,
};

// Fabrica: videos enteros desde un tema (guion por escenas, voz y escenas dibujadas con codigo).
export type FormatoFabrica = "9:16" | "16:9" | "1:1";
export type EstadoFabrica = "en cola" | "guion" | "voz" | "render" | "montaje" | "revision" | "listo" | "error";
export interface CatalogoFabrica {
  nichos: { id: string; nombre: string; descripcion: string }[];
  series: { id: string; nombre: string; descripcion: string }[];
  /** personajes que pueden presentar el video (abajo a la derecha, hablando) */
  presentadores?: { id: string; nombre: string; descripcion: string; propio?: boolean }[];
  /** motor 3D: si hay Blender en esta maquina y las opciones del muneco */
  blender?: CatalogoBlender;
  /** aspecto de los dibujos (familias): madera, plano, grabado, foto, acuarela... */
  visuales?: { id: string; nombre: string }[];
  estilos: { id: string; nombre: string; descripcion: string }[];
  formatos: FormatoFabrica[]; falta: string;
}
export interface PersonajeBlender { forma: string; color: string; material: string; accesorio: string }
export interface CatalogoBlender {
  disponible: boolean; falta: string; personaje: PersonajeBlender;
  formas: { id: string; nombre: string }[]; materiales: { id: string; nombre: string }[];
  accesorios: { id: string; nombre: string }[]; escenarios: { id: string; nombre: string }[];
  calidades: { id: string; nombre: string }[];
}
/** voz: de Microsoft, "clon:<id>" o "propia:<archivo>" (grabacion subida con fabrica.subirAudio). musica: "random", "" o una cancion. */
export interface OpcionesFabrica {
  tema: string; nicho: string; estilo: string; formatos: FormatoFabrica[]; voz: string; velocidad: number;
  duracion: number; musica: string; musica_volumen: number; subtitulos: boolean; efectos: boolean; foco?: boolean; nuevos: boolean; idioma: string;
  /** serie de formato (mitos, abuela...) o vacio; marca: nombre del canal para el cierre */
  serie?: string; marca?: string;
  /** id de catalogo.presentadores o vacio */
  presentador?: string;
  /** "blender": todas las escenas son planos 3D del muneco (solo en el PC con Blender) */
  motor?: "" | "blender"; personaje?: PersonajeBlender; escenario?: string; calidad?: "borrador" | "final";
  /** aspecto de los dibujos: "" = el del estilo, o un id de catalogo.visuales */
  visual?: string;
  /** clonar: id de la receta a seguir; clips: Claude escribe el prompt de video de cada ilustracion (se hacen aparte) */
  receta?: string; clips?: boolean;
  /** banco de clips: ids de videos del banco cuyos clips Claude pone detras de las ilustraciones; modo: pocos o casi todo */
  banco?: string[]; banco_modo?: "insertos" | "mayoria";
  /** se para tras el guion y las imagenes (estado "revision") para subir clips, tu voz o la musica; con clips, siempre */
  revisar?: boolean;
}
/** molde: las opciones de un video que funciona, para repetirlas (sin tema) */
export interface MoldeFabrica { id: string; nombre: string; creado: number; opciones: Omit<OpcionesFabrica, "tema"> }
export interface EscenaFabrica { tipo: string; texto: string; [campo: string]: unknown }
export interface GuionFabrica { titulo: string; descripcion: string; mensaje?: string; colores?: Record<string, string>;
  indicador?: { nombre: string; antes: string; despues: string } | null; escenas: EscenaFabrica[] }
export interface VideoFabrica { formato: FormatoFabrica; archivo: string; duracion: number; ancho: number; alto: number; tam_mb: number; creado: number }
export interface SesionFabrica {
  id: string; titulo: string; opciones: OpcionesFabrica; creado: number; actualizado: number;
  estado: EstadoFabrica; progreso: number; mensaje: string; error: string | null;
  /** videos largos: "00:00 Introduccion\n01:12 ..." para la descripcion de YouTube */
  capitulos?: string;
}
/** muestra: version del video de muestra (0 = todavia se esta haciendo) */
export interface EstiloFabrica { id: string; nombre: string; descripcion: string; familia?: string; muestra: number }
export interface GaleriaEstilos { estilos: EstiloFabrica[]; generando: boolean; error: string }
/** clips: indices de las escenas que tienen un clip de video subido */
export interface DetalleFabrica extends SesionFabrica { guion: GuionFabrica | null; videos: VideoFabrica[]; clips?: number[] }
export interface ResumenFabrica extends SesionFabrica { videos: VideoFabrica[]; trabajando: boolean }
/** origen "virales": salio de un video viral de otra cuenta (porque: por que deberia funcionar) */
export interface IdeaFabrica { tema: string; gancho: string; serie: string; creado: number; porque?: string; origen?: string }
export const fabrica = {
  /** banco de temas por nicho: Claude propone, al usar uno sale del banco */
  ideas: (nicho: string) => pedir<{ ideas: IdeaFabrica[] }>(`/fabrica/ideas?nicho=${encodeURIComponent(nicho)}`),
  sugerir: (nicho: string, serie = "") =>
    pedir<{ ideas: IdeaFabrica[] }>(`/fabrica/ideas`, { method: "POST", ...json({ nicho, serie }) }),
  quitarIdea: (nicho: string, tema: string) =>
    pedir<{ ideas: IdeaFabrica[] }>(`/fabrica/ideas?nicho=${encodeURIComponent(nicho)}&tema=${encodeURIComponent(tema)}`, { method: "DELETE" }),
  /** el video ya hecho que mas se parece a un tema (para no repetir) */
  parecido: (tema: string, nicho: string) =>
    pedir<{ parecido: { id: string; titulo: string; parecido: number } | null }>(
      `/fabrica/parecido?tema=${encodeURIComponent(tema)}&nicho=${encodeURIComponent(nicho)}`),
  catalogo: () => pedir<CatalogoFabrica>(`/fabrica/catalogo`),
  estilos: () => pedir<GaleriaEstilos>(`/fabrica/estilos`),
  urlMuestra: (estilo: string, v: number) => `${BASE}/fabrica/estilos/${estilo}/muestra?v=${v}`,
  listar: () => pedir<{ videos: ResumenFabrica[] }>(`/fabrica`),
  renombrar: (fid: string, titulo: string) => pedir<SesionFabrica>(`/fabrica/${fid}`, { method: "PATCH", ...json({ titulo }) }),
  duplicar: (fid: string) => pedir<SesionFabrica>(`/fabrica/${fid}/duplicar`, { method: "POST" }),
  moldes: () => pedir<{ moldes: MoldeFabrica[] }>(`/fabrica/moldes`),
  /** guarda las opciones dadas, o las de un video ya hecho (desde = su id) */
  guardarMolde: (nombre: string, o: { opciones?: Partial<OpcionesFabrica>; desde?: string }) =>
    pedir<MoldeFabrica>(`/fabrica/moldes`, { method: "POST", ...json({ nombre, ...o }) }),
  borrarMolde: (mid: string) => pedir<{ ok: boolean }>(`/fabrica/moldes/${mid}`, { method: "DELETE" }),
  /** saga: video nuevo que continua la historia de este (Dia 1 -> Dia 2) */
  // Borra la cache de escenas ya dibujadas (se redibujan al rehacer o abrir en el editor).
  liberar: (fid: string) => pedir<{ liberado: number; total: number; liberable: number }>(`/fabrica/${fid}/liberar`, { method: "POST" }),
  siguiente: (fid: string, idea = "") => pedir<SesionFabrica>(`/fabrica/${fid}/siguiente`, { method: "POST", ...json({ idea }) }),
  crear: (o: Partial<OpcionesFabrica> & { tema: string }) => pedir<SesionFabrica>(`/fabrica`, { method: "POST", ...json(o) }),
  /** varios videos con las mismas opciones; se hacen de uno en uno */
  lote: (temas: string[], opciones: Partial<OpcionesFabrica>) =>
    pedir<{ lote: string; videos: SesionFabrica[] }>(`/fabrica/lote`, { method: "POST", ...json({ temas, opciones }) }),
  /** crea un proyecto del Estudio con este video (voz, escenas y clips) para retocarlo en el editor */
  abrirEditor: (fid: string, formato?: FormatoFabrica) =>
    pedir<{ proyecto: string }>(`/fabrica/${fid}/editor`, { method: "POST", ...json({ formato }) }),
  subirAudio: (archivo: File) => {
    const fd = new FormData();
    fd.append("audio", archivo, archivo.name);
    return pedir<{ voz: string; duracion: number }>(`/fabrica/audio`, { method: "POST", body: fd });
  },
  ver: (fid: string) => pedir<DetalleFabrica>(`/fabrica/${fid}`),
  borrar: (fid: string) => pedir<{ ok: boolean }>(`/fabrica/${fid}`, { method: "DELETE" }),
  rehacer: (fid: string, desde: "guion" | "voz" | "render", opciones?: Partial<OpcionesFabrica>) =>
    pedir<SesionFabrica>(`/fabrica/${fid}/rehacer`, { method: "POST", ...json({ desde, opciones }) }),
  /** sigue un video parado en revision (voz "narrada:<archivo>" = tu grabacion leyendo el guion) */
  montar: (fid: string, opciones?: Partial<OpcionesFabrica>) =>
    pedir<SesionFabrica>(`/fabrica/${fid}/montar`, { method: "POST", ...json({ opciones }) }),
  guardarGuion: (fid: string, guion: GuionFabrica) => pedir<SesionFabrica>(`/fabrica/${fid}/guion`, { method: "PUT", ...json({ guion }) }),
  /** clip de video hecho aparte (con el video_prompt de la escena) para una escena de ilustracion */
  subirClip: (fid: string, n: number, archivo: File) => {
    const fd = new FormData();
    fd.append("video", archivo, archivo.name);
    return pedir<{ clips: number[] }>(`/fabrica/${fid}/clip/${n}`, { method: "POST", body: fd });
  },
  borrarClip: (fid: string, n: number) => pedir<{ clips: number[] }>(`/fabrica/${fid}/clip/${n}`, { method: "DELETE" }),
  urlVideo: (fid: string, formato: FormatoFabrica, descargar = false, v = 0) =>
    `${BASE}/fabrica/${fid}/video/${formato.replace(":", "x")}?v=${v}${descargar ? "&descargar=true" : ""}`,
};

// Ideas virales: videos de otras cuentas que hacen 3x su mediana (outliers) -> temas propios para el banco.
export interface VideoViral { id: string; titulo: string; vistas: number; url: string; cuenta: string; veces: number }
export interface CuentaViral { nombre: string; url: string; seguidores: number | null; mediana: number; n: number }
export interface AnalisisViral { cuentas: CuentaViral[]; videos: VideoViral[]; errores: string[]; fecha: number; urls: string[]; criterio: string }
export interface DetalleViral {
  titulo: string; vistas: number; duracion: number | null; likes: number | null; comentarios: number | null;
  likes_mil: number | null; comentarios_mil: number | null; gancho: string; descripcion: string;
  top: { texto: string; likes: number }[];
}
export const virales = {
  ultimo: () => pedir<{ analisis: AnalisisViral | null }>(`/virales`),
  analizar: (cuentas: string[]) => pedir<AnalisisViral>(`/virales`, { method: "POST", ...json({ cuentas }) }),
  detalle: (url: string) => pedir<DetalleViral>(`/virales/detalle`, { method: "POST", ...json({ url }) }),
  aTemas: (videos: (VideoViral & Partial<DetalleViral>)[], nicho: string, serie = "") =>
    pedir<{ ideas: IdeaFabrica[] }>(`/virales/temas`, { method: "POST", ...json({ videos, nicho, serie }) }),
};

// Clonar video: de un video que funciona sale su receta (gancho, bloques, tipos de plano, ritmo) para rehacerlo.
export interface PlanoClon {
  n: number; desde: number; hasta: number; foto: string | null; texto: string; tipo?: string; describe?: string; texto_pantalla?: string;
}
export interface RecetaClon {
  titulo: string; resumen: string; duracion: number; formato: FormatoFabrica; nicho_sugerido: string;
  gancho: { texto: string; visual: string; tipo: string; patron: string };
  por_que_funciona: string[]; temas_parecidos: string[]; efectos: string[]; subtitulos: string; musica: string;
  estructura: { bloque: string; desde: number; hasta: number; que_pasa: string; patron: string }[];
  ritmo: { planos: number; cortes_por_minuto: number; plano_medio_s: number }; palabras_por_segundo: number;
}
export interface SesionClon {
  id: string; origen: string; titulo: string; estado: "en cola" | "descargando" | "analizando" | "listo" | "error";
  progreso: number; mensaje: string; error: string | null; creado: number; duracion?: number; formato?: FormatoFabrica;
}
export interface DetalleClon extends SesionClon { receta: RecetaClon | null; planos: PlanoClon[] }
export const clones = {
  listar: () => pedir<{ clones: SesionClon[] }>(`/clones`),
  crear: (url: string) => pedir<SesionClon>(`/clones`, { method: "POST", ...json({ url }) }),
  subir: (archivo: File) => {
    const fd = new FormData();
    fd.append("video", archivo, archivo.name);
    return pedir<SesionClon>(`/clones/subir`, { method: "POST", body: fd });
  },
  ver: (cid: string) => pedir<DetalleClon>(`/clones/${cid}`),
  borrar: (cid: string) => pedir<{ ok: boolean }>(`/clones/${cid}`, { method: "DELETE" }),
  urlFoto: (cid: string, nombre: string) => `${BASE}/clones/${cid}/foto/${nombre}`,
};

// Banco de clips: videos largos cortados en planos de ~3 s que Claude describe; la Fabrica los usa de fondo.
export interface ClipBanco { n: number; desde: number; dur: number; sirve: boolean; describe?: string; etiquetas?: string[] }
export interface SesionBanco {
  id: string; origen: string; titulo: string; estado: "en cola" | "descargando" | "cortando" | "listo" | "error";
  progreso: number; mensaje: string; error: string | null; creado: number; duracion?: number; n_clips: number;
}
export interface DetalleBanco extends SesionBanco { clips: ClipBanco[] }
export const banco = {
  listar: () => pedir<{ videos: SesionBanco[] }>(`/banco`),
  crear: (url: string) => pedir<SesionBanco>(`/banco`, { method: "POST", ...json({ url }) }),
  subir: (archivo: File) => {
    const fd = new FormData();
    fd.append("video", archivo, archivo.name);
    return pedir<SesionBanco>(`/banco/subir`, { method: "POST", body: fd });
  },
  ver: (bid: string) => pedir<DetalleBanco>(`/banco/${bid}`),
  borrar: (bid: string) => pedir<{ ok: boolean }>(`/banco/${bid}`, { method: "DELETE" }),
  /** cambia si el clip sirve (los que no sirven no se le ofrecen a Claude) */
  sirve: (bid: string, n: number) => pedir<{ clips: ClipBanco[] }>(`/banco/${bid}/clip/${n}/sirve`, { method: "POST" }),
  urlFoto: (bid: string, n: number) => `${BASE}/banco/${bid}/foto/${n}`,
  urlClip: (bid: string, n: number) => `${BASE}/banco/${bid}/clip/${n}`,
};

// Biblioteca de dibujos de la Fabrica: pegatinas (encima del mapa) e ilustraciones (pantalla completa).
export type TipoDibujo = "pegatinas" | "ilustraciones";
export interface Dibujo { id: string; descripcion: string; origen: "base" | "propia"; creado?: number; grupo: string }
export interface Biblioteca {
  pegatinas: Dibujo[]; ilustraciones: Dibujo[]; crear: boolean;
  grupos: { id: string; nombre: string }[]; nichos: Record<string, string[]>; familias: string[];
}
// Presentadores propios (la Fabrica los anima abajo a la derecha): hechos con Nano Banana desde una descripcion o subidos
export interface PresentadorPropio {
  id: string; nombre: string; descripcion: string; creado: number; origen: string;
  ojos: [number, number][]; boca: [number, number]; ancho_boca: number; piel: string;
}
export interface FotoPresentador {
  id: string; estado: "trabajando" | "listo" | "error"; opciones: number[]; total: number; error?: string;
}
export const presentadores = {
  listar: () => pedir<{ presentadores: PresentadorPropio[]; crear: boolean }>(`/presentadores`),
  urlImagen: (id: string, v = 0) => `${BASE}/presentadores/${id}/imagen${v ? `?v=${v}` : ""}`,
  /** tarda ~1 min (Nano Banana en Flow, solo en el PC local) */
  crear: (nombre: string, descripcion: string) =>
    pedir<PresentadorPropio>(`/presentadores`, { method: "POST", ...json({ nombre, descripcion }) }),
  subir: (archivo: File, nombre: string, fondoVerde = false) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    fd.append("nombre", nombre);
    fd.append("fondo_verde", String(fondoVerde));
    return pedir<PresentadorPropio>(`/presentadores/subir`, { method: "POST", body: fd });
  },
  /** Nano Banana dibuja 3 opciones con la foto como referencia en segundo plano (~3 min, solo en el PC local) */
  desdeFoto: (foto: File) => {
    const fd = new FormData();
    fd.append("foto", foto);
    return pedir<FotoPresentador>(`/presentadores/foto`, { method: "POST", body: fd });
  },
  estadoFoto: (oid: string) => pedir<FotoPresentador>(`/presentadores/foto/${oid}`),
  urlOpcion: (oid: string, n: number) => `${BASE}/presentadores/foto/${oid}/${n}`,
  elegirFoto: (oid: string, opcion: number, nombre: string) =>
    pedir<PresentadorPropio>(`/presentadores/foto/${oid}/elegir`, { method: "POST", ...json({ opcion, nombre }) }),
  descartarFoto: (oid: string) => pedir<{ ok: boolean }>(`/presentadores/foto/${oid}`, { method: "DELETE" }),
  corregir: (id: string, cambios: { ojos?: [number, number][]; boca?: [number, number]; ancho_boca?: number; nombre?: string }) =>
    pedir<PresentadorPropio>(`/presentadores/${id}`, { method: "PATCH", ...json(cambios) }),
  borrar: (id: string) => pedir<{ ok: boolean }>(`/presentadores/${id}`, { method: "DELETE" }),
};

export const biblioteca = {
  listar: () => pedir<Biblioteca>(`/fabrica/biblioteca`),
  // familia: "madera" (o vacia) es la base; "plano" y "grabado", las de los otros estilos
  urlImagen: (tipo: TipoDibujo, id: string, v = 0, familia = "") => {
    const q = new URLSearchParams();
    if (v) q.set("v", String(v));
    if (familia && familia !== "madera") q.set("familia", familia);
    return `${BASE}/fabrica/biblioteca/${tipo}/${id}${q.size ? `?${q}` : ""}`;
  },
  crear: (tipo: TipoDibujo, descripcion: string, nombre = "", clase: "personaje" | "objeto" = "personaje", familia = "") =>
    pedir<Dibujo>(`/fabrica/biblioteca/crear`, { method: "POST", ...json({ tipo, descripcion, nombre, clase, familia }) }),
  subir: (tipo: TipoDibujo, archivo: File, nombre: string, descripcion = "", fondoVerde = false) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    fd.append("tipo", tipo);
    fd.append("nombre", nombre);
    fd.append("descripcion", descripcion);
    fd.append("fondo_verde", String(fondoVerde));
    return pedir<Dibujo>(`/fabrica/biblioteca/subir`, { method: "POST", body: fd });
  },
  borrar: (tipo: TipoDibujo, id: string) => pedir<{ ok: boolean }>(`/fabrica/biblioteca/${tipo}/${id}`, { method: "DELETE" }),
};

// Graficos animados del editor (HyperFrames).
export interface PlantillaGrafico {
  id: string; nombre: string; dur: number; posicion: string; color?: string; descripcion: string;
  campos: { id: string; etiqueta: string; defecto: string; lineas?: boolean }[];
}
export interface DatosGrafico { plantilla: string; valores: Record<string, string>; color?: string; posicion?: string }
export interface GraficoHecho { archivo: string; duracion: number; ancho: number; alto: number }
// Una idea de grafico que propuso Claude (en tiempo del video; sin renderizar todavia).
export interface IdeaGrafico {
  id: string; plantilla: string; nombre: string; valores: Record<string, string>; inicio: number; duracion: number;
  posicion: string; color: string; motivo: string; frase: string;
}

// Tarjeta Publicar del paso Video.
export interface Metadatos { plataforma: string; titulos: string[]; descripcion: string; hashtags: string[]; etiquetas: string[] }
export interface Gancho {
  plataforma: string; nota: number | null; bien: string[]; mal: string[]; alternativas: string[];
  plano: { desde: number; hasta: number; texto: string } | null; palabras: number;
}
export interface DatosPublicar {
  metadatos?: Metadatos; capitulos?: { lista: [number, string][]; texto: string }; gancho?: Gancho; traducciones?: string[];
  idiomas: Record<string, string>; plataformas: Record<string, string>;
}

export interface ParteGrabada {
  archivo: string; duracion: number; factor: number; cabe: boolean; sobran: number; texto: string; desde: number; hasta: number;
}

export interface Escena {
  scene_number: number;
  inicio: number;
  fin: number;
  duracion: number;
  planos: number[];
  narration: string;
  image_prompt: string;
  video_prompt: string;
  image_prompt_editado?: boolean;
  video_prompt_editado?: boolean;
}

export interface Recurso {
  id: string;
  nombre: string;
  origen: "subido" | "carpeta";
  tipo: "imagen" | "video";
  ancho: number;
  alto: number;
  duracion: number;
  descripcion: string;
  descripcion_manual: boolean;
  miniatura?: string;
  carpeta?: "images" | "videos" | "";
  escena?: number | null;
}

export const mini = (r: { id: string; miniatura?: string }) => r.miniatura || r.id.split("-")[0];

export interface SalidaGuion { texto: string; origen: string; palabras: number; duracion_estimada_s: number }
export interface SalidaVoz {
  audio: string; srt: string; duracion: number; planos: Plano[];
  sin_voz?: boolean; // voz = "ninguna": suena el audio de los clips
  // solo con audio propio
  texto?: string; texto_de?: "guion" | "transcripcion"; coincidencia?: number; idioma_detectado?: string;
}
export interface SalidaRecursos { recursos: Recurso[]; total: number; imagenes: number; videos: number; sin_descripcion: number }
export interface SalidaEscenas {
  escenas: Escena[]; total: number; con_prompt: number; generar: string; script: string;
  aspecto?: string; avisos?: { escena: number | null; problemas: string[] }[];
}
export interface SalidaAsignacion { planos: Plano[]; recursos_usados: number; faltan?: number[] }
export interface SalidaRender {
  mp4: string; duracion: number; ancho: number; alto: number;
  clips_nuevos: number; clips_reutilizados: number; tam_mb: number; edicion?: string | null;
}

export type Params = Record<string, unknown>;

export interface VistaEtapa<S = unknown> {
  estado: EstadoEtapa;
  salida: S | null;
  error: string | null;
  duracion_s: number | null;
  terminado: number | null;
  params: Params;
}

export interface Trabajo {
  hasta: EtapaId;
  etapa: EtapaId | null;
  progreso: number;
  mensaje: string;
  inicio: number;
}

export interface Vista {
  proyecto: { id: string; titulo: string; creado: number; actualizado: number; params: Record<string, Params> };
  etapas: {
    guion: VistaEtapa<SalidaGuion>;
    voz: VistaEtapa<SalidaVoz>;
    escenas: VistaEtapa<SalidaEscenas>;
    recursos: VistaEtapa<SalidaRecursos>;
    asignacion: VistaEtapa<SalidaAsignacion>;
    render: VistaEtapa<SalidaRender>;
  };
  orden: EtapaId[];
  deps: Record<EtapaId, EtapaId[]>;
  trabajo: Trabajo | null;
  log: string[];
}

export interface Subido {
  nombre: string; tipo: "imagen" | "video"; tam: number;
  carpeta: "images" | "videos" | ""; escena: number | null;
}

export interface ResumenProyecto {
  id: string; titulo: string; creado: number; actualizado: number;
  mp4: string | null; portada: string | null; duracion: number | null; trabajando: boolean;
}

const BASE = "/api/estudio";

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + ruta, { cache: "no-store", ...init });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const j = await r.json();
      msg = j.detail || j.message || msg;
    } catch {}
    throw new Error(msg);
  }
  return r.json();
}

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export type Espacio = {
  total: number;
  liberable: number;
  proyectos: { id: string; total: number; liberable: number }[];
};

export function tamano(bytes: number) {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`;
  return `${Math.max(0, Math.round(bytes / 1e3))} KB`;
}

export interface EscenaFija { n: number; narracion: string; clip?: string; imagen: string | null; video: string }

export const api = {
  listar: () => pedir<{ proyectos: ResumenProyecto[] }>("/proyectos"),
  crear: (titulo: string) => pedir<Vista>("/proyectos", { method: "POST", ...json({ titulo }) }),
  ver: (id: string) => pedir<Vista>(`/proyectos/${id}`),
  editar: (id: string, cambios: { titulo?: string; params?: Record<string, Params> }) =>
    pedir<Vista>(`/proyectos/${id}`, { method: "PATCH", ...json(cambios) }),
  borrar: (id: string) => pedir<{ ok: boolean }>(`/proyectos/${id}`, { method: "DELETE" }),
  duplicar: (id: string, titulo?: string) =>
    pedir<Vista>(`/proyectos/${id}/duplicar`, { method: "POST", ...json({ titulo }) }),
  ejecutar: (id: string, hasta: EtapaId, forzar: EtapaId[] = []) =>
    pedir<Vista>(`/proyectos/${id}/ejecutar`, { method: "POST", ...json({ hasta, forzar }) }),
  cancelar: (id: string) => pedir<{ cancelado: boolean }>(`/proyectos/${id}/cancelar`, { method: "POST" }),
  // Reparte el guion entre los clips subidos por su nombre (1.1, 1.2... o 1, 2, 3...). Solo calcula.
  escenasPorClip: (id: string, texto = "") =>
    pedir<{ fijas: EscenaFija[]; partes: number; clips: number; avisos: string[] }>(
      `/proyectos/${id}/escenas-por-clip`, { method: "POST", ...json({ texto }) }),
  // Liberar espacio: borra solo lo regenerable (cache de clips e intermedios del montaje).
  espacio: () => pedir<Espacio>("/espacio"),
  liberar: (id: string) => pedir<{ liberado: number; total: number; liberable: number }>(`/proyectos/${id}/liberar`, { method: "POST" }),
  liberarTodo: () => pedir<{ liberado: number; proyectos: number; ocupados: string[] }>("/liberar", { method: "POST" }),
  subidos: (id: string) => pedir<{ archivos: Subido[] }>(`/proyectos/${id}/recursos`),
  subir: (id: string, archivos: File[], sub: "" | "images" | "videos" = "") => {
    const fd = new FormData();
    archivos.forEach((a) => fd.append("archivos", a));
    return pedir<{ guardados: string[]; rechazados: string[] }>(`/proyectos/${id}/recursos?sub=${sub}`, { method: "POST", body: fd });
  },
  editor: (id: string) => pedir<DatosEditor>(`/proyectos/${id}/editor`),
  // Regrabar una parte de la voz (tiempos de la voz): ideas de Claude y la grabacion.
  reescribirParte: (id: string, body: { desde: number; hasta: number; texto: string; pedido?: string }) =>
    pedir<{ opciones: string[]; palabras: number }>(`/proyectos/${id}/editor/reescribir`, { method: "POST", ...json(body) }),
  grabarParte: (id: string, body: { desde: number; hasta: number; texto: string }) =>
    pedir<ParteGrabada>(`/proyectos/${id}/editor/grabar`, { method: "POST", ...json(body) }),
  publicar: (id: string) => pedir<DatosPublicar>(`/proyectos/${id}/publicar`),
  plantillasGraficos: () => pedir<{ plantillas: PlantillaGrafico[]; falta: string }>(`/graficos/plantillas`),
  crearGrafico: (id: string, body: DatosGrafico & { duracion: number }) =>
    pedir<GraficoHecho>(`/proyectos/${id}/graficos`, { method: "POST", ...json(body) }),
  ideasGraficos: (id: string) => pedir<{ ideas: IdeaGrafico[]; pedido?: string }>(`/proyectos/${id}/graficos/ideas`),
  proponerGraficos: (id: string, body: { cuantos: number; pedido: string }) =>
    pedir<{ ideas: IdeaGrafico[] }>(`/proyectos/${id}/graficos/ideas`, { method: "POST", ...json(body) }),
  hacerPublicar: (id: string, accion: string, body: Record<string, string>) =>
    pedir<unknown>(`/proyectos/${id}/publicar/${accion}`, { method: "POST", ...json(body) }),
  // Audios del proyecto para las pistas de audio del editor.
  audios: (id: string) => pedir<{ audios: AudioProyecto[] }>(`/proyectos/${id}/audios`),
  subirAudios: (id: string, archivos: File[]) => {
    const fd = new FormData();
    archivos.forEach((a) => fd.append("archivos", a));
    return pedir<{ guardados: string[]; rechazados: string[] }>(`/proyectos/${id}/audios`, { method: "POST", body: fd });
  },
  quitar: (id: string, nombre: string) =>
    pedir<{ ok: boolean }>(`/proyectos/${id}/recursos/${nombre.split("/").map(encodeURIComponent).join("/")}`, { method: "DELETE" }),
};

// Google Flow (solo en la maquina local): imagenes de las escenas generadas en Flow.
export type EstadoEscenaFlow = "lista" | "pendiente" | "error" | "en_curso" | "sin_prompt";
export interface EscenaFlow { escena: number; estado: EstadoEscenaFlow; archivo: string | null; intento: number | null; motivo: string }
export interface EstadoFlow {
  habilitado: boolean; corriendo: boolean; otro_proyecto: boolean; deteniendo: boolean;
  resultado: "fin" | "detenido" | "sin_sesion" | "limite" | "error" | null; motivo: string;
  pasada: number | null; inicio: number | null; fin: number | null;
  cuenta: Record<EstadoEscenaFlow, number>; escenas: EscenaFlow[]; log: string[];
}
export interface InfoFlow { habilitado: boolean; corriendo?: boolean; chrome?: boolean; sesion?: boolean | null; ocupado?: boolean; motivo?: string }

export const flow = {
  info: (comprobar = false) => pedir<InfoFlow>(`/flow${comprobar ? "?comprobar=true" : ""}`),
  conectar: () => pedir<{ ok: boolean }>("/flow/conectar", { method: "POST" }),
  estado: (id: string) => pedir<EstadoFlow>(`/proyectos/${id}/flow`),
  generar: (id: string, reintentar_fallidas = true) =>
    pedir<EstadoFlow>(`/proyectos/${id}/flow/generar`, { method: "POST", ...json({ reintentar_fallidas }) }),
  detener: (id: string, forzar = false) =>
    pedir<EstadoFlow>(`/proyectos/${id}/flow/detener`, { method: "POST", ...json({ forzar }) }),
};

export interface ConceptoMiniatura {
  nombre: string; idea: string; texto: string; prompt: string; prompt_sin_texto: string;
  referencia_escena: number | null;
}
export interface EstadoMiniatura {
  params: { indicaciones: string; texto_en_imagen: boolean; cantidad: number; modelo: string; esfuerzo: string };
  conceptos: ConceptoMiniatura[]; analisis_referencia: string; error: string | null;
  generado: number | null; generando: boolean; referencia: string | null; final: string | null; version: number | null;
}

export const miniatura = {
  ver: (id: string) => pedir<EstadoMiniatura>(`/proyectos/${id}/miniatura`),
  generar: (id: string, params: Partial<EstadoMiniatura["params"]>) =>
    pedir<EstadoMiniatura>(`/proyectos/${id}/miniatura/generar`, { method: "POST", ...json(params) }),
  subir: (id: string, tipo: "referencia" | "final", archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return pedir<EstadoMiniatura>(`/proyectos/${id}/miniatura/${tipo}`, { method: "POST", body: fd });
  },
  quitar: (id: string, tipo: "referencia" | "final") =>
    pedir<EstadoMiniatura>(`/proyectos/${id}/miniatura/${tipo}`, { method: "DELETE" }),
};

export interface VozClonada { id: string; nombre: string; duracion: number | null; transcripcion: string }
export interface VocesClonadas { activo: boolean; voces: VozClonada[]; error: string | null }

export const vozPropia = (id: string, archivo: File) => {
  const fd = new FormData();
  fd.append("audio", archivo, archivo.name);
  return pedir<Vista>(`/proyectos/${id}/voz-propia`, { method: "POST", body: fd });
};

export const clonadas = {
  listar: () => pedir<VocesClonadas>("/voces-clonadas"),
  crear: (audio: Blob, nombre: string, transcripcion = "", archivo = "voz.wav") => {
    const fd = new FormData();
    fd.append("audio", audio, archivo);
    fd.append("nombre", nombre);
    fd.append("transcripcion", transcripcion);
    return pedir<VozClonada>("/voces-clonadas", { method: "POST", body: fd });
  },
};

export interface Turno { rol: "persona" | "asistente"; texto: string; t: number }
export interface Charla { id: string; turnos: Turno[]; pensando: boolean; error: string | null }

export const asistente = {
  preguntar: (pregunta: string, charla?: string | null, proyecto?: string | null) =>
    pedir<Charla>("/asistente", { method: "POST", ...json({ pregunta, charla, proyecto }) }),
  ver: (charla: string) => pedir<Charla>(`/asistente/${charla}`),
};

export const url = {
  archivo: (id: string, ruta: string, v?: number | null) =>
    `${BASE}/proyectos/${id}/archivo/${ruta}${v ? `?v=${Math.round(v)}` : ""}`,
  miniatura: (h: string) => `${BASE}/miniatura/${h}`,
  original: (id: string, h: string) => `${BASE}/proyectos/${id}/original/${h}`,
  ultimoFotograma: (id: string, h: string) => `${BASE}/proyectos/${id}/original/${h}/ultimo-fotograma`,
  descargar: (id: string) => `${BASE}/proyectos/${id}/descargar`,
  scriptJson: (id: string) => `${BASE}/proyectos/${id}/script.json`,
  promptsTxt: (id: string) => `${BASE}/proyectos/${id}/prompts.txt`,
  muestraClonada: (vid: string) => `${BASE}/voces-clonadas/${vid}/audio`,
  descargarMiniatura: (id: string) => `${BASE}/proyectos/${id}/miniatura-descargar`,
  srtVideo: (id: string, idioma = "") => `${BASE}/proyectos/${id}/publicar/subtitulos.srt${idioma ? `?idioma=${idioma}` : ""}`,
};

/** Ultimo fotograma de un clip (PNG) para empezar el siguiente segmento encadenado. */
export async function ultimoFotograma(archivo: File): Promise<Blob> {
  const fd = new FormData();
  fd.append("archivo", archivo);
  const r = await fetch(`${BASE}/herramientas/ultimo-fotograma`, { method: "POST", body: fd });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      msg = (await r.json()).detail || msg;
    } catch {}
    throw new Error(msg);
  }
  return r.blob();
}

export async function listarMusica(): Promise<string[]> {
  try {
    const r = await fetch("/api/motor/musics", { cache: "no-store" });
    const j = await r.json();
    return (j?.data?.files || []).map((f: { file: string }) => f.file).sort();
  } catch {
    return [];
  }
}

export function mmss(s: number | null | undefined) {
  if (s == null || isNaN(s)) return "–";
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}

// ------------------------------------------------------------------ prompts maestros

export interface PasoMaestro {
  n: number; titulo: string; que_hace: string; pregunta: string | null;
  opciones: string[]; respuesta: string; entrega: string[];
}
export interface FichaMaestro {
  nombre: string; categoria: string; resumen: string; herramientas: string[];
  formato: { aspecto?: string; duracion_total_s?: number | null; clip_s?: number | null; escenas?: number | null; duracion_variable?: boolean };
  narracion: { tiene: boolean; idioma?: string; como?: string };
  idiomas?: { prompts?: string; texto_en_imagen?: string | null };
  pasos: PasoMaestro[];
  entregables: { tipo: string; descripcion: string; cantidad?: number | null; idioma?: string }[];
  bloques_fijos: { nombre: string; para_que: string }[];
  reglas_clave: string[];
  estilo_visual: string; audio: string; negativos: string; encaje_estudio: string; advertencias: string[];
}
export interface Maestro {
  id: string; nombre: string; origen: string; creado: number; actualizado: number; caracteres: number;
  estado: "pendiente" | "listo" | "error"; error: string | null; analizando: boolean; portada: boolean;
  ficha: FichaMaestro | null; notas: string;
}
export interface ResumenMaestro {
  id: string; nombre: string; creado: number; actualizado: number; estado: Maestro["estado"]; analizando: boolean;
  portada: boolean; resumen: string; categoria: string; formato: FichaMaestro["formato"]; narracion?: boolean;
}

export const maestros = {
  listar: () => pedir<{ maestros: ResumenMaestro[] }>("/maestros"),
  ver: (id: string) => pedir<Maestro>(`/maestros/${id}`),
  subir: (archivo: File | null, texto = "", nombre = "") => {
    const fd = new FormData();
    if (archivo) fd.append("archivo", archivo);
    fd.append("texto", texto);
    fd.append("nombre", nombre);
    return pedir<Maestro>("/maestros", { method: "POST", body: fd });
  },
  editar: (id: string, cambios: { nombre?: string; notas?: string }) =>
    pedir<Maestro>(`/maestros/${id}`, { method: "PATCH", ...json(cambios) }),
  analizar: (id: string) => pedir<Maestro>(`/maestros/${id}/analizar`, { method: "POST", ...json({}) }),
  borrar: (id: string) => pedir<{ ok: boolean }>(`/maestros/${id}`, { method: "DELETE" }),
  original: async (id: string) => {
    const r = await fetch(`${BASE}/maestros/${id}/original`, { cache: "no-store" });
    return r.text();
  },
  portada: (id: string, v?: number) => `${BASE}/maestros/${id}/portada${v ? `?v=${Math.round(v)}` : ""}`,
  ponerPortada: (id: string, archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return pedir<Maestro>(`/maestros/${id}/portada`, { method: "POST", body: fd });
  },
  quitarPortada: (id: string) => pedir<Maestro>(`/maestros/${id}/portada`, { method: "DELETE" }),
  reemplazarTexto: (id: string, archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return pedir<Maestro>(`/maestros/${id}/texto`, { method: "POST", body: fd });
  },
  exportar: () => `${BASE}/maestros/exportar`,
  importar: (archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return pedir<{ importados: { id: string; nombre: string; nuevo: boolean }[] }>("/maestros/importar", { method: "POST", body: fd });
  },
};

export interface AppTurno { tipo: "texto" | "opcion" | "fin"; opciones: string[]; recomendada: string }
export interface TurnoCreacion { rol: "persona" | "claude"; texto: string; t: number; auto?: boolean; app?: AppTurno }
export interface EscenaEntregable {
  n: number; narracion: string | null; imagen: string | null; video: string | null; duracion_s: number | null;
  continua?: boolean; refs?: string[];
}
export interface Referencia {
  nombre: string; clave: string; tipo: "personaje" | "vehiculo" | "objeto" | "lugar" | "estilo" | "otro";
  prompt: string | null; archivo: string | null; origen: "maestro" | "claude"; imagen: string | null;
  heredada?: boolean;
}
export interface Entregables {
  titulo: string; guion: string | null; escenas: EscenaEntregable[]; miniaturas: string[];
  bloques: { titulo: string; texto: string }[]; referencias?: Referencia[];
}
export interface Creacion {
  id: string; maestro: string; titulo: string; tema: string; modo: "guiado" | "auto"; modelo: string;
  creado: number; actualizado: number; turnos: TurnoCreacion[]; error: string | null; pensando: boolean;
  entregables: Entregables | null; entregables_estado: "preparando" | "listo" | "error" | null; entregables_error: string | null;
  proyectos?: { id: string; narracion: Narracion; t: number }[];
  serie?: string | null; episodio?: number | null;
  serie_info?: { id: string; titulo: string; episodio: number | null } | null;
}
export type Narracion = "propia" | "demostracion" | "libre" | "sin_voz";
export interface ResumenCreacion {
  id: string; titulo: string; creado: number; actualizado: number; pensando: boolean; turnos: number;
  modo: Creacion["modo"]; terminada: boolean; entregables: boolean; serie?: string | null; episodio?: number | null;
}

export interface EpisodioSerie {
  id: string; episodio: number | null; titulo: string; resumen: string; listo: boolean; actualizado: number;
}
export interface Serie {
  id: string; maestro: string; titulo: string; biblia: string; referencias: Referencia[]; episodios: string[];
  episodios_info: EpisodioSerie[]; creado: number; actualizado: number; preparando: boolean; error: string | null;
}
export interface ResumenSerie { id: string; titulo: string; episodios: number; actualizado: number; preparando: boolean }

export const series = {
  listar: (mid: string) => pedir<{ series: ResumenSerie[] }>(`/maestros/${mid}/series`),
  crear: (mid: string, desde: string) => pedir<Serie>(`/maestros/${mid}/series`, { method: "POST", ...json({ desde }) }),
  ver: (mid: string, sid: string) => pedir<Serie>(`/maestros/${mid}/series/${sid}`),
  cambiar: (mid: string, sid: string, cambios: { titulo?: string; biblia?: string; referencias?: Referencia[] }) =>
    pedir<Serie>(`/maestros/${mid}/series/${sid}`, { method: "PATCH", ...json(cambios) }),
  rehacerBiblia: (mid: string, sid: string) => pedir<Serie>(`/maestros/${mid}/series/${sid}/biblia`, { method: "POST" }),
  episodio: (mid: string, sid: string, datos: { tema: string; modo: Creacion["modo"]; modelo: string }) =>
    pedir<Creacion>(`/maestros/${mid}/series/${sid}/episodios`, { method: "POST", ...json(datos) }),
  borrar: (mid: string, sid: string) => pedir<{ ok: boolean }>(`/maestros/${mid}/series/${sid}`, { method: "DELETE" }),
  subirReferencia: (mid: string, sid: string, clave: string, archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return pedir<Serie>(`/maestros/${mid}/series/${sid}/referencias/${clave}`, { method: "POST", body: fd });
  },
  urlReferencia: (mid: string, sid: string, r: Referencia) =>
    `${BASE}/maestros/${mid}/series/${sid}/referencias/${r.clave}?v=${encodeURIComponent(r.imagen || "")}`,
};

export const creaciones = {
  listar: (mid: string) => pedir<{ creaciones: ResumenCreacion[] }>(`/maestros/${mid}/creaciones`),
  crear: (mid: string, datos: { tema: string; modo: Creacion["modo"]; modelo: string }) =>
    pedir<Creacion>(`/maestros/${mid}/creaciones`, { method: "POST", ...json(datos) }),
  ver: (mid: string, cid: string) => pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}`),
  enviar: (mid: string, cid: string, texto: string) =>
    pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/mensaje`, { method: "POST", ...json({ texto }) }),
  reintentar: (mid: string, cid: string) => pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/reintentar`, { method: "POST" }),
  entregables: (mid: string, cid: string) => pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/entregables`, { method: "POST" }),
  cambiar: (mid: string, cid: string, cambios: { titulo?: string; modo?: Creacion["modo"] }) =>
    pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}`, { method: "PATCH", ...json(cambios) }),
  borrar: (mid: string, cid: string) => pedir<{ ok: boolean }>(`/maestros/${mid}/creaciones/${cid}`, { method: "DELETE" }),
  escenas: (mid: string, cid: string, escenas: EscenaEntregable[]) =>
    pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/escenas`, { method: "PUT", ...json({ escenas }) }),
  referencias: (mid: string, cid: string, referencias: Referencia[]) =>
    pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/referencias`, { method: "PUT", ...json({ referencias }) }),
  proponerReferencias: (mid: string, cid: string) =>
    pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/referencias/proponer`, { method: "POST" }),
  subirReferencia: (mid: string, cid: string, clave: string, archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/referencias/${clave}`, { method: "POST", body: fd });
  },
  quitarReferencia: (mid: string, cid: string, clave: string) =>
    pedir<Creacion>(`/maestros/${mid}/creaciones/${cid}/referencias/${clave}`, { method: "DELETE" }),
  urlReferencia: (mid: string, cid: string, r: Referencia) =>
    `${BASE}/maestros/${mid}/creaciones/${cid}/referencias/${r.clave}?v=${encodeURIComponent(r.imagen || "")}`,
  video: (mid: string, cid: string, datos: { narracion: Narracion; aspecto: string; titulo?: string }) =>
    pedir<{ proyecto: { id: string; titulo: string } }>(`/maestros/${mid}/creaciones/${cid}/video`, { method: "POST", ...json(datos) }),
};
