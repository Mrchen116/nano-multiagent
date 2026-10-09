import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { AgentConfiguration, RuntimePort } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { KnowledgeUpdates } from '../src/knowledge.js';

it('recovers committed background changes, enables explicit empty selections and retries only unacknowledged notices', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-knowledge-product-'));
  const store = new NodeStore(join(home, 'node.db'), 'owner'); const inbox = new InboxStore(join(home, 'inbox.db'));
  store.bind({ sessionId: 'original', agentId: 'a', conversationId: 'original-chat', ownerId: 'owner', cwd: home, revision: '1' });
  store.bind({ sessionId: 'later', agentId: 'a', conversationId: 'later-chat', ownerId: 'owner', cwd: home, revision: '1' });
  const agent: AgentConfiguration = { agentId: 'a', workspace: home, revision: '1', mode: 'single_thread', provider: 'test', model: 'test', skillSelection: { mode: 'explicit_allowlist', names: [] } };
  const facts = [{ id: 'write', agentId: 'a', rootSessionId: 'original', sessionId: 'child', reviewId: 'review', turn: 1, kind: 'skills', action: 'create', name: 'new-skill', scope: 'agent', skill_root: join(home, '.nanoassistant/skills') }];
  let status = 'running'; let fail = true; const notices: Record<string, unknown>[] = []; const enables: unknown[] = [];
  const runtime: RuntimePort = { onNotification: () => () => {}, request: async method => {
    if (method === 'knowledge.facts') return { facts: [...facts], reviews: [{ id: 'review', status }] };
    if (method === 'knowledge.acknowledge') facts.splice(0); return {};
  } };
  const options = { nodeId: 'node', agents: [agent], runtime, store, inbox, onError: () => {}, im: async (path: string, init?: RequestInit) => {
    if (path.endsWith('source=mirror')) return { skills: [], profile_version: 7 };
    enables.push(JSON.parse(String(init?.body))); agent.skillSelection!.names.push('new-skill'); return {};
  }, relay: { request: async (_type: string, payload: Record<string, unknown>) => {
    notices.push(payload); if (fail) throw new Error('Disconnected before receipt'); return { type: 'ack', payload: { message_id: 'notice-1' } };
  } } };
  let updates = new KnowledgeUpdates(options);
  try {
    await updates.recover(); expect(notices).toHaveLength(0); expect(enables).toHaveLength(0);
    status = 'completed'; await updates.recover(); expect(facts).toHaveLength(1);
    expect(enables).toEqual([{ skills: ['new-skill'], profile_version: 7 }]);
    await updates.stop(); updates = new KnowledgeUpdates(options); fail = false;
    await updates.recover(); expect(facts).toHaveLength(0); expect(enables).toHaveLength(1);
    expect(notices).toHaveLength(2); expect(notices[0]).toEqual(notices[1]);
    expect(notices[0]).toMatchObject({ node_id: 'node', conversation_id: 'original-chat', system_notice: { updated_targets: ['skills'] } });
  } finally { await updates.stop(); inbox.close(); store.close(); await rm(home, { recursive: true, force: true }); }
});
