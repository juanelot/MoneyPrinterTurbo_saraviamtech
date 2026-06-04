"use client";

import { Download, RotateCcw, CheckCircle, FolderOpen } from "lucide-react";
import type { TaskResult } from "@/app/page";

interface Props {
  result: TaskResult;
  onReset: () => void;
  onViewLibrary?: () => void;
}

export default function VideoResult({ result, onReset, onViewLibrary }: Props) {
  const filename = result.videos[0]?.split("/").pop() ?? result.videos[0];

  const videoUrl = filename
    ? `/api/mpt/v1/tasks/${result.taskId}/stream/${filename}`
    : null;

  const downloadUrl = filename
    ? `/api/mpt/v1/tasks/${result.taskId}/download/${filename}`
    : null;

  return (
    <div style={{ maxWidth: 600, margin: "60px auto 0" }} className="fade-in-up">

      {/* Badge éxito */}
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "8px 18px", borderRadius: 99, fontSize: 13, fontWeight: 600,
          background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.25)", color: "#34d399",
        }}>
          <CheckCircle size={15} />
          Video generado exitosamente
        </div>
      </div>

      <h2 style={{ fontSize: 30, fontWeight: 800, color: "#ffffff", textAlign: "center", marginBottom: 32, letterSpacing: "-0.02em" }}>
        Tu video está listo
      </h2>

      {/* Video player */}
      <div style={{
        borderRadius: 20, overflow: "hidden", marginBottom: 20,
        background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.08)",
        boxShadow: "0 0 60px rgba(139,92,246,0.15)",
      }}>
        {videoUrl ? (
          <video
            src={videoUrl}
            controls
            autoPlay
            style={{ width: "100%", maxHeight: 620, objectFit: "contain", display: "block" }}
          />
        ) : (
          <div style={{ height: 280, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <CheckCircle size={40} color="#34d399" />
            <p style={{ color: "#52525b", fontSize: 14 }}>Task ID: {result.taskId.slice(0, 8)}…</p>
          </div>
        )}
      </div>

      {/* Acciones */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        {downloadUrl && (
          <a
            href={downloadUrl}
            download
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              padding: "16px", borderRadius: 14, textDecoration: "none",
              background: "linear-gradient(135deg, #8b5cf6, #06b6d4)",
              color: "#ffffff", fontSize: 15, fontWeight: 700,
              boxShadow: "0 0 24px rgba(139,92,246,0.3)",
            }}
          >
            <Download size={18} />
            Descargar video
          </a>
        )}
        <button
          onClick={onReset}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            padding: "16px", borderRadius: 14, border: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(255,255,255,0.06)", color: "#a1a1aa",
            fontSize: 15, fontWeight: 600, transition: "all 0.2s", cursor: "pointer",
          }}
        >
          <RotateCcw size={18} />
          Nuevo video
        </button>
      </div>
      {onViewLibrary && (
        <button
          onClick={onViewLibrary}
          style={{
            width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            padding: "12px", borderRadius: 14, border: "1px solid rgba(139,92,246,0.2)",
            background: "rgba(139,92,246,0.07)", color: "#a78bfa",
            fontSize: 14, fontWeight: 600, cursor: "pointer", marginBottom: 16,
          }}
        >
          Ver todos mis videos →
        </button>
      )}

      {/* Info de ubicación */}
      <div style={{
        padding: "14px 18px", borderRadius: 14,
        background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
        display: "flex", alignItems: "flex-start", gap: 10,
      }}>
        <FolderOpen size={15} color="#52525b" style={{ marginTop: 2, flexShrink: 0 }} />
        <p style={{ fontSize: 13, color: "#52525b", lineHeight: 1.6 }}>
          El archivo también está guardado en{" "}
          <code style={{ color: "#a1a1aa", fontSize: 12, background: "rgba(255,255,255,0.06)", padding: "1px 6px", borderRadius: 4 }}>
            storage/tasks/{result.taskId.slice(0, 8)}…/final-1.mp4
          </code>{" "}
          dentro de la carpeta de MoneyPrinterTurbo.
        </p>
      </div>
    </div>
  );
}
