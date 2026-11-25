import type { DatabaseSync } from 'node:sqlite';
type Row=Record<string,any>;

const HISTORY_WINDOW_LIMIT = 20;
const TIMELINE_CONTEXT_LIMIT = 20;

function extractReplyId(message: Row): string | undefined {
  const reply = message.interaction_reply_json ? JSON.parse(message.interaction_reply_json) : undefined;
  const quoted = message.reply_to_json ? JSON.parse(message.reply_to_json) : undefined;
  const replyId = quoted?.message_id ?? reply?.source_message_id;
  return typeof replyId === 'string' && replyId ? replyId : undefined;
}

/** Select source evidence at the original message's stable position, never at review time.
 *
 * Args:
 *   db: Server message store.
 *   messageId: Authenticated binding's source message.
 *   allowed: Current per-message access check, including source exclusions.
 *   evidence: Existing trusted sender and conversation projection.
 * Returns:
 *   Full current message, the previous twenty accessible messages and one direct reply target.
 */
export function personalInputContext(db:DatabaseSync,messageId:string,allowed:(message:Row)=>boolean,evidence:(message:Row)=>Row):Row {
 const current=db.prepare('SELECT rowid AS sequence,* FROM messages WHERE id=?').get(messageId) as Row|undefined;
 if(!current||!allowed(current))throw new Error('Input review source is not accessible');
 const history=db.prepare('SELECT rowid AS sequence,* FROM messages WHERE conversation_id=? AND rowid<? ORDER BY rowid DESC LIMIT 21')
  .all(current.conversation_id,current.sequence) as Row[];
 const omissions:Row[]=[];
 if(history.length>HISTORY_WINDOW_LIMIT)omissions.push({reason:'history_window',limit:HISTORY_WINDOW_LIMIT});
 const previous=history.slice(0,HISTORY_WINDOW_LIMIT).reverse().filter(row=>{
  if(allowed(row))return true;omissions.push({reason:'history_unavailable',message_id:row.id});return false;
 });
 const replyId=extractReplyId(current);
 let replyTarget:Row|undefined;
 if(replyId&&replyId!==current.id&&!previous.some(row=>row.id===replyId)) {
  const row=db.prepare('SELECT rowid AS sequence,* FROM messages WHERE id=?').get(replyId) as Row|undefined;
  if(row&&row.sequence<current.sequence&&allowed(row))replyTarget=evidence(row);
  else omissions.push({reason:'reply_target_unavailable',message_id:replyId});
 }
 return {current:evidence(current),previous:previous.map(evidence),...(replyTarget?{reply_target:replyTarget}:{}),omissions};
}

/** Build bounded timeline evidence for up to twenty pending messages in one conversation.
 *
 * Args:
 *   db: Server message store.
 *   conversationId: Target conversation shared by the pending batch.
 *   messageIds: Pending source message IDs (at most twenty).
 *   sourceAllowed: Current conversation-level access check.
 *   allowed: Current per-message access check.
 *   conversationMeta: Trusted top-level conversation projection.
 *   evidence: Compact message projection preserving sender and decision role.
 * Returns:
 *   Conversation status, isolated unavailable message IDs, shared history, ordered timeline,
 *   deduplicated out-of-window reply targets and explicit omissions.
 */
export function personalInputBatchContext(
  db: DatabaseSync,
  conversationId: string,
  messageIds: unknown,
  sourceAllowed: (conversationId: string) => boolean,
  allowed: (message: Row) => boolean,
  conversationMeta: (chat: Row) => Row,
  evidence: (message: Row, needsDecision?: boolean) => Row,
): Row {
  if (typeof conversationId !== 'string' || !conversationId) throw new Error('Batch input review requires conversation_id');
  if (!Array.isArray(messageIds) || messageIds.length < 1 || messageIds.length > HISTORY_WINDOW_LIMIT || messageIds.some(id => typeof id !== 'string' || !id))
    throw new Error('Batch input review requires between 1 and 20 message IDs');
  const chat = db.prepare('SELECT * FROM conversations WHERE id=?').get(conversationId) as Row | undefined;
  if (!chat || !sourceAllowed(conversationId)) return { source_allowed: false };

  const uniqueIds = [...new Set(messageIds as string[])];
  const unavailable_message_ids: string[] = [];
  const targets: Row[] = [];
  const lookup = db.prepare('SELECT rowid AS sequence,* FROM messages WHERE id=? AND conversation_id=?');
  for (const id of uniqueIds) {
    const row = lookup.get(id, conversationId) as Row | undefined;
    if (!row || !allowed(row)) unavailable_message_ids.push(id);
    else targets.push(row);
  }
  const conversation = conversationMeta(chat);
  if (!targets.length) {
    return { source_allowed: true, unavailable_message_ids, conversation, previous: [], timeline: [], omissions: [] };
  }
  targets.sort((a, b) => a.sequence - b.sequence);
  const first = targets[0]!;
  const last = targets.at(-1)!;
  const targetIds = new Set(targets.map(row => row.id as string));

  const omissions: Row[] = [];
  const history = db.prepare('SELECT rowid AS sequence,* FROM messages WHERE conversation_id=? AND rowid<? ORDER BY rowid DESC LIMIT 21')
    .all(conversationId, first.sequence) as Row[];
  if (history.length > HISTORY_WINDOW_LIMIT) omissions.push({ reason: 'history_window', limit: HISTORY_WINDOW_LIMIT });
  const previousRows = history.slice(0, HISTORY_WINDOW_LIMIT).reverse().filter(row => {
    if (allowed(row)) return true;
    omissions.push({ reason: 'history_unavailable', message_id: row.id });
    return false;
  });

  const span = db.prepare('SELECT rowid AS sequence,* FROM messages WHERE conversation_id=? AND rowid>=? AND rowid<=? ORDER BY rowid ASC')
    .all(conversationId, first.sequence, last.sequence) as Row[];
  const accessibleSpan: Row[] = [];
  const contextCandidates: Row[] = [];
  for (const row of span) {
    if (targetIds.has(row.id)) {
      accessibleSpan.push(row);
      continue;
    }
    if (!allowed(row)) {
      omissions.push({ reason: 'history_unavailable', message_id: row.id });
      continue;
    }
    accessibleSpan.push(row);
    contextCandidates.push(row);
  }
  let droppedContextIds: Set<string> | undefined;
  if (contextCandidates.length > TIMELINE_CONTEXT_LIMIT) {
    omissions.push({ reason: 'timeline_window', limit: TIMELINE_CONTEXT_LIMIT });
    droppedContextIds = new Set(contextCandidates.slice(0, contextCandidates.length - TIMELINE_CONTEXT_LIMIT).map(row => row.id as string));
  }
  const keptSpan = droppedContextIds ? accessibleSpan.filter(row => !droppedContextIds!.has(row.id)) : accessibleSpan;
  const previous = previousRows.map(row => evidence(row));
  const timeline = keptSpan.map(row => evidence(row, targetIds.has(row.id)));

  const includedIds = new Set<string>([...previousRows.map(row => row.id as string), ...keptSpan.map(row => row.id as string)]);
  const seenReplyIds = new Set<string>();
  const replyTargets: Row[] = [];
  const lookupAny = db.prepare('SELECT rowid AS sequence,* FROM messages WHERE id=?');
  for (const target of targets) {
    const replyId = extractReplyId(target);
    if (!replyId || replyId === target.id || includedIds.has(replyId) || seenReplyIds.has(replyId)) continue;
    seenReplyIds.add(replyId);
    const row = lookupAny.get(replyId) as Row | undefined;
    if (row && row.sequence < target.sequence && allowed(row)) {
      replyTargets.push(evidence(row));
      includedIds.add(replyId);
    } else {
      omissions.push({ reason: 'reply_target_unavailable', message_id: replyId });
    }
  }

  return {
    source_allowed: true,
    unavailable_message_ids,
    conversation,
    previous,
    timeline,
    ...(replyTargets.length ? { reply_targets: replyTargets } : {}),
    omissions,
  };
}
