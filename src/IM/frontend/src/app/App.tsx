import { Outlet } from "react-router-dom";

import { InAppToast } from "../features/chat/components/in-app-toast";
import { useGlobalMessageToast } from "../features/chat/hooks/use-global-message-toast";
import { AgentCompletionNotifier } from "../features/notifications/agent-completion-notifier";
import { AppShell } from "./shell/app-shell";

export function App() {
  const { toast, dismiss } = useGlobalMessageToast();

  return (
    <AppShell>
      <AgentCompletionNotifier />
      {toast && (
        <InAppToast
          key={toast.id}
          senderName={toast.senderName}
          preview={toast.preview}
          conversationId={toast.conversationId}
          onDismiss={dismiss}
        />
      )}
      <Outlet />
    </AppShell>
  );
}
