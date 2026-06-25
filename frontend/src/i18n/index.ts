"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  createElement,
  type ReactNode,
} from "react";
import en from "./locales/en.json";
import zh from "./locales/zh.json";

export type Locale = "en" | "zh";

const LOCALE_KEY = "app_locale";

const locales: Record<Locale, typeof en> = { en, zh };

function detectLocale(): Locale {
  if (typeof window === "undefined") return "zh";
  const stored = localStorage.getItem(LOCALE_KEY) as Locale | null;
  if (stored && (stored === "en" || stored === "zh")) return stored;
  const nav = navigator.language || "";
  return nav.startsWith("zh") ? "zh" : "en";
}

// ── Context ────────────────────────────────────────────────

interface I18nContextValue {
  locale: Locale;
  t: typeof en;
  setLocale: (locale: Locale) => void;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh");

  useEffect(() => {
    setLocaleState(detectLocale());
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    localStorage.setItem(LOCALE_KEY, l);
  }, []);

  const value: I18nContextValue = { locale, t: locales[locale], setLocale };

  return createElement(I18nContext.Provider, { value }, children);
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
