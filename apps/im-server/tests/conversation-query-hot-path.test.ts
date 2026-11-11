import { expect, it, vi } from 'vitest';
import { Work } from '../src/work.js';
import { personalFixture } from './personal-fixture.js';

function fixture(personal: boolean) {
  const f = personalFixture();
  if (!personal) {
    f.db.prepare('DELETE FROM pa_policies').run();
    f.db.prepare('DELETE FROM personal_agent_bindings').run();
  }
  f.db.prepare("UPDATE agent_profiles SET work_mode='global' WHERE agent_id='a'").run();
  const work = new Work(f.ctx);
  work.register('a', 'main', 'n', { scope: 'global_main', title: 'Agent' });
  work.register('a', 'child', 'n', { scope: 'subagent', parent_session_id: 'main', title: 'Child' });
  const message = f.ctx.messaging.insertMessage('chat', 'u1', 'user', 'needle');
  const listing = vi.spyOn(f.ctx.messaging, 'conversations');
  const sources = vi.spyOn(f.service, 'sourceConversations');
  const query = (args: Record<string, unknown>) => work.query(f.principal, { agent_id: 'a', session_id: 'main', ...args });
  return { ...f, work, query, message, listing, sources };
}

it.each([false, true])('reads only requested chats without discovery (personal=%s)', personal => {
  const { query, message, listing, sources } = fixture(personal);
  expect(query({ action: 'info', target: 'chat' })).toMatchObject({ target: 'chat', name: 'Chat' });
  expect(query({ action: 'describe', targets: ['chat'] }).conversations.map((c: any) => c.target)).toEqual(['chat']);
  expect(query({ action: 'describe', targets: [] }).conversations).toEqual([]);
  expect(query({ action: 'read', target: 'chat' }).messages.map((m: any) => m.message_id)).toEqual([message.id]);
  expect(query({ action: 'search', target: 'chat', query: 'needle' }).messages.map((m: any) => m.message_id)).toEqual([message.id]);
  expect(listing).not.toHaveBeenCalled();
  expect(sources).not.toHaveBeenCalled();
});

it.each(['single_thread', 'global'])('projects current execution nodes only for authorized group members (%s)', mode => {
  const { db, query } = fixture(false);
  db.prepare("UPDATE agent_profiles SET work_mode=? WHERE agent_id='a'").run(mode);
  db.prepare("UPDATE conversations SET type='group',visibility='public' WHERE id='chat'").run();
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('remote','o2','Node','offline'),('unnamed','o2','unnamed','online')").run();
  for (const [id, owner, node] of [['near', 'o1', 'n'], ['far', 'o2', 'remote'], ['unlabelled', 'o2', 'unnamed'], ['private-peer', 'o2', 'remote']]) {
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?,datetime('now'))")
      .run(id, `agent:${id}`, id, owner);
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,created_at,updated_at) VALUES(?,?,?,?,datetime('now'),datetime('now'))")
      .run(id, owner, node, id);
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)").run(id);
  }
  db.prepare(`INSERT INTO personal_agent_bindings VALUES
    ('owner-pa','o1','u1','near','n',1,'owner-direct','Near','create','active',NULL,datetime('now')),
    ('peer-pa','o2','u2','private-peer','remote',1,'peer-direct','Peer','create','active',NULL,datetime('now'))`).run();
  const info = { action: 'info', target: 'chat' };
  expect(query(info).members.every((member: any) => !member.execution_node)).toBe(true);
  const members = query({ ...info, include_execution_nodes: true }).members;
  expect(members).toEqual(expect.arrayContaining([
    expect.objectContaining({ user_id: 'near', execution_node: { id: 'n', name: 'Node' } }),
    expect.objectContaining({ user_id: 'far', execution_node: { id: 'remote', name: 'Node' } }),
    expect.objectContaining({ user_id: 'unlabelled', execution_node: { id: 'unnamed' } }),
  ]));
  expect(members.find((member: any) => member.user_id === 'private-peer')).not.toHaveProperty('execution_node');
  db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='a1'").run();
  expect(query({ ...info, include_execution_nodes: true }).members.every((member: any) => !member.execution_node)).toBe(true);
});

it('retains the owner observer title in a targeted PA history read', () => {
  const { db, ctx, query, listing, sources } = fixture(true);
  db.prepare("DELETE FROM conversation_participants WHERE conversation_id='peer' AND user_id='u1'").run();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer','a1')").run();
  ctx.messaging.insertMessage('peer', 'u2', 'user', 'needle');
  const expected = ctx.messaging.conversation('peer', 'u1');
  expect(expected.is_observer).toBe(true);
  expect(expected.title).not.toBe('Peer');
  expect(query({ action: 'read', target: 'peer' }).messages[0].source.name).toBe(expected.title);
  expect(listing).not.toHaveBeenCalled();
  expect(sources).not.toHaveBeenCalled();
});

it.each([false, true])('retains discovery and targeted authority checks (personal=%s)', personal => {
  const { db, query, listing, sources, service, principal, args } = fixture(personal);
  const list = query({ action: 'list' });
  expect(list.conversations.some((c: any) => c.target === 'chat')).toBe(true);
  expect(query({ action: 'search', query: 'needle' }).messages).toHaveLength(1);
  if (personal) expect(query({ action: 'resolve_target', target: 'chat' }).target).toBe('chat');
  expect(listing).toHaveBeenCalled();
  if (personal) expect(sources).toHaveBeenCalled();
  listing.mockClear(); sources.mockClear();

  for (const scope of ['bad-scope', '', 12]) expect(() => query({ action: 'info', target: 'chat', scope })).toThrow('invalid scope');
  expect(() => query({ action: 'info', target: 'chat', session_id: 'child' })).toThrow('scope_not_allowed');
  expect(() => query({ action: 'info', target: 'chat', session_id: 'missing' })).toThrow('scope_not_allowed');
  if (personal) {
    expect(() => query({ action: 'info', target: 'chat', binding_id: 'other' })).toThrow('personal_binding_not_authorized');
    const command = service.ctx.messaging.insertMessage('chat', 'u1', 'user', 'Do not read peer');
    service.sources(principal, { ...args, action: 'exclude', conversation_id: 'peer', source_message_id: command.id, expected_revision: 1 });
    expect(() => query({ action: 'info', target: 'peer' })).toThrow('target_not_accessible');
    listing.mockClear(); sources.mockClear();
  }
  db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat'").run();
  expect(() => query({ action: 'info', target: 'chat' })).toThrow('target_not_accessible');
  db.prepare("UPDATE users SET membership_status='disabled',personal_space_enabled=0 WHERE id='u1'").run();
  expect(() => query({ action: 'info', target: 'chat' })).toThrow();
  expect(listing).not.toHaveBeenCalled();
  expect(sources).not.toHaveBeenCalled();
});
