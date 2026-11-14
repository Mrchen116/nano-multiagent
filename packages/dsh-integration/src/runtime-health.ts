/** Observe filesystem progress independently of model and tool execution. */
export class RuntimeHealth {
  private timer?: ReturnType<typeof setInterval>;
  private pending = false;
  private deadline = 0;
  private next = 0;
  private previous: number;
  private closed = false;
  constructor(private readonly probe: () => Promise<unknown>, private readonly fail: () => void,
    private readonly options: {intervalMs?: number; timeoutMs?: number; tickMs?: number} = {}) {
    this.previous = Date.now();
    this.timer = setInterval(() => this.tick(), options.tickMs ?? 1000);
    this.timer.unref();
  }
  private tick(): void {
    if (this.closed) return;
    const now = Date.now(), timeout = this.options.timeoutMs ?? 30000;
    // A suspended host cannot observe progress. Grant a full awake deadline,
    // retaining the sole pending request instead of accumulating abandoned RPCs.
    if (now - this.previous > (this.options.tickMs ?? 1000) * 3 || now < this.previous) {
      if (this.pending) this.deadline = now + timeout;
      this.next = now;
    }
    this.previous = now;
    if (this.pending) {
      if (now >= this.deadline) { this.close(); this.fail(); }
      return;
    }
    if (now < this.next) return;
    this.pending = true;
    this.deadline = now + timeout;
    void this.probe().then(() => {
      this.pending = false;
      this.next = Date.now() + (this.options.intervalMs ?? 15000);
    }, () => {
      if (!this.closed) { this.close(); this.fail(); }
    });
  }
  /** Stop observation; the owning RPC peer settles its pending call on exit. */
  close(): void { this.closed = true; clearInterval(this.timer); }
}

/** Reap the isolated runtime and its independently grouped tool descendants. */
export async function terminateRuntimeTree(pid: number): Promise<void> {
  const {execFile} = await import('node:child_process');
  const {promisify} = await import('node:util');
  const execute=promisify(execFile);
  if (process.platform==='win32') {await execute('taskkill',['/pid',String(pid),'/t','/f'],{timeout:5000});return;}
  const signal=(target:number,kind:NodeJS.Signals)=>{
    try {process.kill(target,kind);}catch(error){if((error as NodeJS.ErrnoException).code!=='ESRCH')throw error;}
  };
  // Freeze the failed owner before collecting tools, so it cannot start more.
  signal(pid,'SIGSTOP');
  try {
    const {stdout}=await execute('ps',['-axo','pid=,ppid=,pgid='],{timeout:2000});
    const rows=stdout.trim().split('\n').map(line=>line.trim().split(/\s+/).map(Number));
    const owned=new Set([pid]);
    for(let size=-1;size!==owned.size;) {size=owned.size;for(const [child,parent] of rows)if(owned.has(parent!))owned.add(child!);}
    const groups=new Set(rows.filter(([child,,group])=>owned.has(child!)&&owned.has(group!)).map(([, ,group])=>group!));
    for(const group of groups)if(group!==pid)signal(-group,'SIGKILL');
    for(const child of owned)if(child!==pid)signal(child,'SIGKILL');
  } finally {signal(-pid,'SIGKILL');}
}
