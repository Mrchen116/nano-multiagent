import type { DatabaseSync } from 'node:sqlite';
import { all, type Row } from './context.js';

/** Query message identities with the shared literal matching and ordering rules. */
export function searchMessages(db: DatabaseSync, options: {
  targets: string[]; kind?: string; terms: string[]; action: string; sort?: string; around?: string;
  messageId?: string; before?: string; after?: string; participantId?: string; senderSourceId?: string;
  cursor?: { created_at: string; id: string }; limit?: number;
  memoryRange?: { after: string; cutoff: string };
}): Row[] {
  if (!options.targets.length) return [];
  const filters = ["m.sender_type IN ('user','agent','system')"], values: unknown[] = [];
  // Classify target chats before the page limit. Empty groups are ordinary
  // groups; legacy directs use the same exact two-Agent count as chat detail.
  let targets = 'SELECT value FROM json_each(?)';
  const targetParams = [JSON.stringify(options.targets)];
  if (options.kind && options.kind !== 'all') {
    targets = `SELECT t.id FROM conversations t
      LEFT JOIN conversation_participants cp ON cp.conversation_id=t.id
      LEFT JOIN users u ON u.id=cp.user_id
      WHERE t.id IN (${targets}) GROUP BY t.id HAVING CASE
        WHEN t.type='direct' THEN CASE COUNT(u.id) FILTER (WHERE u.username GLOB 'agent:*')
          WHEN 0 THEN 'direct-user' WHEN 2 THEN 'agent-network' ELSE 'direct-agent' END
        WHEN COUNT(u.id)>0 AND COUNT(u.id)=COUNT(u.id) FILTER (WHERE u.username GLOB 'agent:*') THEN 'agent-network'
        ELSE 'group' END = ?`;
    targetParams.push(options.kind);
  }
  if (options.memoryRange) {
    // Dreaming may consume only versions proved to exist at its frozen cutoff.
    // Apply this before ranking and pagination, alongside all other search filters.
    filters.push('julianday(m.created_at)<=julianday(?) AND julianday(m.created_at)>=julianday(?)',
      'NOT EXISTS (SELECT 1 FROM conversation_events e WHERE e.message_id=m.id AND julianday(e.created_at)>julianday(?))',
      "EXISTS (SELECT 1 FROM conversation_events e WHERE e.message_id=m.id AND julianday(e.created_at)<=julianday(?) AND e.delivery_status IN ('completed','failed') AND json_extract(e.payload_json,'$.content')=m.content)");
    values.push(options.memoryRange.cutoff, options.memoryRange.after, options.memoryRange.cutoff, options.memoryRange.cutoff);
  }
  if(options.messageId){filters.push('m.id=?');values.push(options.messageId);}
  const termMatch = '(instr(lower(m.content),lower(?))>0 OR instr(lower(i.search_text),lower(?))>0)';
  const termArgs = options.terms.flatMap(term => [term, term]);
  if (termArgs.length) {
    filters.push(`(${options.terms.map(() => termMatch).join(' OR ')})`);
    values.push(...termArgs);
  }
  if(options.before){filters.push('julianday(m.created_at)<julianday(?)');values.push(options.before);}
  if(options.after){filters.push('julianday(m.created_at)>=julianday(?)');values.push(options.after);}
  if(options.participantId){filters.push("m.sender_user_id=? AND NOT (c.external_source IS NOT NULL AND m.sender_type='user' AND COALESCE(m.sender_source_id,'')!='')");values.push(options.participantId);}
  if(options.senderSourceId){filters.push("c.external_source IS NOT NULL AND m.sender_type='user' AND m.sender_source_id=?");values.push(options.senderSourceId);}
  if(options.cursor){filters.push('(julianday(m.created_at)<julianday(?) OR (julianday(m.created_at)=julianday(?) AND m.id<?))');values.push(options.cursor.created_at,options.cursor.created_at,options.cursor.id);}
  const relevance = options.action === 'search' && (options.sort ?? 'relevance') === 'relevance';
  const order = options.action === 'read' && !options.around ? 'm.rowid DESC' : 'julianday(m.created_at) DESC,m.id DESC';
  const cardText = termArgs.length ? ',i.search_text AS interactive_search_text' : '';
  const cardJoin = termArgs.length ? ' LEFT JOIN message_interactive i ON i.message_id=m.id' : '';
  const rank = relevance && termArgs.length ? options.terms.map(() => `CASE WHEN ${termMatch} THEN 1 ELSE 0 END`).join('+') + ' DESC,' : '';
  return all(db, `SELECT m.id,m.created_at,m.sender_source_id,m.sender_display_name${cardText} FROM messages m JOIN conversations c ON c.id=m.conversation_id${cardJoin}
    WHERE m.conversation_id IN (${targets}) AND ${filters.join(' AND ')} ORDER BY ${rank} ${order}${options.limit ? ' LIMIT ?' : ''}`,
    ...targetParams,...values,...(relevance ? termArgs : []),...(options.limit ? [options.limit] : []));
}
