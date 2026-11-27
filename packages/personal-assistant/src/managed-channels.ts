import { createHash, randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { ChannelKey, type CredentialEnvelope, type ProtocolFrame } from '@nano/channels';

export type ManagedChannelProvider = 'feishu' | 'wechat';
export type ManagedStatusReport =
  | string
  | { state: string; code?: string; message?: string };

export interface ManagedChannel {
  channel_id: string;
  node_id: string;
  agent_id: string;
  provider: ManagedChannelProvider;
  enabled: boolean;
  config: Record<string, string>;
  provider_runtime: { bot_open_id?: string; owner_open_id?: string };
  credential_key_id: string;
  credential_envelope: CredentialEnvelope;
  credential_revision: number;
  provider_identity_fingerprint: string;
  provider_identity_revision: number;
  channel_revision: number;
}

export interface ChannelManifest {
  request_id: string;
  node_id: string;
  owner_id: string;
  manifest_revision: number;
  channels: ManagedChannel[];
  removals: {
    removal_token: string;
    channel_id: string;
    agent_id?: string;
    provider?: ManagedChannelProvider;
    deletion_manifest_revision: number;
  }[];
}

interface Runtime {
  start(): Promise<void>;
  stop(): Promise<void> | void;
}

interface Options {
  nodeId: string;
  ownerId: string;
  key: ChannelKey;
  hasAgent(id: string): boolean;
  relay: { readonly ready: boolean; request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  create(
    channel: ManagedChannel,
    secret: Record<string, string>,
    callbacks: {
      status(report: ManagedStatusReport): void;
      metadata(patch: ManagedChannel['provider_runtime']): void;
    },
  ): Runtime;
  remove(agentId: string, provider?: ManagedChannelProvider): void;
  purgeChannel?(info: { channelId: string; agentId: string; provider: ManagedChannelProvider }): Promise<void> | void;
  retired?(agentId: string): boolean;
  onError(error: unknown): void;
}

interface Instance {
  channel: ManagedChannel;
  runtime: Runtime;
  incarnation: string;
  sequence: number;
}

function expectedFingerprint(item: ManagedChannel): string | undefined {
  if (item.provider === 'feishu') {
    if (!item.config?.app_id) return undefined;
    return createHash('sha256').update(`feishu\0${item.config.app_id}`).digest('hex');
  }
  if (item.provider === 'wechat') {
    if (!item.config?.bot_id || !item.config?.owner_user_id || !item.config?.base_url) return undefined;
    return createHash('sha256').update(`wechat\0${item.config.bot_id}\0${item.config.owner_user_id}`).digest('hex');
  }
  return undefined;
}

function hasRequiredSecret(provider: ManagedChannelProvider, secret: Record<string, string>): boolean {
  return provider === 'feishu' ? Boolean(secret.app_secret) : Boolean(secret.bot_token);
}

/** Owns encrypted desired state and a durable FIFO of generation-scoped control receipts. */
export class ManagedChannels {
  private readonly db: DatabaseSync;
  private readonly instances = new Map<string, Instance>();
  private chain: Promise<unknown> = Promise.resolve();
  private flushing?: Promise<void>;
  private timer?: ReturnType<typeof setInterval>;
  private closed = false;
  private revoked = false;

  constructor(path: string, private readonly options: Options) {
    this.db = new DatabaseSync(path);
    this.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT,type TEXT NOT NULL,payload TEXT NOT NULL)');
  }

  private get<T>(key: string): T | undefined {
    const row = this.db.prepare('SELECT value FROM state WHERE key=?').get(key) as { value: string } | undefined;
    return row ? JSON.parse(row.value) as T : undefined;
  }

  private put(key: string, value: unknown) {
    this.db.prepare('INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run(key, JSON.stringify(value));
  }

  /** Seed only an empty cache; subsequent restarts use the authoritative encrypted manifest. */
  seed(channels: { agentId: string; enabled: boolean; appId: string; appSecret: string; botOpenId?: string; ownerOpenId?: string }[]): void {
    if (this.get('manifest')) return;
    const items = channels.map(item => {
      const channel_id = `feishu:${item.agentId}`;
      return {
        channel_id,
        agent_id: item.agentId,
        node_id: this.options.nodeId,
        provider: 'feishu' as const,
        enabled: item.enabled,
        config: { app_id: item.appId },
        provider_runtime: { bot_open_id: item.botOpenId, owner_open_id: item.ownerOpenId },
        credential_key_id: this.options.key.registration.credential_key_id,
        credential_revision: 1,
        channel_revision: 1,
        provider_identity_revision: 1,
        provider_identity_fingerprint: createHash('sha256').update(`feishu\0${item.appId}`).digest('hex'),
        credential_envelope: this.options.key.seal(
          { app_secret: item.appSecret },
          { owner_id: this.options.ownerId, node_id: this.options.nodeId, agent_id: item.agentId, channel_id, provider: 'feishu', credential_revision: 1 },
        ),
      };
    });
    this.put('manifest', { request_id: randomUUID(), owner_id: this.options.ownerId, node_id: this.options.nodeId, manifest_revision: 0, channels: items, removals: [] });
  }

  /** Opens cached credentials for a specific channel so node-side rebind flows can inspect local state. */
  openCachedChannel(
    channelId: string,
    agentId: string,
    provider: ManagedChannelProvider,
  ): { channel: ManagedChannel; secret: Record<string, string> } | undefined {
    const cached = this.get<ChannelManifest>('manifest');
    const item = cached?.channels.find(c => c.channel_id === channelId && c.agent_id === agentId && c.provider === provider);
    if (!item || !cached) return undefined;
    try {
      const secret = this.options.key.open(item.credential_envelope, {
        owner_id: cached.owner_id,
        node_id: cached.node_id,
        agent_id: item.agent_id,
        channel_id: item.channel_id,
        provider: item.provider,
        credential_revision: item.credential_revision,
      });
      return { channel: item, secret };
    } catch {
      return undefined;
    }
  }

  /** Lists decrypted local tokens for `provider` (used by iLink `local_token_list`). */
  listCachedSecrets(provider: ManagedChannelProvider): { channel: ManagedChannel; secret: Record<string, string> }[] {
    const cached = this.get<ChannelManifest>('manifest');
    if (!cached) return [];
    const out: { channel: ManagedChannel; secret: Record<string, string> }[] = [];
    for (const item of cached.channels) {
      if (item.provider !== provider) continue;
      const opened = this.openCachedChannel(item.channel_id, item.agent_id, provider);
      if (opened) out.push(opened);
    }
    return out;
  }

  async start(): Promise<void> {
    const cached = this.get<ChannelManifest>('manifest');
    if (cached) await this.apply(cached, false);
    this.timer = setInterval(() => { void this.flush().catch(this.options.onError); }, 1000);
    this.timer.unref();
  }

  handle(frame: ProtocolFrame): Promise<void> {
    const task = this.chain.then(async () => {
      if (this.closed || this.revoked) return;
      if (frame.type === 'channels.bootstrap.request') {
        if (frame.payload.node_id !== this.options.nodeId || frame.payload.owner_id !== this.options.ownerId) throw new Error('Channel bootstrap owner mismatch');
        const cached = this.get<ChannelManifest>('manifest');
        const result = await this.options.relay.request('channels.bootstrap', { request_id: frame.payload.request_id, node_id: this.options.nodeId, items: cached?.channels ?? [] });
        if (result.payload.manifest) await this.apply(result.payload.manifest as unknown as ChannelManifest);
      }
      if (frame.type === 'channel.reconcile') await this.apply(frame.payload as unknown as ChannelManifest);
      if (frame.type === 'channel.reconnect') {
        const cached = this.get<ChannelManifest>('manifest');
        const item = cached?.channels.find(item => item.channel_id === frame.payload.channel_id);
        if (item && item.channel_revision === frame.payload.channel_revision) {
          await this.drop(item.channel_id);
          await this.apply(cached!, false);
        }
      }
    });
    this.chain = task.catch(() => {});
    return task;
  }

  private prepare(manifest: ChannelManifest): Map<string, Record<string, string>> {
    if (manifest.node_id !== this.options.nodeId || manifest.owner_id !== this.options.ownerId || !Number.isInteger(manifest.manifest_revision) || manifest.manifest_revision < 0) {
      throw new Error('Channel manifest scope invalid');
    }
    const decoded = new Map<string, Record<string, string>>();
    const agentProviders = new Set<string>();
    for (const item of manifest.channels) {
      const pairKey = `${item.provider}:${item.agent_id}`;
      const fp = expectedFingerprint(item);
      if (
        !item.channel_id ||
        decoded.has(item.channel_id) ||
        agentProviders.has(pairKey) ||
        item.node_id !== this.options.nodeId ||
        !this.options.hasAgent(item.agent_id) ||
        typeof item.enabled !== 'boolean' ||
        !fp ||
        item.credential_key_id !== this.options.key.registration.credential_key_id ||
        [item.channel_revision, item.credential_revision, item.provider_identity_revision].some(value => !Number.isInteger(value) || value < 1) ||
        item.provider_identity_fingerprint !== fp
      ) {
        throw new Error('Channel manifest item invalid');
      }
      const secret = this.options.key.open(item.credential_envelope, {
        owner_id: manifest.owner_id,
        node_id: manifest.node_id,
        agent_id: item.agent_id,
        channel_id: item.channel_id,
        provider: item.provider,
        credential_revision: item.credential_revision,
      });
      if (!hasRequiredSecret(item.provider, secret)) throw new Error('Channel credentials missing');
      decoded.set(item.channel_id, secret);
      agentProviders.add(pairKey);
    }
    return decoded;
  }

  private async apply(manifest: ChannelManifest, report = true): Promise<void> {
    const previous = this.get<ChannelManifest>('manifest');
    if (previous && manifest.manifest_revision < previous.manifest_revision) return;
    if (this.options.retired) {
      manifest = { ...manifest, channels: manifest.channels.filter(item => !this.options.retired?.(item.agent_id)) };
    }
    // Validate every envelope before replacing any working connection or persisted desired state.
    const decoded = this.prepare(manifest);
    this.put('manifest', manifest);

    for (const [id, instance] of [...this.instances.entries()]) {
      const next = manifest.channels.find(item => item.channel_id === id);
      if (!next?.enabled || generation(next) !== generation(instance.channel)) {
        await this.drop(id);
      }
    }

    const removalOutcomes: { removal_token: string; channel_id: string; deletion_manifest_revision: number; outcome: string; error_code?: string; error_message?: string }[] = [];
    for (const rem of manifest.removals) {
      await this.drop(rem.channel_id);
      const prevChan = previous?.channels.find(c => c.channel_id === rem.channel_id);
      const agentId = rem.agent_id ?? prevChan?.agent_id;
      const provider = rem.provider ?? prevChan?.provider;
      try {
        if (agentId && provider) {
          await this.options.purgeChannel?.({ channelId: rem.channel_id, agentId, provider });
        }
        removalOutcomes.push({ ...rem, outcome: 'applied' });
      } catch (err) {
        this.options.onError(err);
        removalOutcomes.push({
          ...rem,
          outcome: 'failed',
          error_code: 'channel_purge_failed',
          error_message: 'Channel local state could not be purged',
        });
      }
    }

    const failures: Record<string, unknown>[] = [];
    for (const item of manifest.channels) {
      if (!item.enabled) {
        this.enqueue('channel.status', {
          ...this.scope(item),
          runtime_incarnation: randomUUID(),
          status_sequence: 1,
          instance_started: true,
          connection_state: 'stopped',
          diagnostics_state: 'unknown',
          status_code: 'disabled',
          status_message: 'Channel is disabled',
          checks: [],
        });
        continue;
      }
      if (this.instances.has(item.channel_id)) continue;
      const instance: Instance = { channel: item, runtime: undefined!, incarnation: randomUUID(), sequence: 0 };
      try {
        instance.runtime = this.options.create(item, decoded.get(item.channel_id)!, {
          status: state => this.status(instance, state),
          metadata: patch => this.metadata(instance, patch),
        });
        this.instances.set(item.channel_id, instance);
        this.status(instance, 'connecting');
        await instance.runtime.start();
      } catch {
        this.status(instance, 'failed');
        await this.drop(item.channel_id);
        failures.push({ channel_id: item.channel_id, error_code: 'channel_start_failed', error_message: 'Channel connection could not start' });
      }
    }
    if (report) {
      this.enqueue('channel.reconcile.result', {
        request_id: manifest.request_id,
        node_id: this.options.nodeId,
        manifest_revision: manifest.manifest_revision,
        outcome: failures.length ? 'retryable_failed' : 'applied',
        failures,
        applied_channel_ids: manifest.channels.filter(item => !failures.some(f => f.channel_id === item.channel_id)).map(item => item.channel_id),
        removal_outcomes: removalOutcomes,
      });
    }
    void this.flush().catch(this.options.onError);
  }

  /** Remove the retired Agent from the cached manifest and stop/purge all its listeners. */
  purgeAgent(agentId: string): Promise<void> {
    const task = this.chain.then(async () => {
      const cached = this.get<ChannelManifest>('manifest');
      if (!cached) return;
      for (const item of cached.channels.filter(channel => channel.agent_id === agentId)) {
        await this.drop(item.channel_id);
        await this.options.purgeChannel?.({ channelId: item.channel_id, agentId: item.agent_id, provider: item.provider });
        this.db.prepare("DELETE FROM outbox WHERE json_extract(payload,'$.channel_id')=?").run(item.channel_id);
      }
      this.put('manifest', { ...cached, channels: cached.channels.filter(channel => channel.agent_id !== agentId) });
    });
    this.chain = task.catch(() => {});
    return task;
  }

  private async drop(id: string): Promise<void> {
    const instance = this.instances.get(id);
    if (!instance) return;
    this.instances.delete(id);
    this.options.remove(instance.channel.agent_id, instance.channel.provider);
    await instance.runtime.stop();
  }

  private status(instance: Instance, report: ManagedStatusReport): void {
    if (this.closed || this.instances.get(instance.channel.channel_id) !== instance) return;
    const rawState = typeof report === 'string' ? report : report.state;
    const code = typeof report === 'string' ? report : (report.code ?? report.state);
    const label = instance.channel.provider === 'wechat' ? 'WeChat' : 'Feishu';
    const message = typeof report === 'string' ? `${label} ${report}` : (report.message ?? `${label} ${rawState}`);
    const sequence = ++instance.sequence;
    this.enqueue('channel.status', {
      ...this.scope(instance.channel),
      runtime_incarnation: instance.incarnation,
      status_sequence: sequence,
      instance_started: sequence === 1,
      connection_state: rawState === 'ready' ? 'connected' : rawState,
      diagnostics_state: rawState === 'ready' ? 'ok' : 'unknown',
      status_code: code,
      status_message: message,
      checks: [],
    });
  }

  private metadata(instance: Instance, patch: ManagedChannel['provider_runtime']): void {
    if (this.closed || this.instances.get(instance.channel.channel_id) !== instance) return;
    const cached = this.get<ChannelManifest>('manifest')!;
    const item = cached.channels.find(item => item.channel_id === instance.channel.channel_id);
    if (!item || generation(item) !== generation(instance.channel)) return;
    Object.assign(item.provider_runtime, patch);
    Object.assign(instance.channel.provider_runtime, patch);
    this.put('manifest', cached);
    this.enqueue('channel.runtime_metadata', { ...this.scope(item), provider_runtime_patch: patch });
  }

  private scope(item: ManagedChannel): Record<string, unknown> {
    return {
      request_id: randomUUID(),
      node_id: this.options.nodeId,
      channel_id: item.channel_id,
      provider_identity_fingerprint: item.provider_identity_fingerprint,
      provider_identity_revision: item.provider_identity_revision,
      channel_revision: item.channel_revision,
      credential_revision: item.credential_revision,
    };
  }

  private enqueue(type: string, payload: Record<string, unknown>): void {
    this.db.prepare('INSERT INTO outbox(type,payload) VALUES(?,?)').run(type, JSON.stringify(payload));
    void this.flush().catch(this.options.onError);
  }

  flush(): Promise<void> {
    if (this.flushing) return this.flushing;
    if (this.closed || this.revoked || !this.options.relay.ready || !this.get<ChannelManifest>('manifest')?.manifest_revision) return Promise.resolve();
    const task = (async () => {
      while (!this.closed && this.options.relay.ready) {
        const row = this.db.prepare('SELECT * FROM outbox ORDER BY seq LIMIT 1').get() as { seq: number; type: string; payload: string } | undefined;
        if (!row) break;
        const result = await this.options.relay.request(row.type, JSON.parse(row.payload));
        if (result.payload.outcome === 'fatal_owner_mismatch') { await this.revoke(); break; }
        if (result.payload.outcome === 'retryable_store_busy') break;
        if (row.type === 'channel.reconcile.result') {
          const acks = result.payload.removal_token_outcomes as { outcome: string }[] | undefined;
          if (!['accepted', 'already_applied', 'stale', 'already_applied_by_head'].includes(String(result.payload.head_outcome)) || acks?.some(ack => !['accepted', 'already_applied', 'already_applied_by_head'].includes(ack.outcome))) break;
        }
        this.db.prepare('DELETE FROM outbox WHERE seq=?').run(row.seq);
      }
    })().finally(() => { this.flushing = undefined; });
    this.flushing = task;
    return task;
  }

  async revoke(): Promise<void> {
    this.revoked = true;
    for (const id of [...this.instances.keys()]) await this.drop(id);
  }

  async stop(): Promise<void> {
    this.closed = true;
    clearInterval(this.timer);
    await this.chain;
    for (const id of [...this.instances.keys()]) await this.drop(id);
    await this.flushing?.catch(() => {});
    this.db.close();
  }
}

function generation(item: ManagedChannel): string {
  return `${item.provider_identity_fingerprint}:${item.provider_identity_revision}:${item.channel_revision}:${item.credential_revision}`;
}
