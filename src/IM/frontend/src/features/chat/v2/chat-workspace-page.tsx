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
  forkConversation,
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
import {
  getAgentCapabilities,
  getAgentConfig,
  normalizeAllowlistOptions,
} from "../../settings/agents/im-agent-config-api";
import {
  buildSlashSkills,
  resolveEnabledSkills,
  type AgentEnabledSkills,
} from "./components/slash-candidates";
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

type DistillTargetScope = "agent" | "pa";

const DISTILL_SKILL_NAME = "conversation-skill-distiller";

async function fetchNodes(): Promise<NodeRow[]> {
  const res = await authFetch("/im/v1/nodes");
  if (!res.ok) throw new Error(`listNodes failed: ${res.status}`);
  return (await res.json()) as NodeRow[];
}

function buildDistillDraft(input: {
  sourceJsonlPaths: string[];
  executionAgentId: string;
  targetScope: DistillTargetScope;
}): string {
  const scopeLabel = input.targetScope === "pa" ? "PA 产品" : "agent";
  return [
    `/skill:${DISTILL_SKILL_NAME}`,
    "source_jsonl_paths:",
    ...input.sourceJsonlPaths.map((path) => `  ${path}`),
    `execution_agent_id: ${input.executionAgentId}`,
    `target_scope: ${input.targetScope}`,
    "",
    `请基于上述会话 transcript，总结我反复使用且值得复用的工作方式，直接生成并写入一个 ${scopeLabel} 级 skill。重点关注：`,
    "- 触发这个 skill 的场景",
    "- 应遵循的步骤/检查点",
    "- 失败或边界情况",
    "如果这些会话不足以形成稳定模式，请说明原因，不要创建 skill。"
  ].join("\n");
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
  const [distillMode, setDistillMode] = useState(false);
  const [selectedDistillConversationIds, setSelectedDistillConversationIds] = useState<Set<string>>(() => new Set());
  const [showDistillDialog, setShowDistillDialog] = useState(false);
  const [distillExecutionAgentId, setDistillExecutionAgentId] = useState("");
  const [distillTargetScope, setDistillTargetScope] = useState<DistillTargetScope>("agent");
  const [distillError, setDistillError] = useState<string | null>(null);
  const [distillSubmitting, setDistillSubmitting] = useState(false);
  const [draftSeed, setDraftSeed] = useState<{ id: string; text: string } | null>(null);
  // feat-445-M1: fork success toast (top-left, auto-fade); null = hidden.
  const [forkToast, setForkToast] = useState<boolean>(false);
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

  // feat-430: agents in the active conversation (canonical agent_id + display_name)
  // — drives the slash picker's per-agent skill fetch.
  const conversationAgents = useMemo(() => {
    if (!activeConversation) return [] as { agent_id: string; display_name: string }[];
    const allowed = new Set(
      activeConversation.participants
        .filter((p) => p.type === "agent")
        .map((p) => p.id.replace(/^agent:/, ""))
    );
    return (agentsQuery.data ?? [])
      .filter((a) => allowed.has(a.agent_id.replace(/^agent:/, "")))
      .map((a) => ({ agent_id: a.agent_id, display_name: a.display_name }));
  }, [activeConversation, agentsQuery.data]);

  // feat-430: enabled skills for the slash picker = each agent's config whitelist ∩
  // capabilities (决策 2), then group-union deduped by SKILL.md location (决策 3 / Q7).
  // Fetched per conversation (not per `/` keystroke) and cached by react-query.
  const slashSkillsQuery = useQuery({
    enabled: conversationAgents.length > 0,
    queryKey: [
      "chat-v2",
      "slash-skills",
      conversationAgents.map((a) => a.agent_id).sort(),
    ],
    staleTime: 60_000,
    queryFn: async () => {
      // fix-r2 (P1.4): allSettled so one agent's failed config/capabilities fetch does
      // not collapse the whole picker — only that agent's skills drop out.
      // fix-r2 (P0): source="live" pulls the agent's真实已启用 skills whitelist from the
      // owning Gateway (the IM mirror is empty for Gateway-seeded agents), so the
      // config ∩ capabilities intersection reflects真实 enablement instead of全量.
      const results = await Promise.allSettled(
        conversationAgents.map(async (a): Promise<AgentEnabledSkills> => {
          const [config, capabilities] = await Promise.all([
            getAgentConfig(a.agent_id, "live"),
            getAgentCapabilities(a.agent_id),
          ]);
          const capSkills = normalizeAllowlistOptions(capabilities.skills);
          return {
            agentDisplayName: a.display_name,
            skills: resolveEnabledSkills(config.skills ?? [], capSkills),
          };
        })
      );
      const perAgent = results
        .filter(
          (r): r is PromiseFulfilledResult<AgentEnabledSkills> =>
            r.status === "fulfilled",
        )
        .map((r) => r.value);
      return buildSlashSkills(perAgent);
    },
  });
  const slashSkills = slashSkillsQuery.data ?? [];

  const selectedDistillConversations = useMemo(() => {
    const byId = new Set(selectedDistillConversationIds);
    return (conversationsQuery.data ?? []).filter(
      (c) => byId.has(c.id) && c.run_state !== "running" && c.source_agent_id && c.source_jsonl_path
    );
  }, [conversationsQuery.data, selectedDistillConversationIds]);

  const distillSourceAgentOptions = useMemo(() => {
    const seen = new Set<string>();
    const options: { agentId: string; displayName: string }[] = [];
    for (const c of selectedDistillConversations) {
      const agentId = c.source_agent_id;
      if (!agentId || seen.has(agentId)) continue;
      seen.add(agentId);
      const row = (agentsQuery.data ?? []).find((a) => a.agent_id === agentId);
      const participant = c.participants.find((p) => p.type === "agent" && p.id === agentId);
      options.push({
        agentId,
        displayName: row?.display_name ?? participant?.display_name ?? agentId,
      });
    }
    return options;
  }, [agentsQuery.data, selectedDistillConversations]);

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

  // feat-445-M1: fork from one completed agent reply → new branch chat with history
  // copied to that point. Mirror the create-direct pattern: invalidate both legacy and
  // v2 conversation caches, jump into the branch, and surface a brief success toast.
  const forkMutation = useMutation({
    mutationFn: (messageId: string) =>
      forkConversation(conversationId!, messageId),
    onSuccess: async (conv) => {
      setSendError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }),
        queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] })
      ]);
      navigate(`/chat/${conv.id}`);
      setForkToast(true);
    },
    onError: (err) => {
      setSendError(err instanceof Error ? err.message : t("chat.messagePane.forkError"));
    }
  });

  // Auto-dismiss the fork toast 4s after it appears (matches in-app-toast cadence).
  useEffect(() => {
    if (!forkToast) return;
    const id = setTimeout(() => setForkToast(false), 4000);
    return () => clearTimeout(id);
  }, [forkToast]);

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

  function enterDistillMode() {
    setDistillMode(true);
    setDistillError(null);
  }

  function cancelDistillMode() {
    setDistillMode(false);
    setSelectedDistillConversationIds(new Set());
    setShowDistillDialog(false);
    setDistillError(null);
  }

  function toggleDistillConversation(conversationId: string) {
    setSelectedDistillConversationIds((prev) => {
      const next = new Set(prev);
      if (next.has(conversationId)) next.delete(conversationId);
      else next.add(conversationId);
      return next;
    });
  }

  function openDistillDialog() {
    if (selectedDistillConversations.length === 0) return;
    const sourceAgentIds = [...new Set(selectedDistillConversations.map((c) => c.source_agent_id).filter(Boolean) as string[])];
    setDistillExecutionAgentId(sourceAgentIds.length === 1 ? sourceAgentIds[0]! : "");
    setDistillTargetScope("agent");
    setDistillError(null);
    setShowDistillDialog(true);
  }

  async function executionAgentCanSeeDistiller(agentId: string): Promise<boolean> {
    const [config, capabilities] = await Promise.all([
      getAgentConfig(agentId, "live"),
      getAgentCapabilities(agentId),
    ]);
    const capSkills = normalizeAllowlistOptions(capabilities.skills);
    return resolveEnabledSkills(config.skills ?? [], capSkills).some(
      (skill) => skill.name === DISTILL_SKILL_NAME
    );
  }

  async function startDistillation() {
    if (!distillExecutionAgentId || selectedDistillConversations.length === 0) return;
    setDistillSubmitting(true);
    setDistillError(null);
    try {
      const visible = await executionAgentCanSeeDistiller(distillExecutionAgentId);
      if (!visible) {
        setDistillError(`Enable ${DISTILL_SKILL_NAME} for the execution agent before starting.`);
        return;
      }
      const agentName =
        distillSourceAgentOptions.find((a) => a.agentId === distillExecutionAgentId)?.displayName
        ?? distillExecutionAgentId;
      const conv = await createConversation({
        title: `Skill distill · ${agentName}`,
        agentIds: [distillExecutionAgentId],
      });
      queryClient.setQueryData<Conversation[] | undefined>(["chat-v2", "conversations"], (prev) => {
        const rest = (prev ?? []).filter((c) => c.id !== conv.id);
        return [conv, ...rest];
      });
      setDraftSeed({
        id: `distill-${conv.id}-${Date.now()}`,
        text: buildDistillDraft({
          sourceJsonlPaths: selectedDistillConversations.map((c) => c.source_jsonl_path!).filter(Boolean),
          executionAgentId: distillExecutionAgentId,
          targetScope: distillTargetScope,
        }),
      });
      setShowDistillDialog(false);
      setDistillMode(false);
      setSelectedDistillConversationIds(new Set());
      await queryClient.invalidateQueries({ queryKey: ["chat-v2", "conversations"] });
      navigate(`/chat/${conv.id}`);
    } catch (err) {
      setDistillError(err instanceof Error ? err.message : t("chat.distill.startError"));
    } finally {
      setDistillSubmitting(false);
    }
  }

  const showList = !isMobile || !conversationId;
  const showDetail = !isMobile || Boolean(conversationId);

  return (
    <div className="chat-workspace">
      {forkToast && (
        <div className="fork-toast show" role="status" aria-live="polite">
          <div className="min-w-0 flex-1">
            <p className="t-title">{t("chat.messagePane.forkToastTitle")}</p>
            <p className="t-sub">{t("chat.messagePane.forkToastSub")}</p>
          </div>
        </div>
      )}
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
          distillMode={distillMode}
          selectedDistillConversationIds={selectedDistillConversationIds}
          onToggleDistillConversation={toggleDistillConversation}
          onEnterDistillMode={enterDistillMode}
          onCancelDistillMode={cancelDistillMode}
          onStartDistill={openDistillDialog}
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
            draftSeed={draftSeed}
            slashSkills={slashSkills}
            nodeName={headerAgentContext.nodeName}
            nodeStatus={headerAgentContext.nodeStatus}
            agentColor={headerAgentContext.agentColor}
            agentInitials={headerAgentContext.agentInitials}
            onSend={(text, attachments) => sendMutation.mutate({ text, attachments })}
            sendError={sendError}
            isSending={sendMutation.isPending}
            isDirectChat={conversationKind === "direct-agent"}
            agentOnline={headerAgentContext.nodeStatus === "online"}
            onFork={(messageId) => forkMutation.mutate(messageId)}
            forkPending={forkMutation.isPending}
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
      {showDistillDialog && (
        <div className="chat-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="distill-dialog-title">
          <div className="chat-modal">
            <header className="chat-modal-header">
              <h2 id="distill-dialog-title">{t("chat.distill.title")}</h2>
              <p>{t("chat.distill.subtitle")}</p>
            </header>
            <div className="chat-modal-body">
              {distillSourceAgentOptions.length > 1 && (
                <section className="chat-modal-section">
                  <p className="chat-modal-section-label">Execution agent</p>
                  <ul className="chat-modal-agents">
                    {distillSourceAgentOptions.map((agent) => (
                      <li key={agent.agentId}>
                        <label className={`chat-modal-agent${distillExecutionAgentId === agent.agentId ? " chat-modal-agent--on" : ""}`}>
                          <input
                            type="radio"
                            name="distill-execution-agent"
                            checked={distillExecutionAgentId === agent.agentId}
                            onChange={() => setDistillExecutionAgentId(agent.agentId)}
                          />
                          <span className="chat-modal-agent-body">
                            <span className="chat-modal-agent-name">{agent.displayName}</span>
                            <span className="chat-modal-agent-desc">{agent.agentId}</span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {distillSourceAgentOptions.length === 1 && (
                <section className="chat-modal-section">
                  <p className="chat-modal-section-label">Execution agent</p>
                  <p className="chat-distill-static-agent">
                    {distillSourceAgentOptions[0]!.displayName}
                  </p>
                </section>
              )}
              <section className="chat-modal-section">
                <p className="chat-modal-section-label">{t("chat.distill.scope")}</p>
                <div className="chat-distill-scope-options">
                  <label className={`chat-distill-scope${distillTargetScope === "agent" ? " chat-distill-scope--on" : ""}`}>
                    <input
                      type="radio"
                      name="distill-target-scope"
                      checked={distillTargetScope === "agent"}
                      onChange={() => setDistillTargetScope("agent")}
                    />
                    <span>Agent</span>
                  </label>
                  <label className={`chat-distill-scope${distillTargetScope === "pa" ? " chat-distill-scope--on" : ""}`}>
                    <input
                      type="radio"
                      name="distill-target-scope"
                      checked={distillTargetScope === "pa"}
                      onChange={() => setDistillTargetScope("pa")}
                    />
                    <span>PA product</span>
                  </label>
                </div>
              </section>
              {distillError && (
                <p className="chat-distill-error" role="alert">{distillError}</p>
              )}
            </div>
            <footer className="chat-modal-footer">
              <button type="button" className="chat-modal-btn-ghost" onClick={() => setShowDistillDialog(false)}>
                {t("chat.newGroup.cancel")}
              </button>
              <button
                type="button"
                className="chat-modal-btn-primary"
                disabled={!distillExecutionAgentId || distillSubmitting}
                onClick={() => void startDistillation()}
              >
                {distillSubmitting ? t("chat.distill.starting") : "Start distillation"}
              </button>
            </footer>
          </div>
        </div>
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
