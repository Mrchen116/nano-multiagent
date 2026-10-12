import type { Context } from '@deepseek-ai/cordis';
import { AuthorizationDeclinedError } from '@deepseek-ai/dsh-authorization';
import type {} from '@deepseek-ai/dsh-credentials';
import type {} from '@deepseek-ai/dsh-settings';
import { recordKeyFor, type PiAiProviderProfile } from '@deepseek-ai/dsh-llm-pi-ai';
import { BlockAssembler } from '@deepseek-ai/dsh-llm';
import type { RpcPeer } from './rpc.js';

type Profiles = Record<string, PiAiProviderProfile>;
interface Candidate { id: string; providers: Profiles; provider: string; model: string; login?: boolean; api_key?: string }
interface Transaction { abort: AbortController; previous: Profiles; candidate: Candidate; tested: boolean; keyWritten: boolean }

/** Expose native model configuration/authentication through the existing stdio seam. */
export class NativeModelSetup {
  private providers: Profiles = {};
  private transaction?: Transaction;
  constructor(private readonly ctx: Context, private readonly peer: Pick<RpcPeer, 'handle' | 'notify'>) {
    peer.handle('model.setup.catalog', () => this.catalog());
    peer.handle('model.setup.test', value => this.test(value as Candidate));
    peer.handle('model.setup.finish', value => this.finish((value as { commit: boolean }).commit));
    peer.handle('model.setup.cancel', () => { this.transaction?.abort.abort(); return {}; });
    ctx.effect(() => () => { this.transaction?.abort.abort(); });
  }
  /** Node YAML is authoritative on every cold initialization, including an empty map. */
  async apply(providers: Profiles): Promise<void> {
    await this.ctx.settings.mutate('llm-pi-ai', [{ op: 'set', path: ['providers'], value: providers }]);
    this.providers = structuredClone(providers);
  }
  private async catalog() {
    return Promise.all(['openai-codex', 'openai', 'deepseek', 'anthropic'].map(async provider => ({
      provider, models: (await this.ctx.llm.discoverModels('llm-pi-ai', { provider })).map(model => model.id),
    })));
  }
  private notice(candidate: Candidate, state: 'waiting' | 'testing', data: { message?: string; code?: string; url?: string } = {}) {
    this.peer.notify('model.setup.notice', { id: candidate.id, state, ...data });
  }
  private async test(candidate: Candidate): Promise<{ cancelled?: boolean }> {
    if (this.transaction) throw new Error('A model setup operation is already running');
    // The first-run path adds routes; editing one used by an Agent belongs to configuration management.
    if (Object.hasOwn(this.providers, candidate.provider)) throw new Error('This provider is already configured');
    const transaction: Transaction = { abort: new AbortController(), previous: structuredClone(this.providers), candidate, tested: false, keyWritten: false };
    this.transaction = transaction;
    try {
      if (candidate.login) {
        if (candidate.provider !== 'openai-codex') throw new Error('Unsupported subscription provider');
        const known = await this.ctx.llm.discoverModels('llm-pi-ai', { provider: candidate.provider });
        if (!known.some(model => model.id === candidate.model)) throw new Error('Choose an installed Codex model');
        const result = await this.ctx.authorization.begin({
          key: recordKeyFor(candidate.provider), method: 'oauth', signal: transaction.abort.signal,
          interaction: {
            notify: notice => this.notice(candidate, 'waiting', notice),
            prompt: async prompt => {
              // Device authorization works from a hosted IM and opens no callback listener on the node.
              if (prompt.kind === 'select' && prompt.options.some(option => option.id === 'device_code')) return 'device_code';
              throw new AuthorizationDeclinedError('This setup supports device-code authorization');
            },
          },
        });
        if (result.status === 'cancelled') transaction.abort.abort();
      } else {
        if (!candidate.api_key) throw new Error('An API credential is required');
        await this.ctx.credentials.modifyRecord(recordKeyFor(candidate.provider), async current => {
          if (current) throw new Error('A credential already exists for this new route');
          return { kind: 'api-key', key: candidate.api_key };
        });
        transaction.keyWritten = true;
      }
      // Do not keep the supplied key in the operation record beyond the local write.
      delete candidate.api_key;
      transaction.abort.signal.throwIfAborted();
      await this.apply(candidate.providers);
      this.notice(candidate, 'testing');
      const assembly = new BlockAssembler();
      for await (const chunk of this.ctx.llm.stream({
        provider: candidate.provider, model: candidate.model, maxTokens: 128,
        messages: [{ role: 'user', content: [{ type: 'text', text: 'Reply with the single word READY.' }] }],
        signal: AbortSignal.any([transaction.abort.signal, AbortSignal.timeout(45_000)]),
      })) assembly.push(chunk);
      if (assembly.finish.kind === 'error' || assembly.finish.kind === 'aborted' || !assembly.blocks().some(block => block.type === 'text' && block.text.trim())) throw new Error('Model did not return text');
      transaction.abort.signal.throwIfAborted();
      transaction.tested = true;
      return {};
    } catch {
      delete candidate.api_key;
      const cancelled = transaction.abort.signal.aborted;
      await this.finish(false);
      if (cancelled) return { cancelled: true };
      // Provider exceptions can include request headers or body. Never serialize them into product RPC.
      throw new Error('Model connection verification failed');
    }
  }
  private async finish(commit: boolean): Promise<void> {
    const transaction = this.transaction;
    if (!transaction) return;
    if (commit && !transaction.tested) throw new Error('Model verification has not completed');
    try {
      if (!commit) {
        await this.apply(transaction.previous);
        if (transaction.keyWritten) await this.ctx.credentials.deleteRecord(recordKeyFor(transaction.candidate.provider));
      }
    } finally { this.transaction = undefined; }
  }
}
