import type { Context } from '@deepseek-ai/cordis';
import { BasicCompactionEngine, type BasicCompactionConfig } from '@deepseek-ai/dsh-compaction-basic';
import { CONTEXT_WINDOW_EXCEEDED_CODE, freezeMessage, MessageId, type Message, type ToolSchema } from '@deepseek-ai/dsh-llm';
import type { CompactionTrigger } from '@deepseek-ai/dsh-compaction';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { CommandId } from '@deepseek-ai/dsh-commands/brand';

/** Adds the requested summary focus through the native summarizer's supported hook. */
export default class NanoCompaction extends BasicCompactionEngine {
  private readonly focuses = new Map<string, string>();
  private readonly nanoOverflowRetries = new WeakMap<Agent, number>();
  constructor(ctx: Context, config?: BasicCompactionConfig) {
    super(ctx, { ...config, auto: false });
    if (config?.auto !== false) this.registerAutomaticTriggers();
  }
  private hasPresetCompaction(agent: Agent): boolean {
    return Boolean(this.ctx.get('agentPresets')?.serviceFor(agent, 'compaction'));
  }
  private registerAutomaticTriggers(): void {
    const { ctx } = this;
    ctx.on('agent/status', ({ agent, status }) => {
      if (status === 'idle') this.nanoOverflowRetries.delete(agent);
    });
    ctx.on('session/event', (session, event) => {
      if (event.type !== 'assistant/message') return;
      const agent = ctx.get('agents')?.get(session.id);
      if (agent) this.nanoOverflowRetries.delete(agent);
    });
    ctx.on('agent/pre-step', async ({ agent, signal }, next) => {
      if (!signal.aborted && !this.hasPresetCompaction(agent)) {
        try { await this.compactIfNeeded(agent, 'pressure', signal); }
        catch (error) { ctx.logger.warn(`step compaction failed: ${error instanceof Error ? error.message : String(error)}; continuing the turn`); }
      }
      return next();
    });
    ctx.on('agent/request-error', async ({ agent, failure, signal }, next) => {
      if (failure.code !== CONTEXT_WINDOW_EXCEEDED_CODE || signal.aborted || this.hasPresetCompaction(agent)) return next();
      const retries = this.nanoOverflowRetries.get(agent) ?? 0;
      if (retries >= this.config.maxOverflowRetries) return next();
      const generation = agent.session.surface.replaceGeneration;
      try {
        await this.compactIfNeeded(agent, 'context-overflow', signal);
      } catch (recoveryError) {
        const message = recoveryError instanceof Error ? recoveryError.message : String(recoveryError);
        if (!signal.aborted && agent.session.surface.replaceGeneration > generation) {
          ctx.logger.warn(`context-overflow compaction failed after durable surface progress: ${message}; retrying from the replacement surface`);
          this.nanoOverflowRetries.set(agent, retries + 1);
          return { kind: 'retry' };
        }
        ctx.logger.warn(`context-overflow compaction failed: ${message}; ${signal.aborted ? 'cancellation prevents retry' : 'preserving the original request error'}`);
        return next();
      }
      if (signal.aborted || agent.session.surface.replaceGeneration <= generation) return next();
      this.nanoOverflowRetries.set(agent, retries + 1);
      return { kind: 'retry' };
    });
  }
  /** Leave automatic triggers to the engine owned by this Agent's native preset.
   *
   * Args:
   *   agent: Agent whose preset may supply a compaction engine.
   *   trigger: Native pressure or provider overflow trigger.
   *   signal: Cancellation of the active turn.
   */
  override async compactIfNeeded(agent: Agent, trigger: CompactionTrigger, signal: AbortSignal) {
    if (this.hasPresetCompaction(agent)) return null;
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
