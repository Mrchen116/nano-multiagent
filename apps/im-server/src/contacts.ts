import type { DatabaseSync } from 'node:sqlite';
import { all, type Row } from './context.js';
import { canAccessSpace } from './identity.js';

const batchSize = 100;

function candidates(db: DatabaseSync, where: string, args: string[]): Row[] {
  return all(db, `SELECT u.id AS user_id,u.membership_status AS membership_status,
      CASE WHEN ap.agent_id IS NULL THEN 'human' ELSE 'agent' END AS kind,
      COALESCE(ap.display_name,u.display_name) AS display_name,ap.agent_id,ap.owner_id,ap.space_id,
      owner.display_name AS owner_display_name,COALESCE(NULLIF(n.alias,''),n.node_name) AS node_name,
      COALESCE(n.status,'offline') AS status,ap.work_mode,pb.binding_id,pb.status AS personal_status
    FROM users u
    LEFT JOIN agent_profiles ap ON ap.agent_id=CASE WHEN substr(u.username,1,6)='agent:' THEN substr(u.username,7) END
    LEFT JOIN users owner ON owner.id=ap.owner_id
    LEFT JOIN nodes n ON n.node_id=ap.node_id
    LEFT JOIN personal_agent_bindings pb ON pb.agent_id=ap.agent_id
    WHERE ((u.password_hash IS NOT NULL AND u.password_hash!='' AND ap.agent_id IS NULL)
      OR (ap.agent_id IS NOT NULL AND ap.is_stale=0)) AND ${where}
    ORDER BY u.id LIMIT ${batchSize}`, ...args);
}

function visible(db: DatabaseSync, viewer: Row, rows: Row[]): Row[] {
  const ownerIds = [...new Set(rows.filter(row => row.kind === 'agent').map(row => row.owner_id))];
  const owners = new Map<string, Row>();
  if (ownerIds.length) {
    // Match ownerAccount's first human row, including installations where owner_id differs from id.
    for (const owner of all(db, `SELECT owner_id,membership_status,personal_space_enabled FROM users
      WHERE owner_id IN (${ownerIds.map(() => '?').join(',')})
      AND username NOT LIKE 'agent:%' AND username NOT LIKE 'shadow:%' AND username!='system' ORDER BY rowid`, ...ownerIds)) {
      if (!owners.has(owner.owner_id)) owners.set(owner.owner_id, owner);
    }
  }
  return rows.filter(row => {
    if (row.kind === 'human') return row.user_id === viewer.id || viewer.membership_status === 'active' && row.membership_status === 'active';
    const owner = owners.get(row.owner_id);
    return canAccessSpace(owner, row.space_id) && (canAccessSpace(viewer, row.space_id)
      || viewer.membership_status === 'active' && owner?.membership_status === 'active' && row.personal_status === 'active');
  }).map(row => {
    const {membership_status: _membership, binding_id, personal_status: _personal, ...contact} = row;
    if (row.kind === 'human') return {user_id:row.user_id,kind:row.kind,display_name:row.display_name};
    if (binding_id) return {user_id:row.user_id,kind:row.kind,display_name:row.display_name,agent_id:row.agent_id,
      owner_id:row.owner_id,owner_display_name:row.owner_display_name,role:'personal',status:row.status};
    return contact;
  });
}

/** Read one contact with the same visibility and projection as the directory.
 *
 * Args:
 *   db: IM database.
 *   viewer: Authenticated human account.
 *   id: Contact user ID.
 * Returns:
 *   The visible contact, or undefined for missing/inaccessible identities.
 */
export function contactDetail(db: DatabaseSync, viewer: Row, id: string): Row | undefined {
  return visible(db, viewer, candidates(db, 'u.id=?', [id]))[0];
}

/** Read a cursor page without assembling the complete directory.
 *
 * Args:
 *   db: IM database.
 *   viewer: Authenticated human account.
 *   options: Existing cursor, kind and substring search filters.
 * Returns:
 *   Up to 50 visible contacts and the next cursor, if more matching contacts exist.
 */
export function contactPage(db: DatabaseSync, viewer: Row, options: {cursor?: string; kind?: string; q?: string}): Row {
  const result: Row[] = [], search = options.q?.trim().toLowerCase();
  let cursor = options.cursor;
  while (result.length < 51) {
    const where: string[] = [], args: string[] = [];
    if (cursor) { where.push('u.id>?'); args.push(cursor); }
    if (options.kind) where.push(options.kind === 'human' ? 'ap.agent_id IS NULL' : 'ap.agent_id IS NOT NULL');
    const batch = candidates(db, where.join(' AND ') || '1', args);
    for (const row of visible(db, viewer, batch)) {
      // SQLite lower() is ASCII-only; retain the directory's existing Unicode matching semantics.
      if (search && ![row.display_name,row.user_id,row.agent_id ?? ''].some(value => value.toLowerCase().includes(search))) continue;
      result.push(row);
      if (result.length === 51) break;
    }
    if (batch.length < batchSize) break;
    cursor = batch.at(-1)!.user_id;
  }
  return {items:result.slice(0,50),next_cursor:result.length > 50 ? result[49]!.user_id : null};
}
