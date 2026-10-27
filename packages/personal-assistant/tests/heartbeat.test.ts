import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { expect, it } from 'vitest';
import { Heartbeat } from '../src/heartbeat.js';
import { heartbeatDue, heartbeatTasks, withinActiveHours } from '../src/heartbeat-policy.js';

it('keeps config cadence authoritative, evaluates task rhythms once, and respects active hours', () => {
  const [task] = heartbeatTasks('# Tasks\nevery: 1s\nCheck the inbox', { every: '10m' });
  expect(task?.interval).toBe(600000);
  expect(heartbeatTasks('# Nothing\n- [ ]\n```\n```', {})).toEqual([]);
  const tasks = heartbeatTasks('tasks:\n  - name: inbox\n    interval: 30m\n    prompt: "Check inbox"\n  - name: calendar\n    interval: 2h\n    prompt: Review calendar', {});
  expect(tasks.map(task => task.interval)).toEqual([1800000, 7200000]);
  expect(heartbeatDue(task!, 0, 1850000)).toBe(1800000);
  expect(heartbeatDue(task!, 1800000, 1850000)).toBeUndefined();
  expect(withinActiveHours(Date.parse('2026-10-09T02:00:00Z'), { active_hours: { start: '09:00', end: '18:00', timezone: 'Asia/Shanghai' } })).toBe(true);
  expect(withinActiveHours(Date.parse('2026-10-09T12:00:00Z'), { active_hours: { start: '09:00', end: '18:00', timezone: 'Asia/Shanghai' } })).toBe(false);
});

it('uses the saved user timezone for both active hours and HEARTBEAT cron', () => {
  const morning = Date.parse('2026-10-14T01:00:00Z');
  const night = Date.parse('2026-10-14T17:00:00Z');
  const settings = { timezone: 'Asia/Shanghai', active_hours: { start: '09:00', end: '18:00' } };
  expect(withinActiveHours(morning, settings)).toBe(true);
  expect(withinActiveHours(night, settings)).toBe(false);
  const task = { name: 'daily', prompt: 'Check inbox', cron: '0 9 * * *' };
  expect(heartbeatDue(task, undefined, morning, 'Asia/Shanghai')).toBe(morning);
  expect(heartbeatDue(task, undefined, morning + 8 * 3600000, 'Asia/Shanghai')).toBeUndefined();
});

it('recovers an uncertain heartbeat admission by its original identity and does not refill missed ticks', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-heartbeat-'));
  await mkdir(join(directory, '.nanoassistant'));
  await writeFile(join(directory, '.nanoassistant/HEARTBEAT.md'), 'Check inbox');
  const agent = { agentId: 'a', revision: '1', workspace: directory, mode: 'single_thread' as const, provider: 'p', model: 'm', features: { heartbeat: true } };
  const accepted = new Set<string>(); let fail = true; let submissions = 0;
  const options = { agents: [agent], settings: () => ({ every: '10m', timezone: 'Asia/Shanghai' }), available: () => true, onError: () => {},
    binding: async () => ({ sessionId: 's', conversationId: 'c', ownerId: 'o', agentId: 'a', cwd: directory, revision: '1' }),
    runtime: { onNotification: () => () => {}, request: async (method: string, params: unknown) => {
      const value = params as { inputId: string; onlyIfIdle?: boolean; source?: { channel: string } };
      if (method === 'session.lookup') return { accepted: accepted.has(value.inputId) };
      expect(value.onlyIfIdle).toBe(true); expect(value.source?.channel).toBe('heartbeat');
      const content = (params as { content: {text: string}[] }).content;
      expect(content[0]!.text).toContain('+08:00 (Asia/Shanghai)');
      accepted.add(value.inputId); submissions++;
      if (fail) throw new Error('lost acceptance response'); return { accepted: true };
    } },
  };
  let heartbeat = new Heartbeat(join(directory, 'hb.sqlite3'), options);
  try {
    heartbeat.subscription('a', true);
    await expect(heartbeat.tick(undefined, false, 1200000)).rejects.toThrow('lost acceptance');
    expect(heartbeat.busy).toBe(true);
    expect(heartbeat.hold('a', 'change')).toBe(false);
    heartbeat.release('a', 'change');
    await heartbeat.stop(); fail = false;
    heartbeat = new Heartbeat(join(directory, 'hb.sqlite3'), options); heartbeat.subscription('a', true);
    expect(heartbeat.busy).toBe(true);
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(1);
    expect(heartbeat.busy).toBe(false);
    expect(heartbeat.hold('a', 'change')).toBe(true);
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(1);
    heartbeat.release('a', 'wrong');
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(1);
    heartbeat.release('a', 'change');
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(2);
    await heartbeat.tick(undefined, false, 6000000); expect(submissions).toBe(2);
    heartbeat.subscription('a', false);
    await heartbeat.tick(undefined, false, 12000000); expect(submissions).toBe(2);
    await expect(heartbeat.tick('a', true, 12000000)).rejects.toThrow('disabled');
  } finally { await heartbeat.stop(); await rm(directory, { recursive: true, force: true }); }
});

it('resets cadence and prevents a tick waiting for binding from reviving after disable and enable',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'nano-heartbeat-reset-'));await mkdir(join(directory,'.nanoassistant'));await writeFile(join(directory,'.nanoassistant/HEARTBEAT.md'),'Check inbox');
 let release!:()=>void,started!:()=>void;const ready=new Promise<void>(r=>started=r),gate=new Promise<void>(r=>release=r);let first=true,submits=0;
 const heartbeat=new Heartbeat(join(directory,'heartbeat.sqlite3'),{agents:[{agentId:'a',revision:'1',workspace:directory,mode:'single_thread',provider:'p',model:'m',features:{heartbeat:true}}],
  settings:()=>({every:'10m'}),available:()=>true,onError:()=>{},binding:async()=>{if(first){first=false;started();await gate;}return {agentId:'a',sessionId:'s',conversationId:'c',ownerId:'o',cwd:directory,revision:'1'};},
  runtime:{onNotification:()=>()=>{},request:async(method)=>{if(method==='session.submit')submits++;return {accepted:false};}}});
 try {
  heartbeat.subscription('a',true);const pending=heartbeat.tick(undefined,false,1200000);await ready;
  heartbeat.resetAgent('a',1200000);heartbeat.resetAgent('a',1300000);release();await pending;expect(submits).toBe(0);
  await heartbeat.tick(undefined,false,1300000);expect(submits).toBe(0);
  await heartbeat.tick(undefined,false,1900000);expect(submits).toBe(1);
 }finally{release();await heartbeat.stop();await rm(directory,{recursive:true,force:true});}
});
