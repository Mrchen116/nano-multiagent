import Fastify from 'fastify';
import { backup, DatabaseSync } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { fixture, connectFixtureGateway } from './control-fixture.js';
import { all, one, transaction, type ImContext } from '../src/context.js';
import { openDatabase } from '../src/db.js';
import { createIdentity } from '../src/identity.js';
import { Gateway } from '../src/gateway.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';
import { captureTaskContextAccess, revokeLostTaskContextAccess } from '../src/task-context-access.js';

const migration='task-context-unfinished-relays-v1';
function legacyFixture() {
  const f=fixture();f.ctx.gateway.broadcast=vi.fn();f.ctx.messaging=new Messaging(f.ctx);
  f.db.prepare("UPDATE conversations SET creator_id='u1' WHERE id='chat'").run();
  connectFixtureGateway(f);
  return f;
}
function legacyOriginal(ctx:ImContext,status='queued',senderType='system',notice:unknown={kind:'task_graph',change_kinds:['title'],attention_actor_ids:['a']}) {
  return transaction(ctx.db,()=>{
    const m=ctx.messaging.insertMessage('chat','u1',senderType,'PRIVATE authoritative old Task body',[],null,'completed',{system_notice:notice,publish:false});
    // This is the old persistTaskNotice path, before its ordered index existed.
    ctx.messaging.queueRepresentedRelays(m,'not-a-participant');
    ctx.db.prepare('UPDATE relay_tasks SET status=?,receipt_status=? WHERE message_id=?').run(status,status==='accepted'?'accepted':null,m.id);
    return m;
  });
}
async function saveLegacy(f:ReturnType<typeof legacyFixture>,path:string) {
  // Model the pre-upgrade database, not a new producer deleting modern index rows.
  f.db.exec('DROP TABLE task_context_index; DROP TABLE task_context_revocations;');
  f.db.prepare('DELETE FROM schema_migrations WHERE version=?').run(migration);
  await backup(f.db,path);
}
function upgraded(base:ImContext,db:ReturnType<typeof openDatabase>) {
  const identity=createIdentity(db,'migration-test-secret');
  identity.authenticateRequest=()=>identity.user('u1')!;
  const ctx={...base,db,identity} as ImContext;
  ctx.gateway={...base.gateway,nodes:new Map(),broadcast:vi.fn()} as any;
  ctx.messaging=new Messaging(ctx);
  return ctx;
}
const counts=(ctx:ImContext)=>['messages','conversation_events','relay_tasks'].map(table=>one(ctx.db,`SELECT count(*) AS n FROM ${table}`)!.n);

it('upgrades only unfinished legacy Task originals by their authoritative IDs and resumes without replay after business ACK and reopen',async()=>{
  const f=legacyFixture(),dir=mkdtempSync(join(tmpdir(),'task-context-migration-')),path=join(dir,'im.db');
  let db:ReturnType<typeof openDatabase>|undefined;
  try {
    const originals=Array.from({length:35},(_,i)=>legacyOriginal(f.ctx,['queued','sent','accepted'][i%3]));
    for(const status of ['completed','failed','cancelled'])legacyOriginal(f.ctx,status);
    const spoof=legacyOriginal(f.ctx,'queued','user');
    const spoofRelay=one(f.db,'SELECT * FROM relay_tasks WHERE message_id=?',spoof.id)!;
    const spoofPayload=JSON.parse(spoofRelay.payload_json);spoofPayload.message.sender_type='system';spoofPayload.message.system_notice={kind:'task_graph'};
    f.db.prepare('UPDATE relay_tasks SET payload_json=? WHERE relay_task_id=?').run(JSON.stringify(spoofPayload),spoofRelay.relay_task_id);
    legacyOriginal(f.ctx,'queued','system',{kind:'not_task'});
    const malformedNotice=legacyOriginal(f.ctx);f.db.prepare("UPDATE messages SET system_notice_json='{' WHERE id=?").run(malformedNotice.id);
    const malformedPayload=legacyOriginal(f.ctx);f.db.prepare("UPDATE relay_tasks SET payload_json='{' WHERE message_id=?").run(malformedPayload.id);
    const unknownAgent=legacyOriginal(f.ctx);f.db.prepare("UPDATE relay_tasks SET payload_json=json_set(payload_json,'$.agent_id','unknown') WHERE message_id=?").run(unknownAgent.id);
    const minimal=legacyOriginal(f.ctx,'queued','system',{kind:'task_graph',change_kinds:['access_revoked']});
    const unrelayed=f.ctx.messaging.insertMessage('chat','u1','system','Historical Task with no unfinished delivery',[],null,'completed',{system_notice:{kind:'task_graph'},publish:false});
    const originalRelay=one(f.db,'SELECT * FROM relay_tasks WHERE message_id=?',originals[0].id)!;
    const payload=JSON.parse(originalRelay.payload_json);expect(payload.metadata.task_context).toBeUndefined();
    payload.message.content='FAKE private relay summary';payload.message.id='forged-id';
    f.db.prepare('UPDATE relay_tasks SET payload_json=? WHERE relay_task_id=?').run(JSON.stringify(payload),originalRelay.relay_task_id);
    const before=counts(f.ctx);
    await saveLegacy(f,path);db=openDatabase(path);let ctx=upgraded(f.ctx,db);
    expect(counts(ctx)).toEqual(before);
    const references=all(db,'SELECT * FROM task_context_index ORDER BY seq');
    expect(references).toHaveLength(35);
    expect(references.map(row=>row.message_id)).toEqual(originals.map(m=>m.id));
    expect(references.every(row=>row.agent_id==='a'&&row.conversation_id==='chat'&&row.projection_kind==='full')).toBe(true);
    expect(references.some(row=>[spoof.id,minimal.id,unrelayed.id].includes(row.message_id))).toBe(false);
    expect(all(db,'SELECT * FROM task_context_revocations')).toEqual([]);
    const first=ctx.messaging.syncTaskContext('a',0,undefined,32),second=ctx.messaging.syncTaskContext('a',first.next,first.through,32);
    expect(first.items).toHaveLength(32);expect(second.items).toHaveLength(3);expect(second.next).toBe(first.through);
    const page=[...first.items,...second.items];
    expect(page.map(item=>item.input.message.id)).toEqual(originals.map(m=>m.id));
    expect(page.every(item=>item.input.message.content==='PRIVATE authoritative old Task body')).toBe(true);
    db.close();db=openDatabase(path);ctx=upgraded(f.ctx,db);
    expect(all(db,'SELECT * FROM task_context_index ORDER BY seq')).toEqual(references);
    ctx.gateway=new Gateway(ctx);
    const connection={node_id:'n',owner_id:'o1',node_epoch:1,socket:{readyState:1,bufferedAmount:0,send:vi.fn(),close:vi.fn()}} as any;
    ctx.gateway.nodes.set('n',connection);
    // Prevent intentionally corrupt negative fixtures from reaching the transport drain.
    db.prepare("UPDATE relay_tasks SET status='cancelled' WHERE message_id NOT IN (SELECT message_id FROM task_context_index)").run();
    for(const relay of all(db,"SELECT * FROM relay_tasks WHERE status IN ('queued','sent','accepted')"))await ctx.gateway.handle(connection,'node.delivery_receipt',{node_id:'n',relay_task_id:relay.relay_task_id,delivery_status:'completed'});
    expect(all(db,"SELECT * FROM relay_tasks WHERE status IN ('queued','sent','accepted')")).toEqual([]);
    db.close();db=openDatabase(path);ctx=upgraded(f.ctx,db);
    expect(all(db,'SELECT * FROM task_context_index ORDER BY seq')).toEqual(references);
    expect(ctx.messaging.syncTaskContext('a',second.next,undefined,32).items).toEqual([]);
    expect(counts(ctx)[0]).toBe(before[0]);
  } finally {db?.close();rmSync(dir,{recursive:true,force:true});}
});

it('revalidates upgraded pending originals across a fixed cut and exposes only the new minimal withdrawal after real current loss',async()=>{
  const f=legacyFixture(),dir=mkdtempSync(join(tmpdir(),'task-context-loss-')),path=join(dir,'im.db');
  let db:ReturnType<typeof openDatabase>|undefined;const app=Fastify();
  try {
    const old=legacyOriginal(f.ctx,'accepted');await saveLegacy(f,path);db=openDatabase(path);
    const ctx=upgraded(f.ctx,db);registerMessagingRoutes(app,ctx);
    const cut=ctx.messaging.syncTaskContext('a',0,undefined,32);
    expect(cut.items[0]).toMatchObject({allowed:true,input:{message:{id:old.id}}});
    expect((await app.inject({method:'DELETE',url:'/im/v1/conversations/chat/participants/a1'})).statusCode).toBe(204);
    expect(ctx.messaging.syncTaskContext('a',cut.through,cut.through,32,undefined,[old.id]).revoked_message_ids).toEqual([old.id]);
    const page=ctx.messaging.syncTaskContext('a',0,undefined,32);
    expect(page.items.filter((item:any)=>item.allowed)).toHaveLength(1);
    expect(page.items[0]).toMatchObject({message_id:old.id,allowed:false});expect(page.items[0].input).toBeUndefined();
    const minimal=page.items[1];expect(minimal).toMatchObject({projection_kind:'revoked',allowed:true,input:{participants:[]}});
    expect(minimal.input.message.system_notice.change_kinds).toEqual(['access_revoked']);
    expect(JSON.stringify(minimal)).not.toMatch(/PRIVATE|authoritative old Task/);
    expect(ctx.messaging.message(old.id).content).toContain('PRIVATE');
    expect((await app.inject({method:'DELETE',url:'/im/v1/conversations/chat/participants/a1'})).statusCode).toBe(204);
    expect(all(db,'SELECT * FROM task_context_revocations')).toHaveLength(1);
  } finally {await app.close();db?.close();rmSync(dir,{recursive:true,force:true});}
});

it('never backfills a minimal withdrawal as full or revives an unindexed old source after a prior terminal withdrawal',async()=>{
  const f=legacyFixture(),dir=mkdtempSync(join(tmpdir(),'task-context-terminal-')),path=join(dir,'im.db');
  let db:ReturnType<typeof openDatabase>|undefined;
  try {
    const old=legacyOriginal(f.ctx);
    f.db.prepare("INSERT INTO task_context_index(agent_id,message_id,conversation_id,projection_kind) VALUES('a',?,'chat','full')").run(old.id);
    const notices=transaction(f.db,()=>{
      const before=captureTaskContextAccess(f.db,{agentIds:['a']});
      f.db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='a1'").run();
      return revokeLostTaskContextAccess(f.db,before,'u1');
    });
    expect(notices).toHaveLength(1);
    f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','a1')").run();
    f.db.prepare("DELETE FROM task_context_index WHERE projection_kind='full'").run();
    f.db.prepare('DELETE FROM schema_migrations WHERE version=?').run(migration);
    await backup(f.db,path);db=openDatabase(path);const ctx=upgraded(f.ctx,db);
    const entries=all(db,'SELECT * FROM task_context_index');expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({message_id:notices[0].id,projection_kind:'revoked'});
    expect(ctx.messaging.syncTaskContext('a',0,undefined,32,undefined,[old.id])).toMatchObject({items:[{message_id:notices[0].id,projection_kind:'revoked',allowed:true}],revoked_message_ids:[old.id]});
  } finally {db?.close();rmSync(dir,{recursive:true,force:true});}
});

it('rolls a failed legacy backfill and its migration marker back together, then safely retries',async()=>{
  const f=legacyFixture(),dir=mkdtempSync(join(tmpdir(),'task-context-rollback-')),path=join(dir,'im.db');
  let db:ReturnType<typeof openDatabase>|undefined;
  try {
    const first=legacyOriginal(f.ctx),second=legacyOriginal(f.ctx,'sent');
    f.db.prepare('DELETE FROM schema_migrations WHERE version=?').run(migration);
    f.db.exec(`CREATE TRIGGER fail_legacy_task_index BEFORE INSERT ON task_context_index
      WHEN NEW.message_id=(SELECT message_id FROM relay_tasks WHERE status='sent' LIMIT 1)
      BEGIN SELECT RAISE(ABORT,'test backfill failure'); END;`);
    await backup(f.db,path);
    expect(()=>openDatabase(path)).toThrow('test backfill failure');
    db=new DatabaseSync(path);
    expect(all(db,'SELECT * FROM task_context_index')).toEqual([]);
    expect(one(db,'SELECT * FROM schema_migrations WHERE version=?',migration)).toBeUndefined();
    db.exec('DROP TRIGGER fail_legacy_task_index');db.close();db=undefined;
    db=openDatabase(path);
    expect(all(db,'SELECT message_id FROM task_context_index ORDER BY seq').map(row=>row.message_id)).toEqual([first.id,second.id]);
    expect(one(db,'SELECT * FROM schema_migrations WHERE version=?',migration)).toBeDefined();
  } finally {db?.close();rmSync(dir,{recursive:true,force:true});}
});
