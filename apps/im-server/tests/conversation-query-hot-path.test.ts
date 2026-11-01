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
