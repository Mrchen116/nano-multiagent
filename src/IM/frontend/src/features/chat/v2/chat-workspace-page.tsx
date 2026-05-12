import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

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
): ConversationState {
  if (action.type === "reset") {
    return { conversation_id: action.conversationId, messages: action.messages };
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
  const headerAgentContext = useMemo<{ agentId: string | null; nodeName: string | null; nodeStatus: "online" | "offline" }>(() => {
    if (!activeConversation) return { agentId: null, nodeName: null, nodeStatus: "offline" };
    const agentParticipant = activeConversation.participants.find((p) => p.type === "agent");
    if (!agentParticipant) return { agentId: null, nodeName: null, nodeStatus: "offline" };
    const agentRow = (agentsQuery.data ?? []).find((a) => a.agent_id === agentParticipant.id);
    if (!agentRow) return { agentId: agentParticipant.id, nodeName: null, nodeStatus: "offline" };
    const nodeRow = (nodesQuery.data ?? []).find((n) => n.node_id === agentRow.node_id);
    const nodeStatus = nodeRow?.status === "online" ? "online" : "offline";
    return { agentId: agentRow.agent_id, nodeName: nodeRow?.node_name ?? null, nodeStatus };
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
    onSuccess: () => {
      // Bump conversation list ordering on next refetch; the WS echo will fill
      // in the new message in-place so we only need cache invalidation here.
      void queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });
    }
  });

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
            onSend={(text, attachments) => sendMutation.mutate({ text, attachments })}
            onBack={isMobile ? () => navigate("/chat") : undefined}
            onOpenConfig={
              headerAgentContext.agentId
                ? () => navigate(`/settings/agents/${headerAgentContext.agentId}`)
                : undefined
            }
          />
        ) : (
          !isMobile && (
            <div className="chat-empty-pane">
              <p className="chat-empty-pane-title">{t("chat.messagePane.selectConversationTitle")}</p>
              <p className="chat-empty-pane-sub">{t("chat.messagePane.selectConversationSubtitle")}</p>
            </div>
          )
        )
      )}
      {showNewGroup && (
        <NewGroupModal
          agents={(agentsQuery.data ?? []).map((a) => ({
            agent_id: a.agent_id,
            display_name: a.display_name,
            description: a.description
          }))}
          onClose={() => setShowNewGroup(false)}
          onCreate={(payload) => createGroupMutation.mutate(payload)}
        />
      )}
    </div>
  );
}
