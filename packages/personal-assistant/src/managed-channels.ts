import { createHash, randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { ChannelKey, type CredentialEnvelope, type ProtocolFrame } from '@nano/channels';

export interface ManagedChannel {
  channel_id: string; node_id: string; agent_id: string; provider: 'feishu'; enabled: boolean;
  config: { app_id: string }; provider_runtime: { bot_open_id?: string; owner_open_id?: string };
  credential_key_id: string; credential_envelope: CredentialEnvelope; credential_revision: number;
  provider_identity_fingerprint: string; provider_identity_revision: number; channel_revision: number;
}
export interface ChannelManifest {
  request_id: string; node_id: string; owner_id: string; manifest_revision: number; channels: ManagedChannel[];
  removals: { removal_token: string; channel_id: string; deletion_manifest_revision: number }[];
}
interface Runtime { start(): Promise<void>; stop(): void }
interface Options {
  nodeId: string; ownerId: string; key: ChannelKey; hasAgent(id: string): boolean;
  relay: { readonly ready: boolean; request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  create(channel: ManagedChannel, secret: Record<string, string>, callbacks: { status(state: string): void; metadata(patch: ManagedChannel['provider_runtime']): void }): Runtime;
  remove(agentId: string): void;
  onError(error: unknown): void;
}
interface Instance { channel: ManagedChannel; runtime: Runtime; incarnation: string; sequence: number }

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
  private get<T>(key: string): T | undefined { const row = this.db.prepare('SELECT value FROM state WHERE key=?').get(key) as { value: string } | undefined; return row ? JSON.parse(row.value) as T : undefined; }
  private put(key: string, value: unknown) { this.db.prepare('INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run(key, JSON.stringify(value)); }
  /** Seed only an empty cache; subsequent restarts use the authoritative encrypted manifest. */
  seed(channels: { agentId: string; enabled: boolean; appId: string; appSecret: string; botOpenId?: string; ownerOpenId?: string }[]): void {
    if (this.get('manifest')) return;
    const items = channels.map(item => {
      const channel_id = `feishu:${item.agentId}`;
      return { channel_id, agent_id: item.agentId, node_id: this.options.nodeId, provider: 'feishu' as const, enabled: item.enabled,
        config: { app_id: item.appId }, provider_runtime: { bot_open_id: item.botOpenId, owner_open_id: item.ownerOpenId },
        credential_key_id: this.options.key.registration.credential_key_id, credential_revision: 1, channel_revision: 1, provider_identity_revision: 1,
        provider_identity_fingerprint: createHash('sha256').update(`feishu\0${item.appId}`).digest('hex'),
        credential_envelope: this.options.key.seal({ app_secret: item.appSecret }, { owner_id: this.options.ownerId, node_id: this.options.nodeId, agent_id: item.agentId, channel_id, provider: 'feishu', credential_revision: 1 }),
      };
    });
    this.put('manifest', { request_id: randomUUID(), owner_id: this.options.ownerId, node_id: this.options.nodeId, manifest_revision: 0, channels: items, removals: [] });
  }
  async start(): Promise<void> {
    const cached = this.get<ChannelManifest>('manifest');
    if (cached) await this.apply(cached, false);
    this.timer = setInterval(() => { void this.flush().catch(this.options.onError); }, 1000); this.timer.unref();
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
        const cached = this.get<ChannelManifest>('manifest'); const item = cached?.channels.find(item => item.channel_id === frame.payload.channel_id);
        if (item && item.channel_revision === frame.payload.channel_revision) { this.drop(item.channel_id); await this.apply(cached!, false); }
      }
    });
    this.chain = task.catch(() => {}); return task;
  }
  private prepare(manifest: ChannelManifest): Map<string, Record<string, string>> {
    if (manifest.node_id !== this.options.nodeId || manifest.owner_id !== this.options.ownerId || !Number.isInteger(manifest.manifest_revision) || manifest.manifest_revision < 0) throw new Error('Channel manifest scope invalid');
    const decoded = new Map<string, Record<string, string>>(); const agents = new Set<string>();
    for (const item of manifest.channels) {
      if (!item.channel_id || decoded.has(item.channel_id) || agents.has(item.agent_id) || item.node_id !== this.options.nodeId || !this.options.hasAgent(item.agent_id) || item.provider !== 'feishu' || typeof item.enabled !== 'boolean' || !item.config.app_id || item.credential_key_id !== this.options.key.registration.credential_key_id || [item.channel_revision, item.credential_revision, item.provider_identity_revision].some(value => !Number.isInteger(value) || value < 1) || item.provider_identity_fingerprint !== createHash('sha256').update(`feishu\0${item.config.app_id}`).digest('hex')) throw new Error('Channel manifest item invalid');
      const secret = this.options.key.open(item.credential_envelope, { owner_id: manifest.owner_id, node_id: manifest.node_id, agent_id: item.agent_id, channel_id: item.channel_id, provider: item.provider, credential_revision: item.credential_revision });
      if (!secret.app_secret) throw new Error('Channel credentials missing');
      decoded.set(item.channel_id, secret); agents.add(item.agent_id);
    }
    return decoded;
  }
  private async apply(manifest: ChannelManifest, report = true): Promise<void> {
    const previous = this.get<ChannelManifest>('manifest');
    if (previous && manifest.manifest_revision < previous.manifest_revision) return;
    // Validate every envelope before replacing any working connection or persisted desired state.
    const decoded = this.prepare(manifest);
    this.put('manifest', manifest);
    for (const [id, instance] of this.instances) {
      const next = manifest.channels.find(item => item.channel_id === id);
      if (!next?.enabled || generation(next) !== generation(instance.channel)) this.drop(id);
    }
    const failures: Record<string, unknown>[] = [];
    for (const item of manifest.channels) {
      if (!item.enabled) {
        this.enqueue('channel.status', { ...this.scope(item), runtime_incarnation: randomUUID(), status_sequence: 1, instance_started: true, connection_state: 'stopped', diagnostics_state: 'unknown', status_code: 'disabled', status_message: 'Channel is disabled', checks: [] });
        continue;
      }
      if (this.instances.has(item.channel_id)) continue;
      const instance: Instance = { channel: item, runtime: undefined!, incarnation: randomUUID(), sequence: 0 };
      try {
        instance.runtime = this.options.create(item, decoded.get(item.channel_id)!, { status: state => this.status(instance, state), metadata: patch => this.metadata(instance, patch) });
        this.instances.set(item.channel_id, instance); this.status(instance, 'connecting'); await instance.runtime.start();
      } catch {
        this.status(instance, 'failed'); this.drop(item.channel_id);
        failures.push({ channel_id: item.channel_id, error_code: 'channel_start_failed', error_message: 'Channel connection could not start' });
      }
    }
    if (report) this.enqueue('channel.reconcile.result', { request_id: manifest.request_id, node_id: this.options.nodeId, manifest_revision: manifest.manifest_revision,
      outcome: failures.length ? 'retryable_failed' : 'applied', failures, applied_channel_ids: manifest.channels.filter(item => !failures.some(f => f.channel_id === item.channel_id)).map(item => item.channel_id),
      removal_outcomes: manifest.removals.map(item => ({ ...item, outcome: 'applied' })),
    });
    void this.flush().catch(this.options.onError);
  }
  private drop(id: string): void {
    const instance = this.instances.get(id); if (!instance) return;
    this.instances.delete(id); this.options.remove(instance.channel.agent_id); instance.runtime.stop();
  }
  private status(instance: Instance, state: string): void {
    if (this.closed || this.instances.get(instance.channel.channel_id) !== instance) return;
    const sequence = ++instance.sequence;
    this.enqueue('channel.status', { ...this.scope(instance.channel), runtime_incarnation: instance.incarnation, status_sequence: sequence, instance_started: sequence === 1,
      connection_state: state === 'ready' ? 'connected' : state === 'failed' ? 'disconnected' : state,
      diagnostics_state: state === 'ready' ? 'ok' : 'unknown', status_code: state, status_message: `Feishu ${state}`, checks: [],
    });
  }
  private metadata(instance: Instance, patch: ManagedChannel['provider_runtime']): void {
    if (this.closed || this.instances.get(instance.channel.channel_id) !== instance) return;
    const cached = this.get<ChannelManifest>('manifest')!; const item = cached.channels.find(item => item.channel_id === instance.channel.channel_id);
    if (!item || generation(item) !== generation(instance.channel)) return;
    Object.assign(item.provider_runtime, patch); Object.assign(instance.channel.provider_runtime, patch); this.put('manifest', cached);
    this.enqueue('channel.runtime_metadata', { ...this.scope(item), provider_runtime_patch: patch });
  }
  private scope(item: ManagedChannel): Record<string, unknown> {
    return { request_id: randomUUID(), node_id: this.options.nodeId, channel_id: item.channel_id, provider_identity_fingerprint: item.provider_identity_fingerprint, provider_identity_revision: item.provider_identity_revision, channel_revision: item.channel_revision, credential_revision: item.credential_revision };
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
        if (result.payload.outcome === 'fatal_owner_mismatch') { this.revoke(); break; }
        if (result.payload.outcome === 'retryable_store_busy') break;
        if (row.type === 'channel.reconcile.result') {
          const acks = result.payload.removal_token_outcomes as { outcome: string }[] | undefined;
          if (!['accepted', 'already_applied', 'stale', 'already_applied_by_head'].includes(String(result.payload.head_outcome)) || acks?.some(ack => !['accepted', 'already_applied', 'already_applied_by_head'].includes(ack.outcome))) break;
        }
        this.db.prepare('DELETE FROM outbox WHERE seq=?').run(row.seq);
      }
    })().finally(() => { this.flushing = undefined; }); this.flushing = task; return task;
  }
  revoke(): void { this.revoked = true; for (const id of this.instances.keys()) this.drop(id); }
  async stop(): Promise<void> { this.closed = true; clearInterval(this.timer); await this.chain; for (const id of this.instances.keys()) this.drop(id); await this.flushing?.catch(() => {}); this.db.close(); }
}
function generation(item: ManagedChannel): string { return `${item.provider_identity_fingerprint}:${item.provider_identity_revision}:${item.channel_revision}:${item.credential_revision}`; }
