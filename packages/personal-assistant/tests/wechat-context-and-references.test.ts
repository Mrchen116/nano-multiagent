import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';
import { expect, it } from 'vitest';
import { sourceInstant } from '../src/attention.js';
import { ExternalChannels } from '../src/external.js';
import { GlobalAgent } from '../src/global-agent.js';
import { InboxStore } from '../src/inbox.js';
import { SingleThread } from '../src/single-thread.js';
import { NodeStore } from '../src/store.js';

const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

it('projects <=8-char a_xxxxxx references for external attachments on SingleThread and non-PA Global without leaking raw external keys', async () => {
  const store = new NodeStore(':memory:', 'owner');
  const inbox = new InboxStore(':memory:');
  const submitted: { content: { type: string; text?: string }[] }[] = [];

  const singleCfg: AgentConfiguration = {
    agentId: 'writer',
    mode: 'single_thread',
    workspace: '/tmp/writer',
    revision: '1',
    provider: 'mock',
    model: 'mock-1',
  };
  const globalCfg: AgentConfiguration = {
    agentId: 'coord',
    mode: 'global',
    workspace: '/tmp/coord',
    revision: '1',
    provider: 'mock',
    model: 'mock-1',
  };

  let external!: ExternalChannels;
  const single = new SingleThread({
    nodeId: 'n1',
    ownerId: 'owner',
    agents: [singleCfg],
    store,
    runtime: {
      onNotification: () => () => {},
      request: async (method, params) => {
        if (method === 'session.submit') {
          submitted.push(params as { content: { type: string; text?: string }[] });
          return { accepted: true, durable: true };
        }
        if (method === 'session.lookup') return { accepted: false };
        if (method === 'session.observe') return { durable: true, events: [], modelRuns: [] };
        return {};
      },
    },
    relay: { request: (t, p) => external.request(t, p) },
    image: async (url, agentId) => external.image(url, agentId).data.toString('base64'),
    onError: err => { throw err; },
  });
  const global = new GlobalAgent({
    nodeId: 'n1',
    ownerId: 'owner',
    agents: [globalCfg],
    store,
    inbox,
    runtime: {
      onNotification: () => () => {},
      request: async method => (method === 'session.work.children' ? { children: [] } : { events: [], durable: true, status: 'idle' }),
    },
    relay: { ready: false, request: (t, p) => external.request(t, p) },
    image: async (url, agentId) => external.image(url, agentId).data.toString('base64'),
    onError: err => { throw err; },
  });
  external = new ExternalChannels(':memory:', {
    nodeId: 'n1',
    ownerId: 'owner',
    store,
    globalAgent: id => id === 'coord',
    relay: { ready: false, request: async type => ({ type: 'ack', payload: { message_type: type } }) },
    im: async () => { throw new Error('offline'); },
    receive: async input => {
      if (input.agent_id === 'coord') await global.receive(input);
      else await single.receive(input);
    },
    permission: async () => {},
    onError: err => { throw err; },
  });

  for (const id of ['writer', 'coord']) {
    external.add(id, {
      supportsReactions: false,
      supportsCards: false,
      config: { appId: `bot_${id}`, botOpenId: `bot_${id}`, ownerOpenId: 'wxid_owner' },
      send: async () => 'wx_out_1',
      reaction: async () => undefined,
      image: async () => ({ data: TINY_PNG, mediaType: 'image/png' }),
      updateCard: async () => {},
    }, 'wechat');
  }

  try {
    const richMsg = {
      messageId: 'wx_media_1',
      chatId: 'wxid_owner',
      senderId: 'wxid_owner',
      isGroup: false as const,
      mentioned: true as const,
      time: '1760000000000',
      parts: [
        { type: 'text' as const, text: '第一段说明' },
        { type: 'text' as const, text: '第二段卡片' },
        { type: 'image' as const, key: 'img_0', data: TINY_PNG, mediaType: 'image/png', fileName: 'photo.png' },
        { type: 'file' as const, key: 'voice_1', data: Buffer.from('RIFF'), mediaType: 'audio/wav', fileName: 'voice.wav' },
      ],
    };
    await external.receive('writer', richMsg, 'wechat');
    const singleText = submitted[0]!.content.filter(p => p.type === 'text').map(p => p.text).join('');
    expect(singleText).toContain('source: WeChat.');
    expect(singleText).toContain('第一段说明\n\n第二段卡片');
    expect(singleText).toMatch(/\[Image attachment_id=a_[0-9a-f]{6} \(photo\.png\)\]/);
    expect(singleText).toMatch(/\[Attachment: voice\.wav \(audio\/wav\), attachment_id=a_[0-9a-f]{6} — call download_attachment to save locally\]/);

    await external.receive('coord', richMsg, 'wechat');
    const rootBinding = store.bindingFor('coord', 'global:coord')!;
    const check = await global.call({
      method: 'inbox',
      args: { action: 'check' },
      operationId: 'op-check',
      callId: 'c-check',
      sessionId: rootBinding.sessionId,
      rootSessionId: rootBinding.sessionId,
      agentId: 'coord',
      ownerId: 'owner',
    }) as { sources: { target: string }[] };
    const targetRef = check.sources[0]!.target;
    expect(targetRef).toMatch(/^f_[0-9a-f]{6}$/);

    const readPage = await global.call({
      method: 'inbox',
      args: { action: 'read', target: targetRef },
      operationId: 'op-read',
      callId: 'c-read',
      sessionId: rootBinding.sessionId,
      rootSessionId: rootBinding.sessionId,
      agentId: 'coord',
      ownerId: 'owner',
    }) as { messages: { id: string; content: Record<string, unknown>[] }[] };
    const blocks = readPage.messages.flatMap(m => m.content);
    const textBlock = blocks.find(b => b.type === 'text')!;
    expect(String(textBlock.text)).toBe('第一段说明\n\n第二段卡片');
    const fileBlock = blocks.find(b => b.file_name === 'voice.wav')!;
    const imgBlock = blocks.find(b => b.file_name === 'photo.png')!;
    expect(fileBlock.attachment_id).toMatch(/^a_[0-9a-f]{6}$/);
    expect(fileBlock.url).toBeUndefined();
    expect(imgBlock.attachment_id).toMatch(/^a_[0-9a-f]{6}$/);
    expect(typeof imgBlock.url).toBe('string');

    // Agent reply in external shadow chat retains created_at timestamp in sourceInstant (CTX-F3).
    const agentShadowReply: RelayInput = {
      agent_id: 'coord',
      conversation_id: 'c_shadow',
      relay_task_id: 'obs-1',
      idempotency_key: 'obs-1',
      metadata: { channel: 'wechat', conversation_type: 'direct' },
      message: {
        id: 'm_agent_1',
        content: 'Agent reply',
        sender_type: 'agent',
        sender_user_id: 'u_agent',
        created_at: '2026-07-15T08:00:00.000Z',
        attachments: [],
      },
    };
    expect(sourceInstant(agentShadowReply)).toBe(Date.parse('2026-07-15T08:00:00.000Z'));
  } finally {
    await external.stop();
    await global.stop();
    inbox.close();
    store.close();
  }
});
