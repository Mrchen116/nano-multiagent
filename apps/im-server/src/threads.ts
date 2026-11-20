import type { DatabaseSync } from 'node:sqlite';
import { all, fail, one } from './context.js';

/** A group thread reaches an Agent only when that Agent follows it or is named by this message. */
export function threadAddressesAgent(db: DatabaseSync, messageId: string, agentId: string): boolean {
  const message = one(db, 'SELECT thread_root_id, content, reply_to_json, conversation_id FROM messages WHERE id=?', messageId);
  if (!message?.thread_root_id) return true;
  const chat = one(db, 'SELECT type, external_source FROM conversations WHERE id=?', message.conversation_id);
  if (chat?.type !== 'group') return true;
  const user = one(db, "SELECT id FROM users WHERE username=?", `agent:${agentId}`);
  const followed = user && one(db, 'SELECT 1 FROM thread_follows WHERE conversation_id=? AND root_message_id=? AND user_id=? AND following=1', message.conversation_id, message.thread_root_id, user.id);
  const mentioned = user && String(message.content).includes(user.id);
  const quoted = JSON.parse(message.reply_to_json ?? 'null')?.sender?.id === agentId;
  return !!(followed || mentioned || quoted);
}

/** Record who should hear this thread reply. Direct chats do not filter on this table. */
export function recordThreadFollows(db: DatabaseSync, messageId: string): void {
  const message = one(db, 'SELECT * FROM messages WHERE id=?', messageId);
  if (!message?.thread_root_id) return;
  const chat = one(db, 'SELECT type FROM conversations WHERE id=?', message.conversation_id);
  if (chat?.type !== 'group') return;
  const root = one(db, 'SELECT sender_user_id FROM messages WHERE id=?', message.thread_root_id);
  const ids = new Set<string>([message.sender_user_id, root?.sender_user_id].filter(Boolean));
  for (const match of String(message.content).matchAll(/<mention\s+type="user"\s+target_id="([^"]+)"/g)) ids.add(match[1]);
  const quoted = JSON.parse(message.reply_to_json ?? 'null')?.sender;
  if (quoted?.type === 'agent') {
    const user = one(db, "SELECT id FROM users WHERE username=?", `agent:${quoted.id}`);
    if (user) ids.add(user.id);
  } else if (quoted?.id) ids.add(quoted.id);
  for (const userId of ids) {
    const agent = one(db, "SELECT a.collaboration_scope FROM agent_profiles a JOIN users u ON u.username='agent:'||a.agent_id WHERE u.id=?", userId);
    if (agent?.collaboration_scope === 'owner_only') continue;
    db.prepare(`INSERT INTO thread_follows(conversation_id,root_message_id,user_id,following,unread_count)
      VALUES(?,?,?,1,0) ON CONFLICT(conversation_id,root_message_id,user_id) DO UPDATE SET following=1`).run(message.conversation_id, message.thread_root_id, userId);
  }
}

/** Group thread unread lives beside the main-timeline watermark. */
export function bumpThreadUnread(db: DatabaseSync, messageId: string): void {
  const message = one(db, 'SELECT conversation_id, thread_root_id, sender_user_id FROM messages WHERE id=?', messageId);
  if (!message?.thread_root_id) return;
  if (one(db, 'SELECT type FROM conversations WHERE id=?', message.conversation_id)?.type !== 'group') return;
  const followers = all(db, 'SELECT user_id FROM thread_follows WHERE conversation_id=? AND root_message_id=? AND following=1 AND user_id!=?', message.conversation_id, message.thread_root_id, message.sender_user_id) as {user_id:string}[];
  for (const follower of followers) {
    db.prepare('UPDATE thread_follows SET unread_count=unread_count+1 WHERE conversation_id=? AND root_message_id=? AND user_id=?').run(message.conversation_id, message.thread_root_id, follower.user_id);
    db.prepare('UPDATE conversation_participants SET unread_count=unread_count+1 WHERE conversation_id=? AND user_id=?').run(message.conversation_id, follower.user_id);
  }
}

/** Recompute list unread without letting a main-timeline read erase unseen group threads.
 * Direct chats keep topic replies on the same watermark as ordinary messages.
 */
export function listUnread(db: DatabaseSync, conversationId: string, userId: string, mainWatermark: number | null): number {
  const grouped = one(db, 'SELECT type FROM conversations WHERE id=?', conversationId)?.type === 'group';
  const main = mainWatermark === null
    ? (one(db, 'SELECT unread_count AS count FROM conversation_participants WHERE conversation_id=? AND user_id=?', conversationId, userId)?.count ?? 0)
    : (one(db, `SELECT COUNT(*) AS count FROM messages WHERE conversation_id=? AND rowid>? AND sender_user_id!=?${grouped ? ' AND thread_root_id IS NULL' : ''}`, conversationId, mainWatermark, userId) as {count:number}).count;
  const threads = grouped
    ? (one(db, 'SELECT coalesce(sum(unread_count),0) AS count FROM thread_follows WHERE conversation_id=? AND user_id=? AND following=1', conversationId, userId) as {count:number}).count
    : 0;
  return Number(main) + Number(threads);
}

/** Opening one topic marks that follower caught up, without touching other topics.
 * Returns how many topic unreads were cleared so a missing watermark can subtract them.
 */
export function markThreadRead(db: DatabaseSync, conversationId: string, rootId: string, userId: string): number {
  const current = one(db, 'SELECT unread_count FROM thread_follows WHERE conversation_id=? AND root_message_id=? AND user_id=? AND following=1', conversationId, rootId, userId) as {unread_count?: number} | undefined;
  const latest = one(db, 'SELECT id FROM messages WHERE conversation_id=? AND thread_root_id=? ORDER BY rowid DESC LIMIT 1', conversationId, rootId);
  db.prepare('UPDATE thread_follows SET unread_count=0, last_read_message_id=? WHERE conversation_id=? AND root_message_id=? AND user_id=? AND following=1')
    .run(latest?.id ?? null, conversationId, rootId, userId);
  db.prepare(`UPDATE message_receipts SET status=2 WHERE recipient_id=? AND status<2 AND message_id IN
    (SELECT id FROM messages WHERE conversation_id=? AND thread_root_id=?)`).run(userId, conversationId, rootId);
  return Number(current?.unread_count ?? 0);
}

function excerpt(value: unknown): string {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim();
  return text.length > 1200 ? `${text.slice(0, 1199)}…` : text;
}

/** Root and the previous replies the model should see with this thread message. */
export function threadRelayMetadata(db: DatabaseSync, messageId: string): Record<string, unknown> {
  const message = one(db, 'SELECT thread_root_id, conversation_id, rowid FROM messages WHERE id=?', messageId);
  if (!message?.thread_root_id) return {};
  const root = one(db, 'SELECT sender_display_name, sender_user_id, content FROM messages WHERE id=?', message.thread_root_id);
  const earlier = all(db, `SELECT id, sender_display_name, sender_user_id, content FROM messages
    WHERE conversation_id=? AND thread_root_id=? AND rowid<? ORDER BY rowid DESC LIMIT 20`,
    message.conversation_id, message.thread_root_id, message.rowid).reverse();
  return {
    thread_root_message_id: message.thread_root_id,
    thread_root_sender: root?.sender_display_name || root?.sender_user_id || '',
    thread_root_excerpt: excerpt(root?.content),
    thread_earlier: earlier.map(row => ({id: row.id, sender: row.sender_display_name || row.sender_user_id, excerpt: excerpt(row.content)})),
  };
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
