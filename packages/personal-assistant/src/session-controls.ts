import type { RelayInput, RuntimePort, SessionBinding, AgentConfiguration } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import { NodeStore } from './store.js';
import { needsAttention } from './attention.js';

export interface ControlIntent { id: string; binding: SessionBinding; input: RelayInput; action: string; argument: string; text?: string; delivered?: boolean }
interface Options { nodeId: string; runtime: RuntimePort; store: NodeStore; relay: { request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> } }
export function sessionControl(input: RelayInput, config: AgentConfiguration): { action: string; argument: string } | undefined {
  if (input.message.sender_type !== 'user') return;
  const match = /^\/(compact|effort|workflows)(?:\s+([\s\S]*))?$/.exec(input.message.content.trim());
  if (!match || !needsAttention(input, { ...config, groupReplyPolicy: 'mention_only' })) return;
  return { action: match[1]!, argument: match[2]?.trim() ?? '' };
}

/** Reserves a durable command position before later ordinary product input is submitted. */
export class SessionControls {
  private readonly tails = new Map<string, Promise<unknown>>();
  private readonly active = new Map<string, Promise<void>>();
  constructor(private readonly options: Options) {}
  run(binding: SessionBinding, input: RelayInput, action: string, argument: string): Promise<void> {
    const id = `${input.agent_id}:${input.message.id}`;
    const existing = this.active.get(id); if (existing) return existing;
    const intent = this.options.store.control(id) ?? { id, binding, input, action, argument };
    this.options.store.saveControl(intent);
    const task = (this.tails.get(binding.sessionId) ?? Promise.resolve()).then(() => this.perform(intent));
    const settled = task.catch(() => {}); this.tails.set(binding.sessionId, settled); this.active.set(id, task);
    void settled.then(() => { this.active.delete(id); if (this.tails.get(binding.sessionId) === settled) this.tails.delete(binding.sessionId); });
    return task;
  }
  async wait(sessionId: string) { await this.tails.get(sessionId); }
  async recover(agentId: string) {
    for (const intent of this.options.store.controls()) if (intent.binding.agentId === agentId && !intent.delivered) await this.run(intent.binding, intent.input, intent.action, intent.argument);
  }
  private async perform(intent: ControlIntent) {
    const { store, runtime, relay, nodeId } = this.options; const { binding, input } = intent;
    if (intent.delivered) return;
    if (!intent.text) {
      const current = store.bindingFor(binding.agentId, binding.conversationId);
      if (current?.sessionId !== binding.sessionId) intent.text = '本次控制操作未执行：原会话已被重置。';
      else {
        const { conversationId: _, ...runtimeBinding } = binding;
        await runtime.request('session.ensure', runtimeBinding);
        const result = await runtime.request('session.command', { sessionId: binding.sessionId, id: intent.id, action: intent.action, argument: intent.argument }) as { text: string };
        intent.text = result.text;
      }
      store.saveControl(intent);
    }
    const start = await relay.request('node.streaming_delta', { node_id: nodeId, kind: 'turn_start', conversation_id: input.conversation_id,
      agent_id: binding.agentId, idempotency_key: `command:${intent.id}`, external_reply: input.metadata.external_reply });
    await relay.request('node.streaming_delta', { node_id: nodeId, kind: 'message_completed', message_id: start.payload.message_id,
      final_content: intent.text, delivery_status: 'completed' });
    await relay.request('node.delivery_receipt', { node_id: nodeId, relay_task_id: input.relay_task_id, delivery_status: 'completed' });
    intent.delivered = true; store.saveControl(intent);
  }
  async stop() { await Promise.allSettled([...this.active.values()]); }
}
