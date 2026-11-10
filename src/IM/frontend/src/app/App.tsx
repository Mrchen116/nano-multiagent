import { useMembershipCache } from "../features/chat/use-membership-cache";
import { useEffect, useRef } from "react";
import { Outlet, useMatch } from "react-router-dom";
import { discardOnLeave } from "../features/chat/interaction-background";

import { InAppToast } from "../features/chat/components/in-app-toast";
import { useGlobalMessageToast } from "../features/chat/hooks/use-global-message-toast";
import { AgentCompletionNotifier } from "../features/notifications/agent-completion-notifier";
import { UserStreamConnectionNotice } from "../realtime/user-stream/connection-notice";
import { AppShell } from "./shell/app-shell";
import { useUserTimezone } from "../features/auth/user-timezone";

export function App() {
  useUserTimezone();
  useMembershipCache();
  const conversationId = useMatch("/chat/:conversationId")?.params.conversationId;
  const inChat = Boolean(useMatch("/chat/*"));
  const previousConversation = useRef(conversationId);
  useEffect(() => {
    // Chat handles switches inside its workspace. The app stays mounted when
    // navigating to Tasks or Settings, where the chat workspace cannot do so.
    if (!inChat && previousConversation.current) void discardOnLeave(previousConversation.current);
    previousConversation.current = conversationId;
  }, [conversationId, inChat]);
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
