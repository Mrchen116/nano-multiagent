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
    <div className="mx-auto flex h-screen max-w-[1280px] flex-col gap-4 overflow-hidden px-4 py-4 lg:px-6">
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
