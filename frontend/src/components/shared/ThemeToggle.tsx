"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";

  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;

  const label =
    theme === "light" ? "Light mode" : theme === "dark" ? "Dark mode" : "System";

  return (
    <button
      onClick={() => setTheme(next)}
      className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
      aria-label={`Current: ${label}. Click to switch.`}
      title={`Theme: ${label}`}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}
