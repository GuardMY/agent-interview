"use client";

import { useI18n } from "@/i18n";
import { Button } from "@/components/ui/button";
import { Languages } from "lucide-react";

const TOOLTIPS: Record<string, string> = {
  en: "切换到中文",
  zh: "Switch to English",
};

const LABELS: Record<string, string> = {
  en: "中文",
  zh: "EN",
};

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setLocale(locale === "en" ? "zh" : "en")}
      title={TOOLTIPS[locale]}
    >
      <Languages className="mr-1 h-4 w-4" />
      {LABELS[locale]}
    </Button>
  );
}
