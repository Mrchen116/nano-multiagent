import { expect, it } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import { MAX_AGENT_ID_LENGTH, ToolReferences, splitThreadTarget } from '../src/tool-references.js';

const LONG_CONV_INTERNAL = 'conversation_uuid_1234567890abcdef';
const LONG_CONV_EXTERNAL = 'external:slack:T0123456789:C9876543210ABCDEF';
const LONG_ROOT_MSG = '12345678-90ab-cdef-1234-567890abcdef';
const LONG_REPLY_MSG = 'fedcba98-7654-3210-fedc-ba9876543210';
const LONG_QUOTE_MSG = 'aabbccdd-1122-3344-5566-77889900aabb';
const LONG_USER = 'user_uuid_0123456789abcdef0123456789';
const LONG_EXTERNAL_SENDER = 'slack_open_id_U0123456789ABCDEF999';
const LONG_CURSOR = 'eyJzbmFwc2hvdCI6IjEyMzQ1Njc4LTkwYWItY2RlZi0xMjM0LTU2Nzg5MGFiY2RlZiIsIm9mZnNldCI6MjAsInBhcnQiOjB9';
const LONG_OPERATION = 'op_uuid_9876543210fedcba9876543210';
const LONG_INCIDENT = 'incident_uuid_abcdef0123456789abcdef';

function assertAtomicMax8(label: string, id: unknown): void {
  expect(typeof id, `${label} should be a string`).toBe('string');
  const value = id as string;
  expect(value.length, `${label} (${value}) exceeds ${MAX_AGENT_ID_LENGTH} chars`).toBeGreaterThan(0);
  expect(value.length, `${label} (${value}) exceeds ${MAX_AGENT_ID_LENGTH} chars`).toBeLessThanOrEqual(MAX_AGENT_ID_LENGTH);
}

function assertTargetMax8(label: string, target: unknown): void {
  expect(typeof target, `${label} should be a string`).toBe('string');
  const { base, root } = splitThreadTarget(target as string);
  assertAtomicMax8(`${label}.base`, base);
  if (root !== undefined) assertAtomicMax8(`${label}.root`, root);
}

function assertMentionIdsMax8(label: string, text: string): void {
  for (const match of text.matchAll(/<mention\s+type="user"\s+target_id="([^"]+)"\s*\/>/g)) {
    assertAtomicMax8(`${label}.mention`, match[1]);
  }
}

it('enforces <= 8-char atomic IDs across all 6 IM tool output shapes and round-trips every argument', () => {
  expect(MAX_AGENT_ID_LENGTH).toBe(8);
  const db = new DatabaseSync(':memory:');
  try {
    const refs = new ToolReferences(db);
    const agent = 'agent-alpha';

    // 1. inbox(action="check")
    const inboxCheck = refs.result(agent, 'inbox', {
      sources: [
        { target: LONG_CONV_INTERNAL, unread: 1, mentions: 0 },
        { target: `${LONG_CONV_EXTERNAL}:${LONG_ROOT_MSG}`, parent_target: LONG_CONV_EXTERNAL, unread: 2, mentions: 1 },
      ],
    }) as any;
    assertTargetMax8('inbox.check[0].target', inboxCheck.sources[0].target);
    assertTargetMax8('inbox.check[1].target', inboxCheck.sources[1].target);
    assertTargetMax8('inbox.check[1].parent_target', inboxCheck.sources[1].parent_target);

    // 2. inbox(action="read")
    const inboxRead = refs.result(agent, 'inbox', {
      target: `${LONG_CONV_EXTERNAL}:${LONG_ROOT_MSG}`,
      thread_context: {
        target: `${LONG_CONV_EXTERNAL}:${LONG_ROOT_MSG}`,
        root_message_id: LONG_ROOT_MSG,
        root_excerpt: 'Root topic',
        earlier_replies: [{ id: LONG_QUOTE_MSG, sender: 'Alice', excerpt: 'Earlier' }],
        truncated: false,
      },
      messages: [
        {
          id: LONG_REPLY_MSG,
          sender: { id: LONG_USER, kind: 'external', source_id: LONG_EXTERNAL_SENDER, name: 'Bob' },
          reply_to: { message_id: LONG_QUOTE_MSG, sender: { id: LONG_USER, name: 'Alice' } },
          content: [{ type: 'text', text: 'Reply text' }],
        },
      ],
      incident_ref: LONG_INCIDENT,
      next_cursor: LONG_CURSOR,
    }) as any;
    assertTargetMax8('inbox.read.target', inboxRead.target);
    assertTargetMax8('inbox.read.thread_context.target', inboxRead.thread_context.target);
    assertAtomicMax8('inbox.read.thread_context.root_message_id', inboxRead.thread_context.root_message_id);
    assertAtomicMax8('inbox.read.thread_context.earlier_replies[0].id', inboxRead.thread_context.earlier_replies[0].id);
    assertAtomicMax8('inbox.read.messages[0].id', inboxRead.messages[0].id);
    assertAtomicMax8('inbox.read.messages[0].sender.id', inboxRead.messages[0].sender.id);
    assertAtomicMax8('inbox.read.messages[0].sender.source_id', inboxRead.messages[0].sender.source_id);
    assertAtomicMax8('inbox.read.messages[0].reply_to.message_id', inboxRead.messages[0].reply_to.message_id);
    assertAtomicMax8('inbox.read.incident_ref', inboxRead.incident_ref);
    assertAtomicMax8('inbox.read.next_cursor', inboxRead.next_cursor);

    // 3. conversations(action="list") and conversations(action="info")
    const convList = refs.result(agent, 'conversations', {
      conversations: [
        {
          target: LONG_CONV_INTERNAL,
          name: 'Eng',
          participants: [{ id: LONG_USER, name: 'Alice', kind: 'user' }],
        },
        {
          target: LONG_CONV_EXTERNAL,
          name: 'Slack',
          participants: [{ id: LONG_USER, name: 'Bob', kind: 'user' }],
        },
      ],
      next_cursor: LONG_CURSOR,
    }) as any;
    assertTargetMax8('conversations.list[0].target', convList.conversations[0].target);
    assertAtomicMax8('conversations.list[0].participants[0].id', convList.conversations[0].participants[0].id);
    assertTargetMax8('conversations.list[1].target', convList.conversations[1].target);
    assertAtomicMax8('conversations.list.next_cursor', convList.next_cursor);

    const convInfo = refs.result(agent, 'conversations', {
      target: LONG_CONV_INTERNAL,
      name: 'Eng',
      members: [
        { user_id: LONG_USER, name: 'Alice', type: 'user', mention: `<mention type="user" target_id="${LONG_USER}"/>` },
      ],
    }) as any;
    assertTargetMax8('conversations.info.target', convInfo.target);
    assertAtomicMax8('conversations.info.members[0].user_id', convInfo.members[0].user_id);
    assertMentionIdsMax8('conversations.info.members[0]', convInfo.members[0].mention);

    // 4. read_messages (main timeline with thread summary + thread read with thread_root)
    const readMain = refs.result(agent, 'read_messages', {
      target: LONG_CONV_INTERNAL,
      messages: [
        {
          message_id: LONG_ROOT_MSG,
          sender: { id: LONG_USER, name: 'Alice', kind: 'user' },
          source: { conversation_id: LONG_CONV_INTERNAL, target: LONG_CONV_INTERNAL, reply_target: LONG_CONV_INTERNAL },
          thread: { target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`, reply_count: 3, latest_at: '2026-11-24T00:00:00Z' },
          part_key: '0',
          total_parts: 1,
          complete_message: true,
          content: [{ type: 'text', text: 'Root post' }],
        },
      ],
      next_cursor: LONG_CURSOR,
    }) as any;
    assertTargetMax8('read_messages.main.target', readMain.target);
    assertAtomicMax8('read_messages.main.messages[0].message_id', readMain.messages[0].message_id);
    assertTargetMax8('read_messages.main.messages[0].thread.target', readMain.messages[0].thread.target);
    assertAtomicMax8('read_messages.main.next_cursor', readMain.next_cursor);

    const readThread = refs.result(agent, 'read_messages', {
      target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`,
      thread_root: {
        message_id: LONG_ROOT_MSG,
        sender: { id: LONG_USER, name: 'Alice', kind: 'user' },
        source: { conversation_id: LONG_CONV_INTERNAL, target: LONG_CONV_INTERNAL, reply_target: LONG_CONV_INTERNAL },
        content: [{ type: 'text', text: 'Root post' }],
      },
      messages: [
        {
          message_id: LONG_REPLY_MSG,
          sender: { id: LONG_USER, name: 'Bob', kind: 'user' },
          reply_to: { message_id: LONG_QUOTE_MSG },
          source: { conversation_id: LONG_CONV_INTERNAL, target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`, reply_target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}` },
          part_key: '0',
          total_parts: 1,
          complete_message: true,
          content: [{ type: 'text', text: 'Thread reply' }],
        },
      ],
      next_cursor: LONG_CURSOR,
    }) as any;
    assertTargetMax8('read_messages.thread.target', readThread.target);
    assertAtomicMax8('read_messages.thread.thread_root.message_id', readThread.thread_root.message_id);
    assertTargetMax8('read_messages.thread.messages[0].source.target', readThread.messages[0].source.target);
    assertTargetMax8('read_messages.thread.messages[0].source.reply_target', readThread.messages[0].source.reply_target);
    assertAtomicMax8('read_messages.thread.messages[0].reply_to.message_id', readThread.messages[0].reply_to.message_id);
    assertAtomicMax8('read_messages.thread.next_cursor', readThread.next_cursor);

    // 5. search_messages
    const searchRes = refs.result(agent, 'search_messages', {
      messages: [
        {
          message_id: LONG_REPLY_MSG,
          sender: { kind: 'external', source_id: LONG_EXTERNAL_SENDER, name: 'Bob' },
          source: {
            conversation_id: LONG_CONV_EXTERNAL,
            target: `${LONG_CONV_EXTERNAL}:${LONG_ROOT_MSG}`,
            reply_target: `${LONG_CONV_EXTERNAL}:${LONG_ROOT_MSG}`,
          },
          part_key: '0',
          total_parts: 1,
          complete_message: true,
          content: [{ type: 'text', text: 'Matched thread hit' }],
        },
      ],
      next_cursor: LONG_CURSOR,
    }) as any;
    assertAtomicMax8('search_messages.messages[0].message_id', searchRes.messages[0].message_id);
    assertAtomicMax8('search_messages.messages[0].sender.source_id', searchRes.messages[0].sender.source_id);
    assertTargetMax8('search_messages.messages[0].source.target', searchRes.messages[0].source.target);
    assertTargetMax8('search_messages.messages[0].source.reply_target', searchRes.messages[0].source.reply_target);
    assertAtomicMax8('search_messages.next_cursor', searchRes.next_cursor);

    // 6. threads(action="list" / "follow" / "unfollow")
    const threadsList = refs.result(agent, 'threads', {
      threads: [
        {
          target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`,
          parent_target: LONG_CONV_INTERNAL,
          parent_name: 'Eng',
          root_message_id: LONG_ROOT_MSG,
          root_excerpt: 'Root post',
          reply_count: 3,
        },
      ],
      next_cursor: LONG_CURSOR,
    }) as any;
    assertTargetMax8('threads.list[0].target', threadsList.threads[0].target);
    assertTargetMax8('threads.list[0].parent_target', threadsList.threads[0].parent_target);
    assertAtomicMax8('threads.list[0].root_message_id', threadsList.threads[0].root_message_id);
    assertAtomicMax8('threads.list.next_cursor', threadsList.next_cursor);

    // 7. Additional PA / create / review / security_incidents / external-thread split shapes
    const convCreate = refs.result(agent, 'conversations', {
      target: LONG_CONV_INTERNAL,
      name: 'New Group',
      conversation: {
        id: LONG_CONV_INTERNAL,
        creator_id: LONG_USER,
        owner_id: LONG_USER,
        participant_ids: [LONG_USER],
        participants: [{ id: LONG_USER, user_id: LONG_USER, name: 'Alice' }],
      },
    }) as any;
    assertTargetMax8('conversations.create.target', convCreate.target);
    assertAtomicMax8('conversations.create.conversation.id', convCreate.conversation.id);
    assertAtomicMax8('conversations.create.conversation.creator_id', convCreate.conversation.creator_id);
    assertAtomicMax8('conversations.create.conversation.participants[0].id', convCreate.conversation.participants[0].id);

    const inboxReview = refs.result(agent, 'inbox', {
      kind: 'denied',
      message_id: LONG_REPLY_MSG,
      incident_id: LONG_INCIDENT,
      security_incidents: [{
        incident_ref: LONG_INCIDENT,
        source_message_id: LONG_REPLY_MSG,
        actor_id: LONG_USER,
        owner_target: `conversation:${LONG_CONV_INTERNAL}`,
        peer_target: `conversation:${LONG_CONV_EXTERNAL}`,
        owner_notice_message_id: LONG_QUOTE_MSG,
        conversation: { id: LONG_CONV_EXTERNAL, name: 'Slack' },
      }],
    }) as any;
    assertAtomicMax8('inbox.review.message_id', inboxReview.message_id);
    assertAtomicMax8('inbox.review.incident_id', inboxReview.incident_id);
    assertAtomicMax8('inbox.security_incidents[0].incident_ref', inboxReview.security_incidents[0].incident_ref);
    assertAtomicMax8('inbox.security_incidents[0].source_message_id', inboxReview.security_incidents[0].source_message_id);
    assertAtomicMax8('inbox.security_incidents[0].actor_id', inboxReview.security_incidents[0].actor_id);
    assertTargetMax8('inbox.security_incidents[0].owner_target', inboxReview.security_incidents[0].owner_target);
    assertTargetMax8('inbox.security_incidents[0].peer_target', inboxReview.security_incidents[0].peer_target);
    assertAtomicMax8('inbox.security_incidents[0].conversation.id', inboxReview.security_incidents[0].conversation.id);

    const personalSources = refs.result(agent, 'personal_sources', {
      items: [{ id: LONG_CONV_INTERNAL, owner_id: LONG_USER, participants: [{ id: LONG_USER, name: 'Alice' }] }],
      policy: { excluded_conversation_ids: [LONG_CONV_EXTERNAL] },
    }) as any;
    assertAtomicMax8('personal_sources.items[0].id', personalSources.items[0].id);
    assertAtomicMax8('personal_sources.items[0].owner_id', personalSources.items[0].owner_id);
    assertAtomicMax8('personal_sources.items[0].participants[0].id', personalSources.items[0].participants[0].id);
    assertAtomicMax8('personal_sources.policy.excluded[0]', personalSources.policy.excluded_conversation_ids[0]);

    // Verify conversation: prefix is stripped even for <= 8 char IDs
    expect(refs.conversationRef(agent, 'conversation:c_22xbbh')).toBe('c_22xbbh');

    // Verify splitResolvedTarget splits resolved external:*:<root> so external-channel thread guard cannot be bypassed
    const resolvedExternalThread = refs.resolveTarget(agent, searchRes.messages[0].source.target);
    expect(refs.splitResolvedTarget(agent, resolvedExternalThread)).toEqual({
      base: LONG_CONV_EXTERNAL,
      root: LONG_ROOT_MSG,
    });

    // 8. send_message (sent & unknown operation_id)
    const sendRes = refs.result(agent, 'send_message', {
      status: 'unknown',
      target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`,
      message_id: LONG_REPLY_MSG,
      operation_id: LONG_OPERATION,
    }) as any;
    assertTargetMax8('send_message.target', sendRes.target);
    assertAtomicMax8('send_message.message_id', sendRes.message_id);
    assertAtomicMax8('send_message.operation_id', sendRes.operation_id);

    // 8. Round-trip EVERY projected ref back through ToolReferences.arguments()
    const shortExternalThread = searchRes.messages[0].source.target;
    const shortInternalThread = readThread.target;
    const shortUser = convInfo.members[0].user_id;
    const shortSenderSource = searchRes.messages[0].sender.source_id;
    const shortReplyMsg = searchRes.messages[0].message_id;
    const shortQuoteMsg = readThread.messages[0].reply_to.message_id;

    expect(refs.arguments(agent, 'read_messages', {
      target: shortInternalThread,
      around_message_id: shortReplyMsg,
      participant_id: shortUser,
      cursor: readThread.next_cursor,
    })).toEqual({
      target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`,
      around_message_id: LONG_REPLY_MSG,
      participant_id: LONG_USER,
      cursor: LONG_CURSOR,
    });

    expect(refs.arguments(agent, 'search_messages', {
      target: shortExternalThread,
      sender_source_id: shortSenderSource,
      cursor: searchRes.next_cursor,
    })).toEqual({
      target: `${LONG_CONV_EXTERNAL}:${LONG_ROOT_MSG}`,
      sender_source_id: LONG_EXTERNAL_SENDER,
      cursor: LONG_CURSOR,
    });

    expect(refs.arguments(agent, 'threads', {
      action: 'unfollow',
      target: shortInternalThread,
    })).toEqual({
      action: 'unfollow',
      target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`,
    });

    expect(refs.arguments(agent, 'send_message', {
      target: shortInternalThread,
      reply_to_message_id: shortQuoteMsg,
      receipt_of: sendRes.operation_id,
      text: `Hi ${convInfo.members[0].mention}`,
      interactive: { source: 'root = TextContent("x")', supersedes_message_id: shortReplyMsg },
    })).toEqual({
      target: `${LONG_CONV_INTERNAL}:${LONG_ROOT_MSG}`,
      reply_to_message_id: LONG_QUOTE_MSG,
      receipt_of: LONG_OPERATION,
      text: `Hi <mention type="user" target_id="${LONG_USER}"/>`,
      interactive: { source: 'root = TextContent("x")', supersedes_message_id: LONG_REPLY_MSG },
    });

    expect(refs.arguments(agent, 'send_user_message', {
      target: shortExternalThread,
      incident_ref: inboxRead.incident_ref,
      text: 'Replying as owner',
    })).toEqual({
      target: `${LONG_CONV_EXTERNAL}:${LONG_ROOT_MSG}`,
      incident_ref: LONG_INCIDENT,
      text: 'Replying as owner',
    });
  } finally {
    db.close();
  }
});
