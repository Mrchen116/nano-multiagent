import type { DatabaseSync } from 'node:sqlite';
import { all, fail, one } from './context.js';

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
  // A root author follows by default only once. Their explicit unfollow survives later replies.
  const add = db.prepare(`INSERT INTO thread_follows(conversation_id,root_message_id,user_id,following)
    SELECT ?,?,u.id,1 FROM users u LEFT JOIN agent_profiles a ON u.username='agent:'||a.agent_id
    WHERE u.id=? AND coalesce(a.collaboration_scope,'team')='team' AND (
      EXISTS (SELECT 1 FROM conversation_participants p WHERE p.conversation_id=? AND p.user_id=u.id)
      OR EXISTS (SELECT 1 FROM personal_agent_bindings b JOIN conversation_participants p ON p.user_id=b.owner_user_id
        WHERE b.agent_id=a.agent_id AND b.status='active' AND p.conversation_id=?))
    ON CONFLICT(conversation_id,root_message_id,user_id) DO UPDATE SET following=1 WHERE ?`);
  for(const id of new Set([m.root_author,...named])) add.run(m.conversation_id,m.thread_root_id,id,m.conversation_id,m.conversation_id,named.has(id)?1:0);
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
