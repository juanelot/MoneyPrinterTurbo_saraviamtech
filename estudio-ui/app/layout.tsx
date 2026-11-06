import type { Metadata } from "next";
import { Inter, Sora } from "next/font/google";
import "./globals.css";
import { MARCA } from "@/lib/marca";
import Barra from "@/components/Barra";

const display = Sora({ subsets: ["latin"], variable: "--fuente-display", weight: ["500", "600", "700"] });
const texto = Inter({ subsets: ["latin"], variable: "--fuente-texto" });

export const metadata: Metadata = {
  title: MARCA.nombre,
  description: MARCA.eslogan,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${display.variable} ${texto.variable}`}>
      <body className="min-h-screen">
        <Barra />
        <div className="md:pl-60">{children}</div>
      </body>
    </html>
  );
}
