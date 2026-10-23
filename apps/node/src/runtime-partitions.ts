import type { AgentConfiguration, RuntimePort, SessionBinding } from '@nano/product-contracts';

export interface PartitionRuntime extends RuntimePort {
  readonly available: boolean;
  handle(method: string, handler: (params: unknown) => unknown | Promise<unknown>): void;
  start(): Promise<void>;
  shutdown(): Promise<void>;
}
export interface RuntimePartition {
  key: string;
  agents: AgentConfiguration[];
  runtime: PartitionRuntime;
  generation: number;
}
interface Options {
  agents: AgentConfiguration[];
  bindings(): SessionBinding[];
  create(partition: RuntimePartition): PartitionRuntime;
  onError(error: unknown): void;
}
const object = (value: unknown) => value && typeof value === 'object' ? value as Record<string, unknown> : {};

/** Routes trusted product identities to independent official DSH hosts.
 *
 * Collection RPCs deliberately require scoped ports: an ACK never searches hosts.
 */
export class RuntimePartitions implements RuntimePort {
  readonly partitions = new Map<string, RuntimePartition>();
  private readonly agents = new Map<string, RuntimePartition>();
  private readonly sessions = new Map<string, RuntimePartition>();
  private readonly observers = new Map<string, { partition: RuntimePartition; generation: number }>();
  private readonly approvals = new Map<string, RuntimePartition>();
  private readonly handlers = new Map<string, (params: unknown) => unknown | Promise<unknown>>();
  private readonly listeners = new Set<(method: string, params: unknown) => void>();
  private readonly starting = new Map<string, Promise<void>>();
  private started = false;
  constructor(private readonly options: Options) {
    this.create('ordinary');
    for (const config of options.agents) this.assign(config);
    for (const binding of options.bindings()) this.sessions.set(binding.sessionId, this.forAgent(binding.agentId));
  }
  static key(config: AgentConfiguration): string { return config.personal ? `personal:${config.personal.bindingId}:${config.personal.epoch}` : 'ordinary'; }
  get available() { return [...this.partitions.values()].every(partition => partition.runtime.available); }
  availableFor(agentId: string) { return this.agents.get(agentId)?.runtime.available === true; }
  forAgent(agentId: string): RuntimePartition {
    const partition = this.agents.get(agentId);
    if (!partition) throw new Error(`Unknown runtime Agent: ${agentId}`);
    return partition;
  }
  scoped(partition: RuntimePartition, generation?: number): RuntimePort {
    const current = () => {
      if (generation !== undefined && generation !== partition.generation) throw new Error('Runtime generation_changed');
    };
    return {
      capture: () => this.scoped(partition, generation ?? partition.generation),
      request: async (method, params) => {
        current();
        const value = object(params);
        if (['knowledge.facts', 'knowledge.acknowledge', 'workflow.pending', 'workflow.acknowledge'].includes(method)) {
          const result = await partition.runtime.request(method, params);
          current();
          if (method === 'knowledge.facts') for (const fact of (object(result).facts ?? []) as unknown[]) this.validateOrigin(partition, fact);
          if (method === 'workflow.pending') for (const record of result as unknown[]) this.validateOrigin(partition, record);
          return result;
        }
        if (this.resolve(value) !== partition) throw new Error('Cross-partition scoped request');
        const result = await this.request(method, params);
        current();
        return result;
      },
      onNotification: listener => partition.runtime.onNotification((method, value) => {
        try { if(this.validateOrigin(partition, value, true)) listener(method, value); } catch (error) { this.options.onError(error); }
      }),
    };
  }
  /** Invalidate ephemeral observers on a crash; durable bindings retain their host. */
  unavailable(partition: RuntimePartition): string[] {
    partition.generation++;
    const closed: string[] = [];
    for (const [id, observer] of this.observers) if (observer.partition === partition) { this.observers.delete(id); closed.push(id); }
    for (const [id, owner] of this.approvals) if (owner === partition) this.approvals.delete(id);
    return closed;
  }
  onNotification(listener: (method: string, params: unknown) => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  handle(method: string, handler: (params: unknown) => unknown | Promise<unknown>) {
    this.handlers.set(method, handler);
    for (const partition of this.partitions.values()) this.attachHandler(partition, method, handler);
  }
  async start(): Promise<void> {
    this.started = true;
    await this.startPartition(this.partitions.get('ordinary')!);
    // One unavailable PA must not prevent unrelated Agents from starting.
    await Promise.all([...this.partitions.values()].filter(p => p.key !== 'ordinary').map(p => this.startPartition(p).catch(this.options.onError)));
  }
  async shutdown() { await Promise.all([...this.partitions.values()].map(p => p.runtime.shutdown())); }
  private async startPartition(partition: RuntimePartition): Promise<void> {
    if (partition.runtime.available) return;
    const prior = this.starting.get(partition.key); if (prior) return prior;
    const task = partition.runtime.start().finally(() => this.starting.delete(partition.key));
    this.starting.set(partition.key, task); return task;
  }
  private create(key: string): RuntimePartition {
    const partition = { key, agents: [], generation: 0 } as unknown as RuntimePartition;
    partition.runtime = this.options.create(partition);
    this.partitions.set(key, partition);
    for (const [method, handler] of this.handlers) this.attachHandler(partition, method, handler);
    partition.runtime.onNotification((method, value) => {
      try {
        if(!this.validateOrigin(partition, value, true)) return;
        const data = object(value);
        if (method === 'approval.request' && typeof data.requestId === 'string') this.approvals.set(data.requestId, partition);
        if (method === 'approval.resolved' && typeof data.requestId === 'string') this.approvals.delete(data.requestId);
        for (const listener of this.listeners) listener(method, value);
      } catch (error) { this.options.onError(error); }
    });
    return partition;
  }
  private assign(config: AgentConfiguration): RuntimePartition {
    const key = RuntimePartitions.key(config);
    const prior = this.agents.get(config.agentId);
    if (prior && prior.key !== key) throw new Error('Personal binding and runtime epoch are immutable; retire the binding before replacement');
    const partition = prior ?? this.partitions.get(key) ?? this.create(key);
    if (config.personal && partition.agents.some(agent => agent.agentId !== config.agentId)) throw new Error('Personal runtime may contain only its bound Agent');
    const index = partition.agents.findIndex(agent => agent.agentId === config.agentId);
    if (index === -1) partition.agents.push(config); else partition.agents[index] = config;
    this.agents.set(config.agentId, partition); return partition;
  }
  private resolve(value: Record<string, unknown>): RuntimePartition {
    const agentIds = [value.agentId, value.rootAgentId].filter((id): id is string => typeof id === 'string');
    const sessionIds = [value.rootSessionId, value.sessionId].filter((id): id is string => typeof id === 'string');
    const targets = agentIds.map(id => this.forAgent(id));
    for (const id of sessionIds) {
      let target = this.sessions.get(id);
      if (!target) { const binding = this.options.bindings().find(binding => binding.sessionId === id); if (binding) { target = this.forAgent(binding.agentId); this.sessions.set(id, target); } }
      if (target) targets.push(target);
      else if (!targets.length) throw new Error('Session has no trusted runtime binding');
    }
    if (!targets.length || targets.some(target => target !== targets[0])) throw new Error('Missing or conflicting runtime identity');
    return targets[0]!;
  }
  private validateOrigin(partition: RuntimePartition, params: unknown, notification = false): boolean {
    const data = object(params);
    if (typeof data.agentId === 'string' && this.forAgent(data.agentId) !== partition) throw new Error('Runtime forged another Agent identity');
    const rootId = data.rootSessionId ?? data.parentSessionId;
    if (typeof rootId === 'string') {
      const root = this.resolve({ sessionId: rootId });
      if (root !== partition) throw new Error('Runtime forged another root identity');
      if (typeof data.sessionId === 'string') {
        const existing = this.sessions.get(data.sessionId);
        if (existing && existing !== partition) throw new Error('Child Session identity collision');
        this.sessions.set(data.sessionId, partition);
      }
    }
    if (typeof data.ownerId === 'string' && partition.agents.some(agent => agent.personal && agent.personal.ownerId !== data.ownerId)) throw new Error('Runtime forged personal owner identity');
    if (typeof data.sessionId === 'string') {
      const target = this.sessions.get(data.sessionId);
      if (target && target !== partition) throw new Error('Runtime forged another Session identity');
      // Child creation emits status before its first root-linked event. Do not
      // forward unbound child notifications until lineage has been established.
      if (!target) { if(notification) return false; throw new Error('Runtime notification has no trusted Session lineage'); }
    }
    return true;
  }
  private attachHandler(partition: RuntimePartition, method: string, handler: (params: unknown) => unknown | Promise<unknown>) {
    partition.runtime.handle(method, async params => { this.validateOrigin(partition, params); return handler(params); });
  }
  async request(method: string, params: unknown): Promise<unknown> {
    const value = object(params);
    if (['knowledge.facts', 'knowledge.acknowledge', 'workflow.pending', 'workflow.acknowledge'].includes(method)) throw new Error('Collection operations require a scoped runtime port');
    if (method === 'update.prepare') {
      const prepared: RuntimePartition[] = [];
      try {
        for (const partition of this.partitions.values()) {
          prepared.push(partition);
          const result = await partition.runtime.request(method, params) as {ready: boolean};
          if (!result.ready) throw new Error('A runtime is busy');
        }
        return {ready: true};
      } catch { await Promise.allSettled(prepared.map(p => p.runtime.request('update.release', params))); return {ready: false}; }
    }
    if (method === 'update.release') { await Promise.all([...this.partitions.values()].filter(p => p.runtime.available).map(p => p.runtime.request(method, params))); return {released: true}; }
    if (method.startsWith('model.setup.')) {
      const ordinary = this.partitions.get('ordinary')!;
      if (method === 'model.setup.stage' && !this.available) throw new Error('A runtime is unavailable for model configuration');
      const result = await ordinary.runtime.request(method, params);
      if (['model.setup.stage', 'model.setup.restore'].includes(method)) {
        for (const partition of this.partitions.values()) if (partition !== ordinary && (method !== 'model.setup.restore' || partition.runtime.available)) await partition.runtime.request(method, params);
      }
      if (method === 'model.setup.finish') {
        const snapshot = await ordinary.runtime.request('model.setup.snapshot', {});
        for (const partition of this.partitions.values()) if (partition !== ordinary && partition.runtime.available) { await partition.runtime.request(method, params); await partition.runtime.request('model.setup.sync', snapshot); }
      }
      return result;
    }
    if (method === 'approval.answer') {
      const partition = this.approvals.get(String(value.requestId));
      if (!partition) throw new Error('Unknown approval request');
      return partition.runtime.request(method, params);
    }
    if (method.startsWith('trajectory.') && method !== 'trajectory.prepare') {
      const observer = this.observers.get(String(value.observerId));
      if (!observer || observer.generation !== observer.partition.generation) throw new Error('trajectory generation_changed');
      if (method === 'trajectory.close') this.observers.delete(String(value.observerId));
      return observer.partition.runtime.request(method, params);
    }
    let partition: RuntimePartition;
    if (method === 'configuration.apply' || method === 'configuration.prepare') {
      const candidate = (method === 'configuration.prepare' ? value.config : params) as AgentConfiguration;
      partition = this.assign(candidate);
      if (this.started && !partition.runtime.available) await this.startPartition(partition);
    } else if (['configuration.preview', 'configuration.catalog'].includes(method) && value.config) {
      const candidate = value.config as AgentConfiguration;
      partition = candidate.personal ? this.forAgent(candidate.agentId) : this.partitions.get('ordinary')!;
    } else partition = this.resolve(value);
    if (method === 'session.ensure') {
      const id = String(value.sessionId);
      const existing = this.sessions.get(id);
      if (existing && existing !== partition) throw new Error('Session runtime binding conflict');
      this.sessions.set(id, partition);
    }
    if (method === 'trajectory.prepare') {
      const id = String(value.observerId);
      if (this.observers.has(id)) throw new Error('Observer identity already in use');
      const generation = partition.generation;
      const result = await partition.runtime.request(method, params);
      if (generation !== partition.generation) throw new Error('trajectory generation_changed');
      this.observers.set(id, {partition, generation}); return result;
    }
    const result = await partition.runtime.request(method, params);
    if (method === 'session.fork') { const id = object(result).sessionId; if (typeof id === 'string') this.sessions.set(id, partition); }
    return result;
  }
}
