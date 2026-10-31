import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import { InboxStore } from '../src/inbox.js';
import type { RelayInput } from '@nano/product-contracts';
const input = (id: string, text: string, target = 'group-a'): RelayInput => ({
  relay_task_id: `relay-${id}`, agent_id: 'alice', conversation_id: target, idempotency_key: id,
  metadata: { conversation_type: 'group', conversation_title: target },
  message: { id, content: text, sender_user_id: 'human', sender_type: 'user', attachments: [] },
});
it('only consumes exact durable read fragments, across restart and a frozen page snapshot', () => {
  const dir = mkdtempSync(join(tmpdir(), 'nano-inbox-'));
  let store = new InboxStore(join(dir, 'inbox.sqlite3'));
  try {
    store.receive(input('one', 'a'.repeat(7000)), true);
    const page = store.read('alice', 'main', 'call-1', { target: 'group-a', limit: 1 });
    expect(store.blocking('alice', 'group-a')).toBe(true);
    expect(store.commitRead('main', 'call-1', [{ type: 'text', text: 'truncated' }], false)).toBe(false);
    expect(store.commitRead('main', 'call-1', [{ type: 'text', text: JSON.stringify(page) }], false)).toBe(true);
    expect(store.blocking('alice', 'group-a')).toBe(true);
    store.close(); store = new InboxStore(join(dir, 'inbox.sqlite3'));
    store.receive(input('two', 'new correction'), true);
    const rest = store.read('alice', 'main', 'call-2', { target: 'group-a', cursor: String(page.next_cursor), limit: 1 });
    expect(JSON.stringify(rest)).not.toContain('new correction');
    expect(store.commitRead('main', 'call-2', [{ type: 'text', text: JSON.stringify(rest) }], false)).toBe(true);
    expect(store.check('alice').sources).toMatchObject([{ unread: 1 }]);
    expect(store.blocking('alice', 'group-a')).toBe(true);
    expect(() => store.read('bob', 'other', 'call-3', { target: 'group-a', cursor: String(page.next_cursor) })).toThrow('cursor');
  } finally { store.close(); rmSync(dir, { recursive: true }); }
});
it('keeps duplicate ingress stable and separates background and other-target messages from send revalidation', () => {
  const store = new InboxStore(':memory:');
  try {
    store.receive(input('one', 'background'), false); store.receive(input('one', 'background'), false);
    store.receive(input('two', 'correction', 'group-b'), true);
    expect(store.check('alice').sources).toHaveLength(2);
    expect(store.blocking('alice', 'group-a')).toBe(false);
    expect(store.blocking('alice', 'group-b')).toBe(true);
  } finally { store.close(); }
});
it('does not consume an image descriptor without the matching durable image content', () => {
  const store = new InboxStore(':memory:');
  try {
    const photo = input('photo', 'look');
    photo.message.attachments.push({ url: '/im/media/photo', content_type: 'image/png' });
    store.receive(photo, true);
    const body = store.read('alice', 'main', 'image-call', { target: 'group-a' });
    const text = { type: 'text', text: JSON.stringify(body) };
    expect(store.commitRead('main', 'image-call', [text], false)).toBe(false);
    const content = [text, { type: 'image', source: { kind: 'attachment', id: 'admitted-photo' } }];
    store.prepareRead('main', 'image-call', content);
    expect(store.commitRead('main', 'image-call', content, true)).toBe(false);
    expect(store.commitRead('main', 'image-call', content, false)).toBe(true);
    expect(store.blocking('alice', 'group-a')).toBe(false);
  } finally { store.close(); }
});

it('preserves relay sender names and timestamps in native inbox pages', () => {
  const store = new InboxStore(':memory:');
  const message = input('named', 'hello');
  message.message.sender = {display_name:'Alice'};
  message.message.pa_agent_id='alice-pa';
  message.message.created_at = '2026-10-10T01:00:00Z';
  try {
    store.receive(message, true);
    expect(store.read('alice','main','read',{target:'group-a'})).toMatchObject({messages:[{sender:{name:'Alice'},pa_agent_id:'alice-pa',time:'2026-10-10T01:00:00Z'}]});
  } finally {store.close();}
});

it('renders a message in its captured user timezone without changing its historical instant', () => {
  const store = new InboxStore(':memory:');
  const message = input('local', '早，今天有什么安排？');
  message.message.created_at = '2026-10-14T01:00:00Z';
  Object.assign(message.message, { timezone: 'Asia/Shanghai' });
  try {
    store.receive(message, true);
    expect(store.read('alice', 'main', 'local-read', { target: 'group-a' })).toMatchObject({
      messages: [{ time: '2026-10-14T09:00:00+08:00', content: [{ text: message.message.content }] }],
    });
  } finally { store.close(); }
});

it('wakes for new input after clearing the newest source, including after reopening', () => {
  const dir=mkdtempSync(join(tmpdir(),'nano-inbox-revoke-'));
  let store=new InboxStore(join(dir,'inbox.sqlite3'));
  try {
    store.receive(input('old','Old source'),true);
    store.admitWake('alice',store.wakePending('alice')!);
    store.revokeSource('alice','group-a');
    store.close();store=new InboxStore(join(dir,'inbox.sqlite3'));
    store.receive(input('new','New direct instruction','owner'),true);
    expect(store.wakePending('alice')).toBeDefined();
    expect(JSON.stringify(store.read('alice','main','read',{target:'owner'}))).toContain('New direct instruction');
  } finally {store.close();rmSync(dir,{recursive:true});}
});

const personalInput = (id: string, delivery = 'observer', target = 'owner-chat'): RelayInput => ({
  ...input(id, id, target), metadata: { conversation_type: 'direct', channel: 'web', personal_delivery: delivery, personal_is_owner: id !== 'peer' },
});
it('projects one conversation context per PA page and preserves ordered ingestion across a relation boundary', () => {
  const store = new InboxStore(':memory:');
  try {
    store.updateTarget('alice', 'owner-chat', 'A conversation');
    store.receive(personalInput('peer'), false);
    store.receive(personalInput('owner'), false);
    store.receive(personalInput('joined', 'participant'), true);
    expect(store.check('alice', true).sources).toEqual([{target:'owner-chat',name:'A conversation',unread:3,conversation_type:'direct',delivery:'observer'}]);
    const page = store.read('alice','main','observed',{target:'owner-chat'});
    expect(page).toMatchObject({target:'owner-chat',name:'A conversation',channel:'web',conversation_type:'direct',delivery:'observer',messages:[
      {id:'peer',sender:{is_owner:false}}, {id:'owner',sender:{is_owner:true}},
    ]});
    for (const message of page.messages as Record<string,unknown>[]) {
      expect(message).not.toHaveProperty('delivery'); expect(message).not.toHaveProperty('channel');
      expect(message).not.toHaveProperty('conversation_type'); expect(message).not.toHaveProperty('source_role');
    }
    expect(store.commitRead('main','observed',[{type:'text',text:JSON.stringify(page)}],false)).toBe(true);
    const next = store.read('alice','main','joined',{target:'owner-chat',cursor:String(page.next_cursor)});
    expect(next).toMatchObject({delivery:'participant',messages:[{id:'joined'}]});
    expect(store.commitRead('main','joined',[{type:'text',text:JSON.stringify(next)}],false)).toBe(true);
    expect(store.check('alice',true)).toEqual({sources:[],review_failures:[]});
  } finally {store.close();}
});
it('persists a fixed background deadline and notification identity separately from unread consumption', () => {
  const dir=mkdtempSync(join(tmpdir(),'nano-inbox-background-')); const path=join(dir,'inbox.sqlite3');
  let store=new InboxStore(path);
  try {
    store.receive(personalInput('one'),false,1000);
    store.receive(personalInput('two'),false,2000);
    expect(store.background('alice',2000)).toMatchObject({dueAt:601000,unread:true});
    const first=store.background('alice',601000)!;
    store.prepareBackground('alice',first.watermark);
    store.close();store=new InboxStore(path);
    expect(store.background('alice',602000)).toMatchObject({dueAt:601000,watermark:first.watermark,pending:true});
    store.admitBackground('alice',first.watermark,602000);
    expect(store.background('alice',602000)).toBeUndefined();
    expect(store.check('alice',true).sources[0].unread).toBe(2);
    store.receive(personalInput('three'),false,603000);
    expect(store.background('alice',603000)).toMatchObject({dueAt:1202000});
    const read=store.read('alice','main','read',{target:'owner-chat'});
    expect(store.commitRead('main','read',[{type:'text',text:JSON.stringify(read)}],false)).toBe(true);
    expect(store.background('alice',1202000)).toBeUndefined();
  } finally {store.close();rmSync(dir,{recursive:true});}
});
it('never reuses a background notification sequence after the highest source is revoked', () => {
  const store=new InboxStore(':memory:');
  try {
    store.receive(personalInput('old'),false,0);
    const old=store.background('alice',600000)!;
    store.prepareBackground('alice',old.watermark);
    store.admitBackground('alice',old.watermark,600000);
    store.revokeSource('alice','owner-chat');
    store.receive(personalInput('new','observer','other-chat'),false,700000);
    expect(store.background('alice',700000)!.watermark).toBeGreaterThan(old.watermark);
    expect(store.background('alice',700000)!.dueAt).toBe(1200000);
  } finally {store.close();}
});

it('revokes saved legacy pages by their source fragments without affecting another agent', () => {
  const store = new InboxStore(':memory:');
  const legacy = (body: Record<string, unknown>) => ({
    messages: (body.messages as Record<string, unknown>[]).map(message => ({ ...message, target: body.target })),
  });
  try {
    store.receive(input('old', 'revoked private context'), true);
    store.receive({ ...input('other', 'still authorized'), agent_id: 'bob' }, true);
    const page = store.read('alice', 'alice-main', 'old-read', { target: 'group-a' }, legacy);
    const other = store.read('bob', 'bob-main', 'other-read', { target: 'group-a' }, legacy);
    store.revokeSource('alice', 'group-a');
    expect(store.commitRead('alice-main', 'old-read', [{ type: 'text', text: JSON.stringify(page) }], false, 1)).toBe(false);
    expect(store.read('alice', 'alice-main', 'old-read', { target: 'group-a' })).toMatchObject({ messages: [] });
    expect(store.commitRead('bob-main', 'other-read', [{ type: 'text', text: JSON.stringify(other) }], false, 1)).toBe(true);
  } finally { store.close(); }
});

it('rejects already orphaned durable reads atomically and lets valid unread messages recover', () => {
  const dir = mkdtempSync(join(tmpdir(), 'nano-inbox-orphan-'));
  const path = join(dir, 'inbox.sqlite3');
  let store = new InboxStore(path);
  try {
    store.receive(input('valid', 'keep unread'), true);
    store.receive(input('removed', 'old source'), true);
    const page = store.read('alice', 'main', 'old-read', { target: 'group-a' });
    store.close();
    // Reproduce the persisted state left by legacy source revocation.
    const db = new DatabaseSync(path);
    db.prepare('DELETE FROM inbox WHERE message_id=?').run('removed');
    db.close();
    store = new InboxStore(path);
    expect(store.commitRead('main', 'old-read', [{ type: 'text', text: JSON.stringify(page) }], false, 1)).toBe(false);
    expect(store.check('alice').sources).toMatchObject([{ unread: 1 }]);
    expect(store.completedInputs('main', 1)).toEqual([]);
    const remaining = store.read('alice', 'main', 'new-read', { target: 'group-a' });
    expect(remaining).toMatchObject({ messages: [{ id: 'valid' }] });
    expect(store.commitRead('main', 'new-read', [{ type: 'text', text: JSON.stringify(remaining) }], false, 2)).toBe(true);
    expect(store.check('alice').sources).toEqual([]);
  } finally { store.close(); rmSync(dir, { recursive: true }); }
});

it('commits product projection and its processing position together, independently of the transport ACK', () => {
  const dir=mkdtempSync(join(tmpdir(),'nano-work-checkpoint-')),path=join(dir,'inbox.db');
  let inbox=new InboxStore(path);
  const checkpoint={rootSessionId:'main',throughSeq:8,replayFrom:9,modelVersion:'finished',model:'m',contextWindow:100000};
  try {
    inbox.commitWork('child',checkpoint,[{event_id:'child:runtime:8',root_agent_id:'agent',session_id:'child',type:'turn_end',payload:{usage:{output:7}}}]);
    const through=inbox.journalSeq;
    expect(inbox.throughSeq).toBe(0);
    inbox.close();inbox=new InboxStore(path);
    expect(inbox.workCheckpoints('main')).toEqual({child:checkpoint});
    inbox.commitWork('child',checkpoint,[{event_id:'child:runtime:8',root_agent_id:'agent',session_id:'child',type:'turn_end',payload:{usage:{output:7}}}]);
    expect(inbox.journalSeq).toBe(through);
    inbox.acknowledge(through);
    expect(inbox.workCheckpoints('main').child).toEqual(checkpoint);
    expect(()=>inbox.commitWork('child',{...checkpoint,throughSeq:9},[{event_id:'invalid',root_agent_id:'agent',session_id:'child',type:'tool_end',payload:{arguments:1n}}])).toThrow();
    expect(inbox.workCheckpoints('main').child.throughSeq).toBe(8);
    expect(inbox.journalSeq).toBe(through);
  } finally {inbox.close();rmSync(dir,{recursive:true,force:true});}
});
