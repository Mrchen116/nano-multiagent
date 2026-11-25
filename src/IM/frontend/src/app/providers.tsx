import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PropsWithChildren, useEffect, useState } from "react";
import { openDesktopExternal } from "../desktop/desktop-api";
import { desktopScopedKey, isDesktopClient } from "../desktop/desktop-context";
import { useMobileViewport } from "../hooks/use-mobile-viewport";
import { accountEnabled, useAuthStore } from "../features/auth/auth-store";

import { forgetComposerUser } from "../features/chat/components/composer-draft-store";
import { forgetInteractionBackground } from '../features/chat/interaction-background';

export function AppProviders({ children }: PropsWithChildren) {
  useMobileViewport();
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            retry: false
          }
        }
      })
  );

  useEffect(() => {
    let previousUserId = useAuthStore.getState().user?.id ?? null;
    let previousMembership = useAuthStore.getState().user?.membership_status;
    return useAuthStore.subscribe((state) => {
      const nextUserId = state.user?.id ?? null;
      if (previousUserId !== null && (previousUserId !== nextUserId || !accountEnabled(state.user) || previousMembership !== state.user?.membership_status)) {
        queryClient.clear();
        forgetComposerUser(previousUserId);
        void forgetInteractionBackground(previousUserId).catch(() => {});
        window.sessionStorage.removeItem(desktopScopedKey(`im:user_stream_cursor:${previousUserId}`));
      }
      previousUserId = nextUserId;
      previousMembership = state.user?.membership_status;
    });
  }, [queryClient]);

  useEffect(() => {
    if (!isDesktopClient()) return;
    const onDocClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      const rawHref = anchor.getAttribute("href") ?? "";
      if (!/^https?:\/\//i.test(rawHref)) return;
      try {
        const parsed = new URL(rawHref, window.location.href);
        if (parsed.origin !== window.location.origin) {
          event.preventDefault();
          void openDesktopExternal(parsed.href).catch(() => {});
        }
      } catch {
        // Ignore malformed URLs.
      }
    };
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
