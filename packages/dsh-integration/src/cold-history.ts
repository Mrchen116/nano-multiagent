import { createHash, randomUUID } from 'node:crypto';
import { cp, mkdir, mkdtemp, rename, rm, writeFile } from 'node:fs/promises';
import { isAbsolute, join } from 'node:path';
import { Context } from '@deepseek-ai/cordis';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import type {} from '@deepseek-ai/dsh-client-file-upload';
import { LocalAttachmentStore } from '@deepseek-ai/dsh-attachment-local';
import { SessionId, SessionStore } from '@deepseek-ai/dsh-session';
import JsonlSessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl';
import { SessionQueryEngine } from '@deepseek-ai/dsh-session-query';
import { Storage } from '@deepseek-ai/dsh-storage';
import { JsonStorageBackend } from '@deepseek-ai/dsh-storage-json';
import { DomainFacility } from '@deepseek-ai/dsh-storage-domain';
import { TypertRegistry } from '@deepseek-ai/dsh-typert-registry';
import type { TrajectoryScope } from '@nano/product-contracts';
import type { AgentConfiguration, SessionBinding } from './index.js';
import type { RpcPeer } from './rpc.js';
import { NativeTrajectory } from './trajectory.js';
import { trajectoryRunsDomain } from './trajectory-runs.js';
import { trajectorySourcesDomain } from './trajectory-attachments.js';

interface ColdSource { home: string; binding: SessionBinding; config: AgentConfiguration }
export interface ColdTrajectoryRequest extends ColdSource { scope: TrajectoryScope }
export interface ColdExportRequest extends ColdSource { sessionId: string }
type Handler = (params: unknown) => unknown | Promise<unknown>;
interface Reader { ctx: Context; trajectory: NativeTrajectory; handlers: Map<string, Handler>; close(): Promise<void> }

/** Exact historical reads need no search index or indexing worker. */
class ColdQuery extends SessionQueryEngine {
  async searchSessions(): Promise<never> { throw new Error('trajectory_read_only_method_required'); }
  async searchEvents(): Promise<never> { throw new Error('trajectory_read_only_method_required'); }
}

/** Control-host carrier for stopped product homes; never loads their profiles.
 *
 * Args:
 *   ctx: Control context supplying the installed public, pure projection folds.
 *   home: Control home in which to publish complete distillation exports.
 */
export class ColdHistory {
  private readonly readers = new Map<string, Reader>();
  constructor(private readonly ctx: Context, private readonly home: string) {
    ctx.effect(() => () => this.dispose());
  }

  /** Register private RPCs. Source identities must come from Node's trusted registry. */
  register(peer: RpcPeer): void {
    peer.handle('cold.trajectory.prepare', value => this.prepare(value as ColdTrajectoryRequest));
    for (const method of ['call', 'open', 'next', 'abort']) {
      peer.handle(`cold.trajectory.${method}`, value => {
        const id = (value as { observerId: string }).observerId;
        const reader = this.readers.get(id);
        if (!reader) throw new Error('trajectory_observer_closed');
        return reader.handlers.get(`trajectory.${method}`)!(value);
      });
    }
    peer.handle('cold.trajectory.close', async value => { await this.close((value as { observerId: string }).observerId); return {}; });
    peer.handle('cold.session.export', value => this.export(value as ColdExportRequest));
  }

  /** Bind an observer to one trusted root and verified persisted descendant. */
  async prepare(request: ColdTrajectoryRequest) {
    this.validate(request);
    await this.close(request.scope.observerId);
    const reader = await this.reader(request);
    try {
      const result = await reader.trajectory.prepare(request.scope);
      this.readers.set(request.scope.observerId, reader);
      return result;
    } catch (error) { await reader.close(); throw error; }
  }

  /** Publish an exact cold snapshot without modifying or acquiring its source. */
  async export(request: ColdExportRequest): Promise<{ path: string }> {
    this.validate(request);
    if (request.sessionId !== request.binding.sessionId) throw new Error('trajectory_scope_not_allowed');
    const reader = await this.reader(request);
    try {
      using cut = await reader.ctx.sessionQuery.observeSession(SessionId(request.sessionId), { projectionMode: 'none' });
      const directory = join(this.home, 'cold-exports');
      await mkdir(directory, { recursive: true });
      // Match native export semantics: readers only see complete atomic snapshots.
      const path = join(directory, `${createHash('sha256').update(JSON.stringify([request.home, request.sessionId])).digest('hex')}.jsonl`);
      const body = [{ type: 'nano-dsh-history', version: 1, header: cut.header }, ...cut.events]
        .map(value => JSON.stringify(value)).join('\n') + '\n';
      const temporary = `${path}.${randomUUID()}.tmp`;
      await writeFile(temporary, body);
      await rename(temporary, path);
      return { path };
    } finally { await reader.close(); }
  }

  /** Release the observer and all pending native read streams. */
  async close(id: string): Promise<void> {
    const reader = this.readers.get(id);
    this.readers.delete(id);
    await reader?.close();
  }

  /** Drain every reader when the control host exits. */
  async dispose(): Promise<void> { await Promise.all([...this.readers.keys()].map(id => this.close(id))); }

  private validate({ home, binding, config }: ColdSource): void {
    if (!isAbsolute(home) || binding.agentId !== config.agentId) throw new Error('trajectory_scope_not_allowed');
  }

  private async reader(source: ColdSource): Promise<Reader> {
    const ctx = new Context();
    const scratchRoot = join(this.home, 'cold-readers');
    await mkdir(scratchRoot, { recursive: true });
    const scratch = await mkdtemp(join(scratchRoot, 'reader-'));
    const backend = new JsonStorageBackend(scratch);
    let domains: DomainFacility | undefined;
    let trajectory: NativeTrajectory | undefined;
    const close = async () => { trajectory?.dispose(); await domains?.closeAll(); await backend.close(); await ctx.fiber.dispose(); await rm(scratch, { recursive: true, force: true }); };
    try {
      new SessionStore(ctx);
      new JsonlSessionPersistence(ctx, { root: join(source.home, 'sessions') });
      new LocalAttachmentStore(ctx, { dshHome: source.home });
      // The control assembly already owns the official descriptor/catalog folds.
      // Sharing this public pure registry preserves DTOs without loading source plugins.
      ctx.provide('sessionProjections', this.ctx.sessionProjections);
      new ColdQuery(ctx);
      new TypertRegistry(ctx);
      // No Agent registry, file-upload resolver or execution provider is installed.
      // Controller writes are unreachable from NativeTrajectory; deny acquisition as well.
      const denied = () => { throw new Error('trajectory_read_only_method_required'); };
      ctx.provide('agents', { get: () => undefined, list: () => [], create: denied, resume: denied } as unknown as Context['agents']);
      ctx.provide('fileUploads', { registerAgentResolver: () => () => {} } as unknown as Context['fileUploads']);
      const controller = new SessionController(ctx, { nativeOpen: false });
      // Domain open can bootstrap legacy JSON; copy only Nano provenance so the
      // public storage adapter can never materialize or migrate the stopped home.
      for (const name of [trajectoryRunsDomain.name, trajectorySourcesDomain.name]) {
        for (const suffix of ['', '.json']) {
          await cp(join(source.home, 'storages', name + suffix), join(scratch, name + suffix), { recursive: true })
            .catch(error => { if (error.code !== 'ENOENT') throw error; });
        }
      }
      const storage = new Storage(ctx);
      storage.backend.register('json', backend);
      domains = new DomainFacility(ctx, { backend: 'json' });
      const runs = await domains.open(trajectoryRunsDomain);
      const sources = await domains.open(trajectorySourcesDomain);
      ctx.provide('nanoTrajectoryRuns', { read: async (id: string) => [...runs.table('runs').entries()].map(([, run]) => run)
        .filter(run => run.sessionId === id || run.parentSessionId === id)
        .map(run => ({ ...run, state: run.state === 'running' ? 'unknown' : run.state }))
        .sort((a, b) => a.startedAt - b.startedAt || a.runId.localeCompare(b.runId)) } as unknown as Context['nanoTrajectoryRuns']);
      ctx.provide('nanoTrajectoryAttachments', { read: async (id: string, attachmentId: string) =>
        sources.table('sources').get(Buffer.from(JSON.stringify([id, attachmentId])).toString('base64url')) ?? [] } as unknown as Context['nanoTrajectoryAttachments']);
      trajectory = new NativeTrajectory(ctx, { controller: Promise.resolve(controller),
        bindings: new Map([[source.binding.sessionId, source.binding]]),
        configurations: new Map([[`nano:${source.binding.agentId}:${source.binding.revision}`, source.config]]) });
      const handlers = new Map<string, Handler>();
      trajectory.register({ handle: (method: string, handler: Handler) => { handlers.set(method, handler); return () => { handlers.delete(method); }; } });
      return { ctx, trajectory, handlers, close };
    } catch (error) { await close(); throw error; }
  }
}
