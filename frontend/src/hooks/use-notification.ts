"use client";

import { useEffect, useRef } from "react";
import { listSessions } from "@/lib/api";

const POLL_INTERVAL_MS = 15_000; // 15 seconds

interface NotificationLocale {
  completeTitle: string;
  completeBody: (names: string, verb: string) => string;
}

/** English fallback when locale is not provided. */
const EN_NOTIFICATION: NotificationLocale = {
  completeTitle: "Interview Complete",
  completeBody: (names, verb) => `${names} ${verb} completed their interview.`,
};

const ZH_NOTIFICATION: NotificationLocale = {
  completeTitle: "面试完成",
  completeBody: (names, verb) => `${names} ${verb}完成了面试。`,
};

/**
 * Polls the session list API and triggers browser notifications
 * when new sessions complete. Requires a master admin token.
 */
export function useSessionNotifications(
  masterToken: string | null,
  locale: string = "en",
) {
  const prevCompletedRef = useRef<Set<string> | null>(null);

  useEffect(() => {
    if (!masterToken) return;

    const l10n = locale === "zh" ? ZH_NOTIFICATION : EN_NOTIFICATION;

    // Request notification permission on first use
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }

    // Initial load to establish baseline
    let cancelled = false;

    const init = async () => {
      try {
        const res = await listSessions(masterToken, { size: 100 });
        if (!cancelled) {
          prevCompletedRef.current = new Set(
            res.items.filter((s) => s.status === "done").map((s) => s.id)
          );
        }
      } catch {
        // Silent fail
      }
    };
    init();

    // Periodic polling
    const interval = setInterval(async () => {
      try {
        const res = await listSessions(masterToken, { size: 100 });

        const completed = new Set(
          res.items.filter((s) => s.status === "done").map((s) => s.id)
        );

        if (prevCompletedRef.current) {
          // Find newly completed sessions
          const newIds = [...completed].filter(
            (id) => !prevCompletedRef.current!.has(id)
          );

          if (newIds.length > 0) {
            const names = newIds
              .map((id) => {
                const s = res.items.find((s) => s.id === id);
                return s?.candidate_name || id;
              })
              .join(", ");

            // Chinese doesn't need "have/has" distinction
            const verb = locale === "zh" ? "" : (newIds.length > 1 ? "have " : "has ");

            // Browser notification
            if (
              "Notification" in window &&
              Notification.permission === "granted"
            ) {
              new Notification(l10n.completeTitle, {
                body: l10n.completeBody(names, verb),
                icon: "/favicon.svg",
              });
            }
          }
        }

        if (!cancelled) {
          prevCompletedRef.current = completed;
        }
      } catch {
        // Silent fail on poll error
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [masterToken, locale]);
}
