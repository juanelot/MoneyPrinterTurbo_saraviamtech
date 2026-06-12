"use client";

import { useState, useCallback } from "react";
import { Wand2, Film, Image as ImageIcon } from "lucide-react";
import Header from "@/components/Header";
import VideoForm from "@/components/VideoForm";
import ZennForm from "@/components/ZennForm";
import GenerationProgress from "@/components/GenerationProgress";
import VideoResult from "@/components/VideoResult";
import VideoLibrary from "@/components/VideoLibrary";
import { type LogEntry } from "@/components/LogPanel";

export type GenerationStatus = "idle" | "generating" | "done" | "error";

export interface TaskResult {
  taskId: string;
  videos: string[];
}

type Tab = "create" | "zenn" | "library";

export default function Home() {
  const [tab, setTab] = useState<Tab>("create");
  const [status, setStatus] = useState<GenerationStatus>("idle");
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const handleGenerated = (result: TaskResult) => {
    setTaskResult(result);
    setStatus("done");
  };

  const handleError = (msg: string) => {
    setErrorMsg(msg);
    setStatus("error");
  };

  const handleReset = () => {
    setStatus("idle");
    setTaskResult(null);
    setErrorMsg("");
    setLogs([]);
  };

  const handleLogsChange = useCallback((newLogs: LogEntry[]) => {
    setLogs(newLogs);
  }, []);

  const TAB_BTN = (active: boolean): React.CSSProperties => ({
    display: "flex", alignItems: "center", gap: 7,
    padding: "8px 20px", borderRadius: 10, border: "none",
    background: active ? "rgba(139,92,246,0.15)" : "transparent",
    color: active ? "#a78bfa" : "#52525b",
    fontSize: 14, fontWeight: 600, cursor: "pointer",
    transition: "all 0.2s",
    outline: active ? "1px solid rgba(139,92,246,0.3)" : "none",
  });

  return (
    <div style={{ minHeight: "100vh", background: "#000000" }}>
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: "radial-gradient(ellipse 90% 55% at 50% -15%, rgba(139,92,246,0.13) 0%, transparent 65%)",
      }} />

      <Header />

      {/* Tab bar — solo visible en estado idle o library */}
      {(status === "idle" || tab === "library") && (
        <div style={{
          position: "relative", zIndex: 2,
          display: "flex", justifyContent: "center",
          paddingTop: 8, paddingBottom: 4,
        }}>
          <div style={{
            display: "inline-flex", gap: 4, padding: "4px",
            borderRadius: 14, background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.07)",
          }}>
            <button style={TAB_BTN(tab === "create")} onClick={() => setTab("create")}>
              <Wand2 size={15} />
              Crear video
            </button>
            <button style={TAB_BTN(tab === "zenn")} onClick={() => setTab("zenn")}>
              <ImageIcon size={15} />
              Video de imágenes
            </button>
            <button style={TAB_BTN(tab === "library")} onClick={() => setTab("library")}>
              <Film size={15} />
              Mis videos
            </button>
          </div>
        </div>
      )}

      <main style={{ position: "relative", zIndex: 1, maxWidth: 1100, margin: "0 auto", padding: "0 24px 120px" }}>

        {/* ── TAB: LIBRARY ── */}
        {tab === "library" && <VideoLibrary />}

        {/* ── TAB: CREATE ── */}
        {/* Formularios montados con display:none mientras generan — el polling no se detiene */}
        {tab === "create" && (
          <div style={{ display: status === "idle" ? "block" : "none" }}>
            <VideoForm
              onStart={() => setStatus("generating")}
              onGenerated={handleGenerated}
              onError={handleError}
              onLogsChange={handleLogsChange}
            />
          </div>
        )}

        {tab === "zenn" && (
          <div style={{ display: status === "idle" ? "block" : "none" }}>
            <ZennForm
              onStart={() => setStatus("generating")}
              onGenerated={handleGenerated}
              onError={handleError}
              onLogsChange={handleLogsChange}
            />
          </div>
        )}

        {/* Estado de generación compartido por ambos generadores */}
        {tab !== "library" && (
          <>
            {status === "generating" && (
              <GenerationProgress logs={logs} />
            )}

            {status === "done" && taskResult && (
              <VideoResult
                result={taskResult}
                onReset={handleReset}
                onViewLibrary={() => { setTab("library"); handleReset(); }}
              />
            )}

            {status === "error" && (
              <div style={{ marginTop: 80, display: "flex", justifyContent: "center" }} className="fade-in-up">
                <div style={{
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 16,
                  padding: "40px", borderRadius: 24,
                  background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.18)",
                  maxWidth: 520, width: "100%",
                }}>
                  <div style={{
                    width: 52, height: 52, borderRadius: "50%",
                    background: "rgba(239,68,68,0.15)", display: "flex", alignItems: "center",
                    justifyContent: "center", fontSize: 22, color: "#f87171",
                  }}>✕</div>
                  <div style={{ textAlign: "center" }}>
                    <p style={{ color: "#f87171", fontWeight: 600, fontSize: 16, marginBottom: 6 }}>Error al generar el video</p>
                    <p style={{ color: "#71717a", fontSize: 14, lineHeight: 1.6 }}>{errorMsg || "Ocurrió un error inesperado"}</p>
                  </div>
                  {logs.length > 0 && (
                    <div style={{ width: "100%", marginTop: 4 }}>
                      <div style={{
                        borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)",
                        background: "#080808", overflow: "hidden",
                        fontFamily: "monospace", maxHeight: 200, overflowY: "auto",
                        padding: "10px 14px",
                      }}>
                        {logs.map((entry, i) => (
                          <div key={i} style={{ fontSize: 11, lineHeight: 1.8, color: entry.level === "error" ? "#f87171" : entry.level === "success" ? "#34d399" : entry.level === "warn" ? "#fbbf24" : "#52525b" }}>
                            <span style={{ color: "#3f3f46", marginRight: 8 }}>{entry.time}</span>
                            <span style={{ marginRight: 8, fontWeight: 700 }}>{entry.level.toUpperCase().padEnd(5)}</span>
                            {entry.msg}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 10 }}>
                    <button onClick={handleReset} style={{
                      padding: "10px 24px", borderRadius: 12, border: "1px solid rgba(239,68,68,0.25)",
                      background: "rgba(239,68,68,0.12)", color: "#f87171",
                      fontSize: 14, fontWeight: 600, cursor: "pointer",
                    }}>
                      Intentar de nuevo
                    </button>
                    <button onClick={() => { setTab("library"); handleReset(); }} style={{
                      padding: "10px 24px", borderRadius: 12, border: "1px solid rgba(255,255,255,0.1)",
                      background: "rgba(255,255,255,0.05)", color: "#a1a1aa",
                      fontSize: 14, fontWeight: 600, cursor: "pointer",
                    }}>
                      Ver mis videos
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
