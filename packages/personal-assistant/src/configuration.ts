import { DatabaseSync } from 'node:sqlite';
import { agentConfigurationFingerprint, canonicalAgentConfiguration, type CanonicalAgentConfiguration } from '@nano/product-contracts';

interface Intent { operation_id: string; candidate_fingerprint: string; expected_previous_fingerprint: string | null; agent: Record<string, unknown> }
interface Receipt { kind: string; intent: Intent; candidate: CanonicalAgentConfiguration; status: 'pending' | 'applied' | 'rejected'; error_code?: string; message?: string }
interface Options {
  current(agentId: string): Record<string, unknown> | undefined;
  resolve(candidate: CanonicalAgentConfiguration, creating: boolean): Promise<CanonicalAgentConfiguration>;
  persist(candidate: CanonicalAgentConfiguration): Promise<void>;
  apply(candidate: CanonicalAgentConfiguration): Promise<void>;
}
/** Write-ahead operation receipts reconcile durable node configuration with runtime scopes. */
export class ConfigurationOperations {
  private readonly db: DatabaseSync;
  private readonly chains = new Map<string, Promise<unknown>>();
  constructor(path: string, private readonly options: Options) {
    this.db = new DatabaseSync(path);
    this.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, receipt TEXT NOT NULL)');
  }
  private get(id: string): Receipt | undefined {
    const row = this.db.prepare('SELECT receipt FROM operations WHERE id=?').get(id) as { receipt: string } | undefined;
    return row ? JSON.parse(row.receipt) as Receipt : undefined;
  }
  private save(receipt: Receipt): void { this.db.prepare('INSERT INTO operations VALUES(?,?) ON CONFLICT(id) DO UPDATE SET receipt=excluded.receipt').run(receipt.intent.operation_id, JSON.stringify(receipt)); }
  private result(receipt: Receipt): Record<string, unknown> {
    return { operation_id: receipt.intent.operation_id, candidate_fingerprint: receipt.intent.candidate_fingerprint, status: receipt.status,
      ...(receipt.status === 'applied' ? { agent: receipt.candidate } : {}),
      ...(receipt.error_code ? { error_code: receipt.error_code, message: receipt.message } : {}) };
  }
  status(id: string): Record<string, unknown> { const receipt = this.get(id); return receipt ? this.result(receipt) : { operation_id: id, status: 'pending' }; }
  handle(kind: 'create' | 'apply', intent: Intent): Promise<Record<string, unknown>> {
    const key = String(intent.agent?.agent_id ?? intent.operation_id);
    const task = (this.chains.get(key) ?? Promise.resolve()).then(() => this.perform(kind, intent));
    const settled = task.catch(() => {}); this.chains.set(key, settled);
    void settled.then(() => { if (this.chains.get(key) === settled) this.chains.delete(key); });
    return task;
  }
  private async perform(kind: string, intent: Intent): Promise<Record<string, unknown>> {
    const reject = (code: string, message: string) => ({ operation_id: intent.operation_id, candidate_fingerprint: intent.candidate_fingerprint, status: 'rejected', error_code: code, message });
    if (!intent.operation_id || !intent.candidate_fingerprint || !intent.agent) return reject('invalid_agent_config', 'Missing operation identity or candidate');
    let receipt = this.get(intent.operation_id);
    if (receipt) {
      if (receipt.kind !== kind || receipt.intent.candidate_fingerprint !== intent.candidate_fingerprint || receipt.intent.expected_previous_fingerprint !== intent.expected_previous_fingerprint) return reject('operation_id_reused', 'Operation identity is already bound to a different intent');
      if (receipt.status !== 'pending') return this.result(receipt);
    } else {
      try {
        if (agentConfigurationFingerprint(intent.agent) !== intent.candidate_fingerprint) return reject('invalid_agent_config', 'Candidate fingerprint does not match');
        if (kind === 'apply' && !intent.expected_previous_fingerprint || kind === 'create' && intent.expected_previous_fingerprint != null) return reject('invalid_agent_config', 'Invalid expected previous fingerprint');
        const candidate = await this.options.resolve(canonicalAgentConfiguration(intent.agent), kind === 'create');
        receipt = { kind, intent: { ...intent, agent: canonicalAgentConfiguration(intent.agent) }, candidate, status: 'pending' };
        this.save(receipt);
      } catch (error) { return reject('invalid_agent_config', String(error)); }
    }
    const current = this.options.current(receipt.candidate.agent_id);
    const fingerprint = current ? agentConfigurationFingerprint(current) : null;
    const desired = agentConfigurationFingerprint(receipt.candidate);
    if (fingerprint !== desired && fingerprint !== receipt.intent.expected_previous_fingerprint) {
      receipt.status = 'rejected'; receipt.error_code = 'operation_conflict'; receipt.message = 'Node configuration no longer matches the expected previous state'; this.save(receipt); return this.result(receipt);
    }
    if (fingerprint !== desired) await this.options.persist(receipt.candidate);
    // A crash or disconnected runtime keeps a pending receipt, recoverable by the same intent.
    await this.options.apply(receipt.candidate);
    receipt.status = 'applied'; this.save(receipt); return this.result(receipt);
  }
  async recover(): Promise<void> {
    for (const row of this.db.prepare('SELECT receipt FROM operations').all() as { receipt: string }[]) {
      const receipt = JSON.parse(row.receipt) as Receipt;
      if (receipt.status === 'pending') await this.handle(receipt.kind as 'apply' | 'create', receipt.intent);
    }
  }
  async close(): Promise<void> { await Promise.all(this.chains.values()); this.db.close(); }
}
