import {expect,it} from 'vitest';
import {mkdtempSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {NodeStore} from '../src/store.js';
import {UsageReports} from '../src/usage.js';

it('replays an ambiguous report with the same native ID and never recharges an acknowledged turn',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'nano-usage-'));
  let store=new NodeStore(join(dir,'node.sqlite'),'owner');
  store.bind({sessionId:'root',agentId:'a',conversationId:'old-uuid-chat',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const calls: Record<string,unknown>[]=[];
  let fail=true;
  const options={nodeId:'node',store,runtime:{onNotification:()=>()=>{},async request(){return {cursor:'runtime:1',reports:[{sessionId:'child',turn:1,time:1000,usage:{prompt_tokens:12,completion_tokens:3,total_tokens:15}}]};}},
    relay:{ready:true,async request(_type:string,payload:Record<string,unknown>){calls.push(payload);if(fail){fail=false;throw Error('ack lost');}return {type:'ack',payload:{}};}},onError:()=>{}};
  const first=new UsageReports(options);
  await expect(first.recover()).rejects.toThrow('ack lost');
  expect(store.pendingUsage()).toHaveLength(1);
  await first.stop();
  store.close();
  store=new NodeStore(join(dir,'node.sqlite'),'owner');
  const second=new UsageReports({...options,store});
  await second.recover();
  await second.recover();
  expect(calls).toHaveLength(2);
  expect(calls[0]).toEqual(calls[1]);
  expect(calls[0]).toMatchObject({run_id:'child:1',agent_id:'a',conversation_id:'old-uuid-chat'});
  expect(store.pendingUsage()).toEqual([]);
  await second.stop();store.close();rmSync(dir,{recursive:true,force:true});
});

function report(sessionId: string, turn: number) {
  return {sessionId, turn, time: 1000, usage: {prompt_tokens: 12, completion_tokens: 3, total_tokens: 15}};
}
function bind(store: NodeStore) {
  store.bind({sessionId:'root',agentId:'a',conversationId:'chat',ownerId:'owner',cwd:'/tmp',revision:'1'});
}

it('drains a child completion arriving while the root report awaits its ACK', async () => {
  const store = new NodeStore(':memory:', 'owner'); bind(store);
  const started = Promise.withResolvers<void>(), ack = Promise.withResolvers<void>();
  const reports = [report('root', 1)], cursors: unknown[] = [], sent: unknown[] = [];
  let notify: (method: string, value: unknown) => void = () => {};
  const service = new UsageReports({nodeId: 'node', store,
    runtime: {onNotification(listener) {notify = listener; return () => {};}, async request(_method, value) {
      const cursor = (value as {cursor?: string}).cursor;
      cursors.push(cursor);
      return {reports: reports.slice(cursor ? Number(cursor.split(':')[1]) : 0), cursor: `runtime:${reports.length}`};
    }},
    relay: {ready: true, async request(_method, value) {
      sent.push(value); if (sent.length === 1) {started.resolve(); await ack.promise;}
      return {type: 'ack', payload: {}};
    }}, onError(error) {throw error;}});
  try {
    const running = service.recover();
    await started.promise;
    reports.push(report('child', 2));
    notify('session.event', {sessionId:'child',rootSessionId:'root',event:{type:'turn/end'}});
    ack.resolve(); await running;
    expect(sent).toHaveLength(2);
    expect(cursors).toEqual([undefined, 'runtime:1']);
    await service.recover();
    expect(cursors.at(-1)).toBe('runtime:2');
    expect(sent).toHaveLength(2);
    expect(store.pendingUsage()).toEqual([]);
  } finally {ack.resolve(); await service.stop(); store.close();}
});

it('does not advance a read cursor until every usage fact is durable', async () => {
  const store = new NodeStore(':memory:', 'owner'); bind(store);
  const cursors: unknown[] = [];
  const save = store.saveUsage.bind(store);
  let fail = true;
  store.saveUsage = (id, payload) => {if (id === 'child:1' && fail) {fail = false; throw Error('write failed');} save(id, payload);};
  const service = new UsageReports({nodeId:'node',store,
    runtime:{onNotification:()=>()=>{},async request(_method, value) {
      cursors.push((value as {cursor?:string}).cursor);
      return {cursor:'runtime:2',reports:[report('root',1),report('child',1)]};
    }}, relay:{ready:false,async request(){throw Error('offline');}},onError:()=>{}});
  try {
    await expect(service.recover()).rejects.toThrow('write failed');
    await service.recover();
    expect(cursors).toEqual([undefined, undefined]);
    expect(store.pendingUsage().map(row=>row.runId)).toEqual(['root:1','child:1']);
  } finally {await service.stop();store.close();}
});

it('adds a pending-only access path to existing databases without losing confirmed deduplication', () => {
  const dir=mkdtempSync(join(tmpdir(),'nano-usage-index-')), path=join(dir,'node.sqlite');
  const old=new DatabaseSync(path);
  old.exec('CREATE TABLE usage_reports(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL,acknowledged INTEGER NOT NULL DEFAULT 0); BEGIN');
  const insert=old.prepare('INSERT INTO usage_reports VALUES(?,?,1)');
  for(let i=0;i<20000;i++) insert.run(`old:${i}`, '{}');
  old.exec('COMMIT'); old.close();
  const store=new NodeStore(path,'owner'), probe=new DatabaseSync(path);
  try {
    store.saveUsage('old:1',{unexpected:true});
    store.saveUsage('new:1',{run_id:'new:1'});
    expect(store.pendingUsage()).toEqual([{runId:'new:1',payload:{run_id:'new:1'}}]);
    const plan=probe.prepare('EXPLAIN QUERY PLAN SELECT run_id,payload FROM usage_reports WHERE acknowledged=0 ORDER BY rowid').all();
    expect(plan.some(row=>String(row.detail).includes('USING INDEX'))).toBe(true);
    store.confirmUsage('new:1');
    expect(store.pendingUsage()).toEqual([]);
    expect(probe.prepare('SELECT COUNT(*) n FROM usage_reports').get()!.n).toBe(20001);
  } finally {probe.close();store.close();rmSync(dir,{recursive:true,force:true});}
});
