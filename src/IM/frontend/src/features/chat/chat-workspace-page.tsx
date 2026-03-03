import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { ConversationList } from "./components/conversation-list";
import { MessagePane } from "./components/message-pane";
import { getConversation, listConversations, sendMessage } from "./mock-chat-api";
import { ConversationDetail } from "./types";

export function ChatWorkspacePage() {
  const { conversationId } = useParams();
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();

  const conversationsQuery = useQuery({
    queryKey: ["chat", "conversations"],
    queryFn: listConversations
  });

  const detailQuery = useQuery({
    enabled: Boolean(conversationId),
    queryKey: ["chat", "conversation", conversationId],
    queryFn: () => getConversation(conversationId!)
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) => sendMessage({ conversationId: conversationId!, content }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversation", conversationId] });
    }
  });

  if (conversationsQuery.isLoading) {
    return <section className="im-card flex w-full items-center justify-center">Loading chat...</section>;
  }

  const conversations = conversationsQuery.data ?? [];
  const detail = (detailQuery.data ?? null) as ConversationDetail | null;

  if (isMobile && conversationId) {
    return (
      <div className="w-full">
        <MessagePane
          detail={detail}
          isMobile={isMobile}
          isSending={sendMutation.isPending}
          onSend={(content) => sendMutation.mutate(content)}
        />
      </div>
    );
  }

  return (
    <section className="grid w-full min-h-0 gap-4 lg:grid-cols-[360px_1fr]">
      <ConversationList items={conversations} activeId={conversationId} compact={isMobile} />
      {!isMobile && (
        <MessagePane
          detail={detail}
          isMobile={isMobile}
          isSending={sendMutation.isPending}
          onSend={(content) => sendMutation.mutate(content)}
        />
      )}
    </section>
  );
}
