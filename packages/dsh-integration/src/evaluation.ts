import { appendFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { Socket } from 'node:net';
import { mkdir, mkdtemp, readFile, writeFile, cp, lstat, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { EvaluationHistory, EvaluationQuestion, EvaluationLimits, EvaluationUsage, MemoryCandidate, PreparationResult, EvaluationAnswer } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from './client.js';
import { RpcPeer } from './rpc.js';
import { contextTools } from './agent-context.js';
import { hash } from './evaluation/history.js';
import type { AgentConfiguration, SessionBinding } from './index.js';

export interface NanoEvaluationOptions {
  id: string;
  root: string;
  provider: string;
  model: string;
  /** Explicit provider profile, never discovered from production configuration. */
  providerPatch: unknown[];
  /** Packaged product guidance supplied by the composition root, never private owner skills. */
  builtinSkillsRoot: string;
  knowledge?: AgentConfiguration['knowledge'];
  reasoningEffort?: string;
  allowModelCalls: boolean;
  /** Used by deterministic integration tests, not a CLI injection point. */
  environment?: NodeJS.ProcessEnv;
}
interface Audit { requests: string; deniedTools: number; usage: EvaluationUsage }
interface Running { client: RuntimeClient; peer: RpcPeer; socket: Socket; socketDir: string; dir: string; workspace: string; rootSessionId: string; binding: SessionBinding; audit?: Audit; stopping?: Promise<void> }
interface Prepared { workspace: string; sources: string[]; agentId: string }
const answerConversation = 'evaluation-question';

/** Exercise Nano's native memory services while keeping benchmark control data outside them. */
export class NanoMemoryCandidate implements MemoryCandidate {
  readonly id: string;
  private active?: Running;
  private stopped = false;
  private work?: Promise<unknown>;
  constructor(private readonly options: NanoEvaluationOptions) {
    this.id = options.id;
    if (!options.allowModelCalls) throw new Error('Nano evaluation requires explicit model-call permission');
    if (options.knowledge?.memoryMode === 'legacy') throw new Error('This candidate adapter supports document memory only');
  }

  /** Prepare full history and seal the current candidate's persistent representation. */
  prepare(history: EvaluationHistory, limits: EvaluationLimits): Promise<PreparationResult> {
    return this.track(() => this.prepareHistory(history, limits));
  }

  private async prepareHistory(history: EvaluationHistory, limits: EvaluationLimits): Promise<PreparationResult> {
    this.stopped = false;
    const started = Date.now();
    let run: Running | undefined;
    const agentId = `evaluation-${randomUUID()}`;
    const sources = [...history.sessions.map(session => session.id), answerConversation];
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      timer = setTimeout(() => { this.stopped = true; this.kill(); }, limits.timeoutMs);
      run = await this.launch('prepare', agentId, sources, limits, history);
      const mapping = await run.peer.request('import', history);
      await run.client.rpc.request('knowledge.sources.sync', { agentId, snapshot: { revision: 'evaluation-1', allowed: sources, excluded: [] } });
      await run.client.rpc.request('session.ensure', run.binding);
      const result = await run.peer.request('prepare', {}) as { status: 'ready' | 'incomplete' | 'failed'; reason?: string; details: unknown };
      const audit = await run.peer.request('audit', {}) as Audit;
      const evidenceRef = join(run.dir, 'receipt.json');
      const receipt = { candidateId: this.id, historyDigest: hash(history), importedSessions: history.sessions.length,
        importedMessages: history.sessions.reduce((sum, session) => sum + session.turns.length, 0), evidenceRef,
        usage: { ...audit.usage, elapsedMs: Date.now() - started } };
      await writeFile(join(run.dir, 'source-map.json'), JSON.stringify(mapping, null, 2));
      await writeFile(evidenceRef, JSON.stringify({ ...receipt, ...audit, result }, null, 2));
      await this.stop(run);
      if (result.status !== 'ready') return { status: result.status, receipt, reason: result.reason ?? 'Memory preparation incomplete' };
      const workspace = join(run.dir, 'prepared');
      await copyMemory(run.workspace, workspace);
      const preparedRef = join(run.dir, 'prepared.json');
      await writeFile(preparedRef, JSON.stringify({ workspace, sources, agentId } satisfies Prepared));
      return { status: 'ready', preparedRef, receipt };
    } catch (error) {
      if (!run) return { status: this.stopped ? 'incomplete' : 'failed', reason: String(error) };
      const audit = await this.failedAudit(run, error);
      return { status: this.stopped ? 'incomplete' : 'failed', reason: String(error), receipt: { candidateId: this.id,
        historyDigest: hash(history), importedSessions: 0, importedMessages: 0, evidenceRef: audit.evidenceRef, usage: audit.usage } };
    } finally { if (timer) clearTimeout(timer); if (run) await this.stop(run); }
  }

  /** Answer in a new runtime, restoring memory without the preparation sessions. */
  answer(preparedRef: string, question: EvaluationQuestion, limits: EvaluationLimits): Promise<EvaluationAnswer> {
    return this.track(() => this.answerQuestion(preparedRef, question, limits));
  }

  private async answerQuestion(preparedRef: string, question: EvaluationQuestion, limits: EvaluationLimits): Promise<EvaluationAnswer> {
    this.stopped = false;
    let run: Running | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const prepared = JSON.parse(await readFile(preparedRef, 'utf8')) as Prepared;
      timer = setTimeout(() => { this.stopped = true; this.kill(); }, limits.timeoutMs);
      run = await this.launch('answer', prepared.agentId, prepared.sources, limits, undefined, prepared.workspace, question);
      await run.client.rpc.request('knowledge.sources.sync', { agentId: prepared.agentId, snapshot: { revision: 'evaluation-1', allowed: prepared.sources, excluded: [] } });
      await run.client.rpc.request('session.ensure', run.binding);
      await run.client.rpc.request('session.submit', { sessionId: run.rootSessionId, inputId: question.id, mode: 'followup',
        source: { kind: 'system', channel: 'evaluation-inbox', messageId: question.id },
        content: [{ type: 'text', text: 'Inbox has a new request. Check and read its source conversation.' }] });
      await run.peer.request('idle', {});
      const audit = await run.peer.request('audit', {}) as Audit;
      const evidenceRef = join(run.dir, 'answer.json');
      const deliveries = JSON.parse(await readFile(join(run.dir, 'deliveries.json'), 'utf8')) as string[];
      const terminal = await run.client.rpc.request('session.lookup', { sessionId: run.rootSessionId, inputId: question.id }) as { terminal?: { kind: string } };
      await writeFile(evidenceRef, JSON.stringify({ ...audit, terminal, deliveries, questionDate: question.date }, null, 2));
      if (terminal.terminal?.kind !== 'completed') return { status: 'failed', reason: 'Answer turn did not complete', evidenceRef, usage: audit.usage };
      if (!deliveries.length) return { status: 'failed', reason: 'Agent delivered no public answer', evidenceRef, usage: audit.usage };
      // Keep all delivered prose in order; never choose the best message using gold.
      return { status: 'completed', text: deliveries.join('\n\n'), evidenceRef, usage: audit.usage };
    } catch (error) {
      return { status: 'failed', reason: String(error), ...(run ? await this.failedAudit(run, error) : {}) };
    }
    finally { if (timer) clearTimeout(timer); if (run) await this.stop(run); }
  }

  /** Cancel owned work, retaining its audit directory. */
  async close(): Promise<void> {
    this.stopped = true; this.kill();
    await this.work;
    if (this.active) await this.stop(this.active);
  }

  private track<T>(operation: () => Promise<T>): Promise<T> {
    if (this.work) return Promise.reject(new Error('Evaluation candidate already has an active operation'));
    const work = operation().finally(() => { if (this.work === work) this.work = undefined; });
    this.work = work; return work;
  }

  private async failedAudit(run: Running, error: unknown) {
    const evidenceRef = join(run.dir, 'failure.json');
    let audit: Partial<Audit> = {};
    try { audit = JSON.parse(await readFile(join(run.dir, 'usage.json'), 'utf8')) as Audit; } catch { /* Startup can fail before the recorder mounts. */ }
    const usage = audit.usage ?? { modelCalls: 0, inputTokens: null, outputTokens: null, costUsd: null, elapsedMs: 0 };
    await writeFile(evidenceRef, JSON.stringify({ ...audit, reason: String(error) }, null, 2));
    return { evidenceRef, usage };
  }

  private kill() {
    const child = this.active?.client.process;
    if (!child?.pid || child.exitCode !== null || child.signalCode !== null) return;
    try { process.kill(process.platform === 'win32' ? child.pid : -child.pid, 'SIGKILL'); }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error; }
  }
  private stop(run: Running): Promise<void> {
    return run.stopping ??= this.stopRuntime(run);
  }

  private async stopRuntime(run: Running) {
    if (run.client.process.exitCode === null && run.client.process.signalCode === null) {
      const watchdog = setTimeout(() => this.kill(), 5000);
      try { await run.client.shutdown(); } catch { this.kill(); await run.client.exited; }
      finally { clearTimeout(watchdog); }
    }
    run.peer.close(); run.socket.destroy(); await rm(run.socketDir, { recursive: true, force: true });
    if (this.active === run) this.active = undefined;
  }

  private async launch(stage: 'prepare' | 'answer', agentId: string, sources: string[], limits: EvaluationLimits,
    history?: EvaluationHistory, prepared?: string, question?: EvaluationQuestion): Promise<Running> {
    await mkdir(this.options.root, { recursive: true });
    const dir = await mkdtemp(join(resolve(this.options.root), `${stage}-`));
    const home = join(dir, 'runtime'), workspace = join(dir, 'workspace');
    await mkdir(home); await mkdir(workspace);
    if (prepared) await copyMemory(prepared, workspace);
    const socketDir = await mkdtemp(join(tmpdir(), 'nme-')), socketPath = join(socketDir, 'control');
    const rootSessionId = `evaluation-${stage}-${randomUUID()}`;
    await prepareProfile(home, [...this.options.providerPatch, { insert: [{ id: 'nano-memory-evaluation',
      name: '@nano/dsh-integration/evaluation/runtime', config: { socket: socketPath, workspace, agentId, rootSessionId, stage, audit: dir, limits } }] }]);
    if (this.stopped) { await rm(socketDir, { recursive: true, force: true }); throw new Error('Evaluation cancelled before runtime start'); }
    const client = new RuntimeClient({ home, cwd: workspace, env: this.options.environment,
      onLog: text => appendFileSync(join(dir, 'runtime.log'), text) });
    const socket = new Socket();
    // Install ownership before any awaited runtime initialization, so deadlines can kill it.
    const binding = { sessionId: rootSessionId, agentId, ownerId: 'evaluation-owner', cwd: workspace, revision: '1' };
    const run: Running = { client, socket, peer: new RpcPeer(socket, socket), dir, socketDir, workspace, rootSessionId, binding };
    this.active = run;
    const deliveries: string[] = [];
    await writeFile(join(dir, 'deliveries.json'), '[]');
    client.rpc.handle('product.call', async value => {
      const call = value as { method: string; args: Record<string, unknown> };
      if (call.method === 'memory.sources.refresh') {
        await client.rpc.request('knowledge.sources.sync', { agentId, snapshot: { revision: 'evaluation-1', allowed: sources, excluded: [] } });
        return { refreshed: true };
      }
      if (call.method === 'inbox.prepare') return { prepared: true };
      if (call.method === 'inbox' && question) {
        if (call.args.action === 'check') return { conversations: [{ target: answerConversation, unread_count: 1 }] };
        if (call.args.target !== answerConversation) throw new Error('No historical inbox is connected in the answer environment');
        return { target: answerConversation, messages: [{ id: question.id,
          sender: { id: 'evaluation-owner', type: 'user', name: 'Owner', is_owner: true }, time: question.date,
          content: [{ type: 'text', text: question.text }] }] };
      }
      if (call.method === 'send_message' && question && call.args.target === answerConversation && typeof call.args.text === 'string') {
        deliveries.push(call.args.text); await writeFile(join(dir, 'deliveries.json'), JSON.stringify(deliveries));
        return { status: 'sent', message_id: `local-${deliveries.length}`, target: answerConversation };
      }
      throw new Error(`Evaluation product operation unavailable: ${call.method}`);
    });
    try {
      if (this.stopped) throw new Error('Evaluation cancelled');
      const configuration: AgentConfiguration = { agentId, workspace, revision: '1', mode: 'global', provider: this.options.provider,
        model: this.options.model, reasoningEffort: this.options.reasoningEffort, maxTokens: limits.maxOutputTokens,
        personal: { bindingId: 'evaluation-binding', ownerId: 'evaluation-owner', conversationId: answerConversation, epoch: 1 },
        features: { dreaming: false, skill_creation: false, task_graph: false, heartbeat: false, cron_scheduling: false },
        skillRoots: [{ path: this.options.builtinSkillsRoot, source: 'builtin' }],
        skillSelection: { mode: 'explicit_allowlist', names: stage === 'prepare' ? ['nano-memory'] : [] },
        toolAllowlist: stage === 'prepare' ? ['read', 'write', 'edit', 'memory_maintenance', ...contextTools] : ['read', 'glob', 'grep', 'inbox', 'send_message'],
        knowledge: { ...this.options.knowledge, memoryMode: 'document' } };
      await client.rpc.request('initialize', { protocol: 1, agents: [configuration],
        bindings: [...(history?.sessions.map(session => ({ ...binding, sessionId: session.id })) ?? []), binding] });
      await new Promise<void>((resolveConnect, reject) => {
        socket.once('error', reject); socket.connect(socketPath, () => { socket.off('error', reject); resolveConnect(); });
      });
      return run;
    } catch (error) { await this.failedAudit(run, error); await this.stop(run); throw new Error(`${String(error)} (audit: ${dir})`); }
  }
}

async function copyMemory(sourceWorkspace: string, targetWorkspace: string) {
  const source = join(sourceWorkspace, '.nanoassistant/memory');
  // The answer file tools never receive symlinks back into the source runtime.
  const check = async (path: string): Promise<void> => {
    const info = await lstat(path); if (info.isSymbolicLink()) throw new Error('Prepared memory contains a symlink');
    if (info.isDirectory()) for (const name of await readdir(path)) if (name !== '.git') await check(join(path, name));
  };
  await check(source);
  await mkdir(join(targetWorkspace, '.nanoassistant/maintenance'), { recursive: true });
  await cp(source, join(targetWorkspace, '.nanoassistant/memory'), { recursive: true, filter: path => !path.split('/').includes('.git') });
  await cp(join(sourceWorkspace, '.nanoassistant/maintenance/documents.json'), join(targetWorkspace, '.nanoassistant/maintenance/documents.json'));
}
