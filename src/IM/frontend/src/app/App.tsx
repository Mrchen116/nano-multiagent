import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { WorkspaceTabs } from "../components/workspace-tabs";
import { useUiStore } from "../state/ui-store";

export function App() {
  const location = useLocation();
  const setWorkspace = useUiStore((state) => state.setWorkspace);

  useEffect(() => {
    setWorkspace(location.pathname.startsWith("/settings") ? "settings" : "chat");
  }, [location.pathname, setWorkspace]);

  return (
    <div className="mx-auto flex min-h-screen max-w-[1280px] flex-col gap-4 px-4 py-4 lg:px-6">
      <header className="im-card flex items-center justify-between gap-4 px-4 py-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Nano Multiagent</p>
          <p className="im-title mt-1 text-lg font-bold">Nano IM Workspace</p>
          <p className="mt-1 text-sm text-slate-500">A production-ready inbox for operator, agent, and group conversations.</p>
        </div>
        <WorkspaceTabs />
      </header>
      <main className="flex min-h-0 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
