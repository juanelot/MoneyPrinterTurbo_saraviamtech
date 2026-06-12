"use client";

import { useEffect, useRef } from "react";
import { Terminal } from "lucide-react";
import { useT } from "@/lib/i18n";

export interface LogEntry {
  time: string;
  level: "info" | "success" | "error" | "warn" | "debug";
  msg: string;
}

interface Props {
  logs: LogEntry[];
  title?: string;
  maxHeight?: number;
}

const LEVEL_COLOR: Record<LogEntry["level"], string> = {
  info:    "#a1a1aa",
  success: "#34d399",
  error:   "#f87171",
  warn:    "#fbbf24",
  debug:   "#60a5fa",
};

const LEVEL_PREFIX: Record<LogEntry["level"], string> = {
  info:    "INFO ",
  success: "OK   ",
  error:   "ERR  ",
  warn:    "WARN ",
  debug:   "DBG  ",
};

export function makeLog(level: LogEntry["level"], msg: string): LogEntry {
  const now = new Date();
  const time = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}:${now.getSeconds().toString().padStart(2, "0")}`;
  return { time, level, msg };
}

export default function LogPanel({ logs, title = "Logs", maxHeight = 260 }: Props) {
  const { t } = useT();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div style={{
      borderRadius: 14,
      border: "1px solid rgba(255,255,255,0.08)",
      background: "#080808",
      overflow: "hidden",
      fontFamily: "'Fira Code', 'Cascadia Code', 'Consolas', monospace",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "10px 14px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(255,255,255,0.03)",
      }}>
        <Terminal size={13} color="#52525b" />
        <span style={{ fontSize: 11, fontWeight: 600, color: "#52525b", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          {title}
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 5 }}>
          {(["#ef4444", "#f59e0b", "#22c55e"] as const).map((c, i) => (
            <div key={i} style={{ width: 9, height: 9, borderRadius: "50%", background: c, opacity: 0.6 }} />
          ))}
        </div>
      </div>

      {/* Log lines */}
      <div style={{ maxHeight, overflowY: "auto", padding: "10px 4px" }}>
        {logs.length === 0 ? (
          <p style={{ fontSize: 12, color: "#3f3f46", padding: "4px 12px" }}>
            {t("noActivity")}
          </p>
        ) : (
          logs.map((entry, i) => (
            <div
              key={i}
              style={{
                display: "flex", gap: 0, alignItems: "flex-start",
                padding: "2px 12px",
                background: entry.level === "error" ? "rgba(239,68,68,0.05)"
                  : entry.level === "success" ? "rgba(52,211,153,0.04)"
                  : "transparent",
              }}
            >
              <span style={{ color: "#3f3f46", fontSize: 11, flexShrink: 0, marginRight: 8, userSelect: "none" }}>
                {entry.time}
              </span>
              <span style={{
                fontSize: 11, fontWeight: 700, flexShrink: 0, marginRight: 8,
                color: LEVEL_COLOR[entry.level],
              }}>
                {LEVEL_PREFIX[entry.level]}
              </span>
              <span style={{ fontSize: 12, color: LEVEL_COLOR[entry.level], lineHeight: 1.5, wordBreak: "break-all" }}>
                {entry.msg}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
