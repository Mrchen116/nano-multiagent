import type { AgentConfiguration, RuntimePort } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { NodeStore } from './store.js';
import type { InboxStore } from './inbox.js';

interface Fact {
  id: string; agentId: string; rootSessionId: string; sessionId: string; turn: number;
  kind: 'memory' | 'skills'; action: string; name?: string; scope?: string; skill_root?: string; reviewId?: string;
}
interface Review { id: string; status: string; agentId: string; rootSessionId: string; childSessionId?: string; kind: 'memory' | 'skills' | 'combined' | 'dreaming'; at: number; endedAt?: number; summary?: string }
interface Options {
  partitionKey?: string;
  nodeId: string; agents: AgentConfiguration[]; runtime: RuntimePort; store: NodeStore; inbox: InboxStore;
  relay: { request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  im(path: string, options?: RequestInit): Promise<unknown>;
  onError(error: unknown): void;
  onWork?(): void;
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
  /** Local knowledge notices must settle before the Node stops. */
  get busy(): boolean { return !!this.running || this.again; }
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
    const runtime = this.options.runtime.capture?.() ?? this.options.runtime;
    const { facts, reviews } = await runtime.request('knowledge.facts', {}) as { facts: Fact[]; reviews: Review[] };
    const before = this.options.inbox.journalSeq;
    for (const review of reviews) {
      const binding = this.options.store.bindings().find(item => item.sessionId === review.rootSessionId);
      if (!review.childSessionId || binding?.agentId !== review.agentId || !this.options.agents.some(agent => agent.agentId === review.agentId && agent.mode === 'global')) continue;
      // Work authorization needs only the trusted identity link. Session bodies
      // stay demand-loaded and the model's subagent catalog stays untouched.
      this.options.inbox.append({ event_id: `knowledge-run:${review.id}`, type: 'session_linked', root_agent_id: review.agentId,
        session_id: review.rootSessionId, observed_at: new Date(review.at).toISOString(), payload: {
          parent_session_id: review.rootSessionId, child_session_id: review.childSessionId,
          title: review.kind === 'dreaming' ? 'Dreaming · 自动整理记忆' : review.kind === 'combined' ? '记忆与技能复盘' : review.kind === 'memory' ? '记忆整理' : '技能复盘',
        } });
      if (review.kind === 'dreaming') {
        const identity = { root_agent_id: review.agentId, session_id: review.childSessionId, turn_id: review.id };
        this.options.inbox.append({ ...identity, event_id: `dreaming:${review.id}:start`, type: 'turn_started',
          observed_at: new Date(review.at).toISOString(), payload: { origin: 'dreaming', started_at: new Date(review.at).toISOString() } });
        if (review.endedAt && review.summary) {
          const observed_at = new Date(review.endedAt).toISOString();
          this.options.inbox.append({ ...identity, event_id: `dreaming:${review.id}:${review.endedAt}:receipt`, type: 'message', observed_at,
            payload: { message_id: `dreaming:${review.id}:receipt`, role: 'assistant', text: review.summary, source_kind: 'host_receipt' } });
          this.options.inbox.append({ ...identity, event_id: `dreaming:${review.id}:${review.endedAt}:end`, type: 'turn_end', observed_at,
            payload: { status: review.status, completed: review.status === 'completed', finished_at: observed_at } });
        }
      }
    }
    if (this.options.inbox.journalSeq > before) this.options.onWork?.();
    const groups = new Map<string, Fact[]>();
    for (const fact of facts) {
      const binding = this.options.store.bindings().find(item => item.sessionId === fact.rootSessionId);
      if (!binding || binding.agentId !== fact.agentId || !this.options.agents.some(agent => agent.agentId === fact.agentId) || !this.options.store.lifecycle.allowed(fact.agentId)) continue;
      if (fact.reviewId && reviews.find(review => review.id === fact.reviewId)?.status === 'running') continue;
      const key = fact.reviewId ?? fact.id; const group = groups.get(key) ?? []; group.push(fact); groups.set(key, group);
    }
    for (const [id, group] of groups) {
      try {
        const first = group[0]!;
        await this.options.store.lifecycle.run(first.agentId, undefined, async () => {
        const deliveryId = this.options.partitionKey ? `${this.options.partitionKey}:${id}` : id;
        if (first.reviewId) {
          const agent = this.options.agents.find(agent => agent.agentId === first.agentId); if (!agent) return;
          const targets = agent.personal ? [agent.personal.conversationId] : agent.mode === 'global' ? this.options.inbox.reviewTargets(first.rootSessionId, first.turn)
            : [this.options.store.inputForTurn(first.rootSessionId, first.turn)?.input.conversation_id ?? this.options.store.bindings().find(binding => binding.sessionId === first.rootSessionId)?.conversationId].filter((value): value is string => !!value);
          const updated = ['skills', 'memory'].filter(kind => group.some(fact => fact.kind === kind));
          if (agent.mode === 'global') this.options.inbox.append({ event_id: `knowledge:${deliveryId}`, type: 'self_evolution_review', root_agent_id: first.agentId,
            session_id: first.rootSessionId, turn_id: String(first.turn), payload: { review_id: id, updated_targets: updated }, observed_at: new Date().toISOString() });
          for (const target of targets) {
            this.options.store.lifecycle.assert(first.agentId);
            const result = await this.options.relay.request('node.system_message', { node_id: this.options.nodeId, conversation_id: target, idempotency_key: `knowledge:${deliveryId}:${target}`,
              text: `· background self-evolution review: ${updated.join(' + ')} updated`,
              system_notice: { kind: 'self_evolution_review', source_agent_id: first.agentId, updated_targets: updated } });
            if (typeof result.payload.message_id !== 'string' || !result.payload.message_id) throw new Error('Knowledge notice has no delivery receipt');
          }
        }
        this.options.store.lifecycle.assert(first.agentId);
        for (const fact of group) await runtime.request('knowledge.acknowledge', { id: fact.id });
        });
      } catch (error) { this.options.onError(error); }
    }
  }
  /** Convert legacy choices once through the existing durable configuration operation. */
  async migrateSkills() {
    for (const agent of this.options.agents) {
      if (agent.personal || agent.skillSelection?.mode === 'explicit_denylist') continue;
      try {
        const path = `/im/v1/agents/${encodeURIComponent(agent.agentId)}`;
        const profile = await this.options.im(`${path}/config?source=mirror`) as { profile_version: number; skills: string[] };
        await this.options.im(`${path}/skills/migrate`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile_version: profile.profile_version }) });
      } catch (error) {
        // Keep the legacy selection for a later reconnect, without failing runtime recovery.
        this.options.onError(error);
      }
    }
  }
  async stop() { this.stopped = true; this.unsubscribe(); await this.running; }
}
