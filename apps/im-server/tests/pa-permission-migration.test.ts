import {expect,it} from 'vitest';
import {DatabaseSync,backup} from 'node:sqlite';
import {mkdtempSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {personalFixture,recordOwnerNotice} from './personal-fixture.js';
import {applyPermissionMigration,inspectPermissionMigration,verifyPermissionMigration} from '../src/migrate-pa-permissions.js';

it('invalidates only old unused permits and preserves receipts through repeat apply and rollback',async()=>{
 const {db,ctx,service,principal,args}=personalFixture();
 const root=mkdtempSync(join(tmpdir(),'pa-migrate-'));let before:DatabaseSync|undefined;
 try {
  const source=ctx.messaging.insertMessage('peer','u2','user','Private request');
  const incident=service.incident(principal,{...args,source_message_id:source.id,reason:'Private request'});
  recordOwnerNotice(service,principal,args,incident);
  db.prepare("DELETE FROM pa_source_events WHERE kind='security.incident'").run();
  for(const state of ['allowed','confirmed','sending','unknown']) {
   const p=service.actions.prepare(principal,{...args,request_key:state,representation:'owner',conversation_id:'peer',content:'Public reply'});
   db.prepare('UPDATE pa_operations SET state=?,verdict_ref=?,message_id=? WHERE operation_id=?').run(state,'old-permit',state==='confirmed'?'actual-receipt':null,p.proposal_ref);
  }
  await backup(db,join(root,'before.db'));before=new DatabaseSync(join(root,'before.db'),{readOnly:true});
  expect(inspectPermissionMigration(db).state).toBe('pending');
  db.exec("CREATE TRIGGER interrupt_permission_migration BEFORE INSERT ON schema_migrations WHEN NEW.version='pa-permission-boundaries-v1' BEGIN SELECT RAISE(ABORT,'test interruption'); END;");
  expect(()=>applyPermissionMigration(db)).toThrow('test interruption');
  expect(db.prepare("SELECT state,verdict_ref FROM pa_operations WHERE request_key='allowed'").get()).toEqual({state:'allowed',verdict_ref:'old-permit'});
  expect(db.prepare("SELECT count(*) n FROM pa_source_events WHERE kind='security.incident'").get()!.n).toBe(0);
  db.exec('DROP TRIGGER interrupt_permission_migration');
  applyPermissionMigration(db);
  expect(verifyPermissionMigration(db,before).verified).toBe(true);
  expect(db.prepare("SELECT state,verdict_ref,result_json FROM pa_operations WHERE request_key='allowed'").get()).toMatchObject({state:'invalidated',verdict_ref:null,result_json:JSON.stringify({state:'not_sent',changed_reason:'upgrade_requires_redecision'})});
  const once=JSON.stringify(db.prepare('SELECT * FROM pa_source_events ORDER BY event_id').all());
  applyPermissionMigration(db);
  expect(JSON.stringify(db.prepare('SELECT * FROM pa_source_events ORDER BY event_id').all())).toBe(once);
  expect(verifyPermissionMigration(db,before).verified).toBe(true);
  expect(service.pendingIncidents(principal,args).items[0]).toMatchObject({owner_notice_message_id:incident.owner_notice_message_id,peer_notice_message_id:null});
 }finally{before?.close();rmSync(root,{recursive:true,force:true});}
});
