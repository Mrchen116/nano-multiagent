import {DatabaseSync} from 'node:sqlite';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {all,transaction,now,type Row} from './context.js';

const version='pa-permission-boundaries-v1';
const marked=(db:DatabaseSync)=>!!db.prepare("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").get()&&!!db.prepare('SELECT 1 FROM schema_migrations WHERE version=?').get(version);
/** Inspect upgrade work without reading or rewriting private message bodies. */
export function inspectPermissionMigration(db:DatabaseSync):Row {
 return {version,state:marked(db)?'already_migrated':'pending',operations:all(db,'SELECT state,count(*) count FROM pa_operations GROUP BY state'),
  unfinished_incidents:db.prepare("SELECT count(*) count FROM pa_incidents WHERE status IN ('open','dismissed') AND (owner_notice_message_id IS NULL OR peer_notice_message_id IS NULL)").get()!.count};
}
/** Fence old permits and register unfinished incident communication atomically. */
export function applyPermissionMigration(db:DatabaseSync):Row {
 transaction(db,()=>{
  db.exec('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY)');
  if(marked(db))return;
  db.prepare("UPDATE pa_operations SET state='invalidated',verdict_ref=NULL,result_json=? WHERE state='allowed'")
   .run(JSON.stringify({state:'not_sent',changed_reason:'upgrade_requires_redecision'}));
  for(const incident of all(db,"SELECT i.*,b.agent_id,b.conversation_id owner_conversation_id,p.revision FROM pa_incidents i JOIN personal_agent_bindings b ON b.binding_id=i.binding_id JOIN pa_policies p ON p.binding_id=b.binding_id WHERE i.status IN ('open','dismissed') AND (i.owner_notice_message_id IS NULL OR i.peer_notice_message_id IS NULL)")) {
   if(db.prepare("SELECT 1 FROM pa_source_events WHERE binding_id=? AND kind='security.incident' AND json_extract(payload_json,'$.incident_ref')=?").get(incident.binding_id,incident.id))continue;
   // Projection rechecks access before loading source evidence; migration never reads it.
   const exists=!!db.prepare('SELECT 1 FROM messages WHERE id=?').get(incident.source_message_id);
   db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) VALUES(?,'security.incident',?,?,?)")
    .run(incident.binding_id,JSON.stringify({incident_ref:incident.id,...(!exists?{blocked_reason:'source_unavailable'}:{})}),incident.revision,now());
  }
  db.prepare('INSERT INTO schema_migrations VALUES(?)').run(version);
 });
 return inspectPermissionMigration(db);
}
/** Check that migration preserved all confirmed and uncertain receipts and original messages. */
export function verifyPermissionMigration(db:DatabaseSync,before:DatabaseSync):Row {
 if(!marked(db))throw new Error('Permission migration is incomplete');
 for(const table of ['messages','pa_incidents'])if(JSON.stringify(all(db,`SELECT * FROM ${table} ORDER BY rowid`))!==JSON.stringify(all(before,`SELECT * FROM ${table} ORDER BY rowid`)))throw new Error(`Historical records changed: ${table}`);
 for(const row of all(before,"SELECT * FROM pa_operations WHERE state IN ('confirmed','sending','unknown') ORDER BY rowid"))
  if(JSON.stringify(db.prepare('SELECT * FROM pa_operations WHERE operation_id=?').get(row.operation_id))!==JSON.stringify(row))throw new Error(`Delivery receipt changed: ${row.operation_id}`);
 return {...inspectPermissionMigration(db),verified:true};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
 const [mode,path,backup]=process.argv.slice(2);
 if(!['plan','apply','verify'].includes(mode??'')||!path)throw new Error('Usage: migrate-pa-permissions plan|apply|verify DATABASE [BACKUP]');
 const db=new DatabaseSync(path,{readOnly:mode!=='apply'});
 try {
  if(mode==='verify') {
   if(!backup)throw new Error('Backup is required');
   const before=new DatabaseSync(backup,{readOnly:true});try{console.log(JSON.stringify(verifyPermissionMigration(db,before)));}finally{before.close();}
  }else console.log(JSON.stringify(mode==='apply'?applyPermissionMigration(db):inspectPermissionMigration(db)));
 }finally{db.close();}
}
