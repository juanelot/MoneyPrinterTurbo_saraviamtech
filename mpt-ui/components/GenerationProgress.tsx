"use client";

import { useEffect, useState } from "react";
import { FileText, Mic, Download, Film, Sparkles } from "lucide-react";
import LogPanel, { type LogEntry } from "@/components/LogPanel";
import { useT, type TKey } from "@/lib/i18n";

const STEP_DEFS: { icon: React.ElementType; label: TKey; detail: TKey; ms: number }[] = [
  { icon: FileText, label: "step1Label", detail: "step1Detail", ms: 8000 },
  { icon: Mic, label: "step2Label", detail: "step2Detail", ms: 10000 },
  { icon: Download, label: "step3Label", detail: "step3Detail", ms: 20000 },
  { icon: Film, label: "step4Label", detail: "step4Detail", ms: 180000 },
];

const TIP_KEYS: TKey[] = ["tip1", "tip2", "tip3", "tip4", "tip5", "tip6", "tip7"];

function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec.toString().padStart(2, "0")}s` : `${sec}s`;
}

interface Props {
  logs?: LogEntry[];
}

export default function GenerationProgress({ logs = [] }: Props) {
  const { t } = useT();
  const [elapsed, setElapsed] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [tipIndex] = useState(Math.floor(Math.random() * TIP_KEYS.length));
  const [ffmpegWarning, setFfmpegWarning] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let acc = 0;
    for (let i = 0; i < STEP_DEFS.length - 1; i++) {
      acc += STEP_DEFS[i].ms;
      if (elapsed * 1000 < acc) { setCurrentStep(i); return; }
    }
    setCurrentStep(STEP_DEFS.length - 1);
  }, [elapsed]);

  // Mostrar aviso FFmpeg si lleva más de 3 min en el paso final
  useEffect(() => {
    if (currentStep === STEP_DEFS.length - 1 && elapsed > 180) {
      setFfmpegWarning(true);
    }
  }, [currentStep, elapsed]);

  // Sincronizar step con los logs reales si hay info de progreso
  useEffect(() => {
    const last = logs[logs.length - 1];
    if (!last) return;
    const msg = last.msg.toLowerCase();
    if (msg.includes("guión") || msg.includes("script")) setCurrentStep(0);
    else if (msg.includes("audio") || msg.includes("voz") || msg.includes("voice") || msg.includes("tts")) setCurrentStep(1);
    else if (msg.includes("clip") || msg.includes("material") || msg.includes("pexels") || msg.includes("imágenes") || msg.includes("images")) setCurrentStep(2);
    else if (msg.includes("ensambland") || msg.includes("assembl") || msg.includes("ffmpeg") || msg.includes("final")) setCurrentStep(3);
  }, [logs]);

  const progress = Math.min(((currentStep + 0.5) / STEP_DEFS.length) * 100, 96);

  return (
    <div style={{ maxWidth: 620, margin: "60px auto 0" }} className="fade-in-up">

      {/* Orb animado */}
      <div style={{ position: "relative", width: 96, height: 96, margin: "0 auto 32px" }}>
        <div className="pulse-glow" style={{
          position: "absolute", inset: -8, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(139,92,246,0.3) 0%, rgba(6,182,212,0.15) 60%, transparent 100%)",
          filter: "blur(12px)",
        }} />
        <div style={{
          position: "relative", width: 96, height: 96, borderRadius: "50%",
          background: "linear-gradient(135deg, #8b5cf6, #06b6d4)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 0 40px rgba(139,92,246,0.5)",
        }}>
          <Sparkles size={36} color="white" />
        </div>
      </div>

      <h2 style={{ fontSize: 28, fontWeight: 800, color: "#ffffff", marginBottom: 8, letterSpacing: "-0.02em", textAlign: "center" }}>
        {t("generatingYourVideo")}
      </h2>
      <p style={{ fontSize: 14, color: "#52525b", marginBottom: 32, textAlign: "center" }}>
        {t("elapsedTime")} <span style={{ color: "#a78bfa", fontWeight: 600 }}>{formatTime(elapsed)}</span>
      </p>

      {/* Pasos */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 24 }}>
        {STEP_DEFS.map((step, i) => {
          const Icon = step.icon;
          const isActive = i === currentStep;
          const isDone = i < currentStep;

          return (
            <div
              key={i}
              style={{
                display: "flex", alignItems: "center", gap: 14,
                padding: "14px 16px", borderRadius: 14,
                background: isActive ? "rgba(139,92,246,0.1)" : isDone ? "rgba(16,185,129,0.07)" : "rgba(255,255,255,0.03)",
                border: isActive ? "1px solid rgba(139,92,246,0.3)" : isDone ? "1px solid rgba(16,185,129,0.2)" : "1px solid rgba(255,255,255,0.05)",
                transition: "all 0.4s",
              }}
            >
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: isActive ? "rgba(139,92,246,0.18)" : isDone ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.05)",
              }}>
                {isDone ? (
                  <span style={{ color: "#34d399", fontSize: 16, fontWeight: 800 }}>✓</span>
                ) : (
                  <Icon size={16} color={isActive ? "#a78bfa" : "#52525b"} />
                )}
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: isActive ? "#ffffff" : isDone ? "#34d399" : "#52525b" }}>
                  {t(step.label)}
                </div>
                <div style={{ fontSize: 12, color: isActive ? "#71717a" : isDone ? "#065f46" : "#3f3f46", marginTop: 2 }}>
                  {t(step.detail)}
                </div>
              </div>

              {isActive && (
                <div style={{ display: "flex", gap: 4 }}>
                  {[0, 1, 2].map((d) => (
                    <div
                      key={d}
                      className="pulse-glow"
                      style={{
                        width: 6, height: 6, borderRadius: "50%", background: "#8b5cf6",
                        animationDelay: `${d * 0.3}s`,
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Barra de progreso */}
      <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden", marginBottom: 8 }}>
        <div style={{
          height: "100%", borderRadius: 3, position: "relative", overflow: "hidden",
          width: `${progress}%`, background: "linear-gradient(90deg, #8b5cf6, #06b6d4)",
          transition: "width 1s ease",
        }}>
          <div className="shimmer" style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)" }} />
        </div>
      </div>
      <p style={{ fontSize: 13, color: "#52525b", marginBottom: 24, textAlign: "center" }}>
        {t("pctComplete", { n: Math.round(progress) })}
      </p>

      {/* Aviso FFmpeg lento */}
      {ffmpegWarning && (
        <div style={{
          marginBottom: 16, padding: "14px 18px", borderRadius: 14,
          background: "rgba(251,191,36,0.07)", border: "1px solid rgba(251,191,36,0.2)",
          display: "flex", gap: 12, alignItems: "flex-start",
        }}>
          <span style={{ fontSize: 18, flexShrink: 0 }}>⏳</span>
          <div>
            <p style={{ fontSize: 13, fontWeight: 600, color: "#fbbf24", marginBottom: 4 }}>
              {t("ffmpegTitle")}
            </p>
            <p style={{ fontSize: 12, color: "#78716c", lineHeight: 1.6 }}>
              {t("ffmpegBody")}
            </p>
          </div>
        </div>
      )}

      {/* Panel de logs en tiempo real */}
      <div style={{ marginBottom: 20 }}>
        <LogPanel logs={logs} title={t("liveLog")} maxHeight={220} />
      </div>

      {/* Tip */}
      <div style={{ padding: "14px 18px", borderRadius: 14, background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.15)" }}>
        <p style={{ fontSize: 13, color: "#71717a", lineHeight: 1.6 }}>
          <span style={{ color: "#a78bfa", fontWeight: 600 }}>{t("tipLabel")}</span>
          {t(TIP_KEYS[tipIndex])}
        </p>
      </div>
    </div>
  );
}
