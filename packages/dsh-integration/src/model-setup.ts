import type { Context } from '@deepseek-ai/cordis';
import { AuthorizationDeclinedError } from '@deepseek-ai/dsh-authorization';
import type { CredentialRecord } from '@deepseek-ai/dsh-credentials';
import type {} from '@deepseek-ai/dsh-settings';
import { recordKeyFor, type PiAiProviderProfile } from '@deepseek-ai/dsh-llm-pi-ai';
import { BlockAssembler } from '@deepseek-ai/dsh-llm';
import type { RpcPeer } from './rpc.js';

type Profiles = Record<string, PiAiProviderProfile>;
interface Candidate { id: string; providers: Profiles; provider: string; model?: string; models?: string[]; login?: boolean; api_key?: string }
interface Transaction { abort: AbortController; previous: Profiles; candidate: Candidate; tested: boolean; keyWritten: boolean; record?: CredentialRecord }

/** Expose native model configuration/authentication through the existing stdio seam. */
export class NativeModelSetup {
  private providers: Profiles = {};
  private configured = false;
  /** Current explicit provider metadata for a temporary native inspection. */
  get inspectionProviders(): Profiles | undefined {return this.configured ? structuredClone(this.providers) : undefined;}
  private transaction?: Transaction;
  constructor(private readonly ctx: Context, private readonly peer: Pick<RpcPeer, 'handle' | 'notify'>) {
    peer.handle('model.setup.catalog', () => this.catalog());
    peer.handle('model.setup.snapshot', () => this.snapshot());
    peer.handle('model.setup.sync', value => this.sync(value as Awaited<ReturnType<NativeModelSetup['snapshot']>>));
    peer.handle('model.setup.credential', async value => {
      const record = await this.ctx.credentials.readRecord(recordKeyFor((value as {provider: string}).provider));
      return record && record.kind !== 'api-key' ? {preserve: true} : {record: record ?? null};
    });
    peer.handle('model.setup.restore', async value => {
      const snapshot = value as {provider: string; providers: Profiles; record?: CredentialRecord; preserve?: boolean};
      if (!snapshot.preserve) await this.restore(snapshot.provider, snapshot.providers, snapshot.record);
      else await this.apply(snapshot.providers);
      this.transaction = undefined;
      return {};
    });
    peer.handle('model.setup.stage', value => this.stage(value as Candidate));
    peer.handle('model.setup.test', value => this.test(value as Candidate));
    peer.handle('model.setup.finish', value => this.finish((value as { commit: boolean }).commit));
    peer.handle('model.setup.cancel', () => { this.transaction?.abort.abort(); return {}; });
    ctx.effect(() => () => { this.transaction?.abort.abort(); });
  }
  /** A staged or testing provider transaction must finish before an update. */
  get busy(): boolean { return !!this.transaction; }
  /** Node YAML is authoritative on every cold initialization, including an empty map. */
  async apply(providers: Profiles): Promise<void> {
    await this.ctx.settings.mutate('llm-pi-ai', [{ op: 'set', path: ['providers'], value: providers }]);
    this.providers = structuredClone(providers);
    this.configured = true;
  }
  /** Export only approved model routes and their credentials to a trusted sibling host. */
  async snapshot() {
    const records: Record<string, CredentialRecord | null> = {};
    for (const provider of Object.keys(this.providers)) records[provider] = await this.ctx.credentials.readRecord(recordKeyFor(provider)) ?? null;
    return {providers: structuredClone(this.providers), records};
  }
  /** Apply a host-issued provider snapshot; no Agent configuration or plugin code crosses. */
  async sync(snapshot: {providers: Profiles; records: Record<string, CredentialRecord | null>}) {
    for (const provider of new Set([...Object.keys(this.providers), ...Object.keys(snapshot.providers)])) {
      const record = snapshot.records[provider];
      if (record) await this.ctx.credentials.modifyRecord(recordKeyFor(provider), async () => record);
      else await this.ctx.credentials.deleteRecord(recordKeyFor(provider));
    }
    await this.apply(snapshot.providers);
    return {};
  }
  private async catalog() {
    const entries = this.ctx.llm.listConfigurableProviders().filter(item => item.settingsNs === 'llm-pi-ai' && !item.declared);
    return Promise.all(entries.map(async item => ({provider: item.provider, display_name: item.displayName,
      models: (await this.ctx.llm.discoverModels('llm-pi-ai', {provider: item.provider})).map(model => ({id: model.id, name: model.name, contextWindow: model.contextWindow, maxTokens: model.maxTokens, inputModalities: model.inputModalities})),
    })));
  }
  private async restore(provider: string, providers: Profiles, record?: CredentialRecord) {
    if (record) await this.ctx.credentials.modifyRecord(recordKeyFor(provider), async () => record);
    else await this.ctx.credentials.deleteRecord(recordKeyFor(provider));
    await this.apply(providers);
  }
  private async stage(candidate: Candidate) {
    if (this.transaction) throw new Error('A model setup operation is already running');
    const record = await this.ctx.credentials.readRecord(recordKeyFor(candidate.provider));
    if (record && record.kind !== 'api-key' && candidate.api_key) throw new Error('Cannot replace subscription authorization');
    this.transaction = {abort: new AbortController(), previous: structuredClone(this.providers), candidate, tested: true, keyWritten: false, record};
    if (candidate.api_key) {
      this.transaction.keyWritten = true;
      await this.ctx.credentials.modifyRecord(recordKeyFor(candidate.provider), async () => ({kind: 'api-key', key: candidate.api_key!}));
    } else if (!candidate.providers[candidate.provider] && record?.kind === 'api-key') {
      this.transaction.keyWritten = true;
      await this.ctx.credentials.deleteRecord(recordKeyFor(candidate.provider));
    }
    delete candidate.api_key;
    await this.apply(candidate.providers);
    return {};
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
        if (candidate.api_key) await this.ctx.credentials.modifyRecord(recordKeyFor(candidate.provider), async current => {
          if (current) throw new Error('A credential already exists for this new route');
          return { kind: 'api-key', key: candidate.api_key };
        });
        transaction.keyWritten = Boolean(candidate.api_key);
      }
      // Do not keep the supplied key in the operation record beyond the local write.
      delete candidate.api_key;
      transaction.abort.signal.throwIfAborted();
      await this.apply(candidate.providers);
      this.notice(candidate, 'testing');
      for (const model of candidate.models ?? [candidate.model!]) {
      const assembly = new BlockAssembler();
      for await (const chunk of this.ctx.llm.stream({
        provider: candidate.provider, model, maxTokens: 128,
        messages: [{ role: 'user', content: [{ type: 'text', text: 'Reply with the single word READY.' }] }],
        signal: AbortSignal.any([transaction.abort.signal, AbortSignal.timeout(45_000)]),
      })) assembly.push(chunk);
      if (assembly.finish.kind === 'error' || assembly.finish.kind === 'aborted' || !assembly.blocks().some(block => block.type === 'text' && block.text.trim())) throw new Error('Model did not return text');
      }
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
        if (transaction.keyWritten) {
          if (transaction.record) await this.ctx.credentials.modifyRecord(recordKeyFor(transaction.candidate.provider), async () => transaction.record);
          else await this.ctx.credentials.deleteRecord(recordKeyFor(transaction.candidate.provider));
        }
      }
    } finally { this.transaction = undefined; }
  }
}
