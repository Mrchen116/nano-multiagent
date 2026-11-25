import { expect,it } from 'vitest';
import { personalFixture } from './personal-fixture.js';
import { personalInputContext } from '../src/personal-input-context.js';

it.each(['interaction','quoted'])('freezes input context at source order and supplements only an accessible direct reply (%s)',kind=>{
 const {ctx,db,service,principal,args}=personalFixture();
 {
  const messages=Array.from({length:24},(_,i)=>ctx.messaging.insertMessage('peer',i%2?'u1':'u2','user',`message ${i}`));
  const current=ctx.messaging.insertMessage('peer','u2','user','current');
  if(kind==='quoted') db.prepare('UPDATE messages SET reply_to_json=? WHERE id=?').run(JSON.stringify({message_id:messages[0].id,sender:{type:'user',id:'u2'},content:'message 0',attachments:[]}),current.id);
  else db.prepare('UPDATE messages SET interaction_reply_json=? WHERE id=?').run(JSON.stringify({source_message_id:messages[0].id}),current.id);
  ctx.messaging.insertMessage('peer','u1','user','future context must stay out');
  const binding=service.authority(principal,args);
  const result=personalInputContext(db,current.id,m=>service.sourceAllowed(binding,m.conversation_id),m=>service.messageEvidence(binding,m));
  expect(result.current.content).toBe('current');
  expect(result.previous.map((m:any)=>m.content)).toEqual(Array.from({length:20},(_,i)=>`message ${i+4}`));
  expect(result.reply_target.id).toBe(messages[0].id);expect(result.omissions).toContainEqual({reason:'history_window',limit:20});
  const unavailable=personalInputContext(db,current.id,m=>m.id!==messages[0].id,m=>service.messageEvidence(binding,m));
  expect(unavailable.reply_target).toBeUndefined();expect(unavailable.omissions).toContainEqual({reason:'reply_target_unavailable',message_id:messages[0].id});
  expect(()=>personalInputContext(db,current.id,()=>false,m=>m)).toThrow('not accessible');
 }
});

it('builds compact batch timeline context, caps interleaved context at 20, deduplicates reply_targets and isolates unavailable messages', async () => {
  const { ctx, db, service, principal, args } = personalFixture();
  const agentUser = ctx.messaging.agentUser('a');
  db.prepare("INSERT INTO conversations(id,title,type,created_at) VALUES('grp','Product Group','group',?)").run(new Date().toISOString());
  for (const id of ['u1', 'u2', agentUser.id]) {
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('grp',?)").run(id);
  }
  const earlyQuote = ctx.messaging.insertMessage('grp', 'u1', 'user', 'Early owner baseline decision');
  for (let i = 0; i < 22; i++) {
    ctx.messaging.insertMessage('grp', i % 2 ? 'u1' : 'u2', 'user', `history ${i}`);
  }
  const firstPending = ctx.messaging.insertMessage('grp', 'u2', 'user', 'First pending peer update');
  db.prepare('UPDATE messages SET reply_to_json=? WHERE id=?').run(
    JSON.stringify({ message_id: earlyQuote.id, sender: { type: 'user', id: 'u1' }, content: earlyQuote.content, attachments: [] }),
    firstPending.id,
  );
  // Insert 22 interleaved owner context messages (>20 limit), one carrying an image attachment.
  const interleavedIds: string[] = [];
  for (let i = 0; i < 22; i++) {
    const attachment = i === 21 ? [{ id: 'att1', url: '/img/spec.png', content_type: 'image/png', file_name: 'spec.png' }] : [];
    interleavedIds.push(ctx.messaging.insertMessage('grp', 'u1', 'user', `owner context ${i}`, attachment).id);
  }
  // Block u2 to verify actor_risk is attached on pending items.
  service.blockContact(service.binding('o1')!, 'u2');
  const secondPending = ctx.messaging.insertMessage('grp', 'u2', 'user', `<mention type="user" target_id="${agentUser.id}"/> Second pending quoting same baseline`);
  db.prepare('UPDATE messages SET reply_to_json=? WHERE id=?').run(
    JSON.stringify({ message_id: earlyQuote.id, sender: { type: 'user', id: 'u1' }, content: earlyQuote.content, attachments: [] }),
    secondPending.id,
  );
  const futureMsg = ctx.messaging.insertMessage('grp', 'u1', 'user', 'Future message after batch');

  const batch = await service.handle(principal, 'pa.input.context', {
    ...args,
    conversation_id: 'grp',
    source_message_ids: [secondPending.id, 'missing_msg_id', firstPending.id],
  });
  expect(batch.source_allowed).toBe(true);
  expect(batch.unavailable_message_ids).toEqual(['missing_msg_id']);
  expect(batch.conversation).toEqual({ id: 'grp', type: 'group', delivery: 'participant', channel: 'web' });
  expect(batch.previous).toHaveLength(20);
  expect(batch.previous[0]).not.toHaveProperty('conversation_id');
  expect(batch.previous[0]).not.toHaveProperty('delivery');
  expect(batch.previous[0]).not.toHaveProperty('attachments');
  expect(batch.omissions).toContainEqual({ reason: 'history_window', limit: 20 });
  expect(batch.omissions).toContainEqual({ reason: 'timeline_window', limit: 20 });
  // 2 pending targets + 20 kept interleaved context messages = 22 timeline entries; first 2 interleaved were dropped.
  expect(batch.timeline).toHaveLength(22);
  expect(batch.timeline.map((m: any) => m.id)).not.toContain(interleavedIds[0]);
  expect(batch.timeline.map((m: any) => m.id)).not.toContain(interleavedIds[1]);
  expect(batch.timeline.map((m: any) => m.id)).not.toContain(futureMsg.id);
  expect(batch.timeline[0]).toMatchObject({ id: firstPending.id, needs_decision: true, reply_to: { message_id: earlyQuote.id }, actor_risk: { status: 'blocked' } });
  expect(batch.timeline.at(-2)).toMatchObject({ id: interleavedIds[21], needs_decision: false, sender: { is_owner: true }, attachments: [{ content_type: 'image/png', file_name: 'spec.png' }] });
  expect(batch.timeline.at(-1)).toMatchObject({ id: secondPending.id, needs_decision: true, addressed_to_agent: true, explicit_mentioned_agent_ids: ['a'] });
  expect(batch.reply_targets).toHaveLength(1);
  expect(batch.reply_targets[0].id).toBe(earlyQuote.id);

  // All requested IDs missing while conversation remains allowed returns empty timeline without throwing.
  const emptyTargets = await service.handle(principal, 'pa.input.context', {
    ...args,
    conversation_id: 'grp',
    source_message_ids: ['gone_1', 'gone_2'],
  });
  expect(emptyTargets).toMatchObject({
    source_allowed: true,
    unavailable_message_ids: ['gone_1', 'gone_2'],
    previous: [],
    timeline: [],
  });

  // Excluded conversation returns source_allowed: false without throwing.
  const currentRev = service.policy('binding').revision;
  service.updatePolicy('o1', { expected_revision: currentRev, excluded_conversation_ids: ['grp'] });
  const revoked = await service.handle(principal, 'pa.input.context', {
    ...args,
    conversation_id: 'grp',
    source_message_ids: [firstPending.id],
  });
  expect(revoked).toEqual({ source_allowed: false });
});
