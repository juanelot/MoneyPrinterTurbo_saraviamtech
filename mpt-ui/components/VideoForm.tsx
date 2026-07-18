"use client";

import { useState, useRef, useMemo } from "react";
import {
  Wand2, ChevronDown, ChevronUp, Mic, Music, Type,
  Sparkles, Film, RefreshCw,
  Play, Key, Plus, Pause,
} from "lucide-react";
import type { TaskResult } from "@/app/page";
import {
  getVoicesForServer, getUniqueLanguages, type TtsServer,
} from "@/lib/voices";
import LogPanel, { makeLog, type LogEntry } from "@/components/LogPanel";
import { useT } from "@/lib/i18n";

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
  const { t } = useT();

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
    setLocalUploadMsg(t("filesUploaded", { n: uploaded }));
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

  // ── Música propia (BGM custom) ─────────────────────────────────────────────
  interface SongFile { name: string; size: number; file: string; }
  const [songs, setSongs]                   = useState<SongFile[]>([]);
  const [bgmFile, setBgmFile]               = useState("");
  const [songsLoading, setSongsLoading]     = useState(false);
  const [songUploading, setSongUploading]   = useState(false);
  const [songUploadMsg, setSongUploadMsg]   = useState("");
  const songFileRef = useRef<HTMLInputElement>(null);
  const [playingSong, setPlayingSong]       = useState("");
  const songAudioRef = useRef<HTMLAudioElement | null>(null);

  const togglePlaySong = (file: string) => {
    if (playingSong === file) {
      songAudioRef.current?.pause();
      setPlayingSong("");
      return;
    }
    songAudioRef.current?.pause();
    const audio = new Audio(`/api/mpt/v1/musics/${encodeURIComponent(file)}`);
    songAudioRef.current = audio;
    audio.onended = () => setPlayingSong("");
    audio.play().catch(() => setPlayingSong(""));
    setPlayingSong(file);
  };

  const loadSongs = async () => {
    setSongsLoading(true);
    try {
      const res = await fetch("/api/mpt/v1/musics");
      const data = await res.json();
      setSongs(data?.data?.files ?? []);
    } catch { /* ignore */ } finally { setSongsLoading(false); }
  };

  const handleSongUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setSongUploading(true);
    setSongUploadMsg("");
    let uploaded = 0;
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      try {
        const res = await fetch("/api/mpt/v1/musics", { method: "POST", body: form });
        if (res.ok) uploaded++;
      } catch { /* skip */ }
    }
    setSongUploadMsg(t("filesUploaded", { n: uploaded }));
    await loadSongs();
    setSongUploading(false);
    if (songFileRef.current) songFileRef.current.value = "";
  };
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
    addLog("info", t("logGenScriptP", { s: subject.trim(), p: `${paragraphs}p` }));
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
      addLog("success", t("logScriptDone", { n: script.length }));

      // Auto-generar términos si hay guión
      if (script) {
        setGeneratingTerms(true);
        addLog("info", t("logGenKeywordsAuto"));
        try {
          const res2 = await fetch("/api/mpt/v1/terms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ video_subject: subject.trim(), video_script: script, amount: 5 }),
          });
          if (res2.ok) {
            const d2 = await res2.json();
            const terms = d2?.data?.video_terms;
            if (Array.isArray(terms)) { setVideoTerms(terms.join(", ")); addLog("success", t("logKeywords", { k: terms.join(", ") })); }
            else if (typeof terms === "string") { setVideoTerms(terms); addLog("success", t("logKeywords", { k: terms })); }
          }
        } finally { setGeneratingTerms(false); }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : t("unknownError");
      addLog("error", t("logErrScript", { e: msg }));
    } finally { setGeneratingScript(false); }
  };

  // ── Generar solo términos ──────────────────────────────────────────────────
  const handleGenerateTerms = async () => {
    if (!subject.trim()) return;
    setGeneratingTerms(true);
    addLog("info", t("logGenKeywords"));
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
      if (Array.isArray(terms)) { setVideoTerms(terms.join(", ")); addLog("success", t("logKeywords", { k: terms.join(", ") })); }
      else if (typeof terms === "string") { setVideoTerms(terms); addLog("success", t("logKeywords", { k: terms })); }
    } catch (e) {
      const msg = e instanceof Error ? e.message : t("unknownError");
      addLog("error", t("logErrKeywords", { e: msg }));
    } finally { setGeneratingTerms(false); }
  };

  // ── Preview de voz ─────────────────────────────────────────────────────────
  const handlePreviewVoice = async () => {
    if (!voice || ttsServer === "no-voice") return;
    setPreviewLoading(true);
    setPreviewUrl(null);
    setPreviewError(null);
    addLog("info", t("logPreviewVoice", { v: voice }));
    try {
      const text = generatedScript.slice(0, 300) || subject.trim() || t("voiceSample");
      addLog("debug", t("logSynthText", { n: text.length, t: text.slice(0, 80) }));
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
      if (!taskId) throw new Error(t("logNoTaskId"));
      addLog("info", t("logTaskWaitTts", { id: taskId.slice(0, 8) }));

      // Esperar a que termine el audio (poll cada 2s, hasta 60 intentos = 2 min)
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const r2 = await fetch(`/api/mpt/v1/tasks/${taskId}`);
        if (!r2.ok) { addLog("warn", `Poll ${i+1}: ${r2.status}`); continue; }
        const d2 = await r2.json();
        const state = d2?.data?.state;
        const progress = d2?.data?.progress ?? 0;
        addLog("debug", `Poll ${i+1}: state=${state} progress=${progress}%`);
        if (state === 1) {
          // El backend guarda el audio en "audio_file", no en "videos"
          const rawPath: string = d2?.data?.audio_file ?? d2?.data?.videos?.[0] ?? "";
          addLog("debug", `audio_file raw: ${rawPath || "(-)"}`);
          if (rawPath) {
            const normalized = rawPath.replace(/\\/g, "/");
            const match = normalized.match(/([0-9a-f\-]{36}\/[^/]+)$/i);
            const streamPath = match ? match[1] : `${taskId}/audio.mp3`;
            addLog("success", t("logAudioReady", { p: streamPath }));
            setPreviewUrl(`/api/mpt/v1/stream/${streamPath}`);
            // Borrar carpeta de audio del disco después de 30s
            setTimeout(() => {
              fetch(`/api/library?taskId=${taskId}`, { method: "DELETE" }).catch(() => {});
            }, 30000);
          } else {
            throw new Error(t("logAudioEmpty"));
          }
          break;
        }
        if (state === -1) {
          const errMsg = d2?.data?.message || t("logTtsError");
          throw new Error(errMsg);
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("unknownError");
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
    addLog("info", t("logStarting", { s: subject.trim() }));
    addLog("info", t("logConfig", { p: paragraphs, a: aspect, src: videoSource, v: voice || t("noVoiceSuffix") }));
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
          bgm_file: bgmType === "custom" && bgmFile ? bgmFile : undefined,
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
      if (!taskId) throw new Error(t("logNoTaskIdReceived"));
      await pollTask(taskId);
    } catch (err) {
      onError(err instanceof Error ? err.message : t("unknownError"));
    } finally { setLoading(false); }
  };

  const pollTask = async (taskId: string) => {
    addLog("info", t("logTaskMonitor", { id: taskId.slice(0, 8) }));
    addLog("debug", t("logFfmpegHint"));
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
          ? t("logProgressFfmpeg", { p: progress, e: elapsed > 0 ? t("logElapsedMin", { n: elapsed }) : "" })
          : t("logProgress", { p: progress });
        addLog("info", msg);
        lastProgress = progress;
      }
      // TASK_STATE_COMPLETE = 1
      if (state === 1) {
        const videos: string[] = taskData?.videos ?? [];
        addLog("success", t("logVideoReady", { n: videos.length }));
        onGenerated({ taskId, videos });
        return;
      }
      // TASK_STATE_FAILED = -1
      if (state === -1) {
        const errMsg = taskData?.message || t("logGenFailed");
        addLog("error", errMsg);
        throw new Error(errMsg);
      }
    }
    throw new Error(t("timeout30"));
  };

  const durationLabel = paragraphs <= 2 ? t("dur1") : paragraphs <= 4 ? t("dur2") : paragraphs <= 6 ? t("dur3") : t("dur4");

  // ─── RENDER ──────────────────────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14, paddingTop: 36 }}>

      {/* HERO */}
      <div style={{ textAlign: "center", paddingBottom: 12 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 14px", borderRadius: 99, background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)", marginBottom: 16 }}>
          <Sparkles size={13} color="#a78bfa" />
          <span style={{ fontSize: 13, color: "#a78bfa", fontWeight: 500 }}>{t("heroBadge")}</span>
        </div>
        <h1 style={{ fontSize: 38, fontWeight: 800, lineHeight: 1.15, letterSpacing: "-0.02em", marginBottom: 10 }}>
          <span className="gradient-text">{t("heroTitle1")}</span>
          <br />
          <span style={{ color: "#fff" }}>{t("heroTitle2")}</span>
        </h1>
        <p style={{ color: "#71717a", fontSize: 15, maxWidth: 500, margin: "0 auto", lineHeight: 1.6 }}>
          {t("heroSubtitle")}
        </p>
      </div>

      {/* ══════════════════════════════ GUIÓN ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle open={openScript} onToggle={() => setOpenScript(!openScript)} icon={Sparkles} title={t("scriptSection")} />
        {openScript && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            <Field label={t("subjectLabel")}>
              <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} required
                placeholder={t("subjectPlaceholder")}
                style={INPUT} />
            </Field>

            <Row2>
              <Field label={t("scriptLang")}>
                <select value={videoLanguage} onChange={(e) => setVideoLanguage(e.target.value)} style={SELECT}>
                  <option value="">{t("autoDetect")}</option>
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
              <Field label={t("paragraphsLabelDur", { dur: durationLabel })}>
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

            <Field label={t("extraInstructionsMax")}>
              <textarea value={scriptPrompt} onChange={(e) => setScriptPrompt(e.target.value)}
                placeholder={t("scriptPromptPlaceholder")}
                rows={2} maxLength={2000} style={{ ...INPUT, resize: "vertical" }} />
            </Field>

            {/* Custom system prompt */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <span style={{ fontSize: 13, color: "#a1a1aa" }}>{t("customSysToggle")}</span>
              <Toggle value={useCustomSys} onChange={setUseCustomSys} />
            </div>
            {useCustomSys && (
              <Field label={t("sysPromptLabel")}>
                <textarea value={customSysPrompt} onChange={(e) => setCustomSysPrompt(e.target.value)}
                  placeholder={t("sysPromptPlaceholder")}
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
                {generatingScript ? t("generatingScript") : t("generateScript")}
              </button>
              <button type="button" onClick={handleGenerateTerms} disabled={!subject.trim() || generatingTerms}
                style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 10,
                  border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.05)", color: "#a1a1aa",
                  fontSize: 14, fontWeight: 600 }}>
                {generatingTerms
                  ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} />
                  : <Sparkles size={14} />}
                {generatingTerms ? t("generating") : t("generateKeywordsOnly")}
              </button>
            </div>

            <Field label={t("scriptEditable")}>
              <textarea value={generatedScript} onChange={(e) => setGeneratedScript(e.target.value)}
                placeholder={t("scriptPlaceholder")}
                rows={7} style={{ ...INPUT, resize: "vertical" }} />
            </Field>

            <Field label={t("keywordsLabel")}>
              <input type="text" value={videoTerms} onChange={(e) => setVideoTerms(e.target.value)}
                placeholder="nature, abundance, sunrise, meditation..."
                style={INPUT} />
            </Field>
          </div>
        )}
      </div>

      {/* ══════════════════════════════ VIDEO ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle open={openVideo} onToggle={() => setOpenVideo(!openVideo)} icon={Film} title={t("videoConfigSection")} color="#22d3ee" />
        {openVideo && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Aspect ratio */}
            <Field label={t("aspectLabel")}>
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
              <Field label={t("clipSource")}>
                <select value={videoSource} onChange={(e) => {
                  setVideoSource(e.target.value);
                  if (e.target.value === "local") loadLocalMaterials();
                }} style={SELECT}>
                  <option value="pexels" style={{ background: "#0d0d0d" }}>Pexels</option>
                  <option value="pixabay" style={{ background: "#0d0d0d" }}>Pixabay</option>
                  <option value="local" style={{ background: "#0d0d0d" }}>{t("localOwn")}</option>
                </select>
              </Field>
              <Field label={t("videosSimul")}>
                <select value={videoCount} onChange={(e) => setVideoCount(Number(e.target.value))} style={SELECT}>
                  {[1,2,3,4,5].map((n) => <option key={n} value={n} style={{ background: "#0d0d0d" }}>{n} {n > 1 ? t("videosWord") : t("videoWord")}</option>)}
                </select>
              </Field>
            </Row2>

            {/* ── Medios locales ── */}
            {videoSource === "local" && (
              <div style={{ padding: 18, borderRadius: 14, background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.15)" }}>
                {/* Info de requisitos */}
                <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 10, background: "rgba(6,182,212,0.07)", border: "1px solid rgba(6,182,212,0.15)" }}>
                  <p style={{ fontSize: 12, color: "#67e8f9", fontWeight: 600, marginBottom: 4 }}>{t("localReqTitle")}</p>
                  <ul style={{ fontSize: 11, color: "#71717a", lineHeight: 1.8, margin: 0, paddingLeft: 16 }}>
                    <li>{t("localReq1")}</li>
                    <li>{t("localReq2")}</li>
                    <li>{t("localReq3")}</li>
                    <li>{t("localReq4")}</li>
                    <li>{t("localReq5")}</li>
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
                    {localUploading ? t("uploading") : t("uploadVideos")}
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
                    {localLoading ? t("loadingDots") : t("noVideosUploaded")}
                  </p>
                ) : (
                  <>
                    <p style={{ fontSize: 11, color: "#52525b", marginBottom: 8 }}>
                      {t("selectClips", { n: selectedMaterials.length })}
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
                        {t("selectAll")}
                      </button>
                      <span style={{ color: "#3f3f46" }}>·</span>
                      <button type="button" onClick={() => setSelectedMaterials([])}
                        style={{ fontSize: 11, color: "#52525b", background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                        {t("deselectAll")}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            <Row2>
              <Field label={t("clipOrder")}>
                <select value={concatMode} onChange={(e) => setConcatMode(e.target.value)} style={SELECT}>
                  <option value="random" style={{ background: "#0d0d0d" }}>{t("random")}</option>
                  <option value="sequential" style={{ background: "#0d0d0d" }}>{t("sequential")}</option>
                </select>
              </Field>
              <Field label={t("transitionLabel")}>
                <select value={transition} onChange={(e) => setTransition(e.target.value)} style={SELECT}>
                  <option value="none" style={{ background: "#0d0d0d" }}>{t("noTransition")}</option>
                  <option value="Shuffle" style={{ background: "#0d0d0d" }}>Shuffle</option>
                  <option value="FadeIn" style={{ background: "#0d0d0d" }}>Fade In</option>
                  <option value="FadeOut" style={{ background: "#0d0d0d" }}>Fade Out</option>
                  <option value="SlideIn" style={{ background: "#0d0d0d" }}>Slide In</option>
                  <option value="SlideOut" style={{ background: "#0d0d0d" }}>Slide Out</option>
                </select>
              </Field>
            </Row2>

            <Row2>
              <Field label={t("clipDurationLabel", { n: clipDuration })}>
                <input type="range" min={2} max={10} step={1} value={clipDuration}
                  onChange={(e) => setClipDuration(Number(e.target.value))} />
              </Field>
              <Field label={t("codecLabel")}>
                <select value={codec} onChange={(e) => setCodec(e.target.value)} style={SELECT}>
                  <option value="libx264" style={{ background: "#0d0d0d" }}>{t("codecCpu")}</option>
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
        <SectionToggle open={openAudio} onToggle={() => setOpenAudio(!openAudio)} icon={Mic} title={t("voiceAudioSection")} color="#34d399" />
        {openAudio && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Servidor TTS */}
            <Field label={t("ttsServerLabel")}>
              <select value={ttsServer} onChange={(e) => handleTtsServerChange(e.target.value as TtsServer)} style={SELECT}>
                <option value="no-voice" style={{ background: "#0d0d0d" }}>{t("noVoice")}</option>
                <option value="azure-tts-v1" style={{ background: "#0d0d0d" }}>{t("azureV1")}</option>
                <option value="azure-tts-v2" style={{ background: "#0d0d0d" }}>{t("azureV2")}</option>
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
                  <Field label={t("filterVoicesByLang")}>
                    <select value={voiceLangFilter} onChange={(e) => handleLangChange(e.target.value)} style={SELECT}>
                      {langs.map((l) => <option key={l} value={l} style={{ background: "#0d0d0d" }}>{l}</option>)}
                    </select>
                  </Field>
                )}

                <Field label={t("narratorVoice")}>
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
                      {previewLoading ? t("generatingAudio") : t("testVoice")}
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
              <Field label={t("voiceRateLabel", { n: voiceRate.toFixed(1) })}>
                <select value={voiceRate} onChange={(e) => setVoiceRate(Number(e.target.value))} style={SELECT}>
                  {[0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0].map((r) => (
                    <option key={r} value={r} style={{ background: "#0d0d0d" }}>{r}x</option>
                  ))}
                </select>
              </Field>
              <Field label={t("voiceVolumeLabel", { n: voiceVolume })}>
                <select value={voiceVolume} onChange={(e) => setVoiceVolume(Number(e.target.value))} style={SELECT}>
                  {[0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0].map((v) => (
                    <option key={v} value={v} style={{ background: "#0d0d0d" }}>{v}x</option>
                  ))}
                </select>
              </Field>
            </Row2>

            <Row2>
              <Field label={t("bgmLabel")}>
                <select value={bgmType} onChange={(e) => {
                  setBgmType(e.target.value);
                  if (e.target.value === "custom") loadSongs();
                }} style={SELECT}>
                  <option value="" style={{ background: "#0d0d0d" }}>{t("noMusic")}</option>
                  <option value="random" style={{ background: "#0d0d0d" }}>{t("randomMusic")}</option>
                  <option value="custom" style={{ background: "#0d0d0d" }}>{t("customMusic")}</option>
                </select>
              </Field>
              <Field label={t("bgmVolumeLabel", { n: Math.round(bgmVolume * 100) })}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Music size={13} color="#52525b" style={{ flexShrink: 0 }} />
                  <input type="range" min={0} max={1} step={0.05} value={bgmVolume}
                    onChange={(e) => setBgmVolume(parseFloat(e.target.value))} style={{ flex: 1 }} />
                </div>
              </Field>
            </Row2>

            {/* ── Música propia ── */}
            {bgmType === "custom" && (
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <input
                    ref={songFileRef}
                    type="file"
                    accept=".mp3"
                    multiple
                    onChange={handleSongUpload}
                    style={{ display: "none" }}
                  />
                  <button
                    type="button"
                    onClick={() => songFileRef.current?.click()}
                    disabled={songUploading}
                    style={{
                      display: "flex", alignItems: "center", gap: 6, padding: "7px 14px",
                      background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.35)",
                      borderRadius: 8, color: "#c4b5fd", fontSize: 12.5, fontWeight: 600,
                      cursor: songUploading ? "wait" : "pointer",
                    }}
                  >
                    {songUploading ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} /> : <Plus size={14} />}
                    {songUploading ? t("uploading") : t("uploadMusic")}
                  </button>
                  <button
                    type="button"
                    onClick={loadSongs}
                    disabled={songsLoading}
                    style={{
                      display: "flex", alignItems: "center", gap: 6, padding: "7px 12px",
                      background: "transparent", border: "1px solid #27272a",
                      borderRadius: 8, color: "#a1a1aa", fontSize: 12.5, cursor: "pointer",
                    }}
                  >
                    <RefreshCw size={13} style={songsLoading ? { animation: "spin-slow 1s linear infinite" } : {}} />
                  </button>
                  {songUploadMsg && <span style={{ fontSize: 12, color: "#34d399" }}>{songUploadMsg}</span>}
                </div>

                {songs.length === 0 ? (
                  <p style={{ fontSize: 12.5, color: "#71717a" }}>
                    {songsLoading ? t("loadingDots") : t("noSongsUploaded")}
                  </p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 180, overflowY: "auto" }}>
                    {songs.map((s) => {
                      const selected = bgmFile === s.file;
                      return (
                        <button
                          key={s.file}
                          type="button"
                          onClick={() => setBgmFile(selected ? "" : s.file)}
                          style={{
                            display: "flex", alignItems: "center", gap: 8, padding: "7px 10px",
                            background: selected ? "rgba(139,92,246,0.15)" : "rgba(255,255,255,0.02)",
                            border: `1px solid ${selected ? "rgba(139,92,246,0.5)" : "#1f1f23"}`,
                            borderRadius: 8, cursor: "pointer", textAlign: "left",
                          }}
                        >
                          <span
                            role="button"
                            title="Play / Pause"
                            onClick={(e) => { e.stopPropagation(); togglePlaySong(s.file); }}
                            style={{
                              display: "flex", alignItems: "center", justifyContent: "center",
                              width: 24, height: 24, borderRadius: 6, flexShrink: 0,
                              background: playingSong === s.file ? "rgba(139,92,246,0.25)" : "rgba(255,255,255,0.05)",
                            }}
                          >
                            {playingSong === s.file
                              ? <Pause size={12} color="#c4b5fd" />
                              : <Play size={12} color={selected ? "#c4b5fd" : "#71717a"} />}
                          </span>
                          <span style={{ fontSize: 12.5, color: selected ? "#e4e4e7" : "#a1a1aa", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {s.name}
                          </span>
                          <span style={{ fontSize: 11, color: "#52525b", flexShrink: 0 }}>
                            {(s.size / 1024 / 1024).toFixed(1)} MB
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
                {songs.length > 0 && !bgmFile && (
                  <p style={{ fontSize: 11.5, color: "#f59e0b" }}>{t("selectSongHint")}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ══════════════════════════════ SUBTÍTULOS ══════════════════════════════ */}
      <div style={CARD}>
        <SectionToggle
          open={openSubs} onToggle={() => setOpenSubs(!openSubs)}
          icon={Type} title={t("subtitlesSection")} color="#f59e0b"
          badge={
            <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, marginLeft: 4,
              background: subtitles ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.06)",
              color: subtitles ? "#34d399" : "#52525b" }}>
              {subtitles ? t("enabledBadge") : t("disabledBadge")}
            </span>
          }
        />
        {openSubs && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <span style={{ fontSize: 13, color: "#a1a1aa" }}>{t("enableSubtitles")}</span>
              <Toggle value={subtitles} onChange={setSubtitles} />
            </div>

            {subtitles && (
              <>
                <Row2>
                  <Field label={t("fontLabel")}>
                    <select value={fontName} onChange={(e) => setFontName(e.target.value)} style={SELECT}>
                      {FONTS.map((f) => <option key={f} value={f} style={{ background: "#0d0d0d" }}>{f}</option>)}
                    </select>
                  </Field>
                  <Field label={t("positionLabel")}>
                    <select value={subtitlePos} onChange={(e) => setSubtitlePos(e.target.value)} style={SELECT}>
                      <option value="top" style={{ background: "#0d0d0d" }}>{t("posTop")}</option>
                      <option value="center" style={{ background: "#0d0d0d" }}>{t("posCenter")}</option>
                      <option value="bottom" style={{ background: "#0d0d0d" }}>{t("posBottom")}</option>
                      <option value="custom" style={{ background: "#0d0d0d" }}>{t("posCustom")}</option>
                    </select>
                  </Field>
                </Row2>

                {subtitlePos === "custom" && (
                  <Field label={t("customPositionLabel", { n: customPos })}>
                    <input type="range" min={0} max={100} step={1} value={customPos}
                      onChange={(e) => setCustomPos(Number(e.target.value))} />
                  </Field>
                )}

                <Row2>
                  <Field label={t("fontSizeLabel", { n: fontSize })}>
                    <input type="range" min={30} max={100} step={2} value={fontSize}
                      onChange={(e) => setFontSize(Number(e.target.value))} />
                  </Field>
                  <Field label={t("strokeWidthLabel", { n: strokeWidth })}>
                    <input type="range" min={0} max={10} step={0.5} value={strokeWidth}
                      onChange={(e) => setStrokeWidth(parseFloat(e.target.value))} />
                  </Field>
                </Row2>

                <Row2>
                  <Field label={t("textColorLabel")}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <input type="color" value={textColor} onChange={(e) => setTextColor(e.target.value)}
                        style={{ width: 40, height: 36, borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "none", cursor: "pointer", padding: 2 }} />
                      <code style={{ fontSize: 13, color: "#71717a" }}>{textColor}</code>
                    </div>
                  </Field>
                  <Field label={t("strokeColorLabel")}>
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
                    <span style={{ fontSize: 13, color: "#a1a1aa" }}>{t("subtitleBgLabel")}</span>
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
                        <span style={{ fontSize: 13, color: "#71717a" }}>{t("roundedCorners")}</span>
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
        <SectionToggle open={openConfig} onToggle={() => setOpenConfig(!openConfig)} icon={Key} title={t("configSection")} color="#fb923c" />
        {openConfig && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ padding: "12px 16px", borderRadius: 12, background: "rgba(251,146,60,0.08)", border: "1px solid rgba(251,146,60,0.2)" }}>
              <p style={{ fontSize: 13, color: "#fdba74", lineHeight: 1.6 }}>
                {t("apiKeysInfo")}{" "}
                <code style={{ background: "rgba(255,255,255,0.08)", padding: "1px 6px", borderRadius: 4, fontSize: 12, color: "#e4e4e7" }}>
                  MoneyPrinterTurbo/config.toml
                </code>
              </p>
            </div>

            {/* Pexels keys */}
            <div>
              <label style={LABEL}>{t("addPexelsKey")}</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="text" value={pexelsNewKey} onChange={(e) => setPexelsNewKey(e.target.value)}
                  placeholder={t("pastePexels")}
                  style={{ ...INPUT, flex: 1 }} />
                <button type="button" disabled={!pexelsNewKey.trim()}
                  onClick={() => {
                    alert(t("alertAddKey", { field: "pexels_api_keys", key: pexelsNewKey }));
                    setPexelsNewKey("");
                  }}
                  style={{ padding: "0 16px", borderRadius: 10, border: "none", background: "rgba(139,92,246,0.2)", color: "#a78bfa", fontWeight: 600, fontSize: 14, whiteSpace: "nowrap" }}>
                  <Plus size={16} />
                </button>
              </div>
            </div>

            {/* Pixabay keys */}
            <div>
              <label style={LABEL}>{t("addPixabayKey")}</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="text" value={pixabayNewKey} onChange={(e) => setPixabayNewKey(e.target.value)}
                  placeholder={t("pastePixabay")}
                  style={{ ...INPUT, flex: 1 }} />
                <button type="button" disabled={!pixabayNewKey.trim()}
                  onClick={() => {
                    alert(t("alertAddKey", { field: "pixabay_api_keys", key: pixabayNewKey }));
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
          <LogPanel logs={logs} title={t("activity")} maxHeight={200} />
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
          {loading ? t("creatingVideo") : t("createVideoDur", { dur: durationLabel })}
        </button>
        <p style={{ textAlign: "center", fontSize: 12, color: "#3f3f46", marginTop: 8 }}>
          {videoCount > 1 ? `${videoCount} ${t("videosWord")}` : `1 ${t("videoWord")}`} · {paragraphs} {paragraphs > 1 ? t("paragraphsWord") : t("paragraphWord")} · {aspect} · {videoSource}
          {ttsServer !== "no-voice" ? ` · ${voice.split("-").slice(0,3).join("-")}` : ` · ${t("noVoiceSuffix")}`}
        </p>
      </div>

    </form>
  );
}
