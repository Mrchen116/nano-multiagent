import { expect, it } from 'vitest';
import { InboxStore } from '../src/inbox.js';
import type { RelayInput } from '@nano/product-contracts';

it('admits only the addressed owner from a completed Global Inbox read and spends a message once', () => {
  const inbox = new InboxStore(':memory:');
  try {
    for (const [id, sender, addressed] of [
      ['a', 'owner', true],
      ['b', 'peer', true],
      ['c', 'owner', false],
    ] as const) {
      const input: RelayInput = {
        relay_task_id: id,
        agent_id: 'E',
        conversation_id: 'group',
        idempotency_key: id,
        metadata: { conversation_type: 'group', explicit_mentioned_agent_ids: addressed ? ['E'] : [] },
        message: {
          id,
          content: '把我刚复制的内容整理一下',
          sender_user_id: sender,
          sender_type: 'user',
          attachments: [],
        },
      };
      inbox.acceptRelay(input, true);
    }
    const page = inbox.read('E', 'root', 'read', { target: 'group' });
    const source = (id: string) => inbox.computerRequest('E', 'owner', 'root', 'read', id, false);
    expect(source('a')).toBeUndefined();
    inbox.commitRead('root', 'read', [{ type: 'text', text: JSON.stringify(page) }], false, 1);
    expect(source('a')).toEqual({ id: 'a', text: '把我刚复制的内容整理一下' });
    expect(source('b')).toBeUndefined();
    expect(source('c')).toBeUndefined();
    expect(inbox.claimComputerClipboard('owner', 'a')).toBe(true);
    expect(inbox.claimComputerClipboard('owner', 'a')).toBe(false);
  } finally {
    inbox.close();
  }
});
