import { DatabaseSync } from 'node:sqlite';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { all, transaction, type Row } from './context.js';

const column='representation_operation_id';
const tables=['messages','pa_operations','pa_delegated_messages','conversation_events','relay_tasks','pa_reply_drafts'];
function migrated(db:DatabaseSync):boolean {return all(db,'PRAGMA table_info(pa_delegated_messages)').some(row=>row.name===column);}

/** Inspect the additive provenance migration without rewriting historical identities. */
export function inspectRepresentationMigration(db:DatabaseSync):Row {
  return {state:migrated(db)?'already_migrated':'pending',rows:Object.fromEntries(tables.map(table=>[table,db.prepare(`SELECT count(*) n FROM ${table}`).get()!.n]))};
}

/** Add nullable provenance in one transaction; repeated application preserves existing values. */
export function applyRepresentationMigration(db:DatabaseSync):Row {
  transaction(db,()=>{if(!migrated(db))db.exec('ALTER TABLE pa_delegated_messages ADD COLUMN representation_operation_id TEXT REFERENCES pa_operations(operation_id)');});
  return inspectRepresentationMigration(db);
}

/** Verify preserved business records against a pre-migration backup before reopening traffic. */
export function verifyRepresentationMigration(db:DatabaseSync,before:DatabaseSync):Row {
  if(!migrated(db))throw Error('PA representation migration is incomplete');
  for(const table of tables) {
    const columns=all(before,`PRAGMA table_info(${table})`).map(row=>row.name).join(',');
    if(JSON.stringify(all(db,`SELECT ${columns} FROM ${table} ORDER BY rowid`))!==JSON.stringify(all(before,`SELECT ${columns} FROM ${table} ORDER BY rowid`)))throw Error(`Historical records changed: ${table}`);
  }
  if(!migrated(before)&&db.prepare(`SELECT 1 FROM pa_delegated_messages WHERE ${column} IS NOT NULL LIMIT 1`).get())throw Error('Historical provenance must remain NULL');
  return {...inspectRepresentationMigration(db),verified:true};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
  const [mode,path,backup]=process.argv.slice(2);
  if(!['dry-run','apply','verify'].includes(mode??'')||!path)throw Error('Usage: migrate-pa-representation dry-run|apply|verify DATABASE [PRE_MIGRATION_BACKUP]');
  const db=new DatabaseSync(path,{readOnly:mode!=='apply'});
  try {
    if(mode==='verify') {
      if(!backup)throw Error('Pre-migration backup path is required');
      const before=new DatabaseSync(backup,{readOnly:true});
      try{console.log(JSON.stringify(verifyRepresentationMigration(db,before)));}finally{before.close();}
    }else console.log(JSON.stringify(mode==='apply'?applyRepresentationMigration(db):inspectRepresentationMigration(db)));
  }finally{db.close();}
}
