import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PropsWithChildren, useEffect, useState } from "react";
import { useMobileViewport } from "../hooks/use-mobile-viewport";
import { accountEnabled, useAuthStore } from "../features/auth/auth-store";

import { forgetComposerUser } from "../features/chat/components/composer-draft-store";

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
        window.sessionStorage.removeItem(`im:user_stream_cursor:${previousUserId}`);
      }
      previousUserId = nextUserId;
      previousMembership = state.user?.membership_status;
    });
  }, [queryClient]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
