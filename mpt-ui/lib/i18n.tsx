"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { es } from "./translations/es";
import { en } from "./translations/en";

export type Lang = "es" | "en";
export type TKey = keyof typeof es;

const DICTS: Record<Lang, Record<TKey, string>> = { es, en };
const STORAGE_KEY = "mpt-lang";

interface LangContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TKey, vars?: Record<string, string | number>) => string;
}

const LangContext = createContext<LangContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("es");

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as Lang | null;
    if (saved === "es" || saved === "en") {
      setLangState(saved);
    } else if (typeof navigator !== "undefined" && !navigator.language.startsWith("es")) {
      setLangState("en");
    }
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
  };

  const t = (key: TKey, vars?: Record<string, string | number>) => {
    let text = DICTS[lang][key] ?? DICTS.es[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        text = text.replaceAll(`{${k}}`, String(v));
      }
    }
    return text;
  };

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LangContext.Provider>
  );
}

export function useT() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useT must be used inside <LanguageProvider>");
  return ctx;
}
