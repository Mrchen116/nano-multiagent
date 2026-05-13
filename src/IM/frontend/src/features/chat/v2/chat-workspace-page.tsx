import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { InAppToast } from "../../chat/components/in-app-toast";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import {
  createConversation,
  createMessage,
  listConversations,
  listMentionCandidates,
  listMessages,
  type AgentRow
} from "./chat-api";
import { openChatStream } from "./chat-stream";
import {
  applyWsEvent,
  emptyConversationState,
  type ConversationState
} from "./chat-stream-reducer";
import { authFetch } from "../../auth/auth-fetch";
import type { Attachment, Conversation, Message, WsEvent } from "./chat-types";
import { ConversationSidebar } from "./components/conversation-sidebar";
import { MessagePane } from "./components/message-pane";
import { NewGroupModal } from "./components/new-group-modal";

function streamReducer(
  state: ConversationState,
  action:
    | { type: "reset"; conversationId: string; messages: Message[] }
    | { type: "event"; event: WsEvent; sendersById?: Record<string, string | undefined> }
    | { type: "append_optimistic"; message: Message }
): ConversationState {
  if (action.type === "reset") {
    return { conversation_id: action.conversationId, messages: action.messages };
  }
  if (action.type === "append_optimistic") {
    // feat-340-M18 R9-3: insert the user-authored bubble the moment the POST
    // resolves so the main pane no longer waits on the WS echo (which only
    // arrives for the agent reply path in some flows). Dedupe by id so the
    // later WS message.created — if/when it comes — does not double-print.
    if (action.message.conversation_id !== state.conversation_id) return state;
    if (state.messages.some((m) => m.id === action.message.id)) return state;
    return { ...state, messages: [...state.messages, action.message] };
  }
  return applyWsEvent(state, action.event, { sendersById: action.sendersById });
}

async function fetchAgents(): Promise<AgentRow[]> {
  const res = await authFetch("/im/v1/agents");
  if (!res.ok) throw new Error(`listAgents failed: ${res.status}`);
  return (await res.json()) as AgentRow[];
}

interface NodeRow {
  node_id: string;
  node_name: string;
  status: string;
}

async function fetchNodes(): Promise<NodeRow[]> {
  const res = await authFetch("/im/v1/nodes");
  if (!res.ok) throw new Error(`listNodes failed: ${res.status}`);
  return (await res.json()) as NodeRow[];
}

/**
 * Top-level chat workspace — composes ConversationSidebar (left) and
 * MessagePane (right) on desktop, and either-or (list vs detail) on mobile.
 *
 * Data flow:
 *  - `listConversations` / `listMessages` via react-query for the historical
 *    backbone.
 *  - `openChatStream` for the live WS feed; events are pushed through
 *    `applyWsEvent` (pure reducer from R2) into a local conversation state
 *    keyed by active conversation. When the user switches conversations we
 *    `reset` the reducer with the freshly fetched history.
 *  - Send / create-group go through the v2 chat-api → backend → echoes back as
 *    WS `message.created`; reducer dedupes the echo, so no optimistic insert
 *    is required here.
 */
export function ChatWorkspacePageV2() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const conversationsQuery = useQuery({
    queryKey: ["chat-v2", "conversations"],
    queryFn: listConversations
  });

  const activeConversation: Conversation | null = useMemo(() => {
    if (!conversationId) return null;
    return conversationsQuery.data?.find((c) => c.id === conversationId) ?? null;
  }, [conversationId, conversationsQuery.data]);

  const messagesQuery = useQuery({
    enabled: Boolean(conversationId),
    queryKey: ["chat-v2", "messages", conversationId],
    queryFn: () => listMessages(conversationId!, { markAsRead: true })
  });

  const mentionQuery = useQuery({
    enabled: Boolean(activeConversation),
    queryKey: ["chat-v2", "mention-candidates", conversationId],
    queryFn: () => listMentionCandidates({ conversation: activeConversation! })
  });

  const agentsQuery = useQuery({
    queryKey: ["chat-v2", "agents"],
    queryFn: fetchAgents
  });

  const nodesQuery = useQuery({
    queryKey: ["chat-v2", "nodes"],
    queryFn: fetchNodes
  });

  const sendersById = useMemo(() => {
    const map: Record<string, string | undefined> = {};
    for (const agent of agentsQuery.data ?? []) {
      if (agent.user_id) map[agent.user_id] = agent.display_name;
    }
    return map;
  }, [agentsQuery.data]);

  // For direct-agent conversations, surface the agent's owning node (name +
  // online status) and the agent_id used by the ⚙ Config navigation.
  const headerAgentContext = useMemo<{
    agentId: string | null;
    nodeName: string | null;
    nodeStatus: "online" | "offline";
    agentColor: string | null;
    agentInitials: string | null;
  }>(() => {
    if (!activeConversation) {
      return { agentId: null, nodeName: null, nodeStatus: "offline", agentColor: null, agentInitials: null };
    }
    const agentParticipant = activeConversation.participants.find((p) => p.type === "agent");
    if (!agentParticipant) {
      return { agentId: null, nodeName: null, nodeStatus: "offline", agentColor: null, agentInitials: null };
    }
    const agentRow = (agentsQuery.data ?? []).find((a) => a.agent_id === agentParticipant.id);
    if (!agentRow) {
      return { agentId: agentParticipant.id, nodeName: null, nodeStatus: "offline", agentColor: null, agentInitials: null };
    }
    const nodeRow = (nodesQuery.data ?? []).find((n) => n.node_id === agentRow.node_id);
    const nodeStatus = nodeRow?.status === "online" ? "online" : "offline";
    const initials = agentRow.display_name?.slice(0, 2) ?? agentRow.agent_id.slice(0, 2);
    const color = colorForSeed(agentRow.display_name ?? agentRow.agent_id);
    return {
      agentId: agentRow.agent_id,
      nodeName: nodeRow?.node_name ?? null,
      nodeStatus,
      agentColor: color,
      agentInitials: initials
    };
  }, [activeConversation, agentsQuery.data, nodesQuery.data]);

  const [streamState, dispatch] = useReducer(streamReducer, emptyConversationState);

  // Seed the reducer with REST history whenever the active conversation or its
  // historical fetch changes.
  useEffect(() => {
    if (!conversationId || !messagesQuery.data) return;
    dispatch({ type: "reset", conversationId, messages: messagesQuery.data.items });
  }, [conversationId, messagesQuery.data]);

  // Open the WS stream once for the workspace lifetime; events flow into the
  // reducer which ignores any not matching the active conversation.
  // Captures the latest sendersById via a ref so a fresh agents fetch becomes
  // visible to in-flight reducer dispatches without recreating the WS handle.
  const sendersByIdRef = useRef(sendersById);
  sendersByIdRef.current = sendersById;
  useEffect(() => {
    const handle = openChatStream({
      onEvent: (ev) => dispatch({ type: "event", event: ev, sendersById: sendersByIdRef.current })
    });
    return () => handle.close();
  }, []);

  const sendMutation = useMutation({
    mutationFn: (payload: { text: string; attachments: Attachment[] }) =>
      createMessage({
        conversationId: conversationId!,
        content: payload.text,
        attachments: payload.attachments
      }),
    onSuccess: (created) => {
      setSendError(null);
      // feat-340-M18 R9-3: optimistically render the user's own message immediately
      // after the POST resolves. The WS message.created echo path is reliable for
      // agent replies but not always for self-authored bubbles, so previously the
      // user saw their text vanish into the void until a refetch. Reducer dedupes
      // by id so the later WS event (if any) does not double-print.
      dispatch({ type: "append_optimistic", message: created });
      // Bump conversation list ordering on next refetch.
      void queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });
    },
    onError: (err) => {
      setSendError(err instanceof Error ? err.message : t("chat.messagePane.sendError"));
    }
  });

  // Auto-scroll is handled inside MessagePane via a ref on the messages container.

  const createGroupMutation = useMutation({
    mutationFn: (payload: { agentIds: string[]; name: string }) =>
      createConversation({ title: payload.name, agentIds: payload.agentIds }),
    onSuccess: (conv) => {
      setShowNewGroup(false);
      void queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });
      navigate(`/chat/${conv.id}`);
    }
  });

  const showList = !isMobile || !conversationId;
  const showDetail = !isMobile || Boolean(conversationId);

  return (
    <div className="chat-workspace">
      {sendError && (
        <div className="fixed left-4 top-4 z-50 flex max-w-xs items-start gap-3 rounded-2xl border border-[var(--im-danger)] bg-[oklch(0.98_0.02_25)] px-4 py-3 shadow-lg">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-[var(--im-danger)]">{t("chat.messagePane.sendErrorTitle")}</p>
            <p className="mt-0.5 line-clamp-2 text-xs text-slate-700">{sendError}</p>
          </div>
          <button
            type="button"
            aria-label="Dismiss"
            className="shrink-0 rounded-full p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            onClick={() => setSendError(null)}
          >
            ×
          </button>
        </div>
      )}
      {showList && (
        <ConversationSidebar
          conversations={conversationsQuery.data ?? []}
          activeConversationId={conversationId ?? null}
          onSelect={(id) => navigate(`/chat/${id}`)}
          onNewGroup={() => setShowNewGroup(true)}
        />
      )}
      {showDetail && (
        activeConversation ? (
          <MessagePane
            conversation={activeConversation}
            messages={streamState.messages}
            mentionCandidates={mentionQuery.data ?? []}
            nodeName={headerAgentContext.nodeName}
            nodeStatus={headerAgentContext.nodeStatus}
            agentColor={headerAgentContext.agentColor}
            agentInitials={headerAgentContext.agentInitials}
            onSend={(text, attachments) => sendMutation.mutate({ text, attachments })}
            sendError={sendError}
            isSending={sendMutation.isPending}
            onBack={isMobile ? () => navigate("/chat") : undefined}
            isMobile={isMobile}
            onOpenConfig={
              headerAgentContext.agentId
                ? () => navigate(`/settings/agents/${headerAgentContext.agentId}`)
                : undefined
            }
          />
        ) : (
          !isMobile && (
            <div className="chat-empty-pane">
              <div className="chat-empty-pane-icon" aria-hidden="true">💬</div>
              <p className="chat-empty-pane-title">{t("chat.messagePane.selectConversationTitle")}</p>
              <p className="chat-empty-pane-sub">{t("chat.messagePane.selectConversationSubtitle")}</p>
            </div>
          )
        )
      )}
      {showNewGroup && (
        <NewGroupModal
          agents={(agentsQuery.data ?? []).map((a) => {
            const nodeRow = (nodesQuery.data ?? []).find((n) => n.node_id === a.node_id);
            return {
              agent_id: a.agent_id,
              display_name: a.display_name,
              description: a.description,
              status: nodeRow?.status === "online" ? "online" : "offline"
            };
          })}
          onClose={() => setShowNewGroup(false)}
          onCreate={(payload) => createGroupMutation.mutate(payload)}
        />
      )}
    </div>
  );
}

function colorForSeed(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash << 5) - hash + seed.charCodeAt(i);
  const hue = Math.abs(hash) % 360;
  return `oklch(0.55_0.15_${hue})`;
}
