import { Worker } from 'node:worker_threads';
import { workDetailLimits } from './work-sync.js';
import type { WorkJournalEvent } from './work-events.js';

export { projectWorkDetail } from './work-detail-projection.js';

export type WorkDetailJob =
  | { kind: 'prepare'; dbPath: string; seq: number; totalBytes: number; tempPath: string }
  | { kind: 'verify'; dbPath: string; id: number; totalBytes: number; sha256: string };

/** Own one reusable reader so JSON decode and hashing stay outside the serving loop. */
export class WorkDetailWorker {
  private worker?: Worker;

  run(job: WorkDetailJob): Promise<{ projection: WorkJournalEvent; sha256?: string | null }> {
    const worker = this.worker ??= new Worker(new URL('./work-detail-worker-entry.js', import.meta.url), {
      resourceLimits: {maxOldGenerationSizeMb: 384},
    });
    worker.ref();
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        clearTimeout(timer);
        worker.off('message', message);
        worker.off('error', error);
        worker.off('exit', exit);
        worker.unref();
      };
      const error = (reason: Error) => {
        if (this.worker === worker) this.worker = undefined;
        cleanup();
        reject(reason);
      };
      const exit = () => error(new Error('detail_worker_exited'));
      const message = (result: { projection: WorkJournalEvent; sha256?: string | null; error?: string; retryable?: boolean }) => {
        cleanup();
        if (result.error) reject(Object.assign(new Error(result.error), { validation: !result.retryable }));
        else resolve(result);
      };
      const timer = setTimeout(() => { void this.close(); }, workDetailLimits.workerTimeoutMs);
      worker.once('message', message).once('error', error).once('exit', exit);
      worker.postMessage(job);
    });
  }

  async close(): Promise<void> {
    const worker = this.worker;
    this.worker = undefined;
    await worker?.terminate();
  }
}
