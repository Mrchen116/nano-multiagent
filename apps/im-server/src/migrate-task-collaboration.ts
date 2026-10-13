import { DatabaseSync, backup } from 'node:sqlite';
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { canonicalJson, validateDocument } from './task-graphs.js';
import { all, one, transaction, type Row } from './context.js';
import { qualifiedUser } from './conversation-access.js';

function fingerprint(db:DatabaseSync): string {
  return createHash('sha256').update(canonicalJson({
    graphs:all(db,'SELECT graph_id,document_json FROM task_graphs ORDER BY graph_id'),
    conversations:all(db,'SELECT * FROM conversations ORDER BY id'),
    members:all(db,'SELECT * FROM conversation_participants ORDER BY conversation_id,user_id'),
    receipts:all(db,'SELECT * FROM task_graph_mutation_receipts ORDER BY actor_key,request_key'),
  })).digest('hex');
}
function ref(db:DatabaseSync,value:any): Row {
  if (!value || !['user','agent'].includes(value.type) || typeof value.id !== 'string') throw Error('Each creator/assignee needs a verified type and id');
  const user = one(db,'SELECT * FROM users WHERE '+(value.type==='agent'?'username=?':'id=?'),value.type==='agent'?`agent:${value.id}`:value.id);
  if (!user || (value.type==='user' && user.username.startsWith('agent:'))) throw Error(`Unknown identity: ${value.type}:${value.id}`);
  return {type:value.type,id:value.id};
}
function columns(db:DatabaseSync,table:string):string[] {return all(db,`PRAGMA table_info(${table})`).map(r=>r.name);}
function current(db:DatabaseSync) {return columns(db,'task_graphs').includes('conversation_id') && columns(db,'conversations').includes('visibility') && columns(db,'conversations').includes('dissolved_at') && columns(db,'task_graph_mutation_receipts').includes('conversation_id');}
function plan(db:DatabaseSync,mapping:Row):Row[] {
  if (mapping.fingerprint !== fingerprint(db)) throw Error('Database changed since dry-run; rebuild and review the mapping');
  return all(db,'SELECT * FROM task_graphs ORDER BY graph_id').map(row=>{
    const d=JSON.parse(row.document_json), m=mapping.graphs?.[row.graph_id];
    if (d.schema_version!==1) throw Error('Only pre-v2 documents may be migrated');
    if (!m?.evidence?.trim() || !one(db,'SELECT id FROM conversations WHERE id=?',m.conversation_id)) throw Error(`Missing supported conversation mapping: ${row.graph_id}`);
    d.schema_version=2;d.conversation_id=m.conversation_id;
    for (const n of d.nodes) {
      const entry=m.nodes?.[n.id];
      if (!entry?.evidence?.trim()) throw Error(`Missing creator evidence: ${row.graph_id}/${n.id}`);
      n.created_by=ref(db,entry.created_by);
      n.assignee=entry.assignee==null?null:ref(db,entry.assignee);
      if (n.assignee) {
        const u=one(db,'SELECT * FROM users WHERE '+(n.assignee.type==='agent'?'username=?':'id=?'),n.assignee.type==='agent'?`agent:${n.assignee.id}`:n.assignee.id)!;
        if (!qualifiedUser(db,u.id) || !one(db,'SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?',m.conversation_id,u.id)) throw Error('Assigned actors must already be active members');
      }
      if(n.status==='dropped') n.status='closed';
      // Preserve historical updated_by text; never infer a historical creator from it.
    }
    validateDocument(d);
    return {...row,conversation_id:m.conversation_id,document_json:JSON.stringify(d)};
  });
}
function receiptConversation(db:DatabaseSync,row:Row,mapping:Row):string {
  const id=mapping.graphs?.[row.graph_id]?.conversation_id ?? mapping.deleted_graphs?.[row.graph_id]?.conversation_id;
  if (!id || !one(db,'SELECT 1 FROM conversations WHERE id=?',id)) throw Error(`Missing receipt conversation: ${row.graph_id}`);
  if (!mapping.graphs?.[row.graph_id] && !mapping.deleted_graphs?.[row.graph_id]?.evidence?.trim()) throw Error(`Missing deleted graph evidence: ${row.graph_id}`);
  return id;
}
/** Inspect without guessing missing historical identities or mutating the database. */
export function inspectMigration(db:DatabaseSync):Row {
  if(current(db)) return {state:'already_migrated',graphs:all(db,'SELECT graph_id FROM task_graphs').length};
  return {state:'requires_mapping',fingerprint:fingerprint(db),graphs:Object.fromEntries(all(db,'SELECT * FROM task_graphs').map(row=>{
    const d=JSON.parse(row.document_json);
    return [row.graph_id,{conversation_id:null,evidence:'',nodes:Object.fromEntries(d.nodes.map((n:Row)=>[n.id,{created_by:null,assignee:null,evidence:''}]))}];
  })),deleted_graphs:Object.fromEntries(all(db,'SELECT DISTINCT graph_id FROM task_graph_mutation_receipts WHERE graph_id NOT IN (SELECT graph_id FROM task_graphs)').map(r=>[r.graph_id,{conversation_id:null,evidence:''}]))};
}
/** Apply an explicitly evidenced mapping once, with a consistent pre-change backup. */
export async function applyMigration(db:DatabaseSync,mapping:Row,backupPath:string):Promise<Row> {
  if(current(db)) throw Error('Already migrated; refusing to overwrite v2 progress');
  if(existsSync(backupPath)) throw Error('Backup already exists; choose a new path');
  plan(db,mapping);
  for(const row of all(db,'SELECT * FROM task_graph_mutation_receipts')) receiptConversation(db,row,mapping);
  await backup(db,backupPath);
  return transaction(db,()=>{
    const rows=plan(db,mapping);
    db.exec("ALTER TABLE conversations ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('public','private')); ALTER TABLE conversations ADD COLUMN dissolved_at TEXT; ALTER TABLE task_graphs ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ''; ALTER TABLE task_graph_mutation_receipts ADD COLUMN conversation_id TEXT NOT NULL DEFAULT '';");
    for(const r of rows) db.prepare('UPDATE task_graphs SET conversation_id=?,document_json=? WHERE graph_id=?').run(r.conversation_id,r.document_json,r.graph_id);
    for(const r of all(db,'SELECT * FROM task_graph_mutation_receipts')) db.prepare('UPDATE task_graph_mutation_receipts SET conversation_id=? WHERE actor_key=? AND request_key=?').run(receiptConversation(db,r,mapping),r.actor_key,r.request_key);
    return {state:'migrated',graphs:rows.length,nodes:rows.reduce((n,r)=>n+JSON.parse(r.document_json).nodes.length,0),backup:backupPath};
  });
}
/** Compare preserved history and structure against the actual pre-migration database. */
export function verifyMigration(db:DatabaseSync,before:DatabaseSync):Row {
  if(!current(db)) throw Error('Schema migration is incomplete');
  const prior=all(before,'SELECT * FROM task_graphs ORDER BY graph_id'), after=all(db,'SELECT * FROM task_graphs ORDER BY graph_id');
  if(prior.length!==after.length) throw Error('Graph count changed');
  for(const [i,row] of prior.entries()) {
    const a=JSON.parse(after[i]!.document_json), b=JSON.parse(row.document_json);
    validateDocument(a);
    if(!one(db,'SELECT 1 FROM conversations WHERE id=?',after[i]!.conversation_id)) throw Error('Missing fixed conversation');
    const original=structuredClone(a);delete original.conversation_id;original.schema_version=1;
    for(const n of original.nodes) {delete n.created_by;delete n.assignee;if(n.status==='closed') n.status='dropped';}
    if(canonicalJson(original)!==canonicalJson(b)) throw Error(`Preserved graph facts changed: ${row.graph_id}`);
    const metadata={...after[i]};delete metadata.conversation_id;metadata.document_json=row.document_json;
    if(canonicalJson(metadata)!==canonicalJson(row)) throw Error(`Graph metadata changed: ${row.graph_id}`);
  }
  for(const table of ['messages','conversation_participants','task_node_chat_activity','relay_tasks']) {
    if(canonicalJson(all(db,`SELECT * FROM ${table} ORDER BY rowid`))!==canonicalJson(all(before,`SELECT * FROM ${table} ORDER BY rowid`))) throw Error(`History changed: ${table}`);
  }
  for(const c of all(db,'SELECT * FROM conversations')) if(c.visibility!=='private' || c.dissolved_at) throw Error('Old conversations must remain private and undissolved');
  for(const [table,added] of [['conversations',['visibility','dissolved_at']],['task_graph_mutation_receipts',['conversation_id']]] as const) {
    const restored=all(db,`SELECT * FROM ${table} ORDER BY rowid`).map(row=>{for(const key of added) delete row[key];return row;});
    if(canonicalJson(restored)!==canonicalJson(all(before,`SELECT * FROM ${table} ORDER BY rowid`))) throw Error(`Preserved facts changed: ${table}`);
  }
  return {state:'verified',graphs:after.length,nodes:after.reduce((n,r)=>n+JSON.parse(r.document_json).nodes.length,0),messages:one(db,'SELECT COUNT(*) n FROM messages')!.n};
}
async function main() {
  const [action,database,mappingOrBackup,backupPath]=process.argv.slice(2);
  if(!['dry-run','apply','verify'].includes(action ?? '') || !database) throw Error('Usage: pnpm exec tsx apps/im-server/src/migrate-task-collaboration.ts dry-run DB [MAPPING] | apply DB MAPPING BACKUP | verify DB BACKUP');
  const db=new DatabaseSync(database,{readOnly:action!=='apply'});
  try {
    let result:Row;
    if(action==='dry-run') {
      result=inspectMigration(db);
      if(mappingOrBackup) {const mapping=JSON.parse(readFileSync(mappingOrBackup,'utf8'));const rows=plan(db,mapping);for(const r of all(db,'SELECT * FROM task_graph_mutation_receipts')) receiptConversation(db,r,mapping);result={state:'mapping_valid',graphs:rows.length,fingerprint:fingerprint(db)};}
    } else if(action==='apply') {
      if(!mappingOrBackup || !backupPath) throw Error('Mapping and backup paths are required');
      result=await applyMigration(db,JSON.parse(readFileSync(mappingOrBackup,'utf8')),backupPath);
    } else {
      if(!mappingOrBackup) throw Error('Pre-migration backup path is required');
      const before=new DatabaseSync(mappingOrBackup,{readOnly:true});try {result=verifyMigration(db,before);}finally{before.close();}
    }
    process.stdout.write(JSON.stringify(result,null,2)+'\n');
  } finally {db.close();}
}
if(process.argv[1] && import.meta.url===pathToFileURL(resolve(process.argv[1])).href) main().catch(error=>{process.stderr.write(String(error)+'\n');process.exitCode=1;});
