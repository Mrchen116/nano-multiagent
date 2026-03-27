import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { WorkspaceTabs } from "../components/workspace-tabs";
import { InAppToast } from "../features/chat/components/in-app-toast";
import { useGlobalMessageToast } from "../features/chat/hooks/use-global-message-toast";
import { useUiStore } from "../state/ui-store";

export function App() {
  const location = useLocation();
  const setWorkspace = useUiStore((state) => state.setWorkspace);
  const { toast, dismiss } = useGlobalMessageToast();

  useEffect(() => {
    setWorkspace(location.pathname.startsWith("/settings") ? "settings" : "chat");
  }, [location.pathname, setWorkspace]);

  return (
    <div className="mx-auto flex h-screen min-h-0 max-w-[1280px] flex-col gap-4 overflow-hidden px-4 py-4 max-md:gap-2 max-md:px-3 max-md:py-3 lg:px-6">
      {/* Global in-app toast: shown when a new message arrives while away from that conversation */}
      {toast && (
        <InAppToast
          key={toast.id}
          senderName={toast.senderName}
          preview={toast.preview}
          conversationId={toast.conversationId}
          onDismiss={dismiss}
        />
      )}
      <header className="im-card flex shrink-0 flex-wrap items-center justify-between gap-3 px-4 py-3 max-md:gap-2 max-md:py-2.5">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Nano Multiagent</p>
          <p className="im-title mt-1 text-lg font-bold max-md:text-base">Nano IM Workspace</p>
          <p className="mt-1 hidden text-sm text-slate-500 md:block">A production-ready inbox for operator, agent, and group conversations.</p>
        </div>
        <WorkspaceTabs />
      </header>
      <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
