import type { DatabaseSync } from 'node:sqlite';
import type { UserNotificationKind, UserStreamNotificationHint } from '@nano/product-contracts';
import { externalChannelOwnerId, matchesExternalChannel } from './channels.js';
import type { Row } from './context.js';
import { all, one } from './context.js';
import { conversationName } from './conversation-name.js';

const CANDIDATE_EVENT_TYPES = new Set([
  'message.created',
  'message.sent',
  'message.completed',
  'permission.request',
  'agent.work.updated',
]);

/** Fast O(1) check skipping delta, thinking, tool-call, heartbeat, and presence frames. */
export function isNotificationCandidateEventType(eventType: unknown): eventType is string {
  return typeof eventType === 'string' && CANDIDATE_EVENT_TYPES.has(eventType);
}

function channelMatchesExternalShadow(channel: Row, chat: Row): boolean {
  if (matchesExternalChannel(channel, chat)) return true;
  if (channel.provider !== chat.external_source) return false;
  try {
    const cfg = JSON.parse(String(channel.config_json ?? '{}')) as Record<string, unknown>;
    const extId = String(chat.external_chat_id ?? '');
    if (channel.provider === 'feishu' && typeof cfg.app_id === 'string' && cfg.app_id) {
      return extId.startsWith(`feishu:${cfg.app_id}:`);
    }
    if (channel.provider === 'wechat' && typeof cfg.bot_id === 'string' && cfg.bot_id) {
      return extId.startsWith(`wechat:${cfg.bot_id}:`);
    }
  } catch {
    return false;
  }
  return false;
}

function extractOwnerSourceIdFromChannel(channel: Row): string | undefined {
  const fromRuntime = externalChannelOwnerId(channel);
  if (fromRuntime) return fromRuntime;
  if (channel.provider === 'feishu') {
    try {
      const cfg = JSON.parse(String(channel.config_json ?? '{}')) as Record<string, unknown>;
      if (typeof cfg.owner_open_id === 'string' && cfg.owner_open_id) return cfg.owner_open_id;
    } catch {
      return undefined;
    }
  }
  return undefined;
}

/** Resolve the bound account owner's external platform user/open ID for a shadow conversation. */
export function resolveConversationExternalOwnerSourceId(
  db: DatabaseSync,
  chat: Row | undefined,
): string | undefined {
  if (!chat?.external_source || !chat.config_agent_id) return undefined;
  const channels = all(
    db,
    'SELECT * FROM agent_channels WHERE agent_id=? AND owner_id=? AND provider=? ORDER BY enabled DESC, rowid DESC',
    chat.config_agent_id,
    chat.owner_id,
    chat.external_source,
  );
  const matched = channels.find(row => channelMatchesExternalShadow(row, chat)) ?? channels[0];
  return matched ? extractOwnerSourceIdFromChannel(matched) : undefined;
}

/** Return true when a `'user'` message in an external shadow chat was sent by the owner themselves. */
export function isExternalOwnerMirrorMessage(
  db: DatabaseSync,
  chat: Row | undefined,
  senderSourceId: string | null | undefined,
  messageId?: string | null,
): boolean {
  if (!chat?.external_source) return false;
  if (!senderSourceId) return true;
  const ownerSourceId = resolveConversationExternalOwnerSourceId(db, chat);
  if (ownerSourceId && senderSourceId === ownerSourceId) return true;
  if (messageId && one(db, 'SELECT 1 FROM owner_direct_agent_messages WHERE message_id=? LIMIT 1', messageId)) {
    return true;
  }
  return false;
}

/** Return true iff an external shadow message is a genuine inbound message from an external peer. */
export function isExternalPeerInboundMessage(
  db: DatabaseSync,
  chat: Row | undefined,
  senderType: string,
  senderSourceId: string | null | undefined,
  contextOnly = false,
  messageId?: string | null,
): boolean {
  if (contextOnly || senderType !== 'user' || !chat?.external_source) return false;
  if (!senderSourceId) return false;
  return !isExternalOwnerMirrorMessage(db, chat, senderSourceId, messageId);
}

interface PrefetchedMessageRow {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  sender_type: string;
  content: string;
  attachments_json: string | null;
  delivery_status: string;
  sender_display_name: string | null;
  sender_source_id: string | null;
  permission_request_json: string | null;
  system_notice_json: string | null;
  thread_root_id: string | null;
  account_display_name: string | null;
  interactive_id: string | null;
  context_only: number;
  mentioned_owner: number;
  in_owner_direct: number;
}

interface PrefetchedWorkAgent {
  agent_id: string;
  owner_id: string;
  node_id: string;
  display_name: string | null;
  main_session_id: string | null;
  latest_turn_id: string | null;
  latest_turn_status: string | null;
}

interface BatchSnapshot {
  conversations: Map<string, Row>;
  participants: Map<string, { is_muted: boolean; unread_count: number }>;
  membersByConv: Map<string, Row[]>;
  externalOwnerByConv: Map<string, string | undefined>;
  messages: Map<string, PrefetchedMessageRow>;
  threadDeliveries: Map<string, Set<string>>;
  viewerOwnerIds: Map<string, string>;
  workAgents: Map<string, PrefetchedWorkAgent>;
}

function hasViewerMention(content: string, viewerId: string): boolean {
  for (const match of content.matchAll(/<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g)) {
    if (match[1] === viewerId) return true;
  }
  return false;
}

function formatPreviewText(content: string, members: readonly Row[]): string | undefined {
  if (!content) return undefined;
  const names = new Map(members.map(user => [String(user.id), String(user.display_name || user.id)]));
  const rendered = content
    .replace(
      /<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g,
      (_tag, targetId: string) => `@${names.get(targetId) || 'unknown'}`,
    )
    .replace(/\s+/g, ' ')
    .trim();
  return rendered ? rendered.slice(0, 160) : undefined;
}

function buildConversationRoute(conversationId: string, threadRootId?: string): string {
  const base = `/chat/${encodeURIComponent(conversationId)}`;
  return threadRootId ? `${base}?thread=${encodeURIComponent(threadRootId)}` : base;
}

function extractMessageId(frame: Row): string | undefined {
  const fromRoot = typeof frame.message_id === 'string' && frame.message_id ? frame.message_id : undefined;
  if (fromRoot) return fromRoot;
  const data = frame.data as Record<string, unknown> | undefined;
  if (!data) return undefined;
  if (typeof data.message_id === 'string' && data.message_id) return data.message_id;
  if (typeof data.id === 'string' && data.id) return data.id;
  return undefined;
}

function extractConversationId(frame: Row): string | undefined {
  if (typeof frame.conversation_id === 'string' && frame.conversation_id) return frame.conversation_id;
  const data = frame.data as Record<string, unknown> | undefined;
  return typeof data?.conversation_id === 'string' && data.conversation_id ? data.conversation_id : undefined;
}

function prefetchBatchSnapshot(
  db: DatabaseSync,
  userIds: readonly string[],
  frames: readonly Row[],
): BatchSnapshot {
  const snapshot: BatchSnapshot = {
    conversations: new Map(),
    participants: new Map(),
    membersByConv: new Map(),
    externalOwnerByConv: new Map(),
    messages: new Map(),
    threadDeliveries: new Map(),
    viewerOwnerIds: new Map(),
    workAgents: new Map(),
  };
  if (!userIds.length || !frames.length) return snapshot;

  const convIds = new Set<string>();
  const msgIds = new Set<string>();
  const workAgentIds = new Set<string>();
  for (const frame of frames) {
    if (!isNotificationCandidateEventType(frame.event_type)) continue;
    const cid = extractConversationId(frame);
    if (cid) convIds.add(cid);
    const mid = extractMessageId(frame);
    if (mid) msgIds.add(mid);
    if (frame.event_type === 'agent.work.updated') {
      const aid = typeof frame.data?.agent_id === 'string' ? frame.data.agent_id : undefined;
      if (aid) workAgentIds.add(aid);
    }
  }

  const userJson = JSON.stringify(userIds);

  if (msgIds.size > 0) {
    const msgRows = all(
      db,
      `SELECT m.id, m.conversation_id, m.sender_user_id, m.sender_type, m.content, m.attachments_json,
              m.delivery_status, m.sender_display_name, m.sender_source_id, m.permission_request_json,
              m.system_notice_json, m.thread_root_id,
              COALESCE(ap.display_name, u.display_name) AS account_display_name,
              i.message_id AS interactive_id,
              coalesce(json_extract(f.facts_json, '$.context_only'), 0) AS context_only,
              coalesce(json_extract(f.facts_json, '$.mentioned_owner'), 0) AS mentioned_owner,
              EXISTS(SELECT 1 FROM owner_direct_agent_messages od WHERE od.message_id=m.id) AS in_owner_direct
       FROM messages m
       LEFT JOIN users u ON u.id=m.sender_user_id
       LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id
       LEFT JOIN message_interactive i ON i.message_id=m.id
       LEFT JOIN provider_message_facts f ON f.message_id=m.id
       WHERE m.id IN (SELECT value FROM json_each(?))`,
      JSON.stringify([...msgIds]),
    ) as unknown as PrefetchedMessageRow[];
    const needThreadDeliveries: string[] = [];
    for (const row of msgRows) {
      snapshot.messages.set(row.id, row);
      if (row.conversation_id) convIds.add(row.conversation_id);
      if (row.thread_root_id) needThreadDeliveries.push(row.id);
    }
    if (needThreadDeliveries.length > 0) {
      for (const td of all(
        db,
        'SELECT message_id, user_id FROM thread_deliveries WHERE message_id IN (SELECT value FROM json_each(?))',
        JSON.stringify(needThreadDeliveries),
      )) {
        let set = snapshot.threadDeliveries.get(td.message_id);
        if (!set) snapshot.threadDeliveries.set(td.message_id, (set = new Set()));
        set.add(td.user_id);
      }
    }
  }

  if (convIds.size > 0) {
    const convJson = JSON.stringify([...convIds]);
    const externalAgents = new Set<string>();
    for (const c of all(db, 'SELECT * FROM conversations WHERE id IN (SELECT value FROM json_each(?))', convJson)) {
      snapshot.conversations.set(c.id, c);
      if (c.external_source && c.config_agent_id) externalAgents.add(c.config_agent_id);
    }
    for (const p of all(
      db,
      `SELECT conversation_id, user_id, is_muted, unread_count
       FROM conversation_participants
       WHERE conversation_id IN (SELECT value FROM json_each(?))
         AND user_id IN (SELECT value FROM json_each(?))`,
      convJson,
      userJson,
    )) {
      snapshot.participants.set(`${p.conversation_id}\0${p.user_id}`, {
        is_muted: Boolean(p.is_muted),
        unread_count: Number(p.unread_count ?? 0),
      });
    }
    for (const m of all(
      db,
      `SELECT cp.conversation_id, u.id, u.username, COALESCE(ap.display_name, u.display_name) AS display_name
       FROM conversation_participants cp
       JOIN users u ON u.id=cp.user_id
       LEFT JOIN agent_profiles ap ON u.username='agent:'||ap.agent_id
       WHERE cp.conversation_id IN (SELECT value FROM json_each(?))
       ORDER BY cp.rowid`,
      convJson,
    )) {
      let arr = snapshot.membersByConv.get(m.conversation_id);
      if (!arr) snapshot.membersByConv.set(m.conversation_id, (arr = []));
      arr.push(m);
    }
    if (externalAgents.size > 0) {
      const channels = all(
        db,
        'SELECT * FROM agent_channels WHERE agent_id IN (SELECT value FROM json_each(?)) ORDER BY enabled DESC, rowid DESC',
        JSON.stringify([...externalAgents]),
      );
      for (const c of snapshot.conversations.values()) {
        if (!c.external_source || !c.config_agent_id) continue;
        const candidates = channels.filter(
          ch =>
            ch.agent_id === c.config_agent_id &&
            ch.owner_id === c.owner_id &&
            ch.provider === c.external_source,
        );
        const matched = candidates.find(ch => channelMatchesExternalShadow(ch, c)) ?? candidates[0];
        snapshot.externalOwnerByConv.set(c.id, matched ? extractOwnerSourceIdFromChannel(matched) : undefined);
      }
    }
  }

  if (workAgentIds.size > 0) {
    for (const u of all(
      db,
      'SELECT id, owner_id FROM users WHERE id IN (SELECT value FROM json_each(?))',
      userJson,
    )) {
      snapshot.viewerOwnerIds.set(u.id, u.owner_id);
    }
    for (const row of all(
      db,
      `SELECT ap.agent_id, ap.owner_id, ap.node_id, ap.display_name,
              ws.session_id AS main_session_id,
              (SELECT wt.turn_id FROM agent_work_turns wt WHERE wt.session_id=ws.session_id ORDER BY wt.seq DESC LIMIT 1) AS latest_turn_id,
              (SELECT json_extract(wt.payload, '$.status') FROM agent_work_turns wt WHERE wt.session_id=ws.session_id ORDER BY wt.seq DESC LIMIT 1) AS latest_turn_status
       FROM agent_profiles ap
       LEFT JOIN agent_work_sessions ws
         ON ws.root_agent_id=ap.agent_id
        AND ws.scope='global_main'
        AND coalesce(json_extract(ws.payload, '$.retired'), 0)=0
       WHERE ap.agent_id IN (SELECT value FROM json_each(?)) AND ap.is_stale=0`,
      JSON.stringify([...workAgentIds]),
    ) as unknown as PrefetchedWorkAgent[]) {
      snapshot.workAgents.set(row.agent_id, row);
    }
  }

  return snapshot;
}

function projectSingleHint(
  viewerId: string,
  frame: Row,
  snapshot: BatchSnapshot,
  options: { replayed?: boolean; isNodeOnline?: (nodeId: string) => boolean },
): UserStreamNotificationHint | undefined {
  const eventType = frame.event_type;
  if (!isNotificationCandidateEventType(eventType)) return undefined;
  const data = (frame.data ?? {}) as Record<string, unknown>;
  const replayedField = options.replayed ? ({ replayed: true as const }) : {};

  if (eventType === 'agent.work.updated') {
    const agentId = typeof data.agent_id === 'string' ? data.agent_id : '';
    const revision = data.revision ?? 0;
    const work = snapshot.workAgents.get(agentId);
    const targetRoute = `/settings/agents/${encodeURIComponent(agentId)}?view=work`;
    const viewerOwner = snapshot.viewerOwnerIds.get(viewerId);
    const online = work ? (options.isNodeOnline ? options.isNodeOnline(work.node_id) : true) : false;
    let mainExecution = work?.latest_turn_status ?? 'idle';
    if (['completed', 'failed', 'interrupted'].includes(mainExecution)) mainExecution = 'idle';
    if (!online && ['running', 'waiting_permission'].includes(mainExecution)) mainExecution = 'unknown';

    const eligible = Boolean(
      work &&
        viewerOwner &&
        work.owner_id === viewerOwner &&
        online &&
        mainExecution === 'waiting_permission',
    );
    return {
      eligible,
      ...replayedField,
      ...(eligible ? { kind: 'work_permission' as const } : {}),
      dedupe_key: eligible
        ? `work-perm:${agentId}:${work!.main_session_id ?? 'main'}:${work!.latest_turn_id ?? revision}`
        : `work:${agentId}:${revision}`,
      is_muted: false,
      mentions_viewer: false,
      ...(agentId ? { agent_id: agentId } : {}),
      ...(work?.display_name || agentId ? { sender_name: work?.display_name || agentId } : {}),
      target_route: targetRoute,
    };
  }

  const cid = extractConversationId(frame) ?? '';
  const mid = extractMessageId(frame) ?? '';
  const storedMsg = mid ? snapshot.messages.get(mid) : undefined;
  const conv = cid ? snapshot.conversations.get(cid) : undefined;
  const participant = cid ? snapshot.participants.get(`${cid}\0${viewerId}`) : undefined;
  const isMuted = participant?.is_muted ?? false;
  const conversationUnread = participant?.unread_count ?? 0;
  const members = (cid ? snapshot.membersByConv.get(cid) : undefined) ?? [];
  const convType: 'direct' | 'group' | undefined =
    conv?.type === 'group' ? 'group' : conv?.type === 'direct' ? 'direct' : undefined;
  const convTitle = conv ? conversationName(conv, members, viewerId) : undefined;

  const threadRoot =
    (typeof data.thread_root_message_id === 'string' && data.thread_root_message_id) ||
    storedMsg?.thread_root_id ||
    undefined;
  const targetRoute = cid ? buildConversationRoute(cid, convType === 'group' ? threadRoot : undefined) : '/chat';

  const rawContent =
    typeof data.content === 'string' ? data.content : (storedMsg?.content ?? '');
  const mentionsViewer =
    hasViewerMention(rawContent, viewerId) ||
    Boolean(conv?.external_source && storedMsg?.mentioned_owner && conv.owner_id === viewerId);

  let threadAllowed = true;
  if (convType === 'group' && threadRoot) {
    if (Array.isArray(data.thread_notify_user_ids)) {
      threadAllowed = data.thread_notify_user_ids.includes(viewerId) || mentionsViewer;
    } else if (mid && snapshot.threadDeliveries.has(mid)) {
      threadAllowed = snapshot.threadDeliveries.get(mid)!.has(viewerId) || mentionsViewer;
    }
  }

  const senderObj = (data.sender ?? undefined) as Record<string, unknown> | undefined;
  const senderType =
    (typeof data.sender_type === 'string' && data.sender_type) ||
    (typeof senderObj?.type === 'string' && senderObj.type) ||
    storedMsg?.sender_type ||
    '';
  const senderUserId =
    (typeof data.sender_user_id === 'string' && data.sender_user_id) ||
    storedMsg?.sender_user_id ||
    '';
  const senderName =
    (typeof data.sender_display_name === 'string' && data.sender_display_name.trim()) ||
    (typeof senderObj?.display_name === 'string' && senderObj.display_name.trim()) ||
    (typeof data.sender_name === 'string' && data.sender_name.trim()) ||
    storedMsg?.sender_display_name?.trim() ||
    storedMsg?.sender_source_id ||
    storedMsg?.account_display_name?.trim() ||
    undefined;

  const baseFields = {
    ...replayedField,
    is_muted: isMuted,
    mentions_viewer: mentionsViewer,
    ...(cid ? { conversation_id: cid } : {}),
    ...(convType ? { conversation_type: convType } : {}),
    ...(convTitle ? { conversation_title: convTitle } : {}),
    conversation_unread: conversationUnread,
    ...(convType === 'group' && threadRoot ? { thread_root_message_id: threadRoot } : {}),
    ...(senderName ? { sender_name: senderName } : {}),
    target_route: targetRoute,
  };

  if (eventType === 'permission.request') {
    const nested = (data.permission_request ?? undefined) as Record<string, unknown> | undefined;
    const reqId =
      (typeof data.request_id === 'string' && data.request_id) ||
      (typeof nested?.request_id === 'string' && nested.request_id) ||
      mid;
    const status =
      (typeof data.status === 'string' && data.status) ||
      (typeof nested?.status === 'string' && nested.status) ||
      'pending';
    const toolName =
      (typeof data.tool_name === 'string' && data.tool_name) ||
      (typeof nested?.tool_name === 'string' && nested.tool_name) ||
      undefined;
    const question =
      (typeof data.question === 'string' && data.question.trim()) ||
      (typeof nested?.question === 'string' && nested.question.trim()) ||
      undefined;
    const agentId =
      (typeof data.agent_id === 'string' && data.agent_id) ||
      (typeof nested?.agent_id === 'string' && nested.agent_id) ||
      undefined;
    const eligible = Boolean(cid && status === 'pending' && threadAllowed);
    return {
      eligible,
      ...(eligible ? { kind: 'chat_permission' as const } : {}),
      dedupe_key: `perm:${reqId}`,
      ...baseFields,
      ...(agentId ? { agent_id: agentId } : {}),
      ...(toolName ? { tool_name: toolName } : {}),
      ...(question ? { preview_text: formatPreviewText(question, members) } : {}),
    };
  }

  const dedupeKey = `message:${mid || String(frame.event_id ?? '')}`;
  const hasSystemNotice =
    senderType === 'system' ||
    data.system_notice != null ||
    (storedMsg?.system_notice_json != null && storedMsg.system_notice_json !== 'null');
  if (hasSystemNotice || !cid) {
    return { eligible: false, dedupe_key: dedupeKey, ...baseFields };
  }

  const rawAttachments = Array.isArray(data.attachments)
    ? (data.attachments as Array<Record<string, unknown>>)
    : storedMsg?.attachments_json
      ? (JSON.parse(storedMsg.attachments_json) as Array<Record<string, unknown>>)
      : [];
  const attachmentName =
    typeof rawAttachments[0]?.file_name === 'string' && rawAttachments[0].file_name
      ? rawAttachments[0].file_name
      : undefined;
  const hasInteractiveCard = Boolean(data.interactive != null || storedMsg?.interactive_id);
  const rawPermList = Array.isArray(data.permission_requests)
    ? data.permission_requests
    : storedMsg?.permission_request_json
      ? (JSON.parse(storedMsg.permission_request_json) as unknown[])
      : [];
  const hasPermissionCards = rawPermList.length > 0;
  const deliveryStatus =
    (typeof data.delivery_status === 'string' && data.delivery_status) ||
    (typeof frame.delivery_status === 'string' && frame.delivery_status) ||
    storedMsg?.delivery_status ||
    'completed';
  const previewText = formatPreviewText(rawContent, members);

  if (eventType === 'message.completed') {
    if (senderType === 'user' || deliveryStatus === 'failed' || hasPermissionCards || !threadAllowed) {
      return { eligible: false, dedupe_key: dedupeKey, ...baseFields };
    }
    return {
      eligible: true,
      kind: 'message_completed',
      dedupe_key: dedupeKey,
      ...baseFields,
      ...(previewText ? { preview_text: previewText } : {}),
      ...(hasInteractiveCard ? { has_interactive_card: true } : {}),
      ...(attachmentName ? { attachment_name: attachmentName } : {}),
    };
  }

  // `message.created` or legacy `message.sent`
  if (senderType === 'agent') {
    if (deliveryStatus !== 'completed' || hasPermissionCards || !threadAllowed) {
      return { eligible: false, dedupe_key: dedupeKey, ...baseFields };
    }
    return {
      eligible: true,
      kind: 'message_completed',
      dedupe_key: dedupeKey,
      ...baseFields,
      ...(previewText ? { preview_text: previewText } : {}),
      ...(hasInteractiveCard ? { has_interactive_card: true } : {}),
      ...(attachmentName ? { attachment_name: attachmentName } : {}),
    };
  }

  if (senderType === 'user') {
    const senderSourceId =
      (typeof data.sender_source_id === 'string' && data.sender_source_id) ||
      storedMsg?.sender_source_id ||
      null;
    const contextOnly = Boolean(data.context_only === true || storedMsg?.context_only);
    let isSelfAuthored = senderUserId === viewerId;
    if (isSelfAuthored && conv?.external_source) {
      const ownerSourceId = snapshot.externalOwnerByConv.get(cid);
      const isOwnerMirror =
        !senderSourceId ||
        (ownerSourceId !== undefined && senderSourceId === ownerSourceId) ||
        Boolean(storedMsg?.in_owner_direct);
      isSelfAuthored = isOwnerMirror;
    }
    if (isSelfAuthored || contextOnly || !threadAllowed) {
      return { eligible: false, dedupe_key: dedupeKey, ...baseFields };
    }
    const kind: UserNotificationKind = mentionsViewer ? 'mention' : 'human_message';
    return {
      eligible: true,
      kind,
      dedupe_key: dedupeKey,
      ...baseFields,
      ...(previewText ? { preview_text: previewText } : {}),
      ...(hasInteractiveCard ? { has_interactive_card: true } : {}),
      ...(attachmentName ? { attachment_name: attachmentName } : {}),
    };
  }

  return { eligible: false, dedupe_key: dedupeKey, ...baseFields };
}

/** Batch-project per-recipient `notification_hint` directives for a single broadcast frame. */
export function projectBroadcastNotificationHints(
  db: DatabaseSync,
  recipientIds: readonly string[],
  frame: Row,
  options: { isNodeOnline?: (nodeId: string) => boolean } = {},
): Map<string, UserStreamNotificationHint> {
  const out = new Map<string, UserStreamNotificationHint>();
  if (!recipientIds.length || !isNotificationCandidateEventType(frame.event_type)) return out;
  const snapshot = prefetchBatchSnapshot(db, recipientIds, [frame]);
  for (const userId of recipientIds) {
    const hint = projectSingleHint(userId, frame, snapshot, options);
    if (hint) out.set(userId, hint);
  }
  return out;
}

/** Batch-project `notification_hint` directives (`replayed: true`) for a single user's replay window. */
export function projectReplayNotificationHints(
  db: DatabaseSync,
  viewerId: string,
  frames: readonly Row[],
  options: { isNodeOnline?: (nodeId: string) => boolean } = {},
): Array<UserStreamNotificationHint | undefined> {
  if (!frames.length || !frames.some(f => isNotificationCandidateEventType(f.event_type))) {
    return frames.map(() => undefined);
  }
  const snapshot = prefetchBatchSnapshot(db, [viewerId], frames);
  return frames.map(frame =>
    projectSingleHint(viewerId, frame, snapshot, { ...options, replayed: true }),
  );
}
