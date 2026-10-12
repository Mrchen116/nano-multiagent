import { access, readFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { homedir } from 'node:os';
import { delimiter, dirname, join } from 'node:path';
import type { NodeConfiguration, NodeConfigurationFile } from './configuration.js';
import { providerProfiles } from './providers.js';

type Protocol = 'openai-completions' | 'anthropic-messages' | 'openai-responses';
interface Runtime {
  request(method: string, params: unknown): Promise<unknown>;
  onNotification(listener: (method: string, value: unknown) => void): () => void;
}
interface Discovery { codex: boolean; proxy?: { base_url: string; models: string[]; protocol: Protocol } }
interface Operation { id: string; state: 'waiting' | 'testing' | 'succeeded' | 'failed' | 'cancelled'; code?: string; url?: string; message?: string }
interface CatalogEntry { provider: string; models: string[] }
export interface SetupRequest { action: 'status' | 'configure' | 'login' | 'cancel'; provider?: string; protocol?: Protocol; base_url?: string; model?: string; api_key?: string }

/** Detect named local integrations without reading a Codex credential or scanning disk. */
export async function discoverLocalModels(): Promise<Discovery> {
  const executable = process.platform === 'win32' ? 'codex.exe' : 'codex';
  const present = await Promise.all((process.env.PATH ?? '').split(delimiter).filter(Boolean).map(async path => {
    try { await access(join(path, executable), constants.X_OK); return true; } catch { return false; }
  }));
  const discovered: Discovery = { codex: present.some(Boolean) };
  const path = process.env.NANO_LLM_PROXY_CONFIG ?? join(homedir(), 'Repos', 'LLM_PROXY', 'upstreams.json');
  try {
    // Only profile names, defaults and ingress metadata leave this function.
    const config = JSON.parse(await readFile(path, 'utf8')) as { defaultProfile?: string; profiles?: Record<string, { defaults?: { model?: string }; capabilities?: { ingress?: string[] } }> };
    const base = new URL(process.env.NANO_LLM_PROXY_URL ?? 'http://127.0.0.1:4000');
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)) return discovered;
    const health = await fetch(new URL('/health', base), { signal: AbortSignal.timeout(1500) });
    if (!health.ok || (await health.json() as { ok?: boolean }).ok !== true) return discovered;
    const profiles = Object.entries(config.profiles ?? {}).sort(([left], [right]) => Number(right === config.defaultProfile) - Number(left === config.defaultProfile));
    const anthropic = !profiles.some(([, value]) => value.capabilities?.ingress?.includes('openai_chat'));
    const models = profiles.filter(([, value]) => typeof value.defaults?.model === 'string' && value.capabilities?.ingress?.includes(anthropic ? 'anthropic_messages' : 'openai_chat')).map(([name, value]) => `${name}:${value.defaults!.model}`);
    if (models.length) discovered.proxy = { base_url: new URL(anthropic ? '/' : '/v1', base).href, models, protocol: anthropic ? 'anthropic-messages' : 'openai-completions' };
  } catch { /* An absent or stopped optional proxy leaves the ordinary API/login paths available. */ }
  return discovered;
}

/** One node-owned asynchronous setup operation; the browser only receives safe snapshots. */
export class ModelSetup {
  private operation?: Operation;
  private pending?: Promise<void>;
  private catalog?: Promise<CatalogEntry[]>;
  private discovery?: Promise<Discovery>;
  private readonly unsubscribe: () => void;
  constructor(private readonly configuration: NodeConfiguration, private readonly runtime: Runtime, private readonly discover = discoverLocalModels) {
    this.unsubscribe = runtime.onNotification((method, value) => {
      if (method !== 'model.setup.notice') return;
      const notice = value as Operation;
      if (notice.id === this.operation?.id && this.pending) this.operation = { ...notice };
    });
  }
  /** Start quickly, cancel, or inspect the same operation across page refreshes. */
  async handle(input: SetupRequest) {
    if (input.action === 'cancel') {
      if (this.pending) await this.runtime.request('model.setup.cancel', {});
    } else if (input.action === 'configure' || input.action === 'login') {
      if (!this.pending) this.start(input);
    } else if (input.action !== 'status') throw new Error('Unsupported setup action');
    this.catalog ??= this.runtime.request('model.setup.catalog', {}).then(value => value as CatalogEntry[]).catch(() => { this.catalog = undefined; return []; });
    this.discovery ??= this.discover();
    const [catalog, discovered] = await Promise.all([this.catalog, this.discovery]);
    const llm = this.configuration.value.llm;
    return {
      models: llm.providers.flatMap(provider => provider.models.map(model => ({ provider: provider.name, model: model.name }))),
      catalog,
      discovered,
      default_model: llm.default_model,
      workspace_base: dirname(this.configuration.defaultWorkspace('placeholder')),
      ...(this.operation ? { operation: { ...this.operation } } : {}),
    };
  }
  private start(input: SetupRequest): void {
    const model = input.model?.trim();
    if (!model || model.length > 200) throw new Error('Choose a model before testing the connection');
    if (this.configuration.value.llm.providers.some(provider => provider.models.some(existing => existing.name === model))) throw new Error('This model is already configured; continue to create your assistant');
    const native = input.action === 'login';
    if (native && input.provider !== 'openai-codex') throw new Error('Unsupported subscription provider');
    let provider: NodeConfigurationFile['llm']['providers'][number];
    if (native) {
      if (this.configuration.value.llm.providers.some(item => item.name === 'openai-codex')) throw new Error('Codex is already configured; use its existing connection');
      provider = { name: 'openai-codex', native: true, models: [{ name: model }] };
    } else {
      if (!['openai-completions', 'anthropic-messages', 'openai-responses'].includes(input.protocol ?? '')) throw new Error('Choose an API protocol');
      let url: URL;
      try { url = new URL(input.base_url ?? ''); } catch { throw new Error('Enter a valid API base URL'); }
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Use an HTTP or HTTPS base URL without embedded credentials');
      if (!input.api_key?.trim() && !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('Enter an API key for this service');
      provider = { name: `nano-${randomUUID().slice(0, 8)}`, protocol: input.protocol, base_url: url.href.replace(/\/$/, ''), credential_stored: true, models: [{ name: model }] };
    }
    const operation: Operation = { id: randomUUID(), state: native ? 'waiting' : 'testing' };
    this.operation = operation;
    this.pending = this.run(input, provider, operation).finally(() => { this.pending = undefined; });
  }
  private async run(input: SetupRequest, provider: NodeConfigurationFile['llm']['providers'][number], operation: Operation) {
    let tested = false;
    try {
      const next = { ...this.configuration.value.llm, default_model: this.configuration.value.llm.default_model || input.model!.trim(), providers: [...this.configuration.value.llm.providers, provider] };
      const result = await this.runtime.request('model.setup.test', {
        id: operation.id, providers: providerProfiles(next).providers, provider: provider.name, model: input.model!.trim(),
        login: input.action === 'login', ...(input.action === 'configure' ? { api_key: input.api_key?.trim() || 'nano-local-proxy' } : {}),
      }) as { cancelled?: boolean };
      if (result.cancelled) { this.operation = { id: operation.id, state: 'cancelled' }; return; }
      tested = true;
      await this.configuration.persistModels(next);
      await this.runtime.request('model.setup.finish', { commit: true });
      this.operation = { id: operation.id, state: 'succeeded' };
    } catch {
      if (tested) await this.runtime.request('model.setup.finish', { commit: false }).catch(() => {});
      this.operation = { id: operation.id, state: 'failed', message: 'Connection could not be verified. Check the service, model and credentials, then retry.' };
    }
  }
  /** Cancel before the runtime exits so an unfinished candidate can be rolled back. */
  async stop(): Promise<void> {
    if (this.pending) { await this.runtime.request('model.setup.cancel', {}).catch(() => {}); await this.pending; }
    this.unsubscribe();
  }
}
