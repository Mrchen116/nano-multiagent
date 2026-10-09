import { resolve, join } from 'node:path';
import type { AgentConfiguration, RuntimePort } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { NodeStore } from './store.js';
import type { InboxStore } from './inbox.js';

interface Fact {
  id: string; agentId: string; rootSessionId: string; sessionId: string; turn: number;
  kind: 'memory' | 'skills'; action: string; name?: string; scope?: string; skill_root?: string; reviewId?: string;
}
interface Review { id: string; status: string }
interface Options {
  nodeId: string; agents: AgentConfiguration[]; runtime: RuntimePort; store: NodeStore; inbox: InboxStore;
  relay: { request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  im(path: string, options?: RequestInit): Promise<unknown>;
  onError(error: unknown): void;
}

/** Reconciles committed knowledge facts after foreground execution has already ended. */
export class KnowledgeUpdates {
  private running?: Promise<void>;
  private again = false;
  private stopped = false;
  private readonly unsubscribe: () => void;
  constructor(private readonly options: Options) {
    this.unsubscribe = options.runtime.onNotification((method, value) => {
      if (method === 'knowledge.changed' || method === 'session.event' && (value as { event?: { type: string } }).event?.type === 'turn/end') void this.recover().catch(options.onError);
    });
  }
  recover(): Promise<void> {
    if (this.stopped) return Promise.resolve();
    this.again = true;
    if (this.running) return this.running;
    this.running = (async () => {
      while (this.again) { this.again = false; await this.reconcile(); }
    })().finally(() => { this.running = undefined; });
    return this.running;
  }
  private async reconcile() {
    const { facts, reviews } = await this.options.runtime.request('knowledge.facts', {}) as { facts: Fact[]; reviews: Review[] };
    const groups = new Map<string, Fact[]>();
    for (const fact of facts) {
      if (fact.reviewId && reviews.find(review => review.id === fact.reviewId)?.status === 'running') continue;
      const key = fact.reviewId ?? fact.id; const group = groups.get(key) ?? []; group.push(fact); groups.set(key, group);
    }
    for (const [id, group] of groups) {
      try {
        for (const fact of group) if (fact.kind === 'skills' && fact.action === 'create') await this.enable(fact);
        const first = group[0]!;
        if (first.reviewId) {
          const agent = this.options.agents.find(agent => agent.agentId === first.agentId); if (!agent) continue;
          const targets = agent.mode === 'global' ? this.options.inbox.reviewTargets(first.rootSessionId, first.turn)
            : [this.options.store.bindings().find(binding => binding.sessionId === first.rootSessionId)?.conversationId].filter((value): value is string => !!value);
          const updated = ['skills', 'memory'].filter(kind => group.some(fact => fact.kind === kind));
          if (agent.mode === 'global') this.options.inbox.append({ event_id: `knowledge:${id}`, type: 'self_evolution_review', root_agent_id: first.agentId,
            session_id: first.rootSessionId, turn_id: String(first.turn), payload: { review_id: id, updated_targets: updated }, observed_at: new Date().toISOString() });
          for (const target of targets) {
            const result = await this.options.relay.request('node.system_message', { node_id: this.options.nodeId, conversation_id: target, idempotency_key: `knowledge:${id}:${target}`,
              text: `· background self-evolution review: ${updated.join(' + ')} updated`,
              system_notice: { kind: 'self_evolution_review', source_agent_id: first.agentId, updated_targets: updated } });
            if (typeof result.payload.message_id !== 'string' || !result.payload.message_id) throw new Error('Knowledge notice has no delivery receipt');
          }
        }
        for (const fact of group) await this.options.runtime.request('knowledge.acknowledge', { id: fact.id });
      } catch (error) { this.options.onError(error); }
    }
  }
  private async enable(fact: Fact) {
    const creator = this.options.agents.find(agent => agent.agentId === fact.agentId);
    if (!creator || !fact.name || !fact.skill_root) throw new Error('Skill creation fact has no current owner');
    const root = fact.scope === 'global' ? creator.knowledge?.globalSkillRoot : join(creator.workspace, '.nanoassistant', 'skills');
    if (!root || resolve(root) !== resolve(fact.skill_root)) throw new Error('Skill creation root does not match its owner');
    const affected = fact.scope === 'global' ? this.options.agents : [creator];
    for (const agent of affected) {
      if (agent.skillSelection?.mode !== 'explicit_allowlist' || agent.skillSelection.names.includes(fact.name)) continue;
      const path = `/im/v1/agents/${encodeURIComponent(agent.agentId)}`;
      const profile = await this.options.im(`${path}/config?source=mirror`) as { profile_version: number; skills: string[] };
      await this.options.im(`${path}/skills/enable`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_version: profile.profile_version, skills: [...new Set([...profile.skills, fact.name])] }) });
      // The IM operation calls configuration.apply and returns only after runtime scope replacement.
    }
  }
  async stop() { this.stopped = true; this.unsubscribe(); await this.running; }
}
