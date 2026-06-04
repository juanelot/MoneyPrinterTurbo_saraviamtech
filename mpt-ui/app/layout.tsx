import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VideoAI Studio",
  description: "Genera videos cortos con inteligencia artificial",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className="h-full">
      <body className="min-h-full bg-black text-white antialiased">{children}</body>
    </html>
  );
}
