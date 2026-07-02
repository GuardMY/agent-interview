"use client";

import { I18nProvider } from "@/i18n";
import { ThemeProvider } from "@/components/shared/ThemeProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <I18nProvider>{children}</I18nProvider>
    </ThemeProvider>
  );
}
