import { TRAJECTORY_MAX_BYTES, encodeTrajectoryValue } from '@nano/product-contracts';

interface Batch { frames: unknown[]; bytes: number; created: number }

/** Drains native iterators promptly while bounding memory owned by a slow viewer. */
export class TrajectoryStream {
  private readonly batches: Batch[] = [];
  private failure?: Error;
  private done = false;
  private pulling = false;
  private wake?: () => void;
  private deadline?: NodeJS.Timeout;
  private capacity?: () => void;
  readonly controller = new AbortController();
  readonly settled: Promise<void>;

  constructor(source: (signal: AbortSignal) => AsyncIterable<unknown>) {
    this.settled = this.pump(source);
  }

  /** Pull exactly one bounded batch, or renew an idle long read after twenty seconds. */
  async next(): Promise<{ frames: unknown[]; done: boolean }> {
    if (this.pulling) throw new Error('trajectory_next_already_pending');
    this.pulling = true;
    try {
      if (!this.batches.length && !this.done && !this.failure) {
        await new Promise<void>(resolve => {
          const timer = setTimeout(() => { this.wake = undefined; resolve(); }, 20_000);
          this.wake = () => { clearTimeout(timer); this.wake = undefined; resolve(); };
        });
      }
      if (this.failure) throw this.failure;
      const batch = this.batches.shift();
      this.armDeadline();
      this.capacity?.();
      return { frames: batch?.frames ?? [], done: this.done && this.batches.length === 0 };
    } finally { this.pulling = false; }
  }

  /** Cancels only the read iterator, never its Session or Agent owner. */
  close(error?: Error): void {
    this.failure ??= error;
    this.done = true;
    this.batches.length = 0;
    clearTimeout(this.deadline);
    this.controller.abort(error);
    this.wake?.();
    this.capacity?.();
  }

  private async pump(source: (signal: AbortSignal) => AsyncIterable<unknown>) {
    try {
      for await (const frame of source(this.controller.signal)) {
        if (this.controller.signal.aborted) break;
        let first = true;
        for (const part of encodeTrajectoryValue(frame)) {
          const bytes = Buffer.byteLength(JSON.stringify(part)) + 1;
          const budget = TRAJECTORY_MAX_BYTES - 1024;
          let batch = this.batches.at(-1);
          if (!batch || batch.bytes + bytes > budget) {
            if (this.batches.length === 2) {
              if (first) throw new Error('trajectory_slow_consumer');
              // One large native DTO must be pulled over several bounded batches.
              // Waiting within that DTO is not evidence of a slow observer.
              await new Promise<void>(resolve => { this.capacity = resolve; });
              this.capacity = undefined;
              if (this.controller.signal.aborted) return;
            }
            batch = { frames: [], bytes: 0, created: Date.now() };
            this.batches.push(batch);
          }
          batch.frames.push(part); batch.bytes += bytes;
          first = false;
          this.armDeadline(); this.wake?.();
        }
      }
      this.done = true; this.wake?.();
    } catch (error) {
      if (!this.controller.signal.aborted) this.close(error instanceof Error ? error : new Error(String(error)));
    }
  }

  private armDeadline() {
    clearTimeout(this.deadline);
    const oldest = this.batches[0];
    if (oldest) this.deadline = setTimeout(() => this.close(new Error('trajectory_slow_consumer')), Math.max(0, oldest.created + 5000 - Date.now()));
  }
}
