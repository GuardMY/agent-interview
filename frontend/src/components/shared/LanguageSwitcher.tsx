"use client";

import { useI18n } from "@/i18n";
import { Button } from "@/components/ui/button";
import { Languages } from "lucide-react";

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setLocale(locale === "en" ? "zh" : "en")}
      title={locale === "en" ? "切换到中文" : "Switch to English"}
    >
      <Languages className="mr-1 h-4 w-4" />
      {locale === "en" ? "中文" : "EN"}
    </Button>
  );
}
