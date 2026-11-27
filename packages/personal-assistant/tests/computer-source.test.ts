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

    // Multi-turn owner history is scoped to the exact same target and fenced by afterReads
    inbox.acceptRelay(
      {
        relay_task_id: 'other-chat-1',
        agent_id: 'E',
        conversation_id: 'other-dm',
        idempotency_key: 'other-chat-1',
        metadata: { conversation_type: 'direct', explicit_mentioned_agent_ids: [] },
        message: {
          id: 'other-chat-1',
          content: '看看「草稿 B」窗口',
          sender_user_id: 'owner',
          sender_type: 'user',
          attachments: [],
        },
      },
      true,
    );
    const otherPage = inbox.read('E', 'root', 'read-other', { target: 'other-dm' });
    inbox.commitRead('root', 'read-other', [{ type: 'text', text: JSON.stringify(otherPage) }], false, 2);

    inbox.acceptRelay(
      {
        relay_task_id: 'd',
        agent_id: 'E',
        conversation_id: 'group',
        idempotency_key: 'd',
        metadata: { conversation_type: 'group', explicit_mentioned_agent_ids: ['E'] },
        message: {
          id: 'd',
          content: '截个图发给我',
          sender_user_id: 'owner',
          sender_type: 'user',
          attachments: [],
        },
      },
      true,
    );
    const page2 = inbox.read('E', 'root', 'read-2', { target: 'group' });
    inbox.commitRead('root', 'read-2', [{ type: 'text', text: JSON.stringify(page2) }], false, 3);

    expect(inbox.computerRequest('E', 'owner', 'root', 'read-2', 'd', false)).toEqual({
      id: 'd',
      text: '截个图发给我',
      ownerContext: '把我刚复制的内容整理一下\n截个图发给我',
    });
    expect(inbox.computerRequest('E', 'owner', 'root', 'read-2', 'd', false, ['read-2'])).toEqual({
      id: 'd',
      text: '截个图发给我',
    });
  } finally {
    inbox.close();
  }
});

it('projects computer operations to Work without private input or result content', async () => {
  const { toolPresentation } = await import('../src/presentation.js');
  const call = {
    type: 'tool/call',
    seq: 1,
    time: 10,
    data: {
      name: 'computer_use',
      callId: 'call',
      arguments: JSON.stringify({ surface: 'desktop', action: 'type', input: { text: 'PRIVATE_INPUT' } }),
    },
  };
  const end = {
    type: 'tool/result',
    seq: 2,
    time: 20,
    data: { message: { toolCallId: 'call', content: [{ type: 'text', text: 'PRIVATE_RESULT' }] } },
  };
  const invalid = { ...call, data: { ...call.data, arguments: 'null' } };
  expect(toolPresentation(invalid, [invalid])?.input.action).toBe('operation');
  for (const event of [call, end]) {
    const projected = toolPresentation(event, [call, end]);
    expect(projected).toMatchObject({ name: 'computer_use', input: { surface: 'desktop', action: 'type' } });
    expect(JSON.stringify(projected)).not.toContain('PRIVATE_');
  }
});
