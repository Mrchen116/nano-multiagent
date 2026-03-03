import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { useEffect } from "react";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { ConversationList } from "./components/conversation-list";
import { MessagePane } from "./components/message-pane";
import { getConversation, listConversations, sendMessage, streamConversationEvents } from "./chat-api";
import { ChatMessage, ConversationDetail, ConversationSummary } from "./types";

function toStatus(value: unknown): ChatMessage["delivery_status"] | undefined {
  if (value === "sent" || value === "running" || value === "completed" || value === "failed") {
    return value;
  }
  return undefined;
}

function toStringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function upsertMessage(messages: ChatMessage[], message: ChatMessage) {
  const existingIndex = messages.findIndex((item) => item.message_id === message.message_id);
  if (existingIndex === -1) {
    return [...messages, message];
  }
  const next = [...messages];
  next[existingIndex] = { ...next[existingIndex], ...message };
  return next;
}

function updateConversationList(
  items: ConversationSummary[] | undefined,
  conversationId: string,
  patch: Partial<ConversationSummary>
) {
  if (!items) {
    return items;
  }
  return items.map((item) => (item.conversation_id === conversationId ? { ...item, ...patch } : item));
}

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

  useEffect(() => {
    if (!conversationId) {
      return;
    }
    return streamConversationEvents({
      conversationId,
      onEvent: (event) => {
        const messageId = toStringValue(event.payload.message_id);
        if (!messageId) {
          return;
        }

        if (event.eventType === "message_created") {
          const createdAt = toStringValue(event.payload.created_at) ?? new Date().toISOString();
          const content = toStringValue(event.payload.content) ?? "";
          const sender = toStringValue(event.payload.sender_user_id) ?? "peer";
          const deliveryStatus = toStatus(event.payload.delivery_status) ?? "running";
          const nextMessage: ChatMessage = {
            message_id: messageId,
            sender_type: "user",
            sender_name: sender,
            content,
            created_at: createdAt,
            is_mine: false,
            delivery_status: deliveryStatus
          };
          queryClient.setQueryData<ConversationDetail | null>(
            ["chat", "conversation", conversationId],
            (previous) => {
              if (!previous) {
                return null;
              }
              return {
                ...previous,
                messages: upsertMessage(previous.messages, nextMessage)
              };
            }
          );
          if (content) {
            queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
              updateConversationList(previous, conversationId, {
                last_message_preview: content,
                last_message_at: createdAt
              })
            );
          }
          return;
        }

        if (event.eventType === "text_delta") {
          const delta = toStringValue(event.payload.delta) ?? "";
          if (!delta) {
            return;
          }
          queryClient.setQueryData<ConversationDetail | null>(
            ["chat", "conversation", conversationId],
            (previous) => {
              if (!previous) {
                return null;
              }
              const exists = previous.messages.find((item) => item.message_id === messageId);
              const nextMessage: ChatMessage = exists
                ? {
                    ...exists,
                    content: `${exists.content}${delta}`,
                    delivery_status: "running"
                  }
                : {
                    message_id: messageId,
                    sender_type: "user",
                    sender_name: toStringValue(event.payload.sender_user_id) ?? "peer",
                    content: delta,
                    created_at: new Date().toISOString(),
                    is_mine: false,
                    delivery_status: "running"
                  };
              return {
                ...previous,
                messages: upsertMessage(previous.messages, nextMessage)
              };
            }
          );
          queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) => {
            const active = previous?.find((item) => item.conversation_id === conversationId);
            if (!active) {
              return previous;
            }
            return updateConversationList(previous, conversationId, {
              last_message_preview: `${active.last_message_preview ?? ""}${delta}`,
              last_message_at: new Date().toISOString()
            });
          });
          return;
        }

        if (event.eventType === "turn_end" || event.eventType === "message_status") {
          const status = toStatus(event.payload.status) ?? "completed";
          const content = toStringValue(event.payload.content);
          queryClient.setQueryData<ConversationDetail | null>(
            ["chat", "conversation", conversationId],
            (previous) => {
              if (!previous) {
                return null;
              }
              const existing = previous.messages.find((item) => item.message_id === messageId);
              if (!existing) {
                return previous;
              }
              const nextMessage: ChatMessage = {
                ...existing,
                content: content ?? existing.content,
                delivery_status: status
              };
              return {
                ...previous,
                messages: upsertMessage(previous.messages, nextMessage)
              };
            }
          );
          if (content) {
            queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
              updateConversationList(previous, conversationId, {
                last_message_preview: content,
                last_message_at: new Date().toISOString()
              })
            );
          }
        }
      }
    });
  }, [conversationId, queryClient]);

  const sendMutation = useMutation({
    mutationFn: (content: string) => sendMessage({ conversationId: conversationId!, content }),
    onSuccess: (message) => {
      if (!conversationId) {
        return;
      }
      queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
        if (!previous) {
          return {
            conversation_id: conversationId,
            title: "Conversation",
            messages: [message]
          };
        }
        return {
          ...previous,
          messages: upsertMessage(previous.messages, message)
        };
      });
      queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
        updateConversationList(previous, conversationId, {
          last_message_preview: message.content,
          last_message_at: message.created_at
        })
      );
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
