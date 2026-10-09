import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
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
