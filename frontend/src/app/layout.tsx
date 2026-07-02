import type { Metadata } from "next";
import Script from "next/script";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Interview Agent",
  description: "Autonomous technical interviewer",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#2563eb" />
      </head>
      <body className="bg-background text-foreground font-sans antialiased">
        <Script id="theme-flash" strategy="beforeInteractive">
          {`
            (function() {
              try {
                var t = localStorage.getItem("theme");
                if (t === "dark" || (!t && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
                  document.documentElement.classList.add("dark");
                }
              } catch(e) {}
            })();
          `}
        </Script>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
