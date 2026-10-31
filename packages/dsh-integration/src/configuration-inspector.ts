/** Own disposable native inspections independently of conversation runtimes. */
import {createHash, randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
import {writeFileSync} from 'node:fs';
import {mkdir, mkdtemp, readdir, readFile, rm} from 'node:fs/promises';
import {join} from 'node:path';
import {promisify} from 'node:util';
import {setTimeout as delay} from 'node:timers/promises';
import type {ProfilePnpmInvocation} from '@deepseek-ai/dsh-app-boot';
import type {AgentConfiguration} from './index.js';
import {prepareProfile, RuntimeClient} from './client.js';

const execute = promisify(execFile);
export type InspectionErrorCode = 'catalog_timeout' | 'catalog_cancelled' | 'catalog_busy' | 'catalog_failed' | 'catalog_cleanup_failed';
/** Stable transient failures; none describe a configuration mutation outcome. */
export class InspectionError extends Error {
  constructor(readonly code: InspectionErrorCode, message: string) {super(message); this.name = 'InspectionError';}
}
export interface ConfigurationInspection {
  method: 'catalog' | 'preview';
  config: AgentConfiguration;
  cwd: string;
  providers?: Record<string, unknown>;
  packageManager?: ProfilePnpmInvocation;
  /** Explicit trusted profile additions, used by native integration fixtures. */
  profilePatch?: unknown[];
  requestId?: string;
  deadlineAt?: number;
}
interface Options {
  root: string;
  env?: NodeJS.ProcessEnv;
  onLog?: (text: string) => void;
  timeoutMs?: number;
  maxWorkers?: number;
  retryMs?: number;
}
interface Flight {
  id: string;
  generation: number;
  abort: AbortController;
  waiters: number;
  result: Promise<unknown>;
}
const cancelled = () => new InspectionError('catalog_cancelled', 'Capability inspection was superseded or cancelled');
const cleanupFailed = () => new InspectionError('catalog_cleanup_failed', 'Temporary inspection cleanup could not be confirmed');

/** A bounded native process owner, with one flight per generation and candidate.
 *
 * Node shares this owner across partitions. Each worker owns an entire temporary
 * home, so unknown plugin initialization/teardown can be killed without touching
 * conversation processes or depending on private Session storage formats.
 */
export class ConfigurationInspector {
  private readonly flights = new Map<string, Flight>();
  private readonly failures = new Map<string, {until: number; error: Error}>();
  private generation = 0;
  private closed = false;
  private startup?: Promise<void>;
  private cleanupError?: Error;
  private active = 0;
  private orphanTotal = 0;
  private readonly totals = {current:0, timeout:0, error:0, cancelled:0};
  private readonly duration = {count:0, sum:0, buckets:[0,0,0,0,0]};
  constructor(private readonly options: Options) {}

  /** Recover only this node's marked inspections while its Gateway lock is held. */
  initialize(): Promise<void> {
    return this.startup ??= this.recover();
  }

  /** Build a catalog or prompt with an independently cancellable waiter.
   *
   * Args:
   *   input: Trusted configuration and native composition inputs.
   *   signal: Cancels this waiter; the last waiter cancels the actual worker.
   * Returns:
   *   The unchanged native catalog or prompt projection.
   */
  inspect(input: ConfigurationInspection, signal?: AbortSignal): Promise<unknown> {
    if (this.closed || signal?.aborted) return Promise.reject(cancelled());
    if (this.cleanupError) return Promise.reject(this.cleanupError);
    const key = createHash('sha256').update(JSON.stringify([this.generation, input.method, input.config, input.cwd,
      input.providers, input.packageManager, input.profilePatch])).digest('hex');
    const now = Date.now();
    for (const [id, failure] of this.failures) if (failure.until <= now) this.failures.delete(id);
    const failed = this.failures.get(key);
    if (failed) return Promise.reject(failed.error);
    let flight = this.flights.get(key);
    if (!flight) {
      if (this.active >= (this.options.maxWorkers ?? 2)) return Promise.reject(new InspectionError('catalog_busy', 'Capability inspections are busy; retry shortly'));
      flight = {id:randomUUID(), generation:this.generation, abort:new AbortController(), waiters:0, result:Promise.resolve()};
      const owned = flight;
      this.active++;
      this.flights.set(key, owned);
      owned.result = this.run(owned, input).catch(error => {
        if (!(error instanceof InspectionError && error.code === 'catalog_cancelled')) {
          this.failures.set(key, {until:Date.now() + (this.options.retryMs ?? 1000), error});
        }
        throw error;
      }).finally(() => {this.active--; if (this.flights.get(key) === owned) this.flights.delete(key); this.log('inspection.released',{refresh_id:owned.id});});
    }
    const shared = flight;
    this.log('inspection.join', {request_id:input.requestId,refresh_id:shared.id,agent_id:input.config.agentId});
    return new Promise((resolve, reject) => {
      shared.waiters++;
      let done = false;
      const finish = (error?: unknown, value?: unknown) => {
        if (done) return;
        done = true;
        signal?.removeEventListener('abort', abort);
        shared.waiters--;
        if (shared.waiters === 0) shared.abort.abort(cancelled());
        if (error) reject(error); else resolve(value);
      };
      const abort = () => finish(cancelled());
      signal?.addEventListener('abort', abort, {once:true});
      shared.result.then(value => finish(shared.generation === this.generation ? undefined : cancelled(), value), error => finish(error));
      if (signal?.aborted) abort();
    });
  }

  /** Fence new joins and all old completions after a real model/plugin change. */
  invalidate(): void {
    this.generation++;
    this.failures.clear();
    for (const flight of this.flights.values()) flight.abort.abort(cancelled());
  }

  /** Cancel and reclaim all owned workers before releasing the node's lock. */
  async close(): Promise<void> {
    this.closed = true;
    this.invalidate();
    await Promise.allSettled([...this.flights.values()].map(flight => flight.result));
  }

  /** Bounded process metrics suitable for diagnostics without per-request labels. */
  metrics() {
    return {preview_active:this.active, preview_orphan_total:this.orphanTotal,
      catalog_refresh_total:{...this.totals}, catalog_refresh_duration_ms:{...this.duration, buckets:[...this.duration.buckets]}};
  }

  private log(event: string, fields: Record<string, unknown> = {}) {
    this.options.onLog?.(`${JSON.stringify({component:'node.configuration-inspector',event,...fields,...this.metrics()})}\n`);
  }

  private async run(flight: Flight, input: ConfigurationInspection): Promise<unknown> {
    const started = Date.now();
    const deadline = Math.min(input.deadlineAt ?? Infinity, started + (this.options.timeoutMs ?? 7000));
    const timer = setTimeout(() => flight.abort.abort(new InspectionError('catalog_timeout', 'Capability inspection deadline exceeded')), Math.max(0, deadline - started));
    const signal = flight.abort.signal;
    let home: string | undefined;
    let worker: RuntimeClient | undefined;
    let result: unknown;
    let failure: unknown;
    const trace = {request_id:input.requestId,refresh_id:flight.id,agent_id:input.config.agentId};
    const abort = () => worker?.rpc.notify('configuration.cancel', {});
    signal.addEventListener('abort', abort, {once:true});
    try {
      await this.initialize(); signal.throwIfAborted();
      home = await mkdtemp(join(this.options.root, `inspection-${flight.id}-`));
      await prepareProfile(home, input.profilePatch ?? []); signal.throwIfAborted();
      worker = new RuntimeClient({home, cwd:input.cwd, env:this.options.env, onLog:this.options.onLog,
        inspectionWorker:{id:flight.id, deadlineAt:deadline, requestId:input.requestId}});
      // Flush identity before sending any operation that can mount user plugins.
      writeFileSync(join(home, 'inspection.json'), JSON.stringify({id:flight.id,pid:worker.process.pid}), {mode:0o600});
      this.log('inspection.start', trace);
      const operation = (async () => {
        await worker!.rpc.request('initialize', {protocol:1, agents:[], bindings:[], providers:input.providers, packageManager:input.packageManager});
        signal.throwIfAborted();
        return worker!.rpc.request(`configuration.${input.method}`, {config:input.config,cwd:input.cwd});
      })();
      let rejectAbort: () => void;
      const aborted = new Promise<never>((_resolve, reject) => {
        rejectAbort = () => reject(signal.reason);
        signal.addEventListener('abort', rejectAbort, {once:true});
        if (signal.aborted) rejectAbort();
      });
      try {result = await Promise.race([operation, aborted]);}
      finally {signal.removeEventListener('abort', rejectAbort!);}
      signal.throwIfAborted();
      if (flight.generation !== this.generation) throw cancelled();
    } catch (error) {
      failure = error instanceof InspectionError ? error : new InspectionError('catalog_failed', 'Capability inspection failed');
    } finally {
      clearTimeout(timer);
      signal.removeEventListener('abort', abort);
      try {
        if (worker) await terminateWorker(worker);
        if (home) await rm(home, {recursive:true,force:true});
        this.log('cleanup.done', {...trace,elapsed_ms:Date.now()-started});
      } catch {
        failure = this.cleanupError = cleanupFailed();
        this.log('cleanup.error', {...trace,inspection_home:home});
      }
      const elapsed = Date.now()-started;
      const outcome = failure instanceof InspectionError && failure.code === 'catalog_timeout' ? 'timeout'
        : failure instanceof InspectionError && failure.code === 'catalog_cancelled' ? 'cancelled' : failure ? 'error' : 'current';
      this.totals[outcome]++;
      this.duration.count++; this.duration.sum+=elapsed;
      for (const [i, limit] of [500,1000,3000,5000,Infinity].entries()) if (elapsed<=limit) this.duration.buckets[i]!++;
      this.log('inspection.done', {...trace,result:outcome,elapsed_ms:elapsed,preview_active:this.active-1});
    }
    if (failure) throw failure;
    return result;
  }

  private async recover(): Promise<void> {
    await mkdir(this.options.root, {recursive:true,mode:0o700});
    for (const entry of await readdir(this.options.root, {withFileTypes:true})) {
      if (!entry.isDirectory() || !/^inspection-[0-9a-f-]{36}-[A-Za-z0-9]+$/.test(entry.name)) continue;
      const home = join(this.options.root, entry.name);
      try {
        const lease = JSON.parse(await readFile(join(home,'inspection.json'),'utf8')) as {id:string;pid:number};
        if (!entry.name.startsWith(`inspection-${lease.id}-`) || !Number.isSafeInteger(lease.pid) || lease.pid<=0) throw cleanupFailed();
        const info = await processInfo(lease.pid);
        if (info) {
          if (!info.split(/\s+/).includes(`--nano-inspection-id=${lease.id}`)) throw cleanupFailed();
          killGroup(lease.pid, 'SIGTERM');
          await delay(150);
          if (await processInfo(lease.pid)) {killGroup(lease.pid,'SIGKILL');await delay(150);}
          if (await processInfo(lease.pid)) throw cleanupFailed();
        }
        await rm(home,{recursive:true,force:true});
        this.orphanTotal++;
        this.log('orphan.reclaimed', {refresh_id:lease.id});
      } catch {
        this.log('cleanup.error', {inspection_home:home});
        throw this.cleanupError = cleanupFailed();
      }
    }
  }
}

function killGroup(pid: number, signal: NodeJS.Signals) {
  try {process.kill(process.platform === 'win32' ? pid : -pid, signal);}
  catch (error) {if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error;}
}
async function terminateWorker(worker: RuntimeClient): Promise<void> {
  if (worker.process.exitCode !== null || worker.process.signalCode !== null) {await worker.exited;return;}
  if (!worker.process.pid) {await worker.exited;return;}
  killGroup(worker.process.pid, 'SIGTERM');
  if (await Promise.race([worker.exited.then(()=>true), delay(150).then(()=>false)])) return;
  killGroup(worker.process.pid, 'SIGKILL');
  if (!await Promise.race([worker.exited.then(()=>true), delay(500).then(()=>false)])) throw cleanupFailed();
}
async function processInfo(pid: number): Promise<string | undefined> {
  try {
    const {stdout} = await execute('ps', ['-p',String(pid),'-o','stat=','-o','args='], {timeout:1000});
    const text = stdout.trim();
    return !text || text.startsWith('Z') ? undefined : text;
  } catch (error) {if ((error as {code?:number}).code === 1) return;throw error;}
}
