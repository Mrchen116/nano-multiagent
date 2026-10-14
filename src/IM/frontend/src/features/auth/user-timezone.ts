import { useEffect } from "react";
import { authFetchJson } from "./auth-fetch";
import { useAuthStore } from "./auth-store";

/** Read the browser's current system timezone without asking the user to configure it. */
export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Refresh account timezone only while the authenticated user is using this page. */
export function useUserTimezone(): void {
  const userId = useAuthStore(state => state.user?.id);
  useEffect(() => {
    if (!userId) return;
    let pending: string | undefined;
    const refresh = () => {
      if (document.visibilityState !== "visible") return;
      const timezone = browserTimezone();
      const user = useAuthStore.getState().user;
      // Another device may have changed the account timezone since this page was active.
      if (user?.id !== userId || pending === timezone) return;
      pending = timezone;
      void authFetchJson<{ timezone: string }>("/im/v1/me/timezone", {
        method: "PATCH", body: JSON.stringify({ timezone }),
      }).then(result => {
        const current = useAuthStore.getState().user;
        if (current?.id === userId) useAuthStore.getState().replaceUser({ ...current, timezone: result.timezone });
      }).catch(() => {
        // Retain the last confirmed timezone; the next foreground visit or message retries.
      }).finally(() => { if (pending === timezone) pending = undefined; });
    };
    refresh();
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener("focus", refresh);
    return () => {
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("focus", refresh);
    };
  }, [userId]);
}
