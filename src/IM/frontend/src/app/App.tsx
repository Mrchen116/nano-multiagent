import { useMembershipCache } from "../features/chat/use-membership-cache";
import { Outlet } from "react-router-dom";

import { InAppToast } from "../features/chat/components/in-app-toast";
import { useGlobalMessageToast } from "../features/chat/hooks/use-global-message-toast";
import { AgentCompletionNotifier } from "../features/notifications/agent-completion-notifier";
import { UserStreamConnectionNotice } from "../realtime/user-stream/connection-notice";
import { AppShell } from "./shell/app-shell";
import { useUserTimezone } from "../features/auth/user-timezone";

export function App() {
  useUserTimezone();
  useMembershipCache();
  const { toast, dismiss, agentCompletionCandidate } = useGlobalMessageToast();

  return (
    <AppShell>
      <UserStreamConnectionNotice />
      <AgentCompletionNotifier candidate={agentCompletionCandidate} />
      {toast && (
        <InAppToast
          key={toast.id}
          conversationTitle={toast.conversationTitle}
          senderName={toast.isGroup ? toast.senderName : undefined}
          preview={toast.preview}
          conversationId={toast.conversationId}
          onDismiss={dismiss}
        />
      )}
      <Outlet />
    </AppShell>
  );
}
