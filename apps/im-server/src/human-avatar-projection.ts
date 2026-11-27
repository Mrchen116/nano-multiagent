import type { DatabaseSync } from "node:sqlite";
import { all, one, type ImContext, type Row } from "./context.js";
import { conversationAccess } from "./conversation-access.js";
import { accountEnabled } from "./identity.js";

const SKIPPED_PROJECTION_KEYS = new Set([
  "reply_to",
  "system_notice",
  "tool_calls",
  "thinking",
  "background_returns",
  "reply_process",
  "permission_requests",
  "interaction_reply",
  "interactive",
  "provenance",
]);

/** Return whether a username belongs to a non-human reserved runtime identity. */
export function isReservedRuntimeUsername(username: unknown): boolean {
  return (
    typeof username === "string" &&
    (username === "system" || username.startsWith("agent:") || username.startsWith("shadow:"))
  );
}

/** Check whether `viewerId` has member or observer read access to a conversation involving `targetId`. */
export function hasSharedReadableConversation(
  db: DatabaseSync,
  viewerId: string,
  targetId: string,
): boolean {
  const rows = all(
    db,
    `SELECT DISTINCT conversation_id FROM (
       SELECT conversation_id FROM conversation_participants WHERE user_id=?
       UNION
       SELECT conversation_id FROM messages WHERE sender_user_id=? AND sender_source_id IS NULL
     )`,
    targetId,
    targetId,
  );
  return rows.some((row) => {
    const access = conversationAccess(db, row.conversation_id, viewerId);
    return Boolean(access && (access.is_member || access.is_observer));
  });
}

/** Evaluate whether an authenticated human viewer may read `target`'s custom avatar bytes. */
export function canReadUserAvatar(db: DatabaseSync, viewer: Row, target: Row | undefined): boolean {
  if (!viewer || isReservedRuntimeUsername(viewer.username)) return false;
  if (!target || isReservedRuntimeUsername(target.username) || !target.avatar_storage_name) return false;
  if (viewer.id === target.id) return true;
  if (!accountEnabled(viewer)) return false;
  if (viewer.membership_status === "active" && target.membership_status === "active") return true;
  if (viewer.membership_status === "active" && Boolean(viewer.is_company_admin) && target.membership_status !== "none") {
    return true;
  }
  return hasSharedReadableConversation(db, viewer.id, target.id);
}

/** Broadcast cursor-free `user.profile_updated` to currently connected human sessions eligible to see `user`. */
export function broadcastUserProfileUpdated(ctx: ImContext, user: Row): void {
  if (!ctx.gateway?.browsers?.size || isReservedRuntimeUsername(user.username)) return;
  const candidateIds = new Set<string>();
  for (const browser of ctx.gateway.browsers) {
    if (browser.ready) candidateIds.add(browser.userId);
  }
  if (!candidateIds.size) return;
  const audience: string[] = [];
  for (const viewerId of candidateIds) {
    if (viewerId === user.id) {
      audience.push(viewerId);
      continue;
    }
    const viewer = one(
      ctx.db,
      "SELECT id,username,membership_status,personal_space_enabled,is_company_admin FROM users WHERE id=?",
      viewerId,
    );
    if (!viewer || isReservedRuntimeUsername(viewer.username) || !accountEnabled(viewer)) continue;
    if (
      (viewer.membership_status === "active" && user.membership_status === "active") ||
      (viewer.membership_status === "active" && Boolean(viewer.is_company_admin) && user.membership_status !== "none") ||
      hasSharedReadableConversation(ctx.db, viewer.id, user.id)
    ) {
      audience.push(viewerId);
    }
  }
  if (!audience.length) return;
  ctx.gateway.broadcast(audience, {
    op: "event",
    event_type: "user.profile_updated",
    data: {
      user_id: user.id,
      display_name: user.display_name,
      avatar_version: user.avatar_version ?? null,
    },
  });
}

function resolveHumanActorId(
  node: Record<string, unknown>,
  parentKey?: string,
  parentNode?: Record<string, unknown>,
): string | null {
  if (node.type !== "user" || typeof node.display_name !== "string") return null;
  if (typeof node.avatar_id === "string" && node.avatar_id.startsWith("external:")) return null;
  if (parentKey === "sender" && parentNode && Boolean((parentNode as { sender_source_id?: unknown }).sender_source_id)) {
    return null;
  }
  const uid =
    typeof node.user_id === "string" && node.user_id
      ? node.user_id
      : typeof node.id === "string" && node.id
        ? node.id
        : null;
  return uid;
}

function collectHumanActorIds(
  value: unknown,
  sink: Set<string>,
  parentKey?: string,
  parentNode?: Record<string, unknown>,
): void {
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    for (const item of value) collectHumanActorIds(item, sink);
    return;
  }
  const record = value as Record<string, unknown>;
  const uid = resolveHumanActorId(record, parentKey, parentNode);
  if (uid) sink.add(uid);
  for (const [key, child] of Object.entries(record)) {
    if (SKIPPED_PROJECTION_KEYS.has(key)) continue;
    collectHumanActorIds(child, sink, key, record);
  }
}

function applyHumanAvatarVersions(
  value: unknown,
  versions: ReadonlyMap<string, string | null>,
  parentKey?: string,
  parentNode?: Record<string, unknown>,
): unknown {
  if (!value || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    let changed = false;
    const mapped = value.map((item) => {
      const next = applyHumanAvatarVersions(item, versions);
      if (next !== item) changed = true;
      return next;
    });
    return changed ? mapped : value;
  }
  const record = value as Record<string, unknown>;
  const uid = resolveHumanActorId(record, parentKey, parentNode);
  const hasVersion = uid !== null && versions.has(uid);
  let childChanged = false;
  const nextEntries: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(record)) {
    if (SKIPPED_PROJECTION_KEYS.has(key)) {
      nextEntries[key] = child;
      continue;
    }
    const nextChild = applyHumanAvatarVersions(child, versions, key, record);
    if (nextChild !== child) childChanged = true;
    nextEntries[key] = nextChild;
  }
  if (!hasVersion && !childChanged) return value;
  if (hasVersion) nextEntries.avatar_version = versions.get(uid!)!;
  return nextEntries;
}

/** Attach `avatar_version` to primary human actor slots on human-facing exits only.
 *
 * Internal message projections, `reply_to` quote references, PA evidence hashes,
 * and Gateway Agent payloads remain untouched.
 *
 * Args:
 *   db: Center SQLite database.
 *   value: Outbound human HTTP or WebSocket response payload.
 * Returns:
 *   Payload with `avatar_version: string | null` populated on primary human actors.
 */
export function attachHumanAvatars<T>(db: DatabaseSync, value: T): T {
  const ids = new Set<string>();
  collectHumanActorIds(value, ids);
  if (!ids.size) return value;
  const idList = [...ids];
  const versions = new Map<string, string | null>();
  for (let offset = 0; offset < idList.length; offset += 200) {
    const chunk = idList.slice(offset, offset + 200);
    const placeholders = chunk.map(() => "?").join(",");
    for (const row of all(
      db,
      `SELECT id, avatar_version FROM users
       WHERE id IN (${placeholders})
         AND username NOT LIKE 'agent:%'
         AND username NOT LIKE 'shadow:%'
         AND username != 'system'`,
      ...chunk,
    )) {
      versions.set(row.id, row.avatar_version ?? null);
    }
  }
  if (!versions.size) return value;
  return applyHumanAvatarVersions(value, versions) as T;
}
