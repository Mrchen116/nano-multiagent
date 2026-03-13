import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useIsMobile } from "../../hooks/use-is-mobile";
import { ConversationList } from "./components/conversation-list";
import { MessagePane } from "./components/message-pane";
import {
  createDirectConversation,
  getChatBootstrapState,
  getChatStarter,
  getConversation,
  getUsageMetrics,
  listConversations,
  listDiscoverableAgents,
  resolveSendAvailability,
  sendMessage,
  streamConversationEvents,
  uploadAttachment
} from "./chat-api";
import { ChatAttachment, ChatBootstrapState, ChatMessage, ConversationDetail, ConversationSummary, UsageMetricRow, UsageTotals } from "./types";

function toStatus(value: unknown): ChatMessage["delivery_status"] | undefined {
  if (value === "sent" || value === "running" || value === "completed" || value === "failed") {
    return value;
  }
  return undefined;
}

function toStringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function isChatAttachment(value: ChatAttachment | null): value is ChatAttachment {
  return value !== null;
}

function toAttachments(value: unknown): ChatAttachment[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item): ChatAttachment | null => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const attachment = item as Record<string, unknown>;
      const url = toStringValue(attachment.url);
      if (!url) {
        return null;
      }
      return {
        url,
        file_name: toStringValue(attachment.file_name) ?? undefined,
        content_type: toStringValue(attachment.content_type) ?? undefined
      };
    })
    .filter(isChatAttachment);
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

function toUsageTotals(rows: UsageMetricRow[] | undefined): UsageTotals {
  return (rows ?? []).reduce<UsageTotals>(
    (totals, row) => ({
      turns: totals.turns + row.turns,
      promptTokens: totals.promptTokens + row.prompt_tokens,
      completionTokens: totals.completionTokens + row.completion_tokens,
      totalTokens: totals.totalTokens + row.total_tokens
    }),
    {
      turns: 0,
      promptTokens: 0,
      completionTokens: 0,
      totalTokens: 0
    }
  );
}

export function toRelayAgentMessage(event: {
  eventType: string;
  payload: Record<string, unknown>;
}): ChatMessage | null {
  const messageId = toStringValue(event.payload.message_id);
  if (!messageId) {
    return null;
  }
  const content =
    toStringValue(event.payload.summary) ??
    toStringValue(event.payload.detail) ??
    toStringValue(event.payload.content);
  if (!content) {
    return null;
  }
  const status =
    event.eventType === "relay.processing"
      ? "running"
      : event.eventType === "relay.failed"
        ? "failed"
        : "completed";
  return {
    message_id: `${messageId}:agent`,
    sender_type: "agent",
    sender_name: toStringValue(event.payload.node_id) ?? "Agent",
    is_mine: false,
    content,
    created_at: toStringValue(event.payload.created_at) ?? new Date().toISOString(),
    delivery_status: status
  };
}

export function ChatWorkspacePage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();
  const [isCreatingGroupChat, setIsCreatingGroupChat] = useState(false);
  const [isCreatingDirectChat, setIsCreatingDirectChat] = useState(false);

  const bootstrapQuery = useQuery<ChatBootstrapState>({
    queryKey: ["chat", "bootstrap"],
    queryFn: async () => (await getChatBootstrapState()) as ChatBootstrapState
  });

  const conversationsQuery = useQuery({
    queryKey: ["chat", "conversations"],
    queryFn: listConversations
  });

  const starterQuery = useQuery({
    queryKey: ["chat", "starter"],
    queryFn: getChatStarter
  });

  const discoverableAgentsQuery = useQuery({
    enabled: isCreatingDirectChat,
    queryKey: ["chat", "discoverable-agents"],
    queryFn: listDiscoverableAgents
  });

  const detailQuery = useQuery({
    enabled: Boolean(conversationId),
    queryKey: ["chat", "conversation", conversationId],
    queryFn: () => getConversation(conversationId!)
  });

  const conversationUsageQuery = useQuery({
    enabled: Boolean(conversationId),
    queryKey: ["chat", "usage", "conversation", conversationId],
    queryFn: () => getUsageMetrics({ conversationId: conversationId! })
  });

  const workspaceUsageQuery = useQuery({
    enabled: Boolean(bootstrapQuery.data?.selfUserId),
    queryKey: ["chat", "usage", "workspace", bootstrapQuery.data?.selfUserId],
    queryFn: async () => {
      const rows = await getUsageMetrics({ ownerId: bootstrapQuery.data!.selfUserId });
      return rows.filter((row) => row.owner_id === bootstrapQuery.data!.selfUserId);
    }
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

        if (event.eventType === "message.sent") {
          const createdAt = toStringValue(event.payload.created_at) ?? new Date().toISOString();
          const content = toStringValue(event.payload.content) ?? "";
          const sender = toStringValue(event.payload.sender_user_id) ?? "peer";
          const deliveryStatus = toStatus(event.payload.delivery_status) ?? "sent";
          const nextMessage: ChatMessage = {
            message_id: messageId,
            sender_type: "user",
            sender_name: sender,
            content,
            attachments: toAttachments(event.payload.attachments),
            created_at: createdAt,
            is_mine: false,
            delivery_status: deliveryStatus
          };
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
            if (!previous) {
              return null;
            }
            return {
              ...previous,
              messages: upsertMessage(previous.messages, nextMessage)
            };
          });
          return;
        }

        if (
          event.eventType === "relay.processing" ||
          event.eventType === "relay.completed" ||
          event.eventType === "relay.failed" ||
          event.eventType === "message.delivered"
        ) {
          const nextMessage = toRelayAgentMessage({
            eventType: event.eventType,
            payload: event.payload as Record<string, unknown>
          });
          if (!nextMessage) {
            return;
          }
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
            if (!previous) {
              return null;
            }
            return {
              ...previous,
              messages: upsertMessage(previous.messages, nextMessage)
            };
          });
          queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) =>
            updateConversationList(previous, conversationId, {
              last_message_preview: nextMessage.content,
              last_message_at: nextMessage.created_at
            })
          );
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
            attachments: toAttachments(event.payload.attachments),
            created_at: createdAt,
            is_mine: false,
            delivery_status: deliveryStatus
          };
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
            if (!previous) {
              return null;
            }
            return {
              ...previous,
              messages: upsertMessage(previous.messages, nextMessage)
            };
          });
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
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
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
          });
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

        if (event.eventType === "turn_end" || event.eventType === "message_status" || event.eventType === "conversation.notice") {
          const status = toStatus(event.payload.status) ?? "completed";
          const content = toStringValue(event.payload.content);
          queryClient.setQueryData<ConversationDetail | null>(["chat", "conversation", conversationId], (previous) => {
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
          });
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

  const createDirectConversationMutation = useMutation({
    mutationFn: (payload: { agentId: string }) => createDirectConversation(payload),
    onSuccess: async ({ conversation_id }) => {
      const detail = await getConversation(conversation_id);
      queryClient.setQueryData(["chat", "conversation", conversation_id], detail);
      if (conversationId) {
        queryClient.setQueryData(["chat", "conversation", conversationId], detail);
      }
      if (detail) {
        queryClient.setQueryData<ConversationSummary[] | undefined>(["chat", "conversations"], (previous) => {
          const existing = previous ?? [];
          if (existing.some((item) => item.conversation_id === conversation_id)) {
            return existing;
          }
          return [
            {
              conversation_id,
              title: detail.title,
              last_message_preview: detail.messages.at(-1)?.content ?? "",
              last_message_at: detail.messages.at(-1)?.created_at,
              unread_count: 0,
              participants: detail.target_label ? [detail.target_label] : [],
              kind_label: detail.kind_label,
              target_label: detail.target_label,
              discoverability_hint: detail.discoverability_hint
            },
            ...existing
          ];
        });
      }
      setIsCreatingDirectChat(false);
      navigate(`/chat/${conversation_id}`);
      void queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
    }
  });

  const sendMutation = useMutation({
    mutationFn: (payload: { content: string; attachments: ChatAttachment[] }) =>
      sendMessage({ conversationId: conversationId!, content: payload.content, attachments: payload.attachments }),
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
          last_message_preview: message.content || message.attachments?.[0]?.file_name || "Attachment",
          last_message_at: message.created_at
        })
      );
    }
  });

  if (
    bootstrapQuery.isLoading ||
    conversationsQuery.isLoading ||
    starterQuery.isLoading ||
    (Boolean(conversationId) && detailQuery.isLoading)
  ) {
    return <section className="im-card flex w-full items-center justify-center">Loading chat...</section>;
  }

  const conversations = conversationsQuery.data ?? [];
  const starter = starterQuery.data ?? null;
  const detail = (detailQuery.data ?? null) as ConversationDetail | null;
  const bootstrap = bootstrapQuery.data ?? null;
  const usage = {
    conversation: toUsageTotals(conversationUsageQuery.data),
    workspace: toUsageTotals(workspaceUsageQuery.data)
  };
  const sendAvailability = resolveSendAvailability({
    targetNodeId: bootstrap?.targetNodeId ?? null,
    nodeStatus: bootstrap?.targetNodeStatus ?? null
  });

  if (isMobile && conversationId) {
    return (
      <div className="w-full">
        <MessagePane
          detail={detail}
          starter={null}
          isMobile={isMobile}
          isSending={sendMutation.isPending}
          sendAvailability={sendAvailability}
          usage={usage}
          onSend={(payload) => sendMutation.mutateAsync(payload)}
          onUploadAttachment={uploadAttachment}
        />
      </div>
    );
  }

  const directChatPanel = isCreatingDirectChat ? (
    <section className="im-card rounded-2xl border border-[var(--im-border)] bg-slate-50 px-4 py-4 text-sm text-slate-700">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Direct chat</p>
          <h2 className="im-title mt-1 text-lg font-bold">Available agents</h2>
          <p className="mt-1 text-xs text-slate-500">
            Open a fresh one-to-one conversation with a configured agent from the workspace.
          </p>
        </div>
        <button type="button" className="im-btn im-btn-muted" onClick={() => setIsCreatingDirectChat(false)}>
          Cancel
        </button>
      </div>
      <div className="mt-4 grid gap-3">
        {(discoverableAgentsQuery.data ?? []).map((agent) => (
          <article key={agent.agent_id} className="rounded-xl border border-[var(--im-border)] bg-white px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-slate-900">{agent.display_name}</h3>
                <p className="mt-1 text-xs text-slate-500">{agent.description}</p>
              </div>
              <button
                type="button"
                className="im-btn im-btn-primary"
                onClick={() => createDirectConversationMutation.mutate(agent.agent_id ? { agentId: agent.agent_id } : { agentId: "" })}
              >
                {agent.existing_conversation_id ? `Open ${agent.display_name}` : `Chat with ${agent.display_name}`}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  ) : null;

  const groupChatPanel = isCreatingGroupChat ? (
    <section className="im-card rounded-2xl border border-[var(--im-border)] bg-slate-50 px-4 py-4 text-sm text-slate-700">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Group chat</p>
          <h2 className="im-title mt-1 text-lg font-bold">Select participants</h2>
          <p className="mt-1 text-xs text-slate-500">
            Create a shared thread with multiple agents or teammates, then enter the conversation from the list.
          </p>
        </div>
        <button type="button" className="im-btn im-btn-muted" onClick={() => setIsCreatingGroupChat(false)}>
          Cancel
        </button>
      </div>
    </section>
  ) : null;

  return (
    <section className="grid w-full min-h-0 gap-4 lg:grid-cols-[360px_1fr]">
      <div className="flex min-h-0 flex-col gap-4">
        {isMobile && !conversationId && starter && (
          <MessagePane
            detail={null}
            starter={starter}
            isMobile={isMobile}
            isSending={false}
            sendAvailability={sendAvailability}
            usage={usage}
            onSend={async () => undefined}
            onUploadAttachment={uploadAttachment}
          />
        )}
        {directChatPanel}
        {groupChatPanel}
        <ConversationList
          items={conversations}
          activeId={conversationId}
          compact={isMobile}
          onCreateDirectChat={() => {
            setIsCreatingGroupChat(false);
            setIsCreatingDirectChat(true);
          }}
          onCreateGroupChat={() => {
            setIsCreatingDirectChat(false);
            setIsCreatingGroupChat(true);
          }}
        />
      </div>
      {!isMobile && (
        <MessagePane
          detail={detail}
          starter={conversationId ? null : starter}
          isMobile={isMobile}
          isSending={sendMutation.isPending}
          sendAvailability={sendAvailability}
          usage={usage}
          onSend={(payload) => sendMutation.mutateAsync(payload)}
          onUploadAttachment={uploadAttachment}
        />
      )}
    </section>
  );
}
