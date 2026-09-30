import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PropsWithChildren, useEffect, useState } from "react";
import { useAuthStore } from "../features/auth/auth-store";

import { forgetComposerUser } from "../features/chat/components/composer-draft-store";

export function AppProviders({ children }: PropsWithChildren) {
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
    return useAuthStore.subscribe((state) => {
      const nextUserId = state.user?.id ?? null;
      if (previousUserId !== null && (previousUserId !== nextUserId || state.user?.membership_status !== "active")) {
        queryClient.clear();
        forgetComposerUser(previousUserId);
        window.sessionStorage.removeItem(`im:user_stream_cursor:${previousUserId}`);
      }
      previousUserId = nextUserId;
    });
  }, [queryClient]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
