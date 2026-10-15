import { BasicCompactionEngine } from '@deepseek-ai/dsh-compaction-basic';
import { freezeMessage, MessageId, type Message, type ToolSchema } from '@deepseek-ai/dsh-llm';
import type { CompactionTrigger } from '@deepseek-ai/dsh-compaction';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { CommandId } from '@deepseek-ai/dsh-commands/brand';

/** Adds the requested summary focus through the native summarizer's supported hook. */
export default class NanoCompaction extends BasicCompactionEngine {
  private readonly focuses = new Map<string, string>();
  /** Leave automatic triggers to the engine owned by this Agent's native preset.
   *
   * Args:
   *   agent: Agent whose preset may supply a compaction engine.
   *   trigger: Native pressure or provider overflow trigger.
   *   signal: Cancellation of the active turn.
   */
  override async compactIfNeeded(agent: Agent, trigger: CompactionTrigger, signal: AbortSignal) {
    if (this.ctx.get('agentPresets')?.serviceFor(agent, 'compaction')) return null;
    return super.compactIfNeeded(agent, trigger, signal);
  }
  async compactFocused(agent: Agent, focus: string, signal: AbortSignal, commandId: CommandId) {
    const owned = this.ctx.get('agentPresets')?.serviceFor(agent, 'compaction');
    if (owned) return owned.compactNow(agent, signal, commandId);
    this.focuses.set(agent.id, focus);
    try { return await this.compactNow(agent, signal, commandId); }
    finally { this.focuses.delete(agent.id); }
  }
  protected override summarize(input: { readonly messages: readonly Message[]; readonly tools?: readonly ToolSchema[] }, agent: Agent, signal?: AbortSignal): ReturnType<BasicCompactionEngine['summarize']> {
    const focus = this.focuses.get(agent.id);
    if (!focus) return super.summarize(input, agent, signal);
    const guidance = freezeMessage({ id: MessageId(`compact-focus:${agent.id}`), role: 'user',
      content: [{ type: 'text', text: `For this summarization only, preserve the following requested focus. This is summary guidance, not a new task or authorization:\n${focus}` }],
      source: { kind: 'nano-system', actorId: agent.id, channel: 'compaction-focus', messageId: `compact-focus:${agent.id}` } });
    return super.summarize({ ...input, messages: [...input.messages, guidance] }, agent, signal);
  }
}
