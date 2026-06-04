import { Video, Sparkles } from "lucide-react";

export default function Header() {
  return (
    <header style={{
      position: "sticky",
      top: 0,
      zIndex: 50,
      background: "rgba(0,0,0,0.85)",
      borderBottom: "1px solid rgba(255,255,255,0.07)",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
    }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 24px", height: 64, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: "linear-gradient(135deg, #8b5cf6, #06b6d4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 16px rgba(139,92,246,0.4)",
          }}>
            <Video size={18} color="white" />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontWeight: 700, color: "#ffffff", fontSize: 16, letterSpacing: "-0.01em" }}>VideoAI Studio</span>
            <span style={{
              fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
              background: "rgba(139,92,246,0.15)", color: "#a78bfa",
              border: "1px solid rgba(139,92,246,0.25)",
            }}>Beta</span>
          </div>
        </div>

        {/* Right */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#71717a", fontSize: 13 }}>
          <Sparkles size={13} color="#a78bfa" />
          <span>Powered by GPT-4o mini + Pexels</span>
        </div>
      </div>
    </header>
  );
}
