import type { Agent } from '@deepseek-ai/dsh-agent';

interface Options {
  agents(): Agent[];
  busy(): boolean;
  pause(): Promise<void>;
  resume(): Promise<void>;
}
interface Hold {
  operationId: string;
  cancelled: boolean;
  release(): void;
  released: Promise<void>;
  tasks: Promise<unknown>[];
  preparing: Promise<{ ready: boolean }>;
  cleanup?: Promise<void>;
}

/** Claims native true-idle phases without cancelling or waiting for active work. */
export class UpdateBarrier {
  private current?: Hold;
  constructor(private readonly options: Options) {}

  /** Whether new runtime admissions must wait for the owning update operation. */
  get held(): boolean { return !!this.current; }

  /** Try to freeze every live Agent, including children; busy work is left running. */
  prepare(operationId: string): Promise<{ ready: boolean }> {
    if (this.current) return this.current.operationId === operationId ? this.current.preparing : Promise.resolve({ ready: false });
    let release!: () => void;
    const released = new Promise<void>(resolve => { release = resolve; });
    const hold: Hold = { operationId, cancelled: false, release, released, tasks: [], preparing: Promise.resolve({ ready: false }) };
    this.current = hold;
    hold.preparing = this.acquire(hold).then(async ready => {
      if (!ready) await this.clear(hold);
      return { ready };
    }, async error => { await this.clear(hold); throw error; });
    return hold.preparing;
  }

  private busy(): boolean {
    return this.options.busy() || this.options.agents().some(agent => agent.status !== 'idle' || agent.inbox.nextTurn.length > 0 || agent.inbox.nextStep.length > 0);
  }
  private async acquire(hold: Hold): Promise<boolean> {
    if (this.busy()) return false;
    await this.options.pause();
    if (hold.cancelled || this.busy()) return false;
    const agents = this.options.agents();
    try {
      // runMaintenance claims idle synchronously. No driver can start between
      // this check and its hold, unlike awaiting whenIdle() then stopping.
      for (const agent of agents) hold.tasks.push(agent.runMaintenance(() => hold.released));
    } catch { return false; }
    await Promise.resolve();
    return !hold.cancelled && !this.busy() && this.options.agents().every(agent => agents.includes(agent));
  }
  private clear(hold: Hold, resume = true): Promise<void> {
    return hold.cleanup ??= (async () => {
      hold.release();
      await Promise.allSettled(hold.tasks);
      try { if (resume) await this.options.resume(); }
      finally { if (this.current === hold) this.current = undefined; }
    })();
  }

  /** Release only the matching operation; stale callers cannot release a new hold. */
  async release(operationId: string): Promise<{ released: boolean }> {
    const hold = this.current;
    if (!hold || hold.operationId !== operationId) return { released: false };
    hold.cancelled = true;
    await hold.preparing;
    await this.clear(hold);
    return { released: true };
  }

  /** Release maintenance before shutdown waits for idle, without restarting timers. */
  async stop(): Promise<void> {
    const hold = this.current;
    if (!hold) return;
    hold.cancelled = true;
    await hold.preparing;
    await this.clear(hold, false);
  }
}
