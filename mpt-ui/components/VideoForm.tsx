"use client";

import { useState, useRef, useMemo } from "react";
import {
  Wand2, ChevronDown, ChevronUp, Mic, Music, Type,
  Layers, Clock, Sparkles, Settings, Film, RefreshCw,
  Play, Square, Volume2, Key, Plus, Trash2, Eye, EyeOff,
} from "lucide-react";
import type { TaskResult } from "@/app/page";
import {
  AZURE_VOICES, AZURE_V2_VOICES, SILICONFLOW_VOICES, GEMINI_VOICES, MIMO_VOICES,
  getVoicesForServer, getUniqueLanguages, type TtsServer,
} from "@/lib/voices";
import LogPanel, { makeLog, type LogEntry } from "@/components/LogPanel";

// ─── Sub-fonts list (common ones available in the repo) ──────────────────────
const FONTS = [
  "MicrosoftYaHeiBold.ttc",
  "MicrosoftYaHeiNormal.ttc",
  "STHeitiMedium.ttc",
  "STHeitiLight.ttc",
  "Charm-Bold.ttf",
  "Charm-Regular.ttf",
  "UTM Kabel KT.ttf",
];

// ─── Estilos compartidos ──────────────────────────────────────────────────────
const CARD: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 20,
  padding: 24,
};
const LABEL: React.CSSProperties = {
  display: "block", fontSize: 12, fontWeight: 600,
  color: "#a1a1aa", textTransform: "uppercase" as const, letterSpacing: "0.05em",
  marginBottom: 8,
};
const INPUT: React.CSSProperties = {
  width: "100%", padding: "11px 14px", borderRadius: 10, fontSize: 14,
  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
  color: "#ffffff", fontFamily: "inherit",
};
const SELECT: React.CSSProperties = {
  ...INPUT, appearance: "none" as const, cursor: "pointer",
  background: "#0d0d0d", WebkitAppearance: "none" as const,
};

// ─── Pequeños helpers ─────────────────────────────────────────────────────────
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label style={LABEL}>{label}</label>{children}</div>;
}

function Row2({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>{children}</div>;
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!value)} style={{
      position: "relative", width: 40, height: 22, borderRadius: 11,
      border: "none", background: value ? "#8b5cf6" : "#27272a",
      transition: "background 0.2s", flexShrink: 0,
    }}>
      <div style={{
        position: "absolute", top: 3, width: 16, height: 16,
        borderRadius: "50%", background: "#fff", transition: "left 0.2s",
        left: value ? "calc(100% - 19px)" : 3,
      }} />
    </button>
  );
}

function SectionToggle({
  open, onToggle, icon: Icon, title, color = "#a78bfa", badge,
}: {
  open: boolean; onToggle: () => void;
  icon: React.ElementType; title: string; color?: string; badge?: React.ReactNode;
}) {
  return (
    <button type="button" onClick={onToggle} style={{
      width: "100%", display: "flex", alignItems: "center",
      justifyContent: "space-between", background: "none", border: "none", padding: 0,
      marginBottom: open ? 20 : 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Icon size={15} color={color} />
        <span style={{ fontSize: 14, fontWeight: 700, color: "#e4e4e7" }}>{title}</span>
        {badge}
      </div>
      {open ? <ChevronUp size={16} color="#52525b" /> : <ChevronDown size={16} color="#52525b" />}
    </button>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────
interface Props {
  onStart: () => void;
  onGenerated: (result: TaskResult) => void;
  onError: (msg: string) => void;
  onLogsChange?: (logs: LogEntry[]) => void;
}

// ─── Componente principal ─────────────────────────────────────────────────────
export default function VideoForm({ onStart, onGenerated, onError, onLogsChange }: Props) {

  // ── Guión ──────────────────────────────────────────────────────────────────
  const [subject, setSubject]               = useState("");
  const [videoLanguage, setVideoLanguage]   = useState("");
  const [paragraphs, setParagraphs]         = useState(1);
  const [scriptPrompt, setScriptPrompt]     = useState("");
  const [useCustomSys, setUseCustomSys]     = useState(false);
  const [customSysPrompt, setCustomSysPrompt] = useState("");
  const [generatedScript, setGeneratedScript] = useState("");
  const [videoTerms, setVideoTerms]         = useState("");
  const [generatingScript, setGeneratingScript] = useState(false);
  const [generatingTerms, setGeneratingTerms] = useState(false);

  // ── Video ──────────────────────────────────────────────────────────────────
  const [videoSource, setVideoSource]       = useState("pexels");
  const [aspect, setAspect]                 = useState<"9:16" | "16:9" | "1:1">("9:16");
  const [concatMode, setConcatMode]         = useState("random");
  const [transition, setTransition]         = useState("none");
  const [clipDuration, setClipDuration]     = useState(3);
  const [videoCount, setVideoCount]         = useState(1);
  const [codec, setCodec]                   = useState("libx264");

  // ── Medios locales ─────────────────────────────────────────────────────────
  interface LocalMaterial { name: string; size: number; file: string; }
  const [localMaterials, setLocalMaterials]         = useState<LocalMaterial[]>([]);
  const [selectedMaterials, setSelectedMaterials]   = useState<string[]>([]);
  const [localLoading, setLocalLoading]             = useState(false);
  const [localUploading, setLocalUploading]         = useState(false);
  const [localUploadMsg, setLocalUploadMsg]         = useState("");
  const localFileRef = useRef<HTMLInputElement>(null);

  const loadLocalMaterials = async () => {
    setLocalLoading(true);
    try {
      const res = await fetch("/api/mpt/v1/video_materials");
      const data = await res.json();
      setLocalMaterials(data?.data?.files ?? []);
    } catch { /* ignore */ } finally { setLocalLoading(false); }
  };

  const handleLocalUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setLocalUploading(true);
    setLocalUploadMsg("");
    let uploaded = 0;
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      try {
        const res = await fetch("/api/mpt/v1/video_materials", { method: "POST", body: form });
        if (res.ok) uploaded++;
      } catch { /* skip */ }
    }
    setLocalUploadMsg(`✓ ${uploaded} archivo${uploaded !== 1 ? "s" : ""} subido${uploaded !== 1 ? "s" : ""}`);
    await loadLocalMaterials();
    setLocalUploading(false);
    if (localFileRef.current) localFileRef.current.value = "";
  };

  const toggleMaterial = (filename: string) => {
    setSelectedMaterials((prev) =>
      prev.includes(filename) ? prev.filter((f) => f !== filename) : [...prev, filename]
    );
  };

  // ── Audio / TTS ────────────────────────────────────────────────────────────
  const [ttsServer, setTtsServer]           = useState<TtsServer>("azure-tts-v1");
  const [voiceLangFilter, setVoiceLangFilter] = useState("es-ES");
  const [voice, setVoice]                   = useState("es-ES-ElviraNeural-Female");
  const [voiceVolume, setVoiceVolume]       = useState(1.0);
  const [voiceRate, setVoiceRate]           = useState(1.0);
  const [bgmType, setBgmType]               = useState("random");
  const [bgmVolume, setBgmVolume]           = useState(0.2);
  // TTS extra keys
  const [azureRegion, setAzureRegion]       = useState("");
  const [azureKey, setAzureKey]             = useState("");
  const [siliconflowKey, setSiliconflowKey] = useState("");
  const [mimoKey, setMimoKey]               = useState("");
  // Preview de voz
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewUrl, setPreviewUrl]         = useState<string | null>(null);
  const [previewError, setPreviewError]     = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Logs visuales
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const addLog = (level: LogEntry["level"], msg: string) =>
    setLogs((prev) => {
      const next = [...prev, makeLog(level, msg)];
      onLogsChange?.(next);
      return next;
    });

  // ── Subtítulos ─────────────────────────────────────────────────────────────
  const [subtitles, setSubtitles]           = useState(true);
  const [fontName, setFontName]             = useState(FONTS[0]);
  const [subtitlePos, setSubtitlePos]       = useState("bottom");
  const [customPos, setCustomPos]           = useState(70);
  const [textColor, setTextColor]           = useState("#FFFFFF");
  const [fontSize, setFontSize]             = useState(60);
  const [strokeColor, setStrokeColor]       = useState("#000000");
  const [strokeWidth, setStrokeWidth]       = useState(1.5);
  const [subtitleBg, setSubtitleBg]         = useState(true);
  const [bgColor, setBgColor]               = useState("#000000");
  const [roundedBg, setRoundedBg]           = useState(false);

  // ── API Keys panel ─────────────────────────────────────────────────────────
  const [pexelsNewKey, setPexelsNewKey]     = useState("");
  const [pixabayNewKey, setPixabayNewKey]   = useState("");
  const [showKeys, setShowKeys]             = useState(false);

  // ── Secciones abiertas/cerradas ────────────────────────────────────────────
  const [openScript, setOpenScript]         = useState(true);
  const [openVideo, setOpenVideo]           = useState(true);
  const [openAudio, setOpenAudio]           = useState(true);
  const [openSubs, setOpenSubs]             = useState(false);
  const [openConfig, setOpenConfig]         = useState(false);

  const [loading, setLoading]               = useState(false);

  // ── Voces disponibles según servidor + filtro de idioma ───────────────────
  const availableVoices = useMemo(() => getVoicesForServer(ttsServer), [ttsServer]);
  const langs           = useMemo(() => getUniqueLanguages(availableVoices), [availableVoices]);
  const filteredVoices  = useMemo(
    () => ttsServer === "no-voice" ? [] : availableVoices.filter((v) => v.lang === voiceLangFilter || langs.length === 1),
    [availableVoices, voiceLangFilter, langs]
  );

  // Cuando cambia el servidor TTS, resetear idioma y voz
  const handleTtsServerChange = (s: TtsServer) => {
    setTtsServer(s);
    setPreviewUrl(null);
    setPreviewError(null);
    if (s === "no-voice") { setVoice(""); return; }
    const voices = getVoicesForServer(s);
    const firstLang = voices[0]?.lang ?? "";
    setVoiceLangFilter(firstLang);
    setVoice(voices[0]?.value ?? "");
  };

  // Cuando cambia idioma, seleccionar primera voz de ese idioma
  const handleLangChange = (lang: string) => {
    setVoiceLangFilter(lang);
    setPreviewUrl(null);
    setPreviewError(null);
    const first = availableVoices.find((v) => v.lang === lang);
    if (first) setVoice(first.value);
  };

  // ── Generar guión ──────────────────────────────────────────────────────────
  const handleGenerateScript = async () => {
    if (!subject.trim()) return;
    setGeneratingScript(true);
    addLog("info", `Generando guión para: "${subject.trim()}" (${paragraphs} párrafo${paragraphs > 1 ? "s" : ""})`);
    try {
      const res = await fetch("/api/mpt/v1/scripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_subject: subject.trim(),
          video_language: videoLanguage || undefined,
          paragraph_number: paragraphs,
          video_script_prompt: scriptPrompt || undefined,
          custom_system_prompt: useCustomSys ? customSysPrompt : undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const script = data?.data?.video_script ?? "";
      setGeneratedScript(script);
      addLog("success", `Guión generado (${script.length} chars)`);

      // Auto-generar términos si hay guión
      if (script) {
        setGeneratingTerms(true);
        addLog("info", "Generando keywords automáticamente…");
        try {
          const res2 = await fetch("/api/mpt/v1/terms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ video_subject: subject.trim(), video_script: script, amount: 5 }),
          });
          if (res2.ok) {
            const d2 = await res2.json();
            const terms = d2?.data?.video_terms;
            if (Array.isArray(terms)) { setVideoTerms(terms.join(", ")); addLog("success", `Keywords: ${terms.join(", ")}`); }
            else if (typeof terms === "string") { setVideoTerms(terms); addLog("success", `Keywords: ${terms}`); }
          }
        } finally { setGeneratingTerms(false); }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Error desconocido";
      addLog("error", `Error generando guión: ${msg}`);
    } finally { setGeneratingScript(false); }
  };

  // ── Generar solo términos ──────────────────────────────────────────────────
  const handleGenerateTerms = async () => {
    if (!subject.trim()) return;
    setGeneratingTerms(true);
    addLog("info", "Generando keywords de búsqueda…");
    try {
      const res = await fetch("/api/mpt/v1/terms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_subject: subject.trim(),
          video_script: generatedScript || subject.trim(),
          amount: 5,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const terms = data?.data?.video_terms;
      if (Array.isArray(terms)) { setVideoTerms(terms.join(", ")); addLog("success", `Keywords: ${terms.join(", ")}`); }
      else if (typeof terms === "string") { setVideoTerms(terms); addLog("success", `Keywords: ${terms}`); }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Error desconocido";
      addLog("error", `Error generando keywords: ${msg}`);
    } finally { setGeneratingTerms(false); }
  };

  // ── Preview de voz ─────────────────────────────────────────────────────────
  const handlePreviewVoice = async () => {
    if (!voice || ttsServer === "no-voice") return;
    setPreviewLoading(true);
    setPreviewUrl(null);
    setPreviewError(null);
    addLog("info", `Iniciando preview de voz: ${voice}`);
    try {
      const text = generatedScript.slice(0, 300) || subject.trim() || "Hola, esta es una muestra de voz generada con inteligencia artificial.";
      addLog("debug", `Texto a sintetizar (${text.length} chars): "${text.slice(0, 80)}…"`);
      const res = await fetch("/api/mpt/v1/audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_script: text,
          voice_name: voice,
          voice_rate: voiceRate,
          voice_volume: voiceVolume,
          bgm_type: "random",
          bgm_volume: 0,
          video_source: "local",
        }),
      });
      if (!res.ok) {
        const errBody = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${errBody.slice(0, 200)}`);
      }
      const data = await res.json();
      const taskId = data?.data?.task_id;
      if (!taskId) throw new Error("El servidor no devolvió task_id");
      addLog("info", `Tarea creada: ${taskId.slice(0, 8)}… — esperando TTS…`);

      // Esperar a que termine el audio (poll cada 2s, hasta 60 intentos = 2 min)
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const r2 = await fetch(`/api/mpt/v1/tasks/${taskId}`);
        if (!r2.ok) { addLog("warn", `Poll ${i+1}: respuesta ${r2.status}`); continue; }
        const d2 = await r2.json();
        const state = d2?.data?.state;
        const progress = d2?.data?.progress ?? 0;
        addLog("debug", `Poll ${i+1}: state=${state} progress=${progress}%`);
        if (state === 1) {
          // El backend guarda el audio en "audio_file", no en "videos"
          const rawPath: string = d2?.data?.audio_file ?? d2?.data?.videos?.[0] ?? "";
          addLog("debug", `audio_file raw: ${rawPath || "(vacío)"}`);
          if (rawPath) {
            const normalized = rawPath.replace(/\\/g, "/");
            const match = normalized.match(/([0-9a-f\-]{36}\/[^/]+)$/i);
            const streamPath = match ? match[1] : `${taskId}/audio.mp3`;
            addLog("success", `Audio listo → /stream/${streamPath}`);
            setPreviewUrl(`/api/mpt/v1/stream/${streamPath}`);
            // Borrar carpeta de audio del disco después de 30s
            setTimeout(() => {
              fetch(`/api/library?taskId=${taskId}`, { method: "DELETE" }).catch(() => {});
            }, 30000);
          } else {
            throw new Error("Audio generado pero audio_file está vacío");
          }
          break;
        }
        if (state === -1) {
          const errMsg = d2?.data?.message || "Error al sintetizar voz";
          throw new Error(errMsg);
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error desconocido";
      addLog("error", msg);
      setPreviewError(msg);
    } finally { setPreviewLoading(false); }
  };

  // ── Enviar video ───────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim()) return;
    setLoading(true);
    setLogs([]);
    onLogsChange?.([]);
    addLog("info", `Iniciando generación: "${subject.trim()}"`);
    addLog("info", `Config: ${paragraphs} párrafo(s), ${aspect}, ${videoSource}, voz=${voice || "sin voz"}`);
    onStart();
    try {
      const res = await fetch("/api/mpt/v1/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_subject: subject.trim(),
          video_script: generatedScript.trim() || undefined,
          video_terms: videoTerms.trim() || undefined,
          video_aspect: aspect,
          video_count: videoCount,
          video_clip_duration: clipDuration,
          video_concat_mode: concatMode,
          video_transition_mode: transition === "none" ? null : transition,
          video_source: videoSource,
          video_materials: videoSource === "local" && selectedMaterials.length > 0
            ? selectedMaterials.map((f) => ({ provider: "local", url: f, duration: 0 }))
            : undefined,
          video_language: videoLanguage || undefined,
          video_codec: codec,
          paragraph_number: paragraphs,
          video_script_prompt: scriptPrompt || undefined,
          custom_system_prompt: useCustomSys ? customSysPrompt : undefined,
          voice_name: ttsServer !== "no-voice" ? voice : undefined,
          voice_volume: voiceVolume,
          voice_rate: voiceRate,
          bgm_type: bgmType,
          bgm_volume: bgmVolume,
          subtitle_enabled: subtitles,
          subtitle_position: subtitlePos,
          custom_position: subtitlePos === "custom" ? customPos : undefined,
          font_name: fontName,
          text_fore_color: textColor,
          font_size: fontSize,
          stroke_color: strokeColor,
          stroke_width: strokeWidth,
          text_background_color: subtitleBg ? bgColor : false,
          rounded_subtitle_background: roundedBg,
          n_threads: 2,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string })?.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      const taskId = data?.data?.task_id;
      if (!taskId) throw new Error("No se recibió task_id del servidor");
      await pollTask(taskId);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Error desconocido");
    } finally { setLoading(false); }
  };

  const pollTask = async (taskId: string) => {
    addLog("info", `Tarea creada: ${taskId.slice(0, 8)}… — monitoreando progreso…`);
    addLog("debug", `FFmpeg puede tardar 5–15 min dependiendo de los párrafos y subtítulos`);
    let lastProgress = -1;
    // 360 intentos × 5s = 30 minutos máximo
    for (let i = 0; i < 360; i++) {
      await new Promise((r) => setTimeout(r, 5000));
      const res = await fetch(`/api/mpt/v1/tasks/${taskId}`);
      if (!res.ok) { addLog("warn", `Poll ${i+1}: HTTP ${res.status}`); continue; }
      const data = await res.json();
      const taskData = data?.data ?? data;
      const state = taskData?.state;
      const progress = taskData?.progress ?? 0;
      if (progress !== lastProgress) {
        const elapsed = Math.round((i * 5) / 60);
        const msg = progress >= 75
          ? `Progreso: ${progress}% — FFmpeg ensamblando video${elapsed > 0 ? ` (${elapsed} min transcurridos)` : ""}…`
          : `Progreso: ${progress}%`;
        addLog("info", msg);
        lastProgress = progress;
      }
      // TASK_STATE_COMPLETE = 1
      if (state === 1) {
        const videos: string[] = taskData?.videos ?? [];
        addLog("success", `¡Video listo! ${videos.length} archivo(s) generado(s)`);
        onGenerated({ taskId, videos });
        return;
      }
      // TASK_STATE_FAILED = -1
      if (state === -1) {
        const errMsg = taskData?.message || "La generación falló (state=-1)";
        addLog("error", errMsg);
        throw new Error(errMsg);
      }
    }
    throw new Error("Tiempo de espera agotado (30 min). El video puede haberse generado — revisa 'Mis videos'.");
  };

  const durationLabel = paragraphs <= 2 ? "~40–60 seg" : paragraphs <= 4 ? "~80–120 seg" : paragraphs <= 6 ? "~2–3 min" : "~3–5 min";

  // ─── RENDER ──────────────────────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14, paddingTop: 36 }}>

      {/* HERO */}
      <div style={{ textAlign: "center", paddingBottom: 12 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 14px", borderRadius: 99, background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)", marginBottom: 16 }}>
          <Sparkles size={13} color="#a78bfa" />
          <span style={{ fontSize: 13, color: "#a78bfa", fontWeight: 500 }}>IA Generativa de Video</span>
        </div>
        <h1 style={{ fontSize: 38, fontWeight: 800, lineHeight: 1.15, letterSpacing: "-0.02em", marginBottom: 10 }}>
          <span className="gradient-text">Genera videos virales</span>
          <br />
          <span style={{ color: "#fff" }}>con inteligencia artificial</span>
        </h1>
        <p style={{ color: "#71717a", fontSize: 15, maxWidth: 500, margin: "0 auto", lineHeight: 1.6 }}>
          Escribe un tema y la IA generará el guión, descargará clips, añadirá voz y subtítulos automáticamente.
        </p>
      </div>

      {/* ══════════════════════════════ GUIÓN ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle open={openScript} onToggle={() => setOpenScript(!openScript)} icon={Sparkles} title="Guión del video" />
        {openScript && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            <Field label="Tema del video *">
              <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} required
                placeholder="Ej: 3 señales de que tu abundancia está a punto de llegar"
                style={INPUT} />
            </Field>

            <Row2>
              <Field label="Idioma del guión">
                <select value={videoLanguage} onChange={(e) => setVideoLanguage(e.target.value)} style={SELECT}>
                  <option value="">Auto detectar</option>
                  <option value="es-ES">Español</option>
                  <option value="en-US">English</option>
                  <option value="pt-BR">Português</option>
                  <option value="de-DE">Deutsch</option>
                  <option value="fr-FR">Français</option>
                  <option value="zh-CN">中文</option>
                  <option value="ja-JP">日本語</option>
                  <option value="ko-KR">한국어</option>
                  <option value="ru-RU">Русский</option>
                  <option value="ar-SA">العربية</option>
                  <option value="hi-IN">हिन्दी</option>
                  <option value="vi-VN">Tiếng Việt</option>
                  <option value="th-TH">ภาษาไทย</option>
                  <option value="tr-TR">Türkçe</option>
                </select>
              </Field>
              <Field label={`Número de párrafos · ${durationLabel}`}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {[1,2,3,4,5,6,7,8].map((p) => (
                    <button key={p} type="button" onClick={() => setParagraphs(p)} style={{
                      width: 34, height: 34, borderRadius: 8, border: "none",
                      background: paragraphs === p ? "#8b5cf6" : "rgba(255,255,255,0.06)",
                      color: paragraphs === p ? "#fff" : "#71717a", fontWeight: 700, fontSize: 14,
                    }}>{p}</button>
                  ))}
                </div>
              </Field>
            </Row2>

            <Field label="Instrucciones adicionales para el guión (opcional, máx. 2000 chars)">
              <textarea value={scriptPrompt} onChange={(e) => setScriptPrompt(e.target.value)}
                placeholder="Ej: Usa tono motivacional, incluye 3 puntos con ejemplos reales..."
                rows={2} maxLength={2000} style={{ ...INPUT, resize: "vertical" }} />
            </Field>

            {/* Custom system prompt */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <span style={{ fontSize: 13, color: "#a1a1aa" }}>Usar prompt de sistema personalizado</span>
              <Toggle value={useCustomSys} onChange={setUseCustomSys} />
            </div>
            {useCustomSys && (
              <Field label="Prompt del sistema (máx. 8000 chars)">
                <textarea value={customSysPrompt} onChange={(e) => setCustomSysPrompt(e.target.value)}
                  placeholder="Prompt de sistema para la IA..."
                  rows={4} maxLength={8000} style={{ ...INPUT, resize: "vertical" }} />
              </Field>
            )}

            {/* Botones guión */}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button type="button" onClick={handleGenerateScript} disabled={!subject.trim() || generatingScript}
                style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 10,
                  border: "1px solid rgba(139,92,246,0.35)", background: "rgba(139,92,246,0.12)", color: "#c4b5fd",
                  fontSize: 14, fontWeight: 600 }}>
                {generatingScript
                  ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} />
                  : <Wand2 size={14} />}
                {generatingScript ? "Generando guión…" : "Generar guión con IA"}
              </button>
              <button type="button" onClick={handleGenerateTerms} disabled={!subject.trim() || generatingTerms}
                style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 10,
                  border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.05)", color: "#a1a1aa",
                  fontSize: 14, fontWeight: 600 }}>
                {generatingTerms
                  ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} />
                  : <Sparkles size={14} />}
                {generatingTerms ? "Generando…" : "Generar solo keywords"}
              </button>
            </div>

            <Field label="Guión del video (editable — vacío = la IA lo genera al crear el video)">
              <textarea value={generatedScript} onChange={(e) => setGeneratedScript(e.target.value)}
                placeholder="El guión aparecerá aquí, o escribe el tuyo..."
                rows={7} style={{ ...INPUT, resize: "vertical" }} />
            </Field>

            <Field label="Keywords / términos de búsqueda de clips (editable)">
              <input type="text" value={videoTerms} onChange={(e) => setVideoTerms(e.target.value)}
                placeholder="nature, abundance, sunrise, meditation..."
                style={INPUT} />
            </Field>
          </div>
        )}
      </div>

      {/* ══════════════════════════════ VIDEO ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle open={openVideo} onToggle={() => setOpenVideo(!openVideo)} icon={Film} title="Configuración de video" color="#22d3ee" />
        {openVideo && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Aspect ratio */}
            <Field label="Formato (aspect ratio)">
              <div style={{ display: "flex", gap: 10 }}>
                {([
                  { ratio: "9:16", sub: "TikTok / Reels", w: 22, h: 38 },
                  { ratio: "16:9", sub: "YouTube",        w: 38, h: 22 },
                  { ratio: "1:1",  sub: "Instagram",      w: 30, h: 30 },
                ] as const).map(({ ratio, sub, w, h }) => {
                  const active = aspect === ratio;
                  return (
                    <button key={ratio} type="button" onClick={() => setAspect(ratio)} style={{
                      flex: 1, padding: "14px 8px", borderRadius: 12,
                      border: active ? "1px solid rgba(139,92,246,0.5)" : "1px solid rgba(255,255,255,0.07)",
                      background: active ? "rgba(139,92,246,0.12)" : "rgba(255,255,255,0.03)",
                      display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                    }}>
                      <div style={{ width: w, height: h, borderRadius: 4, background: active ? "#8b5cf6" : "#3f3f46" }} />
                      <span style={{ fontSize: 13, fontWeight: 700, color: active ? "#c4b5fd" : "#71717a" }}>{ratio}</span>
                      <span style={{ fontSize: 11, color: active ? "#a78bfa" : "#52525b" }}>{sub}</span>
                    </button>
                  );
                })}
              </div>
            </Field>

            <Row2>
              <Field label="Fuente de clips">
                <select value={videoSource} onChange={(e) => {
                  setVideoSource(e.target.value);
                  if (e.target.value === "local") loadLocalMaterials();
                }} style={SELECT}>
                  <option value="pexels" style={{ background: "#0d0d0d" }}>Pexels</option>
                  <option value="pixabay" style={{ background: "#0d0d0d" }}>Pixabay</option>
                  <option value="local" style={{ background: "#0d0d0d" }}>Local (archivos propios)</option>
                </select>
              </Field>
              <Field label="Videos a generar simultáneamente">
                <select value={videoCount} onChange={(e) => setVideoCount(Number(e.target.value))} style={SELECT}>
                  {[1,2,3,4,5].map((n) => <option key={n} value={n} style={{ background: "#0d0d0d" }}>{n} video{n > 1 ? "s" : ""}</option>)}
                </select>
              </Field>
            </Row2>

            {/* ── Medios locales ── */}
            {videoSource === "local" && (
              <div style={{ padding: 18, borderRadius: 14, background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.15)" }}>
                {/* Info de requisitos */}
                <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 10, background: "rgba(6,182,212,0.07)", border: "1px solid rgba(6,182,212,0.15)" }}>
                  <p style={{ fontSize: 12, color: "#67e8f9", fontWeight: 600, marginBottom: 4 }}>Requisitos para videos locales</p>
                  <ul style={{ fontSize: 11, color: "#71717a", lineHeight: 1.8, margin: 0, paddingLeft: 16 }}>
                    <li>Formatos: <strong style={{ color: "#a1a1aa" }}>MP4, MOV, AVI, MKV, FLV</strong> (también JPG, PNG para imágenes)</li>
                    <li>Resolución recomendada: <strong style={{ color: "#a1a1aa" }}>1920×1080 o superior</strong></li>
                    <li>Duración por clip: <strong style={{ color: "#a1a1aa" }}>mínimo 3–5 segundos</strong></li>
                    <li>Total de clips: suficiente para cubrir la duración del audio (~45s por párrafo)</li>
                    <li>Sin audio obligatorio (el backend usa tu voz TTS)</li>
                  </ul>
                </div>

                {/* Upload */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                  <input
                    ref={localFileRef}
                    type="file"
                    accept="video/mp4,video/quicktime,video/avi,video/x-matroska,video/x-flv,image/jpeg,image/png"
                    multiple
                    onChange={handleLocalUpload}
                    style={{ display: "none" }}
                  />
                  <button
                    type="button"
                    onClick={() => localFileRef.current?.click()}
                    disabled={localUploading}
                    style={{
                      display: "flex", alignItems: "center", gap: 7,
                      padding: "9px 18px", borderRadius: 10, border: "1px solid rgba(139,92,246,0.3)",
                      background: "rgba(139,92,246,0.12)", color: "#a78bfa",
                      fontSize: 13, fontWeight: 600, cursor: "pointer",
                    }}
                  >
                    {localUploading ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} /> : <Plus size={14} />}
                    {localUploading ? "Subiendo…" : "Subir videos"}
                  </button>
                  <button
                    type="button"
                    onClick={loadLocalMaterials}
                    disabled={localLoading}
                    style={{
                      padding: "9px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.08)",
                      background: "rgba(255,255,255,0.04)", color: "#71717a",
                      fontSize: 13, cursor: "pointer",
                    }}
                  >
                    <RefreshCw size={13} style={localLoading ? { animation: "spin-slow 1s linear infinite" } : {}} />
                  </button>
                  {localUploadMsg && <span style={{ fontSize: 12, color: "#34d399" }}>{localUploadMsg}</span>}
                </div>

                {/* Lista de materiales */}
                {localMaterials.length === 0 ? (
                  <p style={{ fontSize: 13, color: "#52525b", textAlign: "center", padding: "16px 0" }}>
                    {localLoading ? "Cargando…" : "No hay videos subidos. Sube al menos un clip."}
                  </p>
                ) : (
                  <>
                    <p style={{ fontSize: 11, color: "#52525b", marginBottom: 8 }}>
                      Selecciona los clips a usar ({selectedMaterials.length} seleccionados):
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                      {localMaterials.map((m) => {
                        const selected = selectedMaterials.includes(m.file);
                        const sizeMb = (m.size / (1024 * 1024)).toFixed(1);
                        return (
                          <div
                            key={m.file}
                            onClick={() => toggleMaterial(m.file)}
                            style={{
                              display: "flex", alignItems: "center", justifyContent: "space-between",
                              padding: "9px 12px", borderRadius: 10, cursor: "pointer",
                              background: selected ? "rgba(139,92,246,0.12)" : "rgba(255,255,255,0.03)",
                              border: `1px solid ${selected ? "rgba(139,92,246,0.35)" : "rgba(255,255,255,0.07)"}`,
                              transition: "all 0.15s",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <div style={{
                                width: 16, height: 16, borderRadius: 4, flexShrink: 0,
                                border: `2px solid ${selected ? "#8b5cf6" : "#3f3f46"}`,
                                background: selected ? "#8b5cf6" : "transparent",
                                display: "flex", alignItems: "center", justifyContent: "center",
                              }}>
                                {selected && <span style={{ color: "#fff", fontSize: 10, lineHeight: 1 }}>✓</span>}
                              </div>
                              <span style={{ fontSize: 12, color: selected ? "#e4e4e7" : "#71717a", wordBreak: "break-all" }}>
                                {m.name}
                              </span>
                            </div>
                            <span style={{ fontSize: 11, color: "#52525b", flexShrink: 0, marginLeft: 8 }}>
                              {sizeMb} MB
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                      <button type="button" onClick={() => setSelectedMaterials(localMaterials.map((m) => m.file))}
                        style={{ fontSize: 11, color: "#a78bfa", background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                        Seleccionar todo
                      </button>
                      <span style={{ color: "#3f3f46" }}>·</span>
                      <button type="button" onClick={() => setSelectedMaterials([])}
                        style={{ fontSize: 11, color: "#52525b", background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                        Deseleccionar todo
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            <Row2>
              <Field label="Orden de clips">
                <select value={concatMode} onChange={(e) => setConcatMode(e.target.value)} style={SELECT}>
                  <option value="random" style={{ background: "#0d0d0d" }}>Aleatorio</option>
                  <option value="sequential" style={{ background: "#0d0d0d" }}>Secuencial</option>
                </select>
              </Field>
              <Field label="Transición entre clips">
                <select value={transition} onChange={(e) => setTransition(e.target.value)} style={SELECT}>
                  <option value="none" style={{ background: "#0d0d0d" }}>Sin transición</option>
                  <option value="Shuffle" style={{ background: "#0d0d0d" }}>Shuffle</option>
                  <option value="FadeIn" style={{ background: "#0d0d0d" }}>Fade In</option>
                  <option value="FadeOut" style={{ background: "#0d0d0d" }}>Fade Out</option>
                  <option value="SlideIn" style={{ background: "#0d0d0d" }}>Slide In</option>
                  <option value="SlideOut" style={{ background: "#0d0d0d" }}>Slide Out</option>
                </select>
              </Field>
            </Row2>

            <Row2>
              <Field label={`Duración de cada clip · ${clipDuration} seg`}>
                <input type="range" min={2} max={10} step={1} value={clipDuration}
                  onChange={(e) => setClipDuration(Number(e.target.value))} />
              </Field>
              <Field label="Codec de video">
                <select value={codec} onChange={(e) => setCodec(e.target.value)} style={SELECT}>
                  <option value="libx264" style={{ background: "#0d0d0d" }}>libx264 — CPU (universal)</option>
                  <option value="h264_nvenc" style={{ background: "#0d0d0d" }}>h264_nvenc — NVIDIA</option>
                  <option value="h264_amf" style={{ background: "#0d0d0d" }}>h264_amf — AMD</option>
                  <option value="h264_qsv" style={{ background: "#0d0d0d" }}>h264_qsv — Intel QSV</option>
                  <option value="h264_mf" style={{ background: "#0d0d0d" }}>h264_mf — Windows MF</option>
                </select>
              </Field>
            </Row2>
          </div>
        )}
      </div>

      {/* ══════════════════════════════ AUDIO / VOZ ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle open={openAudio} onToggle={() => setOpenAudio(!openAudio)} icon={Mic} title="Voz y audio" color="#34d399" />
        {openAudio && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Servidor TTS */}
            <Field label="Servidor de síntesis de voz (TTS)">
              <select value={ttsServer} onChange={(e) => handleTtsServerChange(e.target.value as TtsServer)} style={SELECT}>
                <option value="no-voice" style={{ background: "#0d0d0d" }}>Sin voz</option>
                <option value="azure-tts-v1" style={{ background: "#0d0d0d" }}>Azure TTS V1 (gratis, recomendado)</option>
                <option value="azure-tts-v2" style={{ background: "#0d0d0d" }}>Azure TTS V2 (multilingüe, requiere API key)</option>
                <option value="siliconflow" style={{ background: "#0d0d0d" }}>SiliconFlow TTS</option>
                <option value="gemini-tts" style={{ background: "#0d0d0d" }}>Google Gemini TTS</option>
                <option value="mimo-tts" style={{ background: "#0d0d0d" }}>Xiaomi MiMo TTS</option>
              </select>
            </Field>

            {/* Claves API condicionales */}
            {ttsServer === "azure-tts-v2" && (
              <Row2>
                <Field label="Azure Speech Region">
                  <input type="text" value={azureRegion} onChange={(e) => setAzureRegion(e.target.value)}
                    placeholder="eastus" style={INPUT} />
                </Field>
                <Field label="Azure Speech Key">
                  <input type="password" value={azureKey} onChange={(e) => setAzureKey(e.target.value)}
                    placeholder="••••••••" style={INPUT} />
                </Field>
              </Row2>
            )}
            {ttsServer === "siliconflow" && (
              <Field label="SiliconFlow API Key">
                <input type="password" value={siliconflowKey} onChange={(e) => setSiliconflowKey(e.target.value)}
                  placeholder="••••••••" style={INPUT} />
              </Field>
            )}
            {ttsServer === "mimo" && (
              <Field label="MiMo API Key">
                <input type="password" value={mimoKey} onChange={(e) => setMimoKey(e.target.value)}
                  placeholder="••••••••" style={INPUT} />
              </Field>
            )}

            {/* Selector de voz */}
            {ttsServer !== "no-voice" && (
              <>
                {/* Filtro de idioma (solo para Azure V1 que tiene muchos) */}
                {(ttsServer === "azure-tts-v1" || ttsServer === "azure-tts-v2") && langs.length > 1 && (
                  <Field label="Filtrar voces por idioma">
                    <select value={voiceLangFilter} onChange={(e) => handleLangChange(e.target.value)} style={SELECT}>
                      {langs.map((l) => <option key={l} value={l} style={{ background: "#0d0d0d" }}>{l}</option>)}
                    </select>
                  </Field>
                )}

                <Field label="Voz del narrador">
                  <select value={voice} onChange={(e) => setVoice(e.target.value)} style={SELECT}>
                    {filteredVoices.map((v) => (
                      <option key={v.value} value={v.value} style={{ background: "#0d0d0d" }}>
                        {v.label} ({v.gender === "Female" ? "♀" : "♂"})
                      </option>
                    ))}
                  </select>
                </Field>

                {/* Probar voz */}
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <button type="button" onClick={handlePreviewVoice} disabled={!voice || previewLoading}
                      style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 10,
                        border: "1px solid rgba(52,211,153,0.35)", background: "rgba(52,211,153,0.1)", color: "#34d399",
                        fontSize: 14, fontWeight: 600, cursor: (!voice || previewLoading) ? "not-allowed" : "pointer",
                        opacity: (!voice || previewLoading) ? 0.5 : 1 }}>
                      {previewLoading
                        ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} />
                        : <Play size={14} />}
                      {previewLoading ? "Generando audio…" : "▶ Probar voz"}
                    </button>
                    {previewUrl && (
                      <audio ref={audioRef} src={previewUrl} controls autoPlay
                        style={{ height: 36, borderRadius: 8, flex: 1, minWidth: 200 }} />
                    )}
                  </div>
                  {previewError && (
                    <p style={{ fontSize: 12, color: "#f87171", padding: "6px 10px", borderRadius: 8,
                      background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
                      ✕ {previewError}
                    </p>
                  )}
                </div>
              </>
            )}

            <Row2>
              <Field label={`Velocidad de voz · ${voiceRate.toFixed(1)}x`}>
                <select value={voiceRate} onChange={(e) => setVoiceRate(Number(e.target.value))} style={SELECT}>
                  {[0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0].map((r) => (
                    <option key={r} value={r} style={{ background: "#0d0d0d" }}>{r}x</option>
                  ))}
                </select>
              </Field>
              <Field label={`Volumen de voz · ${voiceVolume}x`}>
                <select value={voiceVolume} onChange={(e) => setVoiceVolume(Number(e.target.value))} style={SELECT}>
                  {[0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0].map((v) => (
                    <option key={v} value={v} style={{ background: "#0d0d0d" }}>{v}x</option>
                  ))}
                </select>
              </Field>
            </Row2>

            <Row2>
              <Field label="Música de fondo">
                <select value={bgmType} onChange={(e) => setBgmType(e.target.value)} style={SELECT}>
                  <option value="" style={{ background: "#0d0d0d" }}>Sin música</option>
                  <option value="random" style={{ background: "#0d0d0d" }}>Aleatoria</option>
                  <option value="custom" style={{ background: "#0d0d0d" }}>Personalizada</option>
                </select>
              </Field>
              <Field label={`Volumen BGM · ${Math.round(bgmVolume * 100)}%`}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Music size={13} color="#52525b" style={{ flexShrink: 0 }} />
                  <input type="range" min={0} max={1} step={0.05} value={bgmVolume}
                    onChange={(e) => setBgmVolume(parseFloat(e.target.value))} style={{ flex: 1 }} />
                </div>
              </Field>
            </Row2>
          </div>
        )}
      </div>

      {/* ══════════════════════════════ SUBTÍTULOS ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle
          open={openSubs} onToggle={() => setOpenSubs(!openSubs)}
          icon={Type} title="Subtítulos" color="#f59e0b"
          badge={
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, marginLeft: 4,
              background: subtitles ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.06)",
              color: subtitles ? "#34d399" : "#52525b" }}>
              {subtitles ? "Activados" : "Desactivados"}
            </span>
          }
        />
        {openSubs && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <span style={{ fontSize: 13, color: "#a1a1aa" }}>Activar subtítulos automáticos</span>
              <Toggle value={subtitles} onChange={setSubtitles} />
            </div>

            {subtitles && (
              <>
                <Row2>
                  <Field label="Fuente">
                    <select value={fontName} onChange={(e) => setFontName(e.target.value)} style={SELECT}>
                      {FONTS.map((f) => <option key={f} value={f} style={{ background: "#0d0d0d" }}>{f}</option>)}
                    </select>
                  </Field>
                  <Field label="Posición">
                    <select value={subtitlePos} onChange={(e) => setSubtitlePos(e.target.value)} style={SELECT}>
                      <option value="top" style={{ background: "#0d0d0d" }}>Arriba</option>
                      <option value="center" style={{ background: "#0d0d0d" }}>Centro</option>
                      <option value="bottom" style={{ background: "#0d0d0d" }}>Abajo</option>
                      <option value="custom" style={{ background: "#0d0d0d" }}>Personalizada</option>
                    </select>
                  </Field>
                </Row2>

                {subtitlePos === "custom" && (
                  <Field label={`Posición personalizada · ${customPos}% desde arriba`}>
                    <input type="range" min={0} max={100} step={1} value={customPos}
                      onChange={(e) => setCustomPos(Number(e.target.value))} />
                  </Field>
                )}

                <Row2>
                  <Field label={`Tamaño de fuente · ${fontSize}px`}>
                    <input type="range" min={30} max={100} step={2} value={fontSize}
                      onChange={(e) => setFontSize(Number(e.target.value))} />
                  </Field>
                  <Field label={`Grosor del contorno · ${strokeWidth}`}>
                    <input type="range" min={0} max={10} step={0.5} value={strokeWidth}
                      onChange={(e) => setStrokeWidth(parseFloat(e.target.value))} />
                  </Field>
                </Row2>

                <Row2>
                  <Field label="Color del texto">
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <input type="color" value={textColor} onChange={(e) => setTextColor(e.target.value)}
                        style={{ width: 40, height: 36, borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "none", cursor: "pointer", padding: 2 }} />
                      <code style={{ fontSize: 13, color: "#71717a" }}>{textColor}</code>
                    </div>
                  </Field>
                  <Field label="Color del contorno">
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <input type="color" value={strokeColor} onChange={(e) => setStrokeColor(e.target.value)}
                        style={{ width: 40, height: 36, borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "none", cursor: "pointer", padding: 2 }} />
                      <code style={{ fontSize: 13, color: "#71717a" }}>{strokeColor}</code>
                    </div>
                  </Field>
                </Row2>

                {/* Fondo del subtítulo */}
                <div style={{ padding: "14px", borderRadius: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 13, color: "#a1a1aa" }}>Fondo del subtítulo</span>
                    <Toggle value={subtitleBg} onChange={setSubtitleBg} />
                  </div>
                  {subtitleBg && (
                    <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <input type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)}
                          style={{ width: 36, height: 32, borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "none", cursor: "pointer", padding: 2 }} />
                        <code style={{ fontSize: 12, color: "#71717a" }}>{bgColor}</code>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Toggle value={roundedBg} onChange={setRoundedBg} />
                        <span style={{ fontSize: 13, color: "#71717a" }}>Esquinas redondeadas</span>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* ══════════════════════════════ CONFIGURACIÓN / API KEYS ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle open={openConfig} onToggle={() => setOpenConfig(!openConfig)} icon={Key} title="Configuración y API Keys" color="#fb923c" />
        {openConfig && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ padding: "12px 16px", borderRadius: 12, background: "rgba(251,146,60,0.08)", border: "1px solid rgba(251,146,60,0.2)" }}>
              <p style={{ fontSize: 13, color: "#fdba74", lineHeight: 1.6 }}>
                Las API keys de Pexels, Pixabay y el proveedor LLM se configuran editando el archivo{" "}
                <code style={{ background: "rgba(255,255,255,0.08)", padding: "1px 6px", borderRadius: 4, fontSize: 12, color: "#e4e4e7" }}>
                  MoneyPrinterTurbo/config.toml
                </code>
              </p>
            </div>

            {/* Pexels keys */}
            <div>
              <label style={LABEL}>Agregar nueva API key de Pexels</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="text" value={pexelsNewKey} onChange={(e) => setPexelsNewKey(e.target.value)}
                  placeholder="Pega aquí la nueva key de Pexels..."
                  style={{ ...INPUT, flex: 1 }} />
                <button type="button" disabled={!pexelsNewKey.trim()}
                  onClick={() => {
                    alert(`Para agregar la key, añádela manualmente en config.toml en pexels_api_keys.\nKey: ${pexelsNewKey}`);
                    setPexelsNewKey("");
                  }}
                  style={{ padding: "0 16px", borderRadius: 10, border: "none", background: "rgba(139,92,246,0.2)", color: "#a78bfa", fontWeight: 600, fontSize: 14, whiteSpace: "nowrap" }}>
                  <Plus size={16} />
                </button>
              </div>
            </div>

            {/* Pixabay keys */}
            <div>
              <label style={LABEL}>Agregar nueva API key de Pixabay</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="text" value={pixabayNewKey} onChange={(e) => setPixabayNewKey(e.target.value)}
                  placeholder="Pega aquí la nueva key de Pixabay..."
                  style={{ ...INPUT, flex: 1 }} />
                <button type="button" disabled={!pixabayNewKey.trim()}
                  onClick={() => {
                    alert(`Para agregar la key, añádela manualmente en config.toml en pixabay_api_keys.\nKey: ${pixabayNewKey}`);
                    setPixabayNewKey("");
                  }}
                  style={{ padding: "0 16px", borderRadius: 10, border: "none", background: "rgba(139,92,246,0.2)", color: "#a78bfa", fontWeight: 600, fontSize: 14 }}>
                  <Plus size={16} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ══════════════════════════════ LOGS VISUALES ══════════════════════════════ */}
      {logs.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <LogPanel logs={logs} title="Actividad" maxHeight={200} />
        </div>
      )}

      {/* ══════════════════════════════ BOTÓN GENERAR ══════════════════════════════ */}
      <div style={{ paddingTop: 8, paddingBottom: 40 }}>
        <button type="submit" disabled={!subject.trim() || loading} style={{
          width: "100%", padding: "18px", borderRadius: 18, border: "none",
          background: !subject.trim() || loading ? "rgba(255,255,255,0.06)" : "linear-gradient(135deg, #8b5cf6, #06b6d4)",
          color: !subject.trim() || loading ? "#52525b" : "#ffffff",
          fontSize: 17, fontWeight: 700,
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          boxShadow: subject.trim() && !loading ? "0 0 40px rgba(139,92,246,0.3)" : "none",
          transition: "all 0.25s",
        }}>
          <Wand2 size={20} />
          {loading ? "Generando video…" : `Crear video · ${durationLabel}`}
        </button>
        <p style={{ textAlign: "center", fontSize: 12, color: "#3f3f46", marginTop: 8 }}>
          {videoCount > 1 ? `${videoCount} videos` : "1 video"} · {paragraphs} párrafo{paragraphs > 1 ? "s" : ""} · {aspect} · {videoSource}
          {ttsServer !== "no-voice" ? ` · ${voice.split("-").slice(0,3).join("-")}` : " · sin voz"}
        </p>
      </div>

    </form>
  );
}
