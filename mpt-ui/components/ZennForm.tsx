"use client";

import { useState, useRef, useMemo } from "react";
import {
  Wand2, ChevronDown, ChevronUp, Mic, Music, Type, Image as ImageIcon,
  Sparkles, RefreshCw, Play, Clock, Trash2, Plus,
} from "lucide-react";
import type { TaskResult } from "@/app/page";
import {
  getVoicesForServer, getUniqueLanguages, type TtsServer,
} from "@/lib/voices";
import LogPanel, { makeLog, type LogEntry } from "@/components/LogPanel";
import { useT } from "@/lib/i18n";

const FONTS = [
  "MicrosoftYaHeiBold.ttc", "MicrosoftYaHeiNormal.ttc",
  "STHeitiMedium.ttc", "STHeitiLight.ttc",
  "Charm-Bold.ttf", "Charm-Regular.ttf", "UTM Kabel KT.ttf",
];

// Estilo Zenn por defecto (debe coincidir con DEFAULT_KIE_IMAGE_STYLE del backend)
const DEFAULT_STYLE =
  "The image must look like an extremely simple beginner drawing made in MS Paint. " +
  "It should look like someone who is not good at drawing created it quickly by hand. " +
  "Plain white background, thick crude lines, flat colors, no shading, no 3D, " +
  "not cinematic, not realistic, no text, no watermark.";

const CARD: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 20, padding: 24,
};
const LABEL: React.CSSProperties = {
  display: "block", fontSize: 12, fontWeight: 600, color: "#a1a1aa",
  textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8,
};
const INPUT: React.CSSProperties = {
  width: "100%", padding: "11px 14px", borderRadius: 10, fontSize: 14,
  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
  color: "#ffffff", fontFamily: "inherit",
};
const SELECT: React.CSSProperties = {
  ...INPUT, appearance: "none", cursor: "pointer", background: "#0d0d0d",
  WebkitAppearance: "none",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label style={LABEL}>{label}</label>{children}</div>;
}
function Row2({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>{children}</div>;
}
function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!value)} style={{
      position: "relative", width: 40, height: 22, borderRadius: 11, border: "none",
      background: value ? "#8b5cf6" : "#27272a", transition: "background 0.2s", flexShrink: 0,
    }}>
      <div style={{
        position: "absolute", top: 3, width: 16, height: 16, borderRadius: "50%",
        background: "#fff", transition: "left 0.2s", left: value ? "calc(100% - 19px)" : 3,
      }} />
    </button>
  );
}
function SectionToggle({ open, onToggle, icon: Icon, title, color = "#a78bfa" }: {
  open: boolean; onToggle: () => void; icon: React.ElementType; title: string; color?: string;
}) {
  return (
    <button type="button" onClick={onToggle} style={{
      width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
      background: "none", border: "none", padding: 0, marginBottom: open ? 20 : 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Icon size={15} color={color} />
        <span style={{ fontSize: 14, fontWeight: 700, color: "#e4e4e7" }}>{title}</span>
      </div>
      {open ? <ChevronUp size={16} color="#52525b" /> : <ChevronDown size={16} color="#52525b" />}
    </button>
  );
}

interface Props {
  onStart: () => void;
  onGenerated: (result: TaskResult) => void;
  onError: (msg: string) => void;
  onLogsChange?: (logs: LogEntry[]) => void;
}

function PromptCard({ index, scene, prompt }: { index: number; scene: string; prompt: string }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ borderRadius: 10, border: "1px solid rgba(139,92,246,0.2)", background: "rgba(255,255,255,0.03)", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", background: "rgba(139,92,246,0.08)", borderBottom: "1px solid rgba(139,92,246,0.15)" }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#c4b5fd" }}>{t("imageN", { n: index })}</span>
        <button type="button" onClick={async () => {
          await navigator.clipboard.writeText(prompt);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }} style={{
          display: "flex", alignItems: "center", gap: 4, padding: "4px 10px",
          borderRadius: 6, border: "none", cursor: "pointer",
          background: copied ? "rgba(52,211,153,0.15)" : "rgba(139,92,246,0.15)",
          color: copied ? "#34d399" : "#a78bfa", fontSize: 11, fontWeight: 600,
        }}>
          {copied ? t("copiedCheck") : t("copyPrompt")}
        </button>
      </div>
      <div style={{ padding: "8px 12px" }}>
        <p style={{ fontSize: 11, color: "#71717a", marginBottom: 4, fontStyle: "italic" }}>
          "{scene.slice(0, 80)}{scene.length > 80 ? "…" : ""}"
        </p>
        <p style={{ fontSize: 11, color: "#a1a1aa", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {prompt}
        </p>
      </div>
    </div>
  );
}

export default function ZennForm({ onStart, onGenerated, onError, onLogsChange }: Props) {
  const { t } = useT();

  // Guión
  const [subject, setSubject]               = useState("");
  const [videoLanguage, setVideoLanguage]   = useState("");
  const [paragraphs, setParagraphs]         = useState(2);
  const [scriptPrompt, setScriptPrompt]     = useState("");
  const [generatedScript, setGeneratedScript] = useState("");
  const [generatingScript, setGeneratingScript] = useState(false);

  // Imágenes (Zenn / Kie)
  const [kieTheme, setKieTheme]             = useState("");
  const [kieStyle, setKieStyle]             = useState(DEFAULT_STYLE);
  const [aspect, setAspect]                 = useState<"9:16" | "16:9" | "1:1">("9:16");
  const [minImageDuration, setMinImageDuration] = useState(2.5);
  const [maxImages, setMaxImages]           = useState(0);
  const [codec, setCodec]                   = useState("libx264");

  // Imágenes locales
  const [imageSource, setImageSource]       = useState<"kie" | "local">("kie");
  interface LocalImage { name: string; size: number; file: string; }
  const [localImages, setLocalImages]       = useState<LocalImage[]>([]);
  const [localImgLoading, setLocalImgLoading] = useState(false);
  const [localImgUploading, setLocalImgUploading] = useState(false);
  const [localImgMsg, setLocalImgMsg]       = useState("");
  const [localImgMsgError, setLocalImgMsgError] = useState(false);
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const localImgRef = useRef<HTMLInputElement>(null);

  const loadLocalImages = async () => {
    setLocalImgLoading(true);
    try {
      const res = await fetch("/api/mpt/v1/video_materials");
      const data = await res.json();
      const all: LocalImage[] = data?.data?.files ?? [];
      // solo imágenes
      const imgs = all.filter((f) => /\.(jpg|jpeg|png|bmp|webp)$/i.test(f.name));
      setLocalImages(imgs);
    } catch { /* ignore */ } finally { setLocalImgLoading(false); }
  };

  const handleLocalImgUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setLocalImgUploading(true); setLocalImgMsg(""); setLocalImgMsgError(false);
    let uploaded = 0;
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      try {
        const res = await fetch("/api/mpt/v1/video_materials", { method: "POST", body: form });
        if (res.ok) uploaded++;
      } catch { /* skip */ }
    }
    setLocalImgMsg(t("imagesUploaded", { n: uploaded }));
    await loadLocalImages();
    setLocalImgUploading(false);
    if (localImgRef.current) localImgRef.current.value = "";
  };

  const [clearingImgs, setClearingImgs] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const handleClearAllImages = async () => {
    if (!confirmClear) { setConfirmClear(true); return; }
    setClearingImgs(true);
    setLocalImgMsg(""); setLocalImgMsgError(false);
    try {
      const res = await fetch("/api/local-images?action=clear-all", { method: "DELETE" });
      const data = await res.json();
      const deleted = data?.deleted ?? 0;
      setSelectedImages([]);
      setLocalImages([]);
      setLocalImgMsg(t("imagesDeleted", { n: deleted }));
    } catch {
      setLocalImgMsg(t("errorDeletingImages"));
      setLocalImgMsgError(true);
    } finally {
      setClearingImgs(false);
      setConfirmClear(false);
    }
  };

  const moveImage = (idx: number, dir: -1 | 1) => {
    const newSel = [...selectedImages];
    const target = idx + dir;
    if (target < 0 || target >= newSel.length) return;
    [newSel[idx], newSel[target]] = [newSel[target], newSel[idx]];
    setSelectedImages(newSel);
  };

  // Voz / audio
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
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewUrl, setPreviewUrl]         = useState<string | null>(null);
  const [previewError, setPreviewError]     = useState<string | null>(null);

  // Subtítulos
  const [subtitles, setSubtitles]           = useState(true);
  const [fontName, setFontName]             = useState(FONTS[0]);
  const [subtitlePos, setSubtitlePos]       = useState("bottom");
  const [textColor, setTextColor]           = useState("#FFFFFF");
  const [fontSize, setFontSize]             = useState(60);
  const [strokeColor, setStrokeColor]       = useState("#000000");
  const [strokeWidth, setStrokeWidth]       = useState(1.5);

  // Secciones
  const [openScript, setOpenScript]         = useState(true);
  const [openImages, setOpenImages]         = useState(true);
  const [openAudio, setOpenAudio]           = useState(true);
  const [openSubs, setOpenSubs]             = useState(false);

  const [loading, setLoading]               = useState(false);

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const addLog = (level: LogEntry["level"], msg: string) =>
    setLogs((prev) => { const next = [...prev, makeLog(level, msg)]; onLogsChange?.(next); return next; });

  const availableVoices = useMemo(() => getVoicesForServer(ttsServer), [ttsServer]);
  const langs           = useMemo(() => getUniqueLanguages(availableVoices), [availableVoices]);
  const filteredVoices  = useMemo(
    () => ttsServer === "no-voice" ? [] : availableVoices.filter((v) => v.lang === voiceLangFilter || langs.length === 1),
    [availableVoices, voiceLangFilter, langs]
  );

  // Estimación de imágenes / créditos / costo ANTES de generar.
  const estimate = useMemo(() => {
    const words = generatedScript.trim()
      ? generatedScript.trim().split(/\s+/).filter(Boolean).length
      : paragraphs * 50;
    const wpm = 150 * voiceRate;
    const audioSec = (words / wpm) * 60;
    let images = Math.max(1, Math.ceil(audioSec / minImageDuration));
    if (maxImages > 0) images = Math.min(images, maxImages);
    const credits = images * 6;
    const usd = (credits / 1000) * 5;
    const mm = Math.floor(audioSec / 60);
    const ss = Math.round(audioSec % 60);
    return { words, audioSec, images, credits, usd, durLabel: `${mm}:${String(ss).padStart(2, "0")}`, approx: !generatedScript.trim() };
  }, [generatedScript, paragraphs, voiceRate, minImageDuration, maxImages]);

  // Genera los prompts por segmento para imágenes locales.
  // Divide el guion en N partes iguales y construye un prompt por cada una.
  const [copiedAll, setCopiedAll] = useState(false);
  const imagePrompts = useMemo(() => {
    if (!generatedScript.trim() || imageSource !== "local") return [];
    const wpm = 150 * voiceRate;
    const audioSec = (generatedScript.trim().split(/\s+/).filter(Boolean).length / wpm) * 60;
    const n = Math.max(1, Math.ceil(audioSec / minImageDuration));
    // Dividir el guion en n fragmentos por palabras
    const words = generatedScript.trim().split(/\s+/).filter(Boolean);
    const chunkSize = Math.ceil(words.length / n);
    const chunks: string[] = [];
    for (let i = 0; i < n; i++) {
      chunks.push(words.slice(i * chunkSize, (i + 1) * chunkSize).join(" "));
    }
    // Construir prompt por segmento
    const style = kieStyle.trim() || "Extremely simple amateur drawing made in MS Paint style. White background, thick crude lines, flat colors, no shading, no 3D, no watermark.";
    const themeStr = kieTheme.trim() ? `Theme: ${kieTheme.trim()}. ` : "";
    const aspectStr = aspect === "16:9" ? "Landscape 16:9." : aspect === "9:16" ? "Portrait 9:16." : "Square 1:1.";
    return chunks.map((text, i) => ({
      index: i + 1,
      scene: text,
      prompt: `${style} ${themeStr}Scene to illustrate: ${text} ${aspectStr}`,
    }));
  }, [generatedScript, voiceRate, minImageDuration, imageSource, kieStyle, kieTheme, aspect]);

  const handleTtsServerChange = (s: TtsServer) => {
    setTtsServer(s); setPreviewUrl(null); setPreviewError(null);
    if (s === "no-voice") { setVoice(""); return; }
    const voices = getVoicesForServer(s);
    setVoiceLangFilter(voices[0]?.lang ?? "");
    setVoice(voices[0]?.value ?? "");
  };
  const handleLangChange = (lang: string) => {
    setVoiceLangFilter(lang); setPreviewUrl(null); setPreviewError(null);
    const first = availableVoices.find((v) => v.lang === lang);
    if (first) setVoice(first.value);
  };

  // Mapeo idioma del guion → código de voz (para sincronizar automáticamente)
  const LANG_TO_VOICE_FILTER: Record<string, string> = {
    "es-ES": "es-ES", "es-MX": "es-MX", "es-AR": "es-AR",
    "en-US": "en-US", "en-GB": "en-GB",
    "pt-BR": "pt-BR", "pt-PT": "pt-PT",
    "fr-FR": "fr-FR", "de-DE": "de-DE",
    "zh-CN": "zh-CN", "ja-JP": "ja-JP", "ko-KR": "ko-KR",
  };

  const handleScriptLangChange = (lang: string) => {
    setVideoLanguage(lang);
    // Si el idioma del guion tiene una voz correspondiente, sincronizar
    const voiceLang = LANG_TO_VOICE_FILTER[lang];
    if (voiceLang && langs.includes(voiceLang)) {
      handleLangChange(voiceLang);
    }
  };

  const handleGenerateScript = async () => {
    if (!subject.trim()) return;
    setGeneratingScript(true);
    addLog("info", t("logGenScript", { s: subject.trim() }));
    try {
      const res = await fetch("/api/mpt/v1/scripts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_subject: subject.trim(),
          video_language: videoLanguage || undefined,
          paragraph_number: paragraphs,
          video_script_prompt: scriptPrompt || undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const script = data?.data?.video_script ?? "";
      setGeneratedScript(script);
      addLog("success", t("logScriptDone", { n: script.length }));
    } catch (e) {
      addLog("error", t("logErrScript", { e: e instanceof Error ? e.message : t("unknownError") }));
    } finally { setGeneratingScript(false); }
  };

  const handlePreviewVoice = async () => {
    if (!voice || ttsServer === "no-voice") return;
    setPreviewLoading(true); setPreviewUrl(null); setPreviewError(null);
    try {
      const text = generatedScript.slice(0, 300) || subject.trim() || t("voiceSample");
      const res = await fetch("/api/mpt/v1/audio", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_script: text, voice_name: voice, voice_rate: voiceRate,
          voice_volume: voiceVolume, bgm_type: "random", bgm_volume: 0, video_source: "local",
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const taskId = data?.data?.task_id;
      if (!taskId) throw new Error(t("logNoTaskId"));
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const r2 = await fetch(`/api/mpt/v1/tasks/${taskId}`);
        if (!r2.ok) continue;
        const d2 = await r2.json();
        const state = d2?.data?.state;
        if (state === 1) {
          const rawPath: string = d2?.data?.audio_file ?? "";
          if (rawPath) {
            const match = rawPath.replace(/\\/g, "/").match(/([0-9a-f\-]{36}\/[^/]+)$/i);
            setPreviewUrl(`/api/mpt/v1/stream/${match ? match[1] : `${taskId}/audio.mp3`}`);
            setTimeout(() => { fetch(`/api/library?taskId=${taskId}`, { method: "DELETE" }).catch(() => {}); }, 30000);
          }
          break;
        }
        if (state === -1) throw new Error(d2?.data?.message || t("logTtsError"));
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : t("unknownError");
      addLog("error", msg); setPreviewError(msg);
    } finally { setPreviewLoading(false); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim()) return;
    setLoading(true); setLogs([]); onLogsChange?.([]);
    addLog("info", t("logZennStart", { s: subject.trim() }));
    addLog("info", t("logZennSource", {
      src: imageSource === "local" ? t("logZennLocalSrc", { n: selectedImages.length }) : "Kie AI · 1K",
      a: aspect,
      v: voice || t("noVoiceSuffix"),
    }));

    // Validar que si es local haya imágenes seleccionadas
    if (imageSource === "local" && selectedImages.length === 0) {
      setLoading(false);
      onError(t("logLocalNeedImages"));
      return;
    }

    onStart();
    try {
      const res = await fetch("/api/mpt/v1/image-video", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_subject: subject.trim(),
          video_script: generatedScript.trim() || undefined,
          video_language: videoLanguage || undefined,
          paragraph_number: paragraphs,
          video_script_prompt: scriptPrompt || undefined,
          video_aspect: aspect,
          video_codec: codec,
          voice_name: ttsServer !== "no-voice" ? voice : undefined,
          voice_volume: voiceVolume,
          voice_rate: voiceRate,
          bgm_type: bgmType,
          bgm_file: bgmType === "custom" && bgmFile ? bgmFile : undefined,
          bgm_volume: bgmVolume,
          subtitle_enabled: subtitles,
          subtitle_position: subtitlePos,
          font_name: fontName,
          text_fore_color: textColor,
          font_size: fontSize,
          stroke_color: strokeColor,
          stroke_width: strokeWidth,
          // Zenn / Kie
          kie_theme: kieTheme.trim() || undefined,
          kie_image_style: kieStyle.trim() || undefined,
          kie_aspect_ratio: aspect,
          kie_resolution: "1K",
          min_image_duration: minImageDuration,
          max_images: maxImages > 0 ? maxImages : undefined,
          image_source: imageSource,
          local_image_files: imageSource === "local" ? selectedImages : undefined,
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
    const modeMsg = imageSource === "local"
      ? t("logZennTaskLocal", { id: taskId.slice(0, 8) })
      : t("logZennTaskKie", { id: taskId.slice(0, 8) });
    addLog("info", modeMsg);
    if (imageSource !== "local") {
      addLog("debug", t("logZennKieHint"));
    }
    let lastProgress = -1;
    // 480 intentos × 5s = 40 min máximo (muchas imágenes)
    for (let i = 0; i < 480; i++) {
      await new Promise((r) => setTimeout(r, 5000));
      const res = await fetch(`/api/mpt/v1/tasks/${taskId}`);
      if (!res.ok) { addLog("warn", `Poll ${i + 1}: HTTP ${res.status}`); continue; }
      const data = await res.json();
      const taskData = data?.data ?? data;
      const state = taskData?.state;
      const progress = taskData?.progress ?? 0;
      if (progress !== lastProgress) {
        const msg = progress >= 30 && progress < 82
          ? t("logZennProgressImgs", { p: progress })
          : progress >= 82 && progress < 90
          ? t("logZennProgressSync", { p: progress })
          : progress >= 90
          ? t("logZennProgressRender", { p: progress })
          : t("logProgress", { p: progress });
        addLog("info", msg);
        lastProgress = progress;
      }
      if (state === 1) {
        const videos: string[] = taskData?.videos ?? [];
        const imgCount = taskData?.image_count;
        addLog("success", t("logZennReady", { i: imgCount ? t("logZennImgCount", { n: imgCount }) : "", n: videos.length }));
        onGenerated({ taskId, videos });
        return;
      }
      if (state === -1) {
        const errMsg = taskData?.message || t("logGenFailed");
        addLog("error", errMsg);
        throw new Error(errMsg);
      }
    }
    throw new Error(t("timeout40"));
  };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14, paddingTop: 36 }}>

      {/* HERO */}
      <div style={{ textAlign: "center", paddingBottom: 12 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 14px", borderRadius: 99, background: "rgba(34,211,238,0.1)", border: "1px solid rgba(34,211,238,0.2)", marginBottom: 16 }}>
          <ImageIcon size={13} color="#22d3ee" />
          <span style={{ fontSize: 13, color: "#67e8f9", fontWeight: 500 }}>{t("zennBadge")}</span>
        </div>
        <h1 style={{ fontSize: 38, fontWeight: 800, lineHeight: 1.15, letterSpacing: "-0.02em", marginBottom: 10 }}>
          <span className="gradient-text">{t("zennTitle1")}</span>
          <br /><span style={{ color: "#fff" }}>{t("zennTitle2")}</span>
        </h1>
        <p style={{ color: "#71717a", fontSize: 15, maxWidth: 540, margin: "0 auto", lineHeight: 1.6 }}>
          {t("zennSubtitle")}
        </p>
      </div>

      {/* GUIÓN */}
      <div style={CARD}>
        <SectionToggle open={openScript} onToggle={() => setOpenScript(!openScript)} icon={Sparkles} title={t("scriptSection")} />
        {openScript && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <Field label={t("subjectLabel")}>
              <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} required
                placeholder={t("zennSubjectPlaceholder")} style={INPUT} />
            </Field>
            <Row2>
              <Field label={t("scriptLang")}>
                <select value={videoLanguage} onChange={(e) => handleScriptLangChange(e.target.value)} style={SELECT}>
                  <option value="">{t("autoDetect")}</option>
                  <option value="es-ES">Español (España)</option>
                  <option value="es-MX">Español (México)</option>
                  <option value="en-US">English (US)</option>
                  <option value="en-GB">English (UK)</option>
                  <option value="pt-BR">Português (Brasil)</option>
                  <option value="fr-FR">Français</option>
                  <option value="de-DE">Deutsch</option>
                  <option value="zh-CN">中文</option>
                  <option value="ja-JP">日本語</option>
                  <option value="ko-KR">한국어</option>
                </select>
              </Field>
              <Field label={t("paragraphsLabel")}>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {/* Atajos rápidos por duración */}
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {[
                      { label: "~2 min", p: 5 },
                      { label: "~5 min", p: 13 },
                      { label: "~8 min", p: 20 },
                      { label: "~12 min", p: 30 },
                    ].map(({ label, p }) => (
                      <button key={p} type="button" onClick={() => setParagraphs(p)} style={{
                        padding: "6px 14px", borderRadius: 8, border: "none",
                        background: paragraphs === p ? "#8b5cf6" : "rgba(255,255,255,0.06)",
                        color: paragraphs === p ? "#fff" : "#71717a", fontWeight: 600, fontSize: 13,
                      }}>{label} ({p}p)</button>
                    ))}
                  </div>
                  {/* Input numérico libre */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input
                      type="number" min={1} max={50} value={paragraphs}
                      onChange={(e) => setParagraphs(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
                      style={{ ...INPUT, width: 80 }}
                    />
                    <span style={{ fontSize: 12, color: "#52525b" }}>
                      {Math.round(paragraphs * 50 / 150 * 60 / 60 * 100) / 100 < 1
                        ? t("secVideo", { n: Math.round(paragraphs * 50 / 150 * 60) })
                        : t("minVideo", { n: (paragraphs * 50 / 150).toFixed(1) })}
                    </span>
                  </div>
                </div>
              </Field>
            </Row2>
            <Field label={t("extraInstructions")}>
              <textarea value={scriptPrompt} onChange={(e) => setScriptPrompt(e.target.value)}
                placeholder={t("zennScriptPromptPlaceholder")} rows={2} maxLength={2000}
                style={{ ...INPUT, resize: "vertical" }} />
            </Field>
            <button type="button" onClick={handleGenerateScript} disabled={!subject.trim() || generatingScript}
              style={{ alignSelf: "flex-start", display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 10,
                border: "1px solid rgba(139,92,246,0.35)", background: "rgba(139,92,246,0.12)", color: "#c4b5fd", fontSize: 14, fontWeight: 600 }}>
              {generatingScript ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} /> : <Wand2 size={14} />}
              {generatingScript ? t("generatingScript") : t("generateScript")}
            </button>
            <Field label={t("zennScriptEditable")}>
              <textarea value={generatedScript} onChange={(e) => setGeneratedScript(e.target.value)}
                placeholder={t("scriptPlaceholder")} rows={7} style={{ ...INPUT, resize: "vertical" }} />
            </Field>
          </div>
        )}
      </div>

      {/* IMÁGENES */}
      <div style={CARD}>
        <SectionToggle open={openImages} onToggle={() => setOpenImages(!openImages)} icon={ImageIcon} title={t("imagesSection")} color="#22d3ee" />
        {openImages && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Toggle fuente de imágenes */}
            <div style={{ display: "flex", gap: 0, borderRadius: 12, overflow: "hidden", border: "1px solid rgba(255,255,255,0.1)" }}>
              {(["kie", "local"] as const).map((src) => (
                <button key={src} type="button" onClick={() => {
                  setImageSource(src);
                  if (src === "local" && localImages.length === 0) loadLocalImages();
                }} style={{
                  flex: 1, padding: "10px", border: "none", cursor: "pointer",
                  background: imageSource === src ? "rgba(34,211,238,0.15)" : "rgba(255,255,255,0.03)",
                  color: imageSource === src ? "#22d3ee" : "#52525b",
                  fontWeight: 700, fontSize: 13, transition: "all 0.2s",
                  borderRight: src === "kie" ? "1px solid rgba(255,255,255,0.1)" : "none",
                }}>
                  {src === "kie" ? t("kieTab") : t("localImagesTab")}
                </button>
              ))}
            </div>

            {/* Panel Kie AI */}
            {imageSource === "kie" && (
              <>
                <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.15)" }}>
                  <p style={{ fontSize: 12, color: "#67e8f9", lineHeight: 1.6 }}>
                    {t("kieInfo")}
                  </p>
                </div>
                <Field label={t("themeLabel")}>
                  <input type="text" value={kieTheme} onChange={(e) => setKieTheme(e.target.value)}
                    placeholder={t("themePlaceholder")} style={INPUT} />
                </Field>
                <Field label={t("styleLabel")}>
                  <textarea value={kieStyle} onChange={(e) => setKieStyle(e.target.value)} rows={4}
                    style={{ ...INPUT, resize: "vertical", fontSize: 13 }} />
                </Field>
              </>
            )}

            {/* Panel Imágenes locales */}
            {imageSource === "local" && (
              <div style={{ padding: 16, borderRadius: 14, background: "rgba(34,211,238,0.05)", border: "1px solid rgba(34,211,238,0.15)" }}>
                <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.12)", marginBottom: 14 }}>
                  <p style={{ fontSize: 12, color: "#67e8f9", lineHeight: 1.6 }}>
                    {t("localImagesInfo")}
                  </p>
                </div>

                {/* Upload */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                  <input ref={localImgRef} type="file"
                    accept="image/jpeg,image/png,image/bmp,image/webp,.jpg,.jpeg,.png,.bmp,.webp"
                    multiple onChange={handleLocalImgUpload}
                    style={{ display: "none" }} />
                  <button type="button"
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); localImgRef.current?.click(); }}
                    disabled={localImgUploading}
                    style={{ display: "flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 10,
                      border: "1px solid rgba(34,211,238,0.3)", background: "rgba(34,211,238,0.1)", color: "#22d3ee",
                      fontSize: 13, fontWeight: 600, cursor: localImgUploading ? "not-allowed" : "pointer" }}>
                    {localImgUploading
                      ? <><RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} /> {t("uploading")}</>
                      : <>{t("uploadImages")}</>}
                  </button>
                  <button type="button" onClick={loadLocalImages} disabled={localImgLoading}
                    style={{ padding: "9px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.08)",
                      background: "rgba(255,255,255,0.04)", color: "#71717a", fontSize: 13, cursor: "pointer" }}>
                    <RefreshCw size={13} style={localImgLoading ? { animation: "spin-slow 1s linear infinite" } : {}} />
                  </button>

                  {/* Botón borrar todas */}
                  {localImages.length > 0 && (
                    <>
                      <button type="button" onClick={handleClearAllImages} disabled={clearingImgs}
                        style={{ display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10,
                          border: `1px solid ${confirmClear ? "rgba(239,68,68,0.4)" : "rgba(239,68,68,0.2)"}`,
                          background: confirmClear ? "rgba(239,68,68,0.15)" : "rgba(239,68,68,0.06)",
                          color: confirmClear ? "#f87171" : "#ef4444",
                          fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.2s" }}>
                        {clearingImgs
                          ? <><RefreshCw size={13} style={{ animation: "spin-slow 1s linear infinite" }} /> {t("clearing")}</>
                          : <><Trash2 size={13} /> {confirmClear ? t("confirmClearAll") : t("clean")}</>}
                      </button>
                      {confirmClear && !clearingImgs && (
                        <button type="button" onClick={() => setConfirmClear(false)}
                          style={{ fontSize: 12, color: "#52525b", background: "none", border: "none", cursor: "pointer" }}>
                          {t("cancel")}
                        </button>
                      )}
                    </>
                  )}
                  {localImgMsg && <span style={{ fontSize: 12, color: localImgMsgError ? "#f87171" : "#34d399" }}>{localImgMsg}</span>}
                </div>

                {/* Lista de imágenes disponibles */}
                {localImages.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "20px 0" }}>
                    <p style={{ fontSize: 13, color: "#52525b" }}>
                      {localImgLoading ? t("loadingDots") : t("noImagesYet")}
                    </p>
                    {!localImgLoading && (
                      <p style={{ fontSize: 11, color: "#3f3f46", marginTop: 4 }}>
                        {t("uploadHint")}
                      </p>
                    )}
                  </div>
                ) : (
                  <>
                    <p style={{ fontSize: 11, color: "#52525b", marginBottom: 8 }}>
                      {t("selectOrder", { n: selectedImages.length })}
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 260, overflowY: "auto" }}>
                      {localImages.map((img) => {
                        const sel = selectedImages.includes(img.file);
                        const idx = selectedImages.indexOf(img.file);
                        return (
                          <div key={img.file} style={{
                            display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                            borderRadius: 10, cursor: "pointer",
                            background: sel ? "rgba(34,211,238,0.1)" : "rgba(255,255,255,0.03)",
                            border: `1px solid ${sel ? "rgba(34,211,238,0.35)" : "rgba(255,255,255,0.07)"}`,
                          }} onClick={() => {
                            if (sel) setSelectedImages((p) => p.filter((f) => f !== img.file));
                            else setSelectedImages((p) => [...p, img.file]);
                          }}>
                            {/* checkbox */}
                            <div style={{ width: 16, height: 16, borderRadius: 4, flexShrink: 0,
                              border: `2px solid ${sel ? "#22d3ee" : "#3f3f46"}`,
                              background: sel ? "#22d3ee" : "transparent",
                              display: "flex", alignItems: "center", justifyContent: "center" }}>
                              {sel && <span style={{ color: "#000", fontSize: 10 }}>✓</span>}
                            </div>
                            {/* orden */}
                            {sel && (
                              <span style={{ fontSize: 11, color: "#22d3ee", fontWeight: 700, minWidth: 20 }}>
                                #{idx + 1}
                              </span>
                            )}
                            <span style={{ fontSize: 12, color: sel ? "#e4e4e7" : "#71717a", flex: 1, wordBreak: "break-all" }}>
                              {img.name}
                            </span>
                            <span style={{ fontSize: 11, color: "#3f3f46", flexShrink: 0 }}>
                              {(img.size / 1024).toFixed(0)} KB
                            </span>
                            {/* flechas de orden */}
                            {sel && (
                              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                                <button type="button" onClick={(e) => { e.stopPropagation(); moveImage(idx, -1); }}
                                  style={{ background: "none", border: "none", color: "#52525b", cursor: "pointer", fontSize: 10, padding: "1px 4px" }}>▲</button>
                                <button type="button" onClick={(e) => { e.stopPropagation(); moveImage(idx, 1); }}
                                  style={{ background: "none", border: "none", color: "#52525b", cursor: "pointer", fontSize: 10, padding: "1px 4px" }}>▼</button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                      <button type="button" onClick={() => setSelectedImages(localImages.map((m) => m.file))}
                        style={{ fontSize: 11, color: "#22d3ee", background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                        {t("selectAll")}
                      </button>
                      <span style={{ color: "#3f3f46" }}>·</span>
                      <button type="button" onClick={() => setSelectedImages([])}
                        style={{ fontSize: 11, color: "#52525b", background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                        {t("deselect")}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* GUÍA DE IMÁGENES — solo modo local con guion generado */}
            {imageSource === "local" && imagePrompts.length > 0 && (
              <div style={{ padding: 16, borderRadius: 14, background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.2)" }}>
                {/* Header */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 700, color: "#c4b5fd" }}>
                      {t("promptGuideTitle", { n: imagePrompts.length })}
                    </p>
                    <p style={{ fontSize: 11, color: "#71717a", marginTop: 2 }}>
                      {t("promptGuideSub")}
                      {selectedImages.length > 0 && selectedImages.length !== imagePrompts.length && (
                        <span style={{ color: "#f87171", marginLeft: 6 }}>
                          {t("haveNeed", { have: selectedImages.length, need: imagePrompts.length })}
                          {selectedImages.length < imagePrompts.length
                            ? t("missingN", { n: imagePrompts.length - selectedImages.length })
                            : t("surplusN", { n: selectedImages.length - imagePrompts.length })}
                        </span>
                      )}
                      {selectedImages.length === imagePrompts.length && (
                        <span style={{ color: "#34d399", marginLeft: 6 }}>{t("correctCount")}</span>
                      )}
                    </p>
                  </div>
                  {/* Copiar todos */}
                  <button type="button" onClick={async () => {
                    const all = imagePrompts.map((p) => `${t("imageHeaderN", { n: p.index })}\n${p.prompt}`).join("\n\n");
                    await navigator.clipboard.writeText(all);
                    setCopiedAll(true);
                    setTimeout(() => setCopiedAll(false), 2000);
                  }} style={{
                    display: "flex", alignItems: "center", gap: 6, padding: "7px 14px",
                    borderRadius: 8, border: "none", cursor: "pointer",
                    background: copiedAll ? "rgba(52,211,153,0.15)" : "rgba(139,92,246,0.2)",
                    color: copiedAll ? "#34d399" : "#a78bfa",
                    fontSize: 12, fontWeight: 700,
                  }}>
                    {copiedAll ? t("copiedAll") : t("copyAll")}
                  </button>
                </div>

                {/* Lista de prompts */}
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 360, overflowY: "auto" }}>
                  {imagePrompts.map((p) => (
                    <PromptCard key={p.index} index={p.index} scene={p.scene} prompt={p.prompt} />
                  ))}
                </div>
              </div>
            )}

            <Field label={t("aspectLabel")}>
              <div style={{ display: "flex", gap: 10 }}>
                {([
                  { ratio: "9:16", sub: "TikTok / Shorts", w: 22, h: 38 },
                  { ratio: "16:9", sub: "YouTube", w: 38, h: 22 },
                  { ratio: "1:1", sub: "Instagram", w: 30, h: 30 },
                ] as const).map(({ ratio, sub, w, h }) => {
                  const active = aspect === ratio;
                  return (
                    <button key={ratio} type="button" onClick={() => setAspect(ratio)} style={{
                      flex: 1, padding: "14px 8px", borderRadius: 12,
                      border: active ? "1px solid rgba(34,211,238,0.5)" : "1px solid rgba(255,255,255,0.07)",
                      background: active ? "rgba(34,211,238,0.12)" : "rgba(255,255,255,0.03)",
                      display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                    }}>
                      <div style={{ width: w, height: h, borderRadius: 4, background: active ? "#22d3ee" : "#3f3f46" }} />
                      <span style={{ fontSize: 13, fontWeight: 700, color: active ? "#67e8f9" : "#71717a" }}>{ratio}</span>
                      <span style={{ fontSize: 11, color: active ? "#22d3ee" : "#52525b" }}>{sub}</span>
                    </button>
                  );
                })}
              </div>
            </Field>

            {/* Duración mínima solo aplica a Kie (resolución fija en 1K = 6 créditos/imagen) */}
            {imageSource === "kie" && (
              <Field label={t("minImgDurLabel", { n: minImageDuration.toFixed(1) })}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Clock size={13} color="#52525b" style={{ flexShrink: 0 }} />
                  <input type="range" min={1} max={6} step={0.5} value={minImageDuration}
                    onChange={(e) => setMinImageDuration(parseFloat(e.target.value))} style={{ flex: 1 }} />
                </div>
              </Field>
            )}
            {imageSource === "local" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <Field label={t("minImgDurLabel", { n: minImageDuration.toFixed(1) })}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Clock size={13} color="#52525b" style={{ flexShrink: 0 }} />
                    <input type="range" min={1} max={60} step={0.5} value={minImageDuration}
                      onChange={(e) => setMinImageDuration(parseFloat(e.target.value))} style={{ flex: 1 }} />
                  </div>
                </Field>

                {/* Botón de ajuste automático según imágenes seleccionadas */}
                {selectedImages.length > 0 && estimate.words > 0 && (
                  <div style={{ padding: "10px 14px", borderRadius: 10, background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.15)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <div>
                      <p style={{ fontSize: 12, color: "#67e8f9", fontWeight: 600, marginBottom: 2 }}>
                        {t("autoAdjustFor", { n: selectedImages.length })}
                      </p>
                      <p style={{ fontSize: 11, color: "#52525b" }}>
                        {(() => {
                          const audioSec = (estimate.words / (150 * voiceRate)) * 60;
                          const ideal = audioSec / selectedImages.length;
                          return t("autoAdjustCalc", { sec: audioSec.toFixed(0), n: selectedImages.length, d: ideal.toFixed(1) });
                        })()}
                      </p>
                    </div>
                    <button type="button" onClick={() => {
                      const audioSec = (estimate.words / (150 * voiceRate)) * 60;
                      const ideal = Math.max(1, audioSec / selectedImages.length);
                      setMinImageDuration(Math.round(ideal * 2) / 2); // redondea a 0.5s
                    }} style={{
                      padding: "7px 16px", borderRadius: 8, border: "none", cursor: "pointer",
                      background: "rgba(34,211,238,0.2)", color: "#22d3ee",
                      fontSize: 12, fontWeight: 700, whiteSpace: "nowrap",
                    }}>
                      {t("autoAdjustBtn")}
                    </button>
                  </div>
                )}
              </div>
            )}
            <p style={{ fontSize: 11, color: "#52525b", marginTop: -4 }}>
              {imageSource === "kie" ? t("kieDurHint") : t("localDurHint")}
            </p>

            {imageSource === "kie" && (
              <Field label={t("maxImagesLabel")}>
                <input type="number" min={0} max={500} value={maxImages}
                  onChange={(e) => setMaxImages(Math.max(0, Number(e.target.value) || 0))}
                  placeholder="0" style={INPUT} />
              </Field>
            )}

            {/* Estimador de costo en vivo */}
            <div style={{ padding: "14px 16px", borderRadius: 12, background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.18)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <ImageIcon size={15} color="#22d3ee" />
                  <span style={{ fontSize: 13, color: "#a1a1aa" }}>
                    {imageSource === "local" ? t("estimateLocal") : `${t("estimateWord")}${estimate.approx ? t("approxSuffix") : ""}`}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "#67e8f9" }}>
                    {imageSource === "local"
                      ? t("nImagesBold", { n: selectedImages.length })
                      : t("approxImages", { n: estimate.images })}
                  </span>
                  {imageSource === "kie" && (
                    <>
                      <span style={{ fontSize: 14, fontWeight: 700, color: "#c4b5fd" }}>{t("nCredits", { n: estimate.credits })}</span>
                      <span style={{ fontSize: 14, fontWeight: 700, color: "#34d399" }}>≈ ${estimate.usd.toFixed(2)}</span>
                    </>
                  )}
                  {imageSource === "local" && (
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#34d399" }}>{t("noKieCost")}</span>
                  )}
                  <span style={{ fontSize: 14, color: "#71717a" }}>{t("videoDurEst", { d: estimate.durLabel })}</span>
                </div>
              </div>
            </div>

            <Field label={t("codecLabel")}>
              <select value={codec} onChange={(e) => setCodec(e.target.value)} style={SELECT}>
                <option value="libx264" style={{ background: "#0d0d0d" }}>{t("codecCpu")}</option>
                <option value="h264_nvenc" style={{ background: "#0d0d0d" }}>h264_nvenc — NVIDIA</option>
                <option value="h264_amf" style={{ background: "#0d0d0d" }}>h264_amf — AMD</option>
                <option value="h264_qsv" style={{ background: "#0d0d0d" }}>h264_qsv — Intel QSV</option>
              </select>
            </Field>
          </div>
        )}
      </div>

      {/* VOZ */}
      <div style={CARD}>
        <SectionToggle open={openAudio} onToggle={() => setOpenAudio(!openAudio)} icon={Mic} title={t("voiceAudioSection")} color="#34d399" />
        {openAudio && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <Field label={t("ttsServerLabel")}>
              <select value={ttsServer} onChange={(e) => handleTtsServerChange(e.target.value as TtsServer)} style={SELECT}>
                <option value="no-voice" style={{ background: "#0d0d0d" }}>{t("noVoice")}</option>
                <option value="azure-tts-v1" style={{ background: "#0d0d0d" }}>{t("azureV1")}</option>
                <option value="azure-tts-v2" style={{ background: "#0d0d0d" }}>Azure TTS V2</option>
                <option value="siliconflow" style={{ background: "#0d0d0d" }}>SiliconFlow TTS</option>
                <option value="gemini-tts" style={{ background: "#0d0d0d" }}>Google Gemini TTS</option>
                <option value="mimo-tts" style={{ background: "#0d0d0d" }}>Xiaomi MiMo TTS</option>
              </select>
            </Field>

            {ttsServer !== "no-voice" && (
              <>
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
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <button type="button" onClick={handlePreviewVoice} disabled={!voice || previewLoading}
                      style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 18px", borderRadius: 10,
                        border: "1px solid rgba(52,211,153,0.35)", background: "rgba(52,211,153,0.1)", color: "#34d399",
                        fontSize: 14, fontWeight: 600, cursor: (!voice || previewLoading) ? "not-allowed" : "pointer",
                        opacity: (!voice || previewLoading) ? 0.5 : 1 }}>
                      {previewLoading ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} /> : <Play size={14} />}
                      {previewLoading ? t("generatingAudio") : t("testVoice")}
                    </button>
                    {previewUrl && <audio src={previewUrl} controls autoPlay style={{ height: 36, borderRadius: 8, flex: 1, minWidth: 200 }} />}
                  </div>
                  {previewError && (
                    <p style={{ fontSize: 12, color: "#f87171", padding: "6px 10px", borderRadius: 8,
                      background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>✕ {previewError}</p>
                  )}
                </div>
              </>
            )}

            <Row2>
              <Field label={t("voiceRateLabel", { n: voiceRate.toFixed(1) })}>
                <select value={voiceRate} onChange={(e) => setVoiceRate(Number(e.target.value))} style={SELECT}>
                  {[0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5].map((r) => <option key={r} value={r} style={{ background: "#0d0d0d" }}>{r}x</option>)}
                </select>
              </Field>
              <Field label={t("voiceVolumeLabel", { n: voiceVolume })}>
                <select value={voiceVolume} onChange={(e) => setVoiceVolume(Number(e.target.value))} style={SELECT}>
                  {[0.6, 0.8, 1.0, 1.2, 1.5, 2.0].map((v) => <option key={v} value={v} style={{ background: "#0d0d0d" }}>{v}x</option>)}
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
                          <Music size={13} color={selected ? "#c4b5fd" : "#52525b"} style={{ flexShrink: 0 }} />
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

      {/* SUBTÍTULOS */}
      <div style={CARD}>
        <SectionToggle open={openSubs} onToggle={() => setOpenSubs(!openSubs)} icon={Type} title={t("subtitlesSection")} color="#f59e0b" />
        {openSubs && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <span style={{ fontSize: 13, color: "#a1a1aa" }}>{t("burnedSubtitles")}</span>
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
                    </select>
                  </Field>
                </Row2>
                <Row2>
                  <Field label={t("fontSizeLabel", { n: fontSize })}>
                    <input type="range" min={30} max={100} step={2} value={fontSize} onChange={(e) => setFontSize(Number(e.target.value))} />
                  </Field>
                  <Field label={t("strokeWidthLabel", { n: strokeWidth })}>
                    <input type="range" min={0} max={10} step={0.5} value={strokeWidth} onChange={(e) => setStrokeWidth(parseFloat(e.target.value))} />
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
              </>
            )}
          </div>
        )}
      </div>

      {logs.length > 0 && (
        <div style={{ marginBottom: 4 }}><LogPanel logs={logs} title={t("activity")} maxHeight={200} /></div>
      )}

      <div style={{ paddingTop: 8, paddingBottom: 40 }}>
        <button type="submit" disabled={!subject.trim() || loading} style={{
          width: "100%", padding: "18px", borderRadius: 18, border: "none",
          background: !subject.trim() || loading ? "rgba(255,255,255,0.06)" : "linear-gradient(135deg, #06b6d4, #8b5cf6)",
          color: !subject.trim() || loading ? "#52525b" : "#ffffff",
          fontSize: 17, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          boxShadow: subject.trim() && !loading ? "0 0 40px rgba(34,211,238,0.3)" : "none", transition: "all 0.25s",
        }}>
          <ImageIcon size={20} />
          {loading
            ? t("creatingVideo")
            : imageSource === "local"
            ? t("createVideoLocal", { n: selectedImages.length })
            : t("createVideoKie", { n: estimate.images, c: estimate.credits, usd: estimate.usd.toFixed(2) })}
        </button>
        <p style={{ textAlign: "center", fontSize: 12, color: "#3f3f46", marginTop: 8 }}>
          {paragraphs} {paragraphs > 1 ? t("paragraphsWord") : t("paragraphWord")} · {aspect} · 1K · {kieTheme || "general"}
          {maxImages > 0 ? ` · ${t("maxImgShort", { n: maxImages })}` : ""}
          {ttsServer !== "no-voice" ? ` · ${voice.split("-").slice(0,3).join("-")}` : ` · ${t("noVoiceSuffix")}`}
        </p>
      </div>
    </form>
  );
}
