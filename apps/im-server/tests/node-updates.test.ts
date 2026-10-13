import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import Fastify from 'fastify';
import { afterEach, expect, it, vi } from 'vitest';
import { NodeUpdates, registerNodeUpdateRoutes } from '../src/node-updates.js';
import { Messaging } from '../src/messaging.js';
import { fixture } from './control-fixture.js';

const homes: string[] = [];
afterEach(() => { for (const home of homes.splice(0)) rmSync(home, {recursive:true, force:true}); });
const target = {version:'1.2.3', source_commit:'a'.repeat(40), sha256:'b'.repeat(64), package:'nano-node.tgz',
  node_major:24, pnpm_version:'11.7.0', updater_protocol:1, data_epoch:1,
  download_url:'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.2.3/nano-node.tgz'};
const old = {kind:'managed' as const, version:'1.2.2', source_commit:'c'.repeat(40),sha256:'d'.repeat(64),updater_protocol:1,data_epoch:1};
const id = {node_id:'n',owner_id:'o1',node_epoch:3};
function setup() {
  const f = fixture();
  const dir = mkdtempSync(join(tmpdir(),'nano-update-server-')); homes.push(dir);
  writeFileSync(join(dir,'manifest.json'), JSON.stringify(target));
  f.ctx.publicUrl = 'https://im.test';
  f.db.prepare('INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES(?,?,?)').run('n','o1',3);
  let online = true;
  f.ctx.gateway.isOnline = () => online;
  const sent: any[] = [];
  f.ctx.gateway.send = (node, frame) => {if (frame.type === 'relay.message' && f.ctx.updates?.gate(node)) return false;sent.push(frame);return online;};
  f.ctx.gateway.broadcast = vi.fn();
  f.ctx.messaging = new Messaging(f.ctx);
  const updates = f.ctx.updates = new NodeUpdates(f.ctx,dir);
  updates.register(id,old);
  const start = (request_id='click') => updates.begin('n','o1',{request_id,version:target.version,sha256:target.sha256});
  const progress = (operation_id:string, action:string, state?:string, rest={}) => updates.report(id,{operation_id,action,state,...rest});
  const prepare = () => {const op=start();progress(op.id,'progress','downloading');progress(op.id,'progress','installing');progress(op.id,'prepare');return op;};
  return {...f,dir,updates,sent,start,progress,prepare,offline:()=>{online=false;}};
}
it('checks metadata without dispatch, binds each click to the displayed target and retains request receipts', () => {
  const f=setup();
  expect(f.updates.view({node_id:'n',owner_id:'o1'}).available).toBe(true);
  expect(f.sent).toEqual([]);
  expect(()=>f.updates.begin('n','o1',{request_id:'stale',version:'1.2.4',sha256:target.sha256})).toThrow('Published version changed');
  const a=f.start(); const duplicate=f.start('second-click');expect(duplicate.id).toBe(a.id);
  f.progress(a.id,'terminal','cancelled',{resumed:true});
  expect(f.start('second-click').state).toBe('cancelled');
  expect(f.start('retry').id).not.toBe(a.id);
  expect(()=>f.updates.begin('n','o2',{request_id:'other'})).toThrow('Computer not found');
});
it('arbitrates cancel and switch and rejects success until the exact release reconnects', () => {
  const f=setup();const a=f.prepare();f.updates.cancel('n','o1',a.id);
  expect(()=>f.progress(a.id,'claim_switch')).toThrow('no longer authorized');
  expect(()=>f.progress(a.id,'terminal','cancelled')).toThrow('must resume');
  f.progress(a.id,'terminal','cancelled',{resumed:true});
  const b=f.start('retry');f.progress(b.id,'progress','downloading');f.progress(b.id,'progress','installing');f.progress(b.id,'prepare');f.progress(b.id,'claim_switch');
  expect(()=>f.updates.cancel('n','o1',b.id)).toThrow('already switching');
  f.progress(b.id,'progress','verifying');
  expect(()=>f.progress(b.id,'terminal','succeeded')).toThrow('has not connected');
  f.updates.register(id,{...old,...target,kind:'managed'});f.progress(b.id,'terminal','succeeded');
  expect(f.updates.view({node_id:'n',owner_id:'o1'}).reason).toBe('current');
});
it('replays a sent message when a preparation is cancelled without a reconnect', () => {
  const f=setup(); const a=f.prepare();
  f.db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at) VALUES('message','chat','u1','user','Continue after update','pending',?)").run(new Date().toISOString());
  f.db.prepare("INSERT INTO relay_tasks VALUES('relay','message','chat','n',?,'key','sent',NULL,NULL,?,?)")
    .run(JSON.stringify({agent_id:'a',conversation_id:'chat',idempotency_key:'key',metadata:{node_epoch:3}}),new Date().toISOString(),new Date().toISOString());
  // The message projection is computed from durable relay rows, including after refresh.
  expect(f.updates.messageWait('message')).toBe('updating');
  f.ctx.messaging.event=vi.fn();
  f.updates.cancel('n','o1',a.id);f.progress(a.id,'terminal','cancelled',{resumed:true});
  expect(f.sent.filter(x=>x.type==='relay.message')).toHaveLength(1);
  expect(f.updates.messageWait('message')).toBeNull();
});
it('expires an absent worker truthfully and rejects an obsolete epoch', () => {
  const f=setup();const a=f.prepare();
  f.db.prepare('UPDATE node_update_operations SET updated_at=? WHERE id=?').run('2000-01-01T00:00:00Z',a.id);
  f.updates.sweep();expect(f.updates.gate('n')?.state).toBe('recovery_required');
  expect(f.updates.acceptingQueue('n')).toBe(false);
  f.db.prepare('UPDATE node_binding_state SET node_epoch=4').run();
  expect(()=>f.progress(a.id,'poll')).toThrow('identity changed');expect(f.updates.gate('n')).toBeUndefined();
});
it('keeps rollback gated until the original release is really online', () => {
  const f=setup();const a=f.prepare();f.progress(a.id,'claim_switch');f.progress(a.id,'progress','rolling_back');
  f.offline();expect(()=>f.progress(a.id,'terminal','rolled_back')).toThrow('has not connected');
  expect(f.updates.gate('n')?.state).toBe('rolling_back');
});
it('authenticates the updater report independently of a browser session or live WebSocket', async () => {
  const f=setup();const op=f.start();const app=Fastify();
  f.ctx.identity.authenticateRuntime=(token)=>token==='runtime-token'?id:null;
  registerNodeUpdateRoutes(app,f.ctx,f.dir);
  try {
    expect((await app.inject({method:'POST',url:'/im/v1/node-update/report',headers:{authorization:'Bearer browser-token'},payload:{node_id:'n',operation_id:op.id,action:'poll'}})).statusCode).toBe(401);
    f.offline();
    const result=await app.inject({method:'POST',url:'/im/v1/node-update/report',headers:{authorization:'Bearer runtime-token'},payload:{node_id:'n',operation_id:op.id,action:'poll'}});
    expect(result.statusCode).toBe(200);expect(result.json().operation.id).toBe(op.id);expect(result.json().registered.online).toBe(false);
  } finally {await app.close();}
});
