"use client";

import { useEffect, useState, useRef } from "react";
import { Download, Trash2, Film, RefreshCw, HardDrive, Clock, Copy, Check, List } from "lucide-react";
import type { VideoItem } from "@/app/api/library/route";

function fmtSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtDate(epoch: number) {
  const d = new Date(epoch);
  return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" }) +
    " " + d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}

function VideoCard({ video, onDelete }: { video: VideoItem; onDelete: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [showChapters, setShowChapters] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyChapters = async () => {
    if (!video.chapters) return;
    await navigator.clipboard.writeText(video.chapters);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDelete = async () => {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    setDeleting(true);
    setDeleteError("");

    // Release file lock: pause + clear src before deleting
    const vid = videoRef.current;
    if (vid) {
      vid.pause();
      vid.src = "";
      vid.load();
    }
    // Wait for browser to release the file handle
    await new Promise((r) => setTimeout(r, 800));

    try {
      const res = await fetch(`/api/library?taskId=${video.taskId}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok || data.error) {
        setDeleteError(data.error ?? "Error al eliminar");
        setDeleting(false);
        setConfirmDelete(false);
      } else {
        onDelete();
      }
    } catch (e) {
      setDeleteError(String(e));
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <div style={{
      borderRadius: 18,
      border: "1px solid rgba(255,255,255,0.08)",
      background: "rgba(255,255,255,0.03)",
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      transition: "border-color 0.2s",
    }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "rgba(139,92,246,0.3)")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)")}
    >
      {/* Video preview con controles nativos */}
      <div style={{ background: "#000", aspectRatio: "9/16", maxHeight: 340, overflow: "hidden" }}>
        <video
          ref={videoRef}
          src={video.streamUrl}
          controls
          preload="metadata"
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
        />
      </div>

      {/* Info */}
      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        {video.script && (
          <p style={{
            fontSize: 12, color: "#a1a1aa", lineHeight: 1.5,
            display: "-webkit-box", WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical" as const, overflow: "hidden",
          }}>
            {video.script}…
          </p>
        )}

        <div style={{ display: "flex", gap: 12, fontSize: 11, color: "#52525b" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <HardDrive size={11} /> {fmtSize(video.sizeBytes)}
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <Clock size={11} /> {fmtDate(video.createdAt)}
          </span>
        </div>

        <p style={{ fontSize: 10, color: "#3f3f46", fontFamily: "monospace", wordBreak: "break-all" }}>
          {video.taskId.slice(0, 8)}…/{video.filename}
        </p>

        {/* Actions */}
        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          <a
            href={video.downloadUrl}
            download
            style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
              gap: 6, padding: "9px", borderRadius: 10, textDecoration: "none",
              background: "linear-gradient(135deg, #8b5cf6, #06b6d4)",
              color: "#fff", fontSize: 13, fontWeight: 600,
            }}
          >
            <Download size={14} /> Descargar
          </a>

          <button
            onClick={handleDelete}
            disabled={deleting}
            style={{
              padding: "9px 14px", borderRadius: 10, border: "none", cursor: "pointer",
              background: confirmDelete ? "rgba(239,68,68,0.2)" : "rgba(255,255,255,0.05)",
              color: confirmDelete ? "#f87171" : "#71717a",
              fontSize: 13, fontWeight: 600, transition: "all 0.2s",
              display: "flex", alignItems: "center", gap: 6,
            }}
          >
            {deleting
              ? <RefreshCw size={14} style={{ animation: "spin-slow 1s linear infinite" }} />
              : <Trash2 size={14} />}
            {confirmDelete ? "¿Seguro?" : "Eliminar"}
          </button>
        </div>

        {confirmDelete && !deleting && (
          <button
            onClick={() => setConfirmDelete(false)}
            style={{
              padding: "6px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)",
              background: "none", color: "#52525b", fontSize: 12, cursor: "pointer",
            }}
          >
            Cancelar
          </button>
        )}
        {deleteError && (
          <p style={{ fontSize: 11, color: "#f87171", lineHeight: 1.5, marginTop: 2 }}>
            ✕ {deleteError}
          </p>
        )}

        {/* Capítulos YouTube */}
        {video.chapters && (
          <div style={{ marginTop: 4 }}>
            <button
              type="button"
              onClick={() => setShowChapters(!showChapters)}
              style={{
                width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "8px 12px", borderRadius: 10, border: "1px solid rgba(34,211,238,0.2)",
                background: showChapters ? "rgba(34,211,238,0.08)" : "rgba(34,211,238,0.04)",
                color: "#67e8f9", fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <List size={13} /> Capítulos YouTube
              </span>
              <span style={{ fontSize: 10, color: "#22d3ee" }}>{showChapters ? "▲" : "▼"}</span>
            </button>

            {showChapters && (
              <div style={{
                marginTop: 6, padding: "10px 12px", borderRadius: 10,
                background: "rgba(0,0,0,0.4)", border: "1px solid rgba(34,211,238,0.15)",
              }}>
                <pre style={{
                  fontSize: 11, color: "#a1a1aa", lineHeight: 1.8, margin: 0,
                  whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "monospace",
                  maxHeight: 180, overflowY: "auto",
                }}>
                  {video.chapters}
                </pre>
                <button
                  type="button"
                  onClick={handleCopyChapters}
                  style={{
                    marginTop: 8, width: "100%", display: "flex", alignItems: "center",
                    justifyContent: "center", gap: 6, padding: "7px",
                    borderRadius: 8, border: "none", cursor: "pointer",
                    background: copied ? "rgba(52,211,153,0.15)" : "rgba(34,211,238,0.12)",
                    color: copied ? "#34d399" : "#22d3ee",
                    fontSize: 12, fontWeight: 600, transition: "all 0.2s",
                  }}
                >
                  {copied ? <Check size={13} /> : <Copy size={13} />}
                  {copied ? "¡Copiado!" : "Copiar para YouTube"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface CacheInfo { count: number; sizeBytes: number; }

export default function VideoLibrary() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cacheInfo, setCacheInfo] = useState<CacheInfo | null>(null);
  const [clearingCache, setClearingCache] = useState(false);
  const [confirmClearCache, setConfirmClearCache] = useState(false);
  const [cacheMsg, setCacheMsg] = useState("");

  const loadVideos = async () => {
    setLoading(true);
    setError("");
    try {
      const [resVideos, resCache] = await Promise.all([
        fetch("/api/library"),
        fetch("/api/library?action=cache-info"),
      ]);
      const dataVideos = await resVideos.json();
      const dataCache = await resCache.json();
      setVideos(dataVideos.videos ?? []);
      setCacheInfo(dataCache);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleClearCache = async () => {
    if (!confirmClearCache) { setConfirmClearCache(true); return; }
    setClearingCache(true);
    setCacheMsg("");
    try {
      const res = await fetch("/api/library?action=clear-cache", { method: "DELETE" });
      const data = await res.json();
      if (data.ok) {
        setCacheMsg(`✓ ${data.deleted} clips eliminados`);
        setCacheInfo({ count: 0, sizeBytes: 0 });
      } else {
        setCacheMsg(`Error: ${data.error}`);
      }
    } catch (e) {
      setCacheMsg(String(e));
    } finally {
      setClearingCache(false);
      setConfirmClearCache(false);
    }
  };

  useEffect(() => { loadVideos(); }, []);

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", paddingTop: 40 }} className="fade-in-up">

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <Film size={20} color="#a78bfa" />
            <h2 style={{ fontSize: 24, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em" }}>
              Mis videos
            </h2>
            <span style={{
              fontSize: 12, fontWeight: 600, padding: "3px 10px", borderRadius: 99,
              background: "rgba(139,92,246,0.15)", color: "#a78bfa",
              border: "1px solid rgba(139,92,246,0.2)",
            }}>
              {videos.length}
            </span>
          </div>
          <p style={{ fontSize: 13, color: "#52525b" }}>
            Videos generados guardados localmente
          </p>
        </div>

        <button
          onClick={loadVideos}
          disabled={loading}
          style={{
            display: "flex", alignItems: "center", gap: 7, padding: "9px 18px",
            borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(255,255,255,0.04)", color: "#a1a1aa",
            fontSize: 13, fontWeight: 600, cursor: "pointer",
          }}
        >
          <RefreshCw size={14} style={loading ? { animation: "spin-slow 1s linear infinite" } : {}} />
          Actualizar
        </button>
      </div>

      {/* Cache panel */}
      {cacheInfo && (
        <div style={{
          marginBottom: 28, padding: "14px 18px", borderRadius: 14,
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)",
          display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <HardDrive size={15} color="#71717a" />
            <span style={{ fontSize: 13, color: "#71717a" }}>
              Caché de clips: <strong style={{ color: "#a1a1aa" }}>{cacheInfo.count} archivos</strong>
              {" · "}<strong style={{ color: "#a1a1aa" }}>{fmtSize(cacheInfo.sizeBytes)}</strong>
            </span>
            {cacheMsg && (
              <span style={{ fontSize: 12, color: cacheMsg.startsWith("✓") ? "#34d399" : "#f87171", marginLeft: 8 }}>
                {cacheMsg}
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {confirmClearCache && !clearingCache && (
              <button onClick={() => setConfirmClearCache(false)} style={{
                padding: "7px 14px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)",
                background: "none", color: "#52525b", fontSize: 12, cursor: "pointer",
              }}>
                Cancelar
              </button>
            )}
            <button
              onClick={handleClearCache}
              disabled={clearingCache || cacheInfo.count === 0}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "7px 16px", borderRadius: 8, border: "none", cursor: cacheInfo.count === 0 ? "not-allowed" : "pointer",
                background: confirmClearCache ? "rgba(239,68,68,0.15)" : "rgba(255,255,255,0.05)",
                color: confirmClearCache ? "#f87171" : "#71717a",
                fontSize: 12, fontWeight: 600, transition: "all 0.2s",
                opacity: cacheInfo.count === 0 ? 0.4 : 1,
              }}
            >
              {clearingCache
                ? <RefreshCw size={12} style={{ animation: "spin-slow 1s linear infinite" }} />
                : <Trash2 size={12} />}
              {confirmClearCache ? "¿Limpiar todo?" : "Limpiar caché"}
            </button>
          </div>
        </div>
      )}

      {/* States */}
      {error && (
        <div style={{ padding: "16px 20px", borderRadius: 14, background: "rgba(239,68,68,0.07)",
          border: "1px solid rgba(239,68,68,0.2)", color: "#f87171", fontSize: 13, marginBottom: 24 }}>
          Error: {error}
        </div>
      )}

      {!loading && videos.length === 0 && (
        <div style={{ textAlign: "center", paddingTop: 80, paddingBottom: 80 }}>
          <div style={{ width: 72, height: 72, borderRadius: "50%", background: "rgba(255,255,255,0.04)",
            display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
            <Film size={30} color="#3f3f46" />
          </div>
          <p style={{ color: "#52525b", fontSize: 15, fontWeight: 600 }}>Sin videos todavía</p>
          <p style={{ color: "#3f3f46", fontSize: 13, marginTop: 6 }}>
            Genera tu primer video y aparecerá aquí
          </p>
        </div>
      )}

      {/* Grid */}
      {videos.length > 0 && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 20,
        }}>
          {videos.map((v) => (
            <VideoCard
              key={`${v.taskId}-${v.filename}`}
              video={v}
              onDelete={() => setVideos((prev) => prev.filter(
                (x) => !(x.taskId === v.taskId && x.filename === v.filename)
              ))}
            />
          ))}
        </div>
      )}
    </div>
  );
}
