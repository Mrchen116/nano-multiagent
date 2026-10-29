import {DatabaseSync} from 'node:sqlite';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {InboxStore} from './inbox.js';

/** Inspect counts only; plan never opens a writable Inbox or recovers interrupted work. */
export function inspectInputMigration(db:DatabaseSync) {
 const hasState=db.prepare('PRAGMA table_info(inbox)').all().some(row=>row.name==='review_state');
 const marked=!!db.prepare("SELECT 1 FROM sqlite_master WHERE name='metadata'").get()&&!!db.prepare("SELECT 1 FROM metadata WHERE key='input-review-v1'").get();
 return {version:'input-review-v1',state:marked?'already_migrated':'pending',rows:db.prepare('SELECT agent_id,consumed,count(*) count FROM inbox GROUP BY agent_id,consumed').all(),
  reviews:hasState?db.prepare('SELECT review_state,review_error_code,count(*) count FROM inbox GROUP BY review_state,review_error_code').all():[]};
}
/** Verify original input, consumption and publication records against an offline backup. */
export function verifyInputMigration(db:DatabaseSync,before:DatabaseSync) {
 const plan=inspectInputMigration(db);if(plan.state!=='already_migrated')throw new Error('Input review migration is incomplete');
 for(const table of ['inbox','publications']) {
  const columns=before.prepare(`PRAGMA table_info(${table})`).all().map(row=>row.name).filter(name=>!String(name).startsWith('review_')).join(',');
  if(JSON.stringify(db.prepare(`SELECT ${columns} FROM ${table} ORDER BY rowid`).all())!==JSON.stringify(before.prepare(`SELECT ${columns} FROM ${table} ORDER BY rowid`).all()))throw new Error(`Historical records changed: ${table}`);
 }
 return {...plan,verified:true};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
 const [mode,path,...rest]=process.argv.slice(2);
 if(!['plan','apply','verify'].includes(mode??'')||!path)throw new Error('Usage: migrate-input-review plan DATABASE | apply DATABASE PA_AGENT_ID... | verify DATABASE BACKUP');
 if(mode==='apply') {
  if(!rest.length)throw new Error('Explicit personal Agent IDs are required');
  const inbox=new InboxStore(path);try{inbox.reviews.migrate(rest);}finally{inbox.close();}
 }
 const db=new DatabaseSync(path,{readOnly:true});
 try {
  if(mode==='verify') {
   if(rest.length!==1)throw new Error('Backup is required');
   const before=new DatabaseSync(rest[0]!,{readOnly:true});try{console.log(JSON.stringify(verifyInputMigration(db,before)));}finally{before.close();}
  }else console.log(JSON.stringify(inspectInputMigration(db)));
 }finally{db.close();}
}
