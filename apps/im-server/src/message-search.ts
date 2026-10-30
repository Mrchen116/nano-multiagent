import type { DatabaseSync } from 'node:sqlite';
import { all, type Row } from './context.js';

/** Query message identities with the shared literal matching and ordering rules. */
export function searchMessages(db: DatabaseSync, options: {
  targets: string[]; terms: string[]; action: string; sort?: string; around?: string;
  messageId?: string; before?: string; after?: string; participantId?: string; senderSourceId?: string;
  cursor?: { created_at: string; id: string }; limit?: number;
}): Row[] {
  if (!options.targets.length) return [];
  const filters = ["m.sender_type IN ('user','agent','system')"], values: unknown[] = [];
  if(options.messageId){filters.push('m.id=?');values.push(options.messageId);}
  if(options.terms.length){filters.push(`(${options.terms.map(() => 'instr(lower(m.content),lower(?))>0').join(' OR ')})`);values.push(...options.terms);}
  if(options.before){filters.push('julianday(m.created_at)<julianday(?)');values.push(options.before);}
  if(options.after){filters.push('julianday(m.created_at)>=julianday(?)');values.push(options.after);}
  if(options.participantId){filters.push("m.sender_user_id=? AND NOT (c.external_source IS NOT NULL AND m.sender_type='user' AND COALESCE(m.sender_source_id,'')!='')");values.push(options.participantId);}
  if(options.senderSourceId){filters.push("c.external_source IS NOT NULL AND m.sender_type='user' AND m.sender_source_id=?");values.push(options.senderSourceId);}
  if(options.cursor){filters.push('(julianday(m.created_at)<julianday(?) OR (julianday(m.created_at)=julianday(?) AND m.id<?))');values.push(options.cursor.created_at,options.cursor.created_at,options.cursor.id);}
  const relevance = options.action === 'search' && (options.sort ?? 'relevance') === 'relevance';
  const order = options.action === 'read' && !options.around ? 'm.rowid DESC' : 'julianday(m.created_at) DESC,m.id DESC';
  return all(db, `SELECT m.id,m.created_at FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.conversation_id IN (${options.targets.map(()=>'?').join(',')}) AND ${filters.join(' AND ')} ORDER BY ${relevance && options.terms.length ? options.terms.map(() => 'CASE WHEN instr(lower(m.content),lower(?))>0 THEN 1 ELSE 0 END').join('+') + ' DESC,' : ''} ${order}${options.limit ? ' LIMIT ?' : ''}`,
    ...options.targets,...values,...(relevance ? options.terms : []),...(options.limit ? [options.limit] : []));
}
