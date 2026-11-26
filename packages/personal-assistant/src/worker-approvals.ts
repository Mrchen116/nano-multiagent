import type { ProtocolFrame } from '@nano/channels';
import type { AgentConfiguration, ChatStreamFact, RuntimePort, WorkerPermissionRequest } from '@nano/product-contracts';
import type { NodeStore } from './store.js';

interface Approval {
  requestId: string; sessionId: string; callId: string; toolName: string; reason: string;
  worker: WorkerPermissionRequest['worker']; expiresAt: number; toolInput: {arguments: Record<string, unknown>}; lifecycle_revision?: number;
}
interface Pending {
  agentId: string; revision: number; request: Approval; messageId: Promise<string | undefined>;
  terminal?: Promise<void>;
}
interface Options {
  nodeId: string; agents: AgentConfiguration[]; store: NodeStore; runtime: RuntimePort;
  relay: {request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame>};
  onError(error: unknown): void;
}

/** Delivers Worker requests to the owner's Nano IM independently of the root turn. */
export class WorkerApprovals {
  private readonly pending = new Map<string, Pending>();
  private readonly unsubscribe: () => void;

  constructor(private readonly options: Options) {
    this.unsubscribe = options.runtime.onNotification((method, value) => {
      if (method === 'approval.request') {
        const request = value as Approval;
        if (request.worker) this.open(request).catch(options.onError);
      } else if (method === 'approval.resolved') {
        const {requestId, sessionId, outcome} = value as {requestId: string; sessionId: string; outcome: string};
        const pending = this.pending.get(requestId);
        if (pending?.request.sessionId === sessionId) this.finish(pending, outcome).catch(options.onError);
      }
    });
  }

  private async open(request: Approval): Promise<void> {
    if (this.pending.has(request.requestId)) return;
    const {store, agents, runtime} = this.options;
    const binding = store.bindingForSession(request.sessionId);
    if (!binding || binding.conversationId !== `global:${binding.agentId}` ||
        !agents.some(agent => agent.agentId === binding.agentId && agent.mode === 'global')) {
      await runtime.request('approval.answer', {requestId: request.requestId, decision: 'rejected', reason: 'Worker has no active Global root binding'});
      return;
    }
    const revision = store.lifecycle.assert(binding.agentId, request.lifecycle_revision);
    const messageId = this.publish(request, binding.agentId, revision).catch(async error => {
      const pending = this.pending.get(request.requestId);
      if (pending && !pending.terminal) {
        this.pending.delete(request.requestId);
        await runtime.request('approval.answer', {
          requestId: request.requestId, decision: 'rejected', reason: 'The owner approval card could not be delivered to Nano IM.',
        }).catch(this.options.onError);
      }
      this.options.onError(error);
      return undefined;
    });
    this.pending.set(request.requestId, {request, agentId: binding.agentId, revision, messageId});
  }

  private async publish(request: Approval, agentId: string, revision: number): Promise<string> {
    const payload: WorkerPermissionRequest = {
      kind: 'worker_permission_request', node_id: this.options.nodeId, agent_id: agentId, lifecycle_revision: revision,
      session_id: request.sessionId, run_id: request.sessionId, worker: request.worker, expires_at: request.expiresAt,
      permission_request: {
        request_id: request.requestId, call_id: request.callId, tool_name: request.toolName,
        question: request.reason, reason: request.reason, status: 'pending',
        tool_input: request.toolInput.arguments,
        options: [{id: 'allow_once', label: 'Allow once', description: ''}, {id: 'deny', label: 'Deny', description: ''}],
      },
    };
    const ack = await this.options.relay.request('node.streaming_delta', {...payload});
    const id = ack.payload.message_id;
    if (typeof id !== 'string' || !id) throw new Error('IM did not acknowledge the Worker approval message identity');
    return id;
  }

  /** Consume an authenticated Nano IM answer for the original private card. */
  async answer(payload: Record<string, unknown>): Promise<boolean> {
    const pending = this.pending.get(String(payload.request_id));
    if (!pending) return false;
    const messageId = await pending.messageId;
    if (!messageId || payload.message_id !== messageId || payload.lifecycle_revision !== pending.revision ||
        pending.terminal || Date.now() >= pending.request.expiresAt) throw new Error('Worker permission is no longer pending for this card');
    this.options.store.lifecycle.assert(pending.agentId, pending.revision);
    if (payload.decision !== 'allow_once' && payload.decision !== 'deny') throw new Error('Invalid Worker permission decision');
    await this.options.runtime.request('approval.answer', {
      requestId: pending.request.requestId, decision: payload.decision === 'allow_once' ? 'allowed-once' : 'rejected',
      ...(typeof payload.reason === 'string' ? {reason: payload.reason} : {}),
    });
    return true;
  }

  private finish(pending: Pending, outcome: string): Promise<void> {
    pending.terminal ??= pending.messageId.then(async messageId => {
      if (!messageId) return;
      const {request, agentId, revision} = pending;
      const payload: ChatStreamFact = {
        kind: 'permission_resolved', node_id: this.options.nodeId, agent_id: agentId, lifecycle_revision: revision,
        message_id: messageId, session_id: request.sessionId, run_id: request.sessionId,
        permission_request: {request_id: request.requestId},
        decision: outcome === 'allowed-once' ? 'allow_once' : outcome === 'rejected' ? 'deny' : outcome,
      };
      await this.options.relay.request('node.streaming_delta', {...payload});
    }).finally(() => this.pending.delete(pending.request.requestId));
    return pending.terminal;
  }

  /** The dead process cannot honor further answers, including a click racing the card ACK. */
  cancelAgent(agentId: string, outcome: 'cancelled' | 'unavailable' = 'cancelled'): void {
    for (const pending of this.pending.values()) {
      if (pending.agentId === agentId) this.finish(pending, outcome).catch(this.options.onError);
    }
  }

  async stop(): Promise<void> {
    this.unsubscribe();
    await Promise.allSettled([...this.pending.values()].map(pending => this.finish(pending, 'cancelled')));
  }
}
