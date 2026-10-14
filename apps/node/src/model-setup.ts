import { randomUUID } from 'node:crypto';
import { dirname } from 'node:path';
import type { NodeConfiguration } from './configuration.js';
import { providerProfiles } from './providers.js';
import { probeModels } from './model-probe.js';
import { ModelSetupError, type ModelDefinition, type ModelProvider, type ModelProtocol, type ModelConfiguration } from './model-types.js';

interface Runtime {
  request(method: string, params: unknown): Promise<unknown>;
  onNotification(listener: (method: string, value: unknown) => void): () => void;
}
interface PublicError {code: string; message: string; dependencies?: {agent_id: string; display_name: string}[]}
interface Operation { id: string; state: 'waiting' | 'testing' | 'succeeded' | 'failed' | 'cancelled'; code?: string; url?: string; message?: string; error?: PublicError }
interface CatalogEntry { provider: string; display_name?: string; models: {id: string; name?: string; contextWindow?: number; maxTokens?: number; inputModalities?: string[]}[] }
export interface SetupRequest {
  action: 'status' | 'save' | 'remove' | 'login' | 'cancel'; revision?: string; provider?: string; source?: string; display_name?: string;
  protocol?: ModelProtocol; base_url?: string; model?: string; api_key?: string;
  models?: {id: string; display_name?: string; context_window?: number; max_tokens?: number; input?: ('text' | 'image')[]}[];
}
interface Credential {record?: {kind: string; key?: string} | null; preserve?: boolean}
interface Rollback extends Credential {provider: string; providers: Record<string, unknown>}
const publicError = (error: unknown): PublicError => error instanceof ModelSetupError
  ? {code: error.code, message: error.message, ...(error.dependencies ? {dependencies: error.dependencies} : {})}
  : {code: 'connection_failed', message: 'Connection could not be verified. Check the service, models and credentials, then retry.'};
const invalid = (message: string): never => {throw new ModelSetupError('invalid', message);};

/** Node-owned edits hold secrets in memory and expose only a safe product snapshot. */
export class ModelSetup {
  private operation?: Operation;
  private pending?: Promise<void>;
  private abort?: AbortController;
  private catalog?: Promise<CatalogEntry[]>;
  private rollback?: Rollback;
  private committing = false;
  private catalogError = false;
  private restored?: () => void;
  private readonly unsubscribe: () => void;
  constructor(private readonly configuration: NodeConfiguration, private readonly runtime: Runtime, private readonly probe = probeModels) {
    this.unsubscribe = runtime.onNotification((method, value) => {
      if (method !== 'model.setup.notice') return;
      const notice = value as Operation;
      if (notice.id === this.operation?.id && this.pending) this.operation = {...notice};
    });
  }
  /** An in-flight credential/provider change must finish before a process update. */
  get busy(): boolean { return !!this.pending || !!this.rollback || this.committing; }
  /** Inspect or mutate one computer; optimistic revisions fence drafts from other pages. */
  async handle(input: SetupRequest) {
    this.catalog ??= this.runtime.request('model.setup.catalog', {}).then(value => {this.catalogError = false; return value as CatalogEntry[];}).catch(() => {this.catalog = undefined; this.catalogError = true; return [];});
    const catalog = await this.catalog;
    let error: PublicError | undefined;
    try {
      if (input.action === 'cancel') {
        if (!this.committing) this.abort?.abort();
        if (this.pending && !this.committing) await this.runtime.request('model.setup.cancel', {}).catch(() => {});
      } else if (['save', 'remove', 'login'].includes(input.action)) {
        if (this.pending || this.rollback) throw new ModelSetupError('busy', 'Another model change is running. Wait for it to finish.');
        this.start(input, catalog);
      } else if (input.action !== 'status') invalid('Unsupported model setup action');
    } catch (caught) {error = publicError(caught);}
    const llm = this.configuration.value.llm;
    return {
      revision: this.configuration.modelRevision,
      services: llm.providers.map(provider => ({provider: provider.name, display_name: provider.display_name ?? provider.name, native: Boolean(provider.native), source: provider.native ? provider.name : 'custom', protocol: provider.protocol ?? (!provider.native ? (provider.name === 'anthropic' ? 'anthropic-messages' : 'openai-completions') : undefined), base_url: provider.base_url, credential_stored: Boolean(provider.credential_stored || provider.api_key), models: provider.models.map(model => ({...model, id: model.id ?? model.name}))})),
      models: llm.providers.flatMap(provider => provider.models.map(model => ({provider: provider.name, model: model.name, display_name: model.display_name ?? model.id ?? model.name}))),
      catalog, ...(this.catalogError ? {catalog_error: 'The service catalog is unavailable. Retry or use a custom API.'} : {}), default_model: llm.default_model, workspace_base: dirname(this.configuration.defaultWorkspace('placeholder')),
      ...(this.operation ? {operation: {...this.operation}} : {}), ...(error ? {error} : {}),
    };
  }
  private start(input: SetupRequest, catalog: CatalogEntry[]) {
    if (input.revision !== this.configuration.modelRevision) throw new ModelSetupError('conflict', 'Model services changed in another page. Review the latest configuration before saving.');
    const current = this.configuration.value.llm;
    const previous = current.providers.find(provider => provider.name === input.provider);
    if (input.provider && !previous && input.action !== 'login') invalid('This model service no longer exists');
    let provider: ModelProvider;
    if (input.action === 'remove') {
      if (!previous) invalid('Choose a model service to remove');
      provider = previous!;
    } else if (input.action === 'login') {
      if (input.provider !== 'openai-codex' || previous) invalid('Choose an unconfigured subscription service');
      if (!catalog.find(item => item.provider === 'openai-codex')?.models.some(model => model.id === input.model)) invalid('Choose an installed Codex model');
      provider = {name: 'openai-codex', native: true, models: [{name: `openai-codex/${input.model}`, id: input.model}]};
    } else {
      if (previous?.name === 'openai-codex') invalid('Subscription services use the login flow');
      const source = previous ? (previous.native ? previous.name : 'custom') : input.source ?? 'custom';
      if (source !== 'custom' && !catalog.some(item => item.provider === source && item.provider !== 'openai-codex')) invalid('Choose an installed API service');
      if (!previous && current.providers.some(item => item.name === source)) invalid('This service is already configured. Edit its connection or add a custom service.');
      const name = previous?.name ?? (source === 'custom' ? `nano-${randomUUID()}` : source);
      const base = input.base_url?.trim();
      if (source === 'custom' && !base) invalid('Enter an API base URL');
      if (base) {
        let url: URL; try {url = new URL(base);} catch {invalid('Enter a valid API base URL');}
        if (!['http:', 'https:'].includes(url!.protocol) || url!.username || url!.password || url!.search || url!.hash) invalid('Use an HTTP or HTTPS base URL without embedded credentials');
      }
      if ((source === 'custom' || input.protocol) && !['openai-completions', 'anthropic-messages', 'openai-responses'].includes(input.protocol ?? '')) invalid('Choose an API protocol');
      if (!input.models?.length) invalid('Add at least one model');
      const ids = new Set<string>();
      const models: ModelDefinition[] = input.models!.map(model => {
        const id = model.id?.trim();
        if (!id || id.length > 200 || ids.has(id)) invalid('Model IDs must be nonempty and unique within this service');
        ids.add(id);
        for (const count of [model.context_window, model.max_tokens]) if (count !== undefined && (!Number.isSafeInteger(count) || count <= 0)) invalid('Token limits must be positive whole numbers');
        if (model.input && (!model.input.length || model.input.some(value => !['text', 'image'].includes(value)))) invalid('Choose text or image model input');
        const old = previous?.models.find(item => (item.id ?? item.name) === id);
        return {...old, name: old?.name ?? `${name}/${id}`, id, display_name: model.display_name?.trim() || undefined, context_window: model.context_window, max_tokens: model.max_tokens, input: model.input};
      });
      provider = {...previous, name, display_name: input.display_name?.trim() || source, native: source !== 'custom', protocol: input.protocol, base_url: base || undefined, models};
      if (input.api_key?.trim() || previous?.api_key) {delete provider.api_key; provider.credential_stored = true;}
      if (!previous && source === 'custom' && !input.api_key?.trim() && !['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base!).hostname)) invalid('Enter an API key for this service');
    }
    const providers = current.providers.filter(item => item.name !== provider.name);
    if (input.action !== 'remove') providers.splice(previous ? current.providers.indexOf(previous) : providers.length, 0, provider);
    const names = new Set(providers.flatMap(item => item.models.map(model => model.name)));
    const next = {...current, providers, default_model: names.has(current.default_model) ? current.default_model : providers[0]?.models[0]?.name ?? ''};
    this.configuration.assertModelUpdate(next, input.revision!);
    const operation: Operation = {id: randomUUID(), state: input.action === 'login' ? 'waiting' : 'testing'};
    this.operation = operation;
    this.abort = new AbortController();
    this.pending = this.run(input, provider, previous, next, operation, this.abort.signal).finally(() => {this.pending = undefined; this.abort = undefined; this.committing = false;});
  }
  private async run(input: SetupRequest, provider: ModelProvider, previous: ModelProvider | undefined, next: ModelConfiguration, operation: Operation, signal: AbortSignal) {
    let loginTested = false;
    try {
      const profiles = providerProfiles(next).providers;
      if (input.action === 'login') {
        const result = await this.runtime.request('model.setup.test', {id: operation.id, providers: profiles, provider: provider.name, model: input.model, login: true}) as {cancelled?: boolean};
        if (result.cancelled) {this.operation = {id: operation.id, state: 'cancelled'}; return;}
        loginTested = true;
        await this.configuration.persistModels(next, input.revision, {apply: async () => {signal.throwIfAborted(); this.committing = true;}, rollback: async () => {await this.runtime.request('model.setup.finish', {commit: false});}});
      } else {
        const credential = await this.runtime.request('model.setup.credential', {provider: provider.name}) as Credential;
        const key = input.api_key?.trim() || previous?.api_key || credential.record?.key || (!provider.native ? 'nano-local-proxy' : undefined);
        if (input.action === 'save' && key) {provider.credential_stored = true; delete (profiles[provider.name] as Record<string, unknown>).apiKeyEnv;}
        if (input.action === 'save') {
          if (credential.preserve) invalid('This service uses subscription authorization');
          // A blank key keeps the existing local record or the provider's native environment credential.
          const profile = {...profiles[provider.name] as Record<string, unknown>};
          delete profile.apiKeyEnv;
          await this.probe({provider: provider.name, providers: {[provider.name]: profile}, models: provider.models.map(model => model.id ?? model.name), api_key: key || (!provider.native ? 'nano-local-proxy' : undefined)}, signal);
        }
        signal.throwIfAborted();
        await this.configuration.persistModels(next, input.revision, {
          apply: async () => {
            signal.throwIfAborted();
            this.committing = true;
            this.rollback = {provider: provider.name, providers: providerProfiles(this.configuration.value.llm).providers, ...credential};
            await this.runtime.request('model.setup.stage', {id: operation.id, provider: provider.name, providers: profiles, ...(input.action === 'save' && key ? {api_key: key} : {})});
          },
          rollback: async () => {
            try {await this.recover();} catch {
              // Keep the shared write queue occupied until onReady restores the old key.
              await new Promise<void>((resolve, reject) => {
                this.restored = resolve;
                signal.addEventListener('abort', () => reject(new Error('Node stopped during recovery')), {once: true});
              });
            }
          },
        });
        this.rollback = undefined;
      }
      // Commit is already durable; finish only drops the subprocess's in-memory rollback record.
      await this.runtime.request('model.setup.finish', {commit: true}).catch(() => {});
      this.operation = {id: operation.id, state: 'succeeded'};
    } catch (error) {
      if (loginTested) await this.runtime.request('model.setup.finish', {commit: false}).catch(() => {});
      this.operation = signal.aborted ? {id: operation.id, state: 'cancelled'} : {id: operation.id, state: 'failed', error: publicError(error), message: publicError(error).message};
    } finally {delete input.api_key;}
  }
  /** Restore an interrupted live apply before restarted Agent sessions may resume. */
  async recover(): Promise<void> {
    if (!this.rollback) return;
    await this.runtime.request('model.setup.restore', this.rollback);
    this.rollback = undefined;
    this.restored?.();
    this.restored = undefined;
  }
  /** Cancel and drain the operation before shutting down the live runtime. */
  async stop(): Promise<void> {
    this.abort?.abort();
    if (this.pending) {await this.runtime.request('model.setup.cancel', {}).catch(() => {}); await this.pending;}
    this.unsubscribe();
  }
}
