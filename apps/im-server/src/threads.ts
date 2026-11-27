import type { DatabaseSync } from 'node:sqlite';
import { all, fail, now, one } from './context.js';
import { isOwnerInternalConversation } from './collaboration.js';

const EXCERPT_LIMIT = 1200;
const EARLIER_REPLY_LIMIT = 10;

/** Only eligible group followers may receive or wake on a topic message. */
export function threadAddressesAgent(db: DatabaseSync, messageId: string, agentId: string): boolean {
  return !!one(db, `SELECT 1 FROM messages m JOIN conversations c ON c.id=m.conversation_id
    WHERE m.id=? AND (m.thread_root_id IS NULL OR c.type!='group' OR EXISTS (
      SELECT 1 FROM thread_follows f JOIN users u ON u.id=f.user_id
      WHERE f.root_message_id=m.thread_root_id AND f.following=1 AND u.username=?))`, messageId, 'agent:'+agentId);
}

/** Freeze the audience when a reply arrives, including newly named recipients of completed streamed text. */
export function recordThreadDelivery(db: DatabaseSync, messageId: string): void {
  const m = one(db, `SELECT m.*, root.sender_user_id AS root_author FROM messages m
    JOIN messages root ON root.id=m.thread_root_id JOIN conversations c ON c.id=m.conversation_id
    WHERE m.id=? AND c.type='group'`, messageId);
  if (!m) return;
  const named = new Set<string>([m.sender_user_id]);
  for (const match of m.content.matchAll(/<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g)) named.add(match[1]);
  const quoted = JSON.parse(m.reply_to_json ?? 'null')?.sender;
  if (quoted?.user_id) named.add(quoted.user_id);
  else if (quoted?.type==='user') named.add(quoted.id);
  else if (quoted?.type==='agent') {
    const user=one(db,'SELECT id FROM users WHERE username=?','agent:'+quoted.id);
    if(user)named.add(user.id);
  }
  const at = now();
  // A root author follows by default only once. Their explicit unfollow survives later replies
  // unless explicitly re-mentioned or quoted, which reactivates follow and records the trigger message.
  const add = db.prepare(`INSERT INTO thread_follows(conversation_id,root_message_id,user_id,following,followed_at)
    SELECT ?,?,u.id,1,? FROM users u LEFT JOIN agent_profiles a ON u.username='agent:'||a.agent_id
    WHERE u.id=? AND (
      EXISTS (SELECT 1 FROM conversation_participants p WHERE p.conversation_id=? AND p.user_id=u.id)
      OR EXISTS (SELECT 1 FROM personal_agent_bindings b JOIN conversation_participants p ON p.user_id=b.owner_user_id
        WHERE b.agent_id=a.agent_id AND b.status='active' AND p.conversation_id=?))
    ON CONFLICT(conversation_id,root_message_id,user_id) DO UPDATE SET
      reactivated_by_message_id=CASE WHEN thread_follows.following=0 AND ? THEN ? ELSE thread_follows.reactivated_by_message_id END,
      followed_at=CASE WHEN thread_follows.following=0 AND ? THEN excluded.followed_at ELSE coalesce(thread_follows.followed_at, excluded.followed_at) END,
      following=CASE WHEN ? THEN 1 ELSE thread_follows.following END`);
  for (const id of new Set([m.root_author, ...named])) {
    const targetUser = one(db, 'SELECT u.id,u.username,a.agent_id,a.owner_id,a.collaboration_scope FROM users u LEFT JOIN agent_profiles a ON u.username=\'agent:\'||a.agent_id WHERE u.id=?', id);
    if (targetUser?.agent_id && (targetUser.collaboration_scope ?? 'team') === 'owner_only') {
      const isPaObserver = !!one(db, 'SELECT 1 FROM personal_agent_bindings b JOIN conversation_participants p ON p.user_id=b.owner_user_id WHERE b.agent_id=? AND b.status=\'active\' AND p.conversation_id=?', targetUser.agent_id, m.conversation_id);
      if (!isOwnerInternalConversation(db, m.conversation_id, targetUser.owner_id) && !isPaObserver) continue;
    }
    const reactivate = named.has(id) ? 1 : 0;
    add.run(m.conversation_id, m.thread_root_id, at, id, m.conversation_id, m.conversation_id, reactivate, messageId, reactivate, reactivate);
  }
  const added=all(db,`INSERT OR IGNORE INTO thread_deliveries(message_id,user_id)
    SELECT ?,f.user_id FROM thread_follows f JOIN conversation_participants p
      ON p.conversation_id=f.conversation_id AND p.user_id=f.user_id
    WHERE f.root_message_id=? AND f.following=1 AND f.user_id!=? RETURNING user_id`, messageId,m.thread_root_id,m.sender_user_id);
  for(const {user_id} of added) adjustUnread(db,m.conversation_id,m.thread_root_id,user_id,1);
}

function adjustUnread(db:DatabaseSync,cid:string,root:string,userId:string,delta:number):void {
  db.prepare('UPDATE thread_follows SET unread_count=max(0,unread_count+?) WHERE conversation_id=? AND root_message_id=? AND user_id=?').run(delta,cid,root,userId);
  db.prepare('UPDATE conversation_participants SET unread_count=max(0,unread_count+?) WHERE conversation_id=? AND user_id=?').run(delta,cid,userId);
}

/** Undo only outstanding deliveries of a discarded provisional topic bubble. */
export function discardThreadUnread(db:DatabaseSync,cid:string,root:string,id:string):void {
  for(const row of all(db,'SELECT user_id FROM thread_deliveries WHERE message_id=? AND unread=1',id))
    adjustUnread(db,cid,root,row.user_id,-1);
}

/** Compute unread after a main-timeline watermark. Direct chats share one watermark. */
export function listUnread(db: DatabaseSync, conversationId: string, userId: string, mainWatermark: number): number {
  const grouped = one(db, 'SELECT type FROM conversations WHERE id=?', conversationId)?.type === 'group';
  const main = one(db, `SELECT count(*) AS n FROM messages WHERE conversation_id=? AND rowid>? AND sender_user_id!=?${grouped ? ' AND thread_root_id IS NULL' : ''}`, conversationId, mainWatermark, userId)!.n;
  const topics = grouped ? one(db, 'SELECT sum(unread_count) AS n FROM thread_follows WHERE conversation_id=? AND user_id=?', conversationId,userId)?.n : 0;
  return main+(topics??0);
}

/** Acknowledge rendered replies through the supplied message, leaving newer arrivals untouched. */
export function markThreadRead(db: DatabaseSync, cid:string, root:string, userId:string, id:string, rowid:number):void {
  const seen=db.prepare(`UPDATE thread_deliveries SET unread=0 WHERE user_id=? AND unread=1 AND message_id IN
    (SELECT id FROM messages WHERE thread_root_id=? AND rowid<=?)`).run(userId,root,rowid).changes;
  if(seen) adjustUnread(db,cid,root,userId,-Number(seen));
  db.prepare(`UPDATE thread_follows SET last_read_message_id=? WHERE root_message_id=? AND user_id=?
    AND coalesce((SELECT rowid FROM messages WHERE id=last_read_message_id),0)<?`).run(id,root,userId,rowid);
}

function excerpt(value: unknown, limit = EXCERPT_LIMIT): { text: string; truncated: boolean } {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim();
  return text.length > limit ? { text: `${text.slice(0, limit - 1)}…`, truncated: true } : { text, truncated: false };
}

/** Root and bounded recent replies for first-sight or reactivated thread delivery. */
export function threadRelayMetadata(db: DatabaseSync, messageId: string, agentId?: string): Record<string, unknown> {
  const message = one(db, 'SELECT thread_root_id, conversation_id, rowid FROM messages WHERE id=?', messageId);
  if (!message?.thread_root_id) return {};
  const root = one(db, "SELECT coalesce(nullif(m.sender_display_name,''),u.display_name,m.sender_user_id) AS name,m.content FROM messages m JOIN users u ON u.id=m.sender_user_id WHERE m.id=?", message.thread_root_id);
  const rawEarlier = all(db, `SELECT m.id,coalesce(nullif(m.sender_display_name,''),u.display_name,m.sender_user_id) AS name,m.content FROM messages m
    JOIN users u ON u.id=m.sender_user_id WHERE m.conversation_id=? AND m.thread_root_id=? AND m.rowid<?
      AND coalesce(json_extract(m.system_notice_json,'$.kind'),'')!='thread_unfollowed'
    ORDER BY m.rowid DESC LIMIT ?`,
    message.conversation_id, message.thread_root_id, message.rowid, EARLIER_REPLY_LIMIT + 1);
  const hasOlderReplies = rawEarlier.length > EARLIER_REPLY_LIMIT;
  const earlierRows = (hasOlderReplies ? rawEarlier.slice(0, EARLIER_REPLY_LIMIT) : rawEarlier).reverse();
  const rootExcerpt = excerpt(root?.content);
  let truncated = hasOlderReplies || rootExcerpt.truncated;
  const earlier = earlierRows.map(row => {
    const item = excerpt(row.content);
    if (item.truncated) truncated = true;
    return { id: row.id, sender: row.name, excerpt: item.text };
  });
  const reactivated = agentId ? !!one(db, `SELECT 1 FROM thread_follows f JOIN users u ON u.id=f.user_id
    WHERE f.conversation_id=? AND f.root_message_id=? AND u.username=? AND f.reactivated_by_message_id=?`,
    message.conversation_id, message.thread_root_id, 'agent:' + agentId, messageId) : false;
  return {
    thread_root_message_id: message.thread_root_id,
    thread_root_sender: root?.name ?? '',
    thread_root_excerpt: rootExcerpt.text,
    thread_earlier: earlier,
    thread_history_truncated: truncated,
    ...(reactivated ? { thread_follow_reactivated: true } : {}),
  };
}

/** List threads currently followed by an Agent across accessible conversations. */
export function listAgentFollowedThreads(db: DatabaseSync, agentUserId: string, conversationIds: readonly string[]) {
  if (!conversationIds.length) return [];
  const rows = all(db, `SELECT f.conversation_id, f.root_message_id, f.followed_at,
      root.content AS root_content, root.created_at AS root_created_at,
      coalesce(nullif(root.sender_display_name,''), ru.display_name, root.sender_user_id) AS root_sender,
      (SELECT count(*) FROM messages r WHERE r.thread_root_id=f.root_message_id
        AND coalesce(json_extract(r.system_notice_json,'$.kind'),'')!='thread_unfollowed') AS reply_count,
      (SELECT max(r.created_at) FROM messages r WHERE r.thread_root_id=f.root_message_id
        AND coalesce(json_extract(r.system_notice_json,'$.kind'),'')!='thread_unfollowed') AS latest_reply_at
    FROM thread_follows f
    JOIN messages root ON root.id=f.root_message_id AND root.conversation_id=f.conversation_id
    LEFT JOIN users ru ON ru.id=root.sender_user_id
    WHERE f.user_id=? AND f.following=1 AND f.conversation_id IN (SELECT value FROM json_each(?))
    ORDER BY coalesce(latest_reply_at, root.created_at) DESC, f.root_message_id DESC`,
    agentUserId, JSON.stringify(conversationIds));
  return rows.map(row => ({
    target: `${row.conversation_id}:${row.root_message_id}`,
    parent_target: String(row.conversation_id),
    root_message_id: String(row.root_message_id),
    root_sender: String(row.root_sender ?? ''),
    root_excerpt: excerpt(row.root_content, 200).text,
    reply_count: Number(row.reply_count ?? 0),
    latest_at: String(row.latest_reply_at ?? row.root_created_at),
    followed_at: String(row.followed_at ?? row.root_created_at),
  }));
}

/** Update an Agent's follow state for one thread; unfollowing a direct-chat thread is rejected. */
export function setAgentThreadFollow(
  db: DatabaseSync,
  conversationId: string,
  rootMessageId: string,
  agentUserId: string,
  following: boolean,
): { target: string; following: boolean; changed: boolean } {
  const rootId = threadRootOrFail(db, conversationId, rootMessageId)!;
  const chat = one(db, 'SELECT type FROM conversations WHERE id=?', conversationId);
  if (!chat) fail(404, 'target_not_accessible');
  if (!following && chat.type === 'direct') fail(422, 'direct_chat_thread_unfollow_not_supported');
  const target = `${conversationId}:${rootId}`;
  if (chat.type === 'direct') return { target, following: true, changed: false };
  const existing = one(db, 'SELECT following FROM thread_follows WHERE conversation_id=? AND root_message_id=? AND user_id=?', conversationId, rootId, agentUserId);
  const wasFollowing = existing?.following === 1;
  const at = now();
  if (following) {
    db.prepare(`INSERT INTO thread_follows(conversation_id,root_message_id,user_id,following,followed_at,reactivated_by_message_id)
      VALUES(?,?,?,1,?,NULL)
      ON CONFLICT(conversation_id,root_message_id,user_id) DO UPDATE SET
        following=1, followed_at=CASE WHEN thread_follows.following=0 THEN excluded.followed_at ELSE coalesce(thread_follows.followed_at, excluded.followed_at) END,
        reactivated_by_message_id=NULL`).run(conversationId, rootId, agentUserId, at);
    return { target, following: true, changed: !wasFollowing };
  }
  db.prepare(`INSERT INTO thread_follows(conversation_id,root_message_id,user_id,following,followed_at,reactivated_by_message_id)
    VALUES(?,?,?,0,NULL,NULL)
    ON CONFLICT(conversation_id,root_message_id,user_id) DO UPDATE SET following=0, reactivated_by_message_id=NULL`).run(conversationId, rootId, agentUserId);
  return { target, following: false, changed: wasFollowing };
}

/** A quote inside a topic may name the root or one reply in that same topic. */
export function assertThreadQuote(db: DatabaseSync, conversationId: string, threadRoot: string | undefined, replyToId: string | undefined): void {
  if (!threadRoot || !replyToId || replyToId === threadRoot) return;
  const quoted = one(db, 'SELECT conversation_id, thread_root_id FROM messages WHERE id=?', replyToId);
  if (!quoted || quoted.conversation_id !== conversationId || quoted.thread_root_id !== threadRoot)
    fail(422, 'reply target is outside this thread');
}

export function threadRootOrFail(db: DatabaseSync, conversationId: string, rootId: string | undefined): string | undefined {
  if (rootId === undefined) return;
  if (!rootId) fail(422, 'invalid thread root');
  const chat = one(db, 'SELECT external_source FROM conversations WHERE id=?', conversationId);
  if (chat?.external_source) fail(422, 'threads are not available in external chats');
  const root = one(db, 'SELECT * FROM messages WHERE id=? AND conversation_id=?', rootId, conversationId);
  if (!root) fail(404, 'thread root not found');
  if (root.thread_root_id || !['user','agent'].includes(root.sender_type) || !['completed','sent','pending'].includes(root.delivery_status))
    fail(422, 'thread root is not available');
  return rootId;
}
