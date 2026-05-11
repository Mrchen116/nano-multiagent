import { PropsWithChildren, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "./auth-store";

/**
 * Route guard component — redirects to /login when there is no current session.
 *
 * Hydrates the auth store from localStorage on first mount; until hydration runs,
 * we suppress a redirect to avoid a flash from a freshly loaded tab.
 */
export function RequireAuth({ children }: PropsWithChildren) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const hydrated = useAuthStore((s) => s.hydrated);
  const [hydrating, setHydrating] = useState(!hydrated);
  const location = useLocation();

  useEffect(() => {
    if (!hydrated) {
      useAuthStore.getState().hydrate();
      setHydrating(false);
    }
  }, [hydrated]);

  if (hydrating) return null;
  if (!accessToken || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
