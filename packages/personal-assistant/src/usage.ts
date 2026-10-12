import type { RuntimePort, UsageReport } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import type { NodeStore } from './store.js';

interface Options {
  nodeId: string;
  store: NodeStore;
  runtime: RuntimePort;
  relay: {ready: boolean; request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame>};
  onError(error: unknown): void;
}

/** Durable usage delivery; an ambiguous acknowledgement retries the same native turn ID. */
export class UsageReports {
  private running?: Promise<void>;
  private readonly dirty = new Set<string>();
  private stopped = false;
  private readonly unsubscribe: () => void;
  constructor(private readonly options: Options) {
    this.unsubscribe = options.runtime.onNotification((method, value) => {
      const data = value as {sessionId: string; rootSessionId?: string; event?: {type: string}};
      if (method === 'session.event' && data.event?.type === 'turn/end')
        void this.recover(data.rootSessionId ?? data.sessionId).catch(options.onError);
    });
  }
  recover(sessionId?: string): Promise<void> {
    if (this.stopped) return Promise.resolve();
    for (const binding of this.options.store.bindings()) if (!sessionId || binding.sessionId === sessionId) this.dirty.add(binding.sessionId);
    if (this.running) return this.running;
    this.running = this.drain().finally(() => { this.running = undefined; });
    return this.running;
  }
  private async drain() {
    const {store, runtime, relay, nodeId} = this.options;
    while (this.dirty.size) {
      const sessionId = this.dirty.values().next().value!;
      this.dirty.delete(sessionId);
      const binding = store.bindings().find(binding => binding.sessionId === sessionId)!;
      const reports = await runtime.request('usage.read', {sessionId}) as UsageReport[];
      for (const report of reports) {
        const runId = `${report.sessionId}:${report.turn}`;
        store.saveUsage(runId, {node_id: nodeId, agent_id: binding.agentId, run_id: runId, status: 'completed',
          ...(!binding.conversationId.includes(':') ? {conversation_id: binding.conversationId} : {}),
          usage: report.usage, completed_at: new Date(report.time).toISOString()});
      }
    }
    if (!relay.ready) return;
    for (const report of store.pendingUsage()) {
      await relay.request('node.report', report.payload);
      store.confirmUsage(report.runId);
    }
  }
  async stop() {
    this.stopped = true;
    this.unsubscribe();
    await this.running;
  }
}
