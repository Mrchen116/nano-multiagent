import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { InAppToast } from "../../chat/components/in-app-toast";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { colorForAgent } from "./components/avatar";
import {
  addParticipants,
  createConversation,
  createMessage,
  deleteConversation,
  listConversations,
  listMessages,
  removeParticipant,
  updateConversation,
  type AgentRow
} from "./chat-api";
import { openChatStream } from "./chat-stream";
import {
  applyWsEvent,
  compareMessages,
  emptyConversationState,
  type ConversationState
} from "./chat-stream-reducer";
import { authFetch } from "../../auth/auth-fetch";
import { attachUserConversationStream } from "../../chat/im-chat-api";
import { useAuthStore } from "../../auth/auth-store";
import {
  classifyConversationKind,
  type Attachment,
  type Conversation,
  type Message,
  type PermissionRequest,
  type WsEvent
} from "./chat-types";
import { ConversationSidebar } from "./components/conversation-sidebar";
import {
  GroupSettings,
  type GroupSettingsAgentOption,
  type GroupSettingsMember
} from "./components/group-settings";
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
    // Preserve token_usage from existing state if server response lacks it
    // (token_usage is only available via WS message.completed, not in history fetch)
    const existingById = state.conversation_id === action.conversationId
      ? new Map(state.messages.map((m) => [m.id, m]))
      : new Map();
    const merged = action.messages.map((m) => {
      const existing = existingById.get(m.id);
      let out = m;
      if (!m.token_usage && existing?.token_usage) {
        out = {
          ...out,
          token_usage: existing.token_usage,
          delivery_status: existing.delivery_status
        };
      }
      const permission_requests = mergePermissionRequests(
        m.permission_requests,
        existing?.permission_requests
      );
      if (
        permission_requests.length > 0
        || (m.permission_requests?.length ?? 0) > 0
        || (existing?.permission_requests?.length ?? 0) > 0
      ) {
        out = { ...out, permission_requests };
      }
      return out;
    });
    // bugfix-419: REST history may already be sorted, but sort explicitly so
    // any WS messages merged in via existingById keep the ordering invariant.
    return { conversation_id: action.conversationId, messages: [...merged].sort(compareMessages) };
  }
  if (action.type === "append_optimistic") {
    // feat-340-M18 R9-3: insert the user-authored bubble the moment the POST
    // resolves so the main pane no longer waits on the WS echo (which only
    // arrives for the agent reply path in some flows). Dedupe by id so the
    // later WS message.created — if/when it comes — does not double-print.
    if (action.message.conversation_id !== state.conversation_id) return state;
    if (state.messages.some((m) => m.id === action.message.id)) return state;
    // bugfix-419: sort the new list so a WS echo with a different created_at
    // (e.g. server clock vs. client optimistic timestamp) lands in order.
    return { ...state, messages: [...state.messages, action.message].sort(compareMessages) };
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
 * REST 历史与 WS 流式状态合并 permission_requests（对齐 token_usage 保留策略）。
 *
 * bugfix-367: 同泡多次 ask 后若 refetchOnWindowFocus 命中 React Query 缓存,
 * 服务端列表可能短暂落后于 WS reducer；合并时按 request_id 取并集,
 * resolved 优先于 pending, 避免 pending 卡被 reset 抹掉。
 */
function mergePermissionRequests(
  fromServer: PermissionRequest[] | undefined,
  fromStream: PermissionRequest[] | undefined,
): PermissionRequest[] {
  const server = fromServer ?? [];
  const stream = fromStream ?? [];
  if (stream.length === 0) return server;
  if (server.length === 0) return stream;

  const byId = new Map<string, PermissionRequest>();
  for (const req of server) byId.set(req.request_id, req);
  for (const req of stream) {
    const prev = byId.get(req.request_id);
    if (!prev) {
      byId.set(req.request_id, req);
      continue;
    }
    if (prev.status === "pending" && req.status === "resolved") {
      byId.set(req.request_id, req);
    } else if (prev.status === "resolved" && req.status === "pending") {
      continue;
    } else {
      byId.set(req.request_id, req);
    }
  }
  const order: string[] = [];
  for (const req of server) {
    if (!order.includes(req.request_id)) order.push(req.request_id);
  }
  for (const req of stream) {
    if (!order.includes(req.request_id)) order.push(req.request_id);
  }
  return order.map((id) => byId.get(id)!);
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
  const [showGroupSettings, setShowGroupSettings] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const selfUserId = useAuthStore((s) => s.user?.id ?? null);
  const accessToken = useAuthStore((s) => s.accessToken ?? "");

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
    queryFn: () => listMessages(conversationId!, { markAsRead: true }),
    refetchOnWindowFocus: false
  });

  // bugfix-442: 实时消息流驱动侧边栏会话列表刷新时去抖，避免群聊多 agent 同回合
  // 连续重拉。timer 跨渲染稳定，组件卸载时清理。
  const conversationsRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    return () => {
      if (conversationsRefreshTimer.current) clearTimeout(conversationsRefreshTimer.current);
    };
  }, []);

  // bugfix-442: 读消息走 markAsRead=true 让后端把该会话 unread_count 清零，但侧边栏
  // 角标来自独立的 conversations query，不会自动反映。react-query v5 的 useQuery 无
  // onSuccess，用 effect 监听每次成功取数(dataUpdatedAt 变化)后刷新会话列表。
  useEffect(() => {
    if (messagesQuery.isSuccess) {
      void queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });
    }
  }, [messagesQuery.isSuccess, messagesQuery.dataUpdatedAt, queryClient]);

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

  // Derive mention candidates from already-loaded agentsQuery instead of a
  // separate API round-trip. This eliminates the loading race where the user
  // types `@` before listMentionCandidates resolves.
  const mentionCandidates = useMemo(() => {
    if (!activeConversation) return [];
    const allowed = new Set(
      activeConversation.participants
        .filter((p) => p.type === "agent")
        .map((p) => p.id.replace(/^agent:/, ""))
    );
    return (agentsQuery.data ?? [])
      .filter((a) => allowed.has(a.agent_id.replace(/^agent:/, "")))
      .map((a) => ({
        agent_id: a.agent_id,
        display_name: a.display_name,
        initials: a.display_name?.slice(0, 2).toUpperCase() ?? a.agent_id.slice(0, 2).toUpperCase(),
        status: ((nodesQuery.data ?? []).find((n) => n.node_id === a.node_id)?.status === "online" ? "online" : "offline") as "online" | "offline"
      }));
  }, [activeConversation, agentsQuery.data, nodesQuery.data]);

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
    const color = colorForAgent(agentRow);
    return {
      agentId: agentRow.agent_id,
      nodeName: nodeRow?.node_name ?? null,
      nodeStatus,
      agentColor: color,
      agentInitials: initials
    };
  }, [activeConversation, agentsQuery.data, nodesQuery.data]);

  // feat-438 决策 2: the ⚙ entry dispatches by conversation kind. Group /
  // agent-network open the in-place GroupSettings surface; direct-agent keeps
  // navigating to the single agent's config page.
  const conversationKind = activeConversation
    ? classifyConversationKind(activeConversation)
    : null;
  const isGroupKind = conversationKind === "group" || conversationKind === "agent-network";

  // Pre-resolve members + addable agents for GroupSettings so the component stays
  // presentational. Status comes from the nodes cache (same derivation the header
  // and sidebar use); `userId` carries the UUID the remove endpoint keys on.
  const groupMembers = useMemo<GroupSettingsMember[]>(() => {
    if (!activeConversation) return [];
    return activeConversation.participants.map((p) => {
      const userId = p.user_id ?? (p.type === "user" ? p.id : null);
      let status: "online" | "offline" | null = null;
      if (p.type === "agent") {
        const agentRow = (agentsQuery.data ?? []).find((a) => a.agent_id === p.id);
        const nodeRow = agentRow
          ? (nodesQuery.data ?? []).find((n) => n.node_id === agentRow.node_id)
          : undefined;
        status = nodeRow?.status === "online" ? "online" : "offline";
      }
      return {
        id: p.id,
        userId,
        type: p.type,
        displayName: p.display_name ?? p.id,
        isSelf: p.type === "user" && userId === selfUserId,
        isCreator: userId != null && userId === activeConversation.creator_id,
        status,
        isStale: p.is_stale ?? null
      };
    });
  }, [activeConversation, agentsQuery.data, nodesQuery.data, selfUserId]);

  const addableAgents = useMemo<GroupSettingsAgentOption[]>(() => {
    if (!activeConversation) return [];
    const inGroup = new Set(
      activeConversation.participants
        .filter((p) => p.type === "agent")
        .map((p) => p.id.replace(/^agent:/, ""))
    );
    return (agentsQuery.data ?? [])
      .filter((a) => !inGroup.has(a.agent_id.replace(/^agent:/, "")))
      .map((a) => {
        const nodeRow = (nodesQuery.data ?? []).find((n) => n.node_id === a.node_id);
        return {
          agentId: a.agent_id,
          displayName: a.display_name,
          status: (nodeRow?.status === "online" ? "online" : "offline") as "online" | "offline"
        };
      });
  }, [activeConversation, agentsQuery.data, nodesQuery.data]);

  // Switching conversations closes any open settings surface.
  useEffect(() => {
    setShowGroupSettings(false);
  }, [conversationId]);

  const [streamState, dispatch] = useReducer(streamReducer, emptyConversationState);

  // Persistent cache for token_usage (and delivery_status) so that switching
  // browser tabs — which triggers React Query refetchOnWindowFocus — does not
  // wipe token chips.  REST history never carries token_usage; only WS
  // message.completed provides it.  The cache survives across resets.
  const tokenUsageCache = useRef(new Map<string, { token_usage: NonNullable<Message["token_usage"]>; delivery_status: Message["delivery_status"] }>());

  // Whenever the stream receives a completed message with token_usage, write
  // it into the persistent cache.
  useEffect(() => {
    for (const m of streamState.messages) {
      if (m.token_usage && m.delivery_status === "completed") {
        tokenUsageCache.current.set(m.id, { token_usage: m.token_usage, delivery_status: m.delivery_status });
      }
    }
  }, [streamState.messages]);

  // Seed the reducer with REST history whenever the active conversation or its
  // historical fetch changes.  Prefer the persistent cache, then fallback to
  // the current reducer state.
  useEffect(() => {
    if (!conversationId || !messagesQuery.data) return;
    const restored = messagesQuery.data.items.map((m) => {
      const cached = tokenUsageCache.current.get(m.id);
      if (cached) {
        return { ...m, token_usage: cached.token_usage, delivery_status: cached.delivery_status };
      }
      // Fallback to existing reducer state (legacy merge path)
      if (m.token_usage) return m;
      const existing = streamState.conversation_id === conversationId
        ? streamState.messages.find((sm) => sm.id === m.id)
        : undefined;
      if (existing?.token_usage) {
        return { ...m, token_usage: existing.token_usage, delivery_status: existing.delivery_status };
      }
      return m;
    });
    dispatch({ type: "reset", conversationId, messages: restored });
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

  // Subscribe to owner-scoped status events so all node/agent status indicators
  // in the Chat workspace (Node chip, sidebar status dot, mention candidate
  // status) update in real time when a Gateway connects or disconnects.
  // Mirrors the pattern used by nodes-page.tsx and agent-status-ws-consumer.ts.
  useEffect(() => {
    if (!selfUserId || !accessToken) return;
    const dispose = attachUserConversationStream({
      selfUserId,
      token: accessToken,
      // Fix B: 断线重连后 IM 发 resync 命令时，强制刷新会话列表，防止侧边栏
      // 停在断线期间错过消息的旧快照（对齐 use-global-message-toast 的同路径）。
      onResyncRequired: async () => {
        await queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });
      },
      onEvent: (event) => {
        if (event.eventType === "node.status_changed") {
          const payload = event.payload as { node_id?: unknown; status?: unknown };
          const nodeId = typeof payload.node_id === "string" ? payload.node_id : null;
          const status = typeof payload.status === "string" ? payload.status : null;
          if (!nodeId || !status) return;
          queryClient.setQueryData<NodeRow[] | undefined>(["chat-v2", "nodes"], (prev) => {
            if (!prev) return prev;
            let changed = false;
            const next = prev.map((n) => {
              if (n.node_id !== nodeId) return n;
              if (n.status === status) return n;
              changed = true;
              return { ...n, status };
            });
            return changed ? next : prev;
          });
        } else if (event.eventType === "agent.status_changed") {
          const payload = event.payload as { agent_id?: unknown; status?: unknown };
          const agentId = typeof payload.agent_id === "string" ? payload.agent_id : null;
          const status = typeof payload.status === "string" ? payload.status : null;
          if (!agentId || (status !== "online" && status !== "offline")) return;
          // AgentRow carries node_id but not status directly — all status indicators
          // in Chat are derived from the nodes cache. Find the agent's owning node
          // and patch the nodes cache so sidebar dot, Node chip, and mention
          // candidate status all flip without a network round-trip.
          const agents = queryClient.getQueryData<AgentRow[]>(["chat-v2", "agents"]);
          const agentRow = agents?.find((a) => a.agent_id === agentId);
          const nodeId = agentRow?.node_id;
          if (!nodeId) return;
          queryClient.setQueryData<NodeRow[] | undefined>(["chat-v2", "nodes"], (prev) => {
            if (!prev) return prev;
            let changed = false;
            const next = prev.map((n) => {
              if (n.node_id !== nodeId) return n;
              if (n.status === status) return n;
              changed = true;
              return { ...n, status };
            });
            return changed ? next : prev;
          });
        } else if (
          event.eventType === "message.sent" ||
          event.eventType === "message.created" ||
          event.eventType === "relay.completed"
        ) {
          // bugfix-442: 新消息/回复到达——该会话的未读、preview、时间、排序都可能变。
          // 后端在收消息时已维护好这些字段，去抖后重新拉会话列表一次性反映。
          // message.sent = 用户发消息（repositories.py）；message.created = agent
          // 回复占位创建（event_bridge.py）；relay.completed = gateway 旧 relay 路径。
          // 前端不归一化 event_type，必须用点号 canonical 名（event_types.py）。
          // 注：message_created（下划线）是 _helpers.py 内的历史 DB 行识别 alias，
          // 后端不再 emit，不应出现在 onEvent 分支里。
          // 这条用户维流覆盖所有会话，是驱动侧边栏的正确通道；与会话内
          // openChatStream（只更新当前打开会话的气泡）正交。
          if (conversationsRefreshTimer.current) clearTimeout(conversationsRefreshTimer.current);
          conversationsRefreshTimer.current = setTimeout(() => {
            void queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });
          }, 250);
        }
      }
    });
    return dispose;
  }, [selfUserId, accessToken, queryClient]);

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

  // feat-438 决策 4: write operations refresh via react-query invalidation
  // (the backend emits no conversation-metadata WS events). Dissolve additionally
  // leaves the now-deleted conversation for the list empty state.
  const invalidateConversations = () =>
    void queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });

  // These four feed GroupSettings via mutateAsync so a rejection propagates to the
  // panel, which renders the error inline (the global sendError toast sits below
  // the panel's z-index and would be hidden by the scrim / mobile full-screen).
  const renameMutation = useMutation({
    mutationFn: (title: string) => updateConversation(conversationId!, { title }),
    onSuccess: invalidateConversations
  });

  const addParticipantsMutation = useMutation({
    mutationFn: (agentIds: string[]) => addParticipants(conversationId!, agentIds),
    onSuccess: invalidateConversations
  });

  const removeParticipantMutation = useMutation({
    mutationFn: (userId: string) => removeParticipant(conversationId!, userId),
    onSuccess: invalidateConversations
  });

  const dissolveMutation = useMutation({
    mutationFn: () => deleteConversation(conversationId!),
    onSuccess: () => {
      setShowGroupSettings(false);
      invalidateConversations();
      navigate("/chat");
    }
  });

  const groupSettingsBusy =
    renameMutation.isPending
    || addParticipantsMutation.isPending
    || removeParticipantMutation.isPending
    || dissolveMutation.isPending;

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
          agents={(agentsQuery.data ?? []).map((a) => {
            const nodeRow = (nodesQuery.data ?? []).find((n) => n.node_id === a.node_id);
            return {
              agent_id: a.agent_id,
              display_name: a.display_name,
              status: nodeRow?.status === "online" ? "online" : "offline"
            };
          })}
        />
      )}
      {showDetail && (
        activeConversation ? (
          <MessagePane
            conversation={activeConversation}
            messages={streamState.messages}
            mentionCandidates={mentionCandidates}
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
              isGroupKind
                ? () => setShowGroupSettings(true)
                : headerAgentContext.agentId
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
      {showGroupSettings && activeConversation && isGroupKind && (
        <GroupSettings
          title={activeConversation.title}
          members={groupMembers}
          addableAgents={addableAgents}
          isMobile={isMobile}
          isBusy={groupSettingsBusy}
          onClose={() => setShowGroupSettings(false)}
          onRename={(title) => renameMutation.mutateAsync(title)}
          onAddParticipants={(agentIds) => addParticipantsMutation.mutateAsync(agentIds)}
          onRemoveParticipant={(userId) => removeParticipantMutation.mutateAsync(userId)}
          onDissolve={() => dissolveMutation.mutateAsync()}
          onOpenAgentConfig={(agentId) => navigate(`/settings/agents/${agentId}`)}
        />
      )}
    </div>
  );
}

