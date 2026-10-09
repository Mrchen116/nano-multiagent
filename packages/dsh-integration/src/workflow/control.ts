import type { ObjectJsonSchema } from "@deepseek-ai/dsh-tools";
import { createHash } from "node:crypto";

export interface CallOptions {
  label?: string;
  phase?: string;
  provider?: string;
  model?: string;
  reasoningEffort?: string;
  schema?: ObjectJsonSchema;
}
export interface WorkflowCall {
  ordinal: number;
  key: string;
  prompt: string;
  options: CallOptions;
  state: "queued" | "running" | "completed" | "failed" | "cancelled";
  attempts: { id: string; startedAt: number; endedAt?: number }[];
  completion?: number;
  value?: unknown;
  replayed?: boolean;
  error?: string;
}
interface Child {
  id: string;
  result: Promise<{ value: unknown; success: boolean }>;
  dispose(): Promise<void>;
}
interface Configuration {
  concurrency: number;
  maxAgents: number;
  previous?: WorkflowCall[];
  persist(calls: WorkflowCall[]): Promise<void>;
  remaining(): Promise<number | null>;
  start(
    prompt: string,
    options: CallOptions,
    signal: AbortSignal,
  ): Promise<Child>;
}
interface Active {
  abort?: AbortController;
  restart: boolean;
  stopped: boolean;
  settled?: Promise<void>;
  settle?: () => void;
}
const canonical = (value: unknown): string =>
  JSON.stringify(value, (_key, item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? Object.fromEntries(
          Object.keys(item)
            .sort()
            .map((key) => [key, item[key]]),
        )
      : item,
  );

/** Owns logical calls; native child handles remain honest per-attempt identities. */
export class WorkflowControl {
  readonly calls: WorkflowCall[] = [];
  private paused = false;
  private stopped = false;
  private slots = 0;
  private completion = 0;
  private readonly active = new Map<number, Active>();
  private readonly tasks = new Set<Promise<unknown>>();
  private readonly waiters = new Set<() => void>();
  private writes = Promise.resolve();
  private prefix: WorkflowCall[];
  private replayOpen = true;
  private readonly replayWaiters = new Map<
    number,
    { resolve(value: unknown): void; reject(error: unknown): void }
  >();
  private replayDraining = false;
  constructor(private readonly config: Configuration) {
    this.prefix = [];
    for (const call of config.previous ?? []) {
      if (call.ordinal !== this.prefix.length + 1 || call.state !== "completed")
        break;
      this.prefix.push(call);
    }
  }
  private persist() {
    const snapshot = structuredClone(this.calls);
    const write = this.writes.then(() => this.config.persist(snapshot));
    this.writes = write;
    return write;
  }
  private wake() {
    for (const resolve of this.waiters) resolve();
    this.waiters.clear();
  }
  private wait() {
    return new Promise<void>((resolve) => this.waiters.add(resolve));
  }
  pause() {
    this.paused = true;
  }
  resume() {
    this.paused = false;
    this.wake();
  }
  stop() {
    this.stopped = true;
    for (const entry of this.active.values()) entry.abort?.abort();
    for (const entry of this.replayWaiters.values())
      entry.reject(new Error("Workflow stopped"));
    this.replayWaiters.clear();
    this.wake();
  }
  async restart(ordinal: number) {
    const entry = this.active.get(ordinal);
    if (
      !entry?.abort ||
      entry.restart ||
      this.calls[ordinal - 1]?.state !== "running"
    )
      throw new Error("Only a running child can be restarted");
    entry.restart = true;
    entry.abort.abort();
    await entry.settled;
  }
  async stopChild(ordinal: number) {
    const entry = this.active.get(ordinal);
    if (!entry) throw new Error("Unknown active child");
    entry.stopped = true;
    entry.abort?.abort();
    this.wake();
    await entry.settled;
  }
  /** Assign the ordinal before any asynchronous admission or concurrency wait. */
  call(prompt: string, options: CallOptions): Promise<unknown> {
    if (this.stopped) return Promise.reject(new Error("Workflow stopped"));
    if (this.calls.length >= this.config.maxAgents)
      return Promise.reject(new Error("Workflow total Agent cap exceeded"));
    const { label: _label, phase: _phase, ...behavior } = options;
    const ordinal = this.calls.length + 1;
    const key = createHash("sha256")
      .update(canonical([this.calls.at(-1)?.key ?? "", prompt, behavior]))
      .digest("hex");
    const call: WorkflowCall = {
      ordinal,
      key,
      prompt,
      options: structuredClone(options),
      state: "queued",
      attempts: [],
    };
    this.calls.push(call);
    const task = this.perform(call);
    this.tasks.add(task);
    void task.then(
      () => this.tasks.delete(task),
      () => this.tasks.delete(task),
    );
    return task;
  }
  private async perform(call: WorkflowCall): Promise<unknown> {
    const original = this.prefix[call.ordinal - 1];
    if (this.replayOpen && original?.key === call.key) {
      const result = new Promise<unknown>((resolve, reject) =>
        this.replayWaiters.set(call.ordinal, { resolve, reject }),
      );
      void this.releaseReplay();
      return result;
    }
    this.replayOpen = false;
    void this.releaseReplay();
    const entry: Active = { restart: false, stopped: false };
    this.active.set(call.ordinal, entry);
    let acquired = false;
    try {
      await this.persist();
      while (true) {
        while (
          !this.stopped &&
          !entry.stopped &&
          (this.paused || (!acquired && this.slots >= this.config.concurrency))
        )
          await this.wait();
        if (this.stopped) throw new Error("Workflow stopped");
        if (entry.stopped) {
          call.state = "cancelled";
          call.value = null;
          await this.persist();
          return null;
        }
        const remaining = await this.config.remaining();
        // Budget reads may yield; recheck the gate before publishing a child.
        if (
          this.stopped ||
          this.paused ||
          (!acquired && this.slots >= this.config.concurrency)
        )
          continue;
        if (remaining !== null && remaining <= 0)
          throw new Error("Workflow output-token budget exhausted");
        if (!acquired) {
          this.slots++;
          acquired = true;
        }
        entry.restart = false;
        entry.abort = new AbortController();
        entry.settled = new Promise<void>((resolve) => {
          entry.settle = resolve;
        });
        let child: Child | undefined;
        let outcome: { value: unknown; success: boolean } | undefined;
        let failure: unknown;
        try {
          child = await this.config.start(
            call.prompt,
            call.options,
            entry.abort.signal,
          );
          call.state = "running";
          call.attempts.push({ id: child.id, startedAt: Date.now() });
          await this.persist();
          outcome = await child.result;
        } catch (error) {
          failure = error;
        } finally {
          try {
            await child?.dispose();
          } finally {
            const attempt = call.attempts.at(-1);
            if (attempt) attempt.endedAt = Date.now();
            entry.settle!();
          }
        }
        if (this.stopped) throw new Error("Workflow stopped");
        if (entry.restart) {
          call.state = "queued";
          await this.persist();
          continue;
        }
        if (failure) throw failure;
        call.state = entry.stopped
          ? "cancelled"
          : outcome!.success
            ? "completed"
            : "failed";
        call.value = call.state === "completed" ? outcome!.value : null;
        call.completion = ++this.completion;
        await this.persist();
        return call.value;
      }
    } catch (error) {
      call.state = this.stopped ? "cancelled" : "failed";
      call.error = String(error);
      await this.persist();
      throw error;
    } finally {
      this.active.delete(call.ordinal);
      if (acquired) this.slots--;
      this.wake();
    }
  }
  private async releaseReplay() {
    if (this.replayDraining) return;
    this.replayDraining = true;
    try {
      while (this.replayWaiters.size) {
        const remaining = this.prefix
          .filter(
            (call) =>
              !this.calls[call.ordinal - 1]?.replayed &&
              (this.replayOpen || this.replayWaiters.has(call.ordinal)),
          )
          .sort((a, b) => a.completion! - b.completion!);
        const original = remaining[0];
        if (!original) break;
        const waiting = this.replayWaiters.get(original.ordinal);
        if (!waiting) break;
        const call = this.calls[original.ordinal - 1]!;
        call.state = "completed";
        call.value = structuredClone(original.value);
        call.replayed = true;
        call.completion = ++this.completion;
        await this.persist();
        this.replayWaiters.delete(original.ordinal);
        waiting.resolve(structuredClone(call.value));
      }
    } catch (error) {
      for (const waiting of this.replayWaiters.values()) waiting.reject(error);
      this.replayWaiters.clear();
    } finally {
      this.replayDraining = false;
    }
  }
  async drain() {
    await Promise.allSettled([...this.tasks]);
    await this.writes;
  }
}
