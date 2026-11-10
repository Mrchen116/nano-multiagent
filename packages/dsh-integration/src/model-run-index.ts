import type { ModelRun } from './model-fallback.js';

interface Entry {
  run: ModelRun;
  order: number;
}

/** Look up mutable ModelRuns in the original per-session insertion order. */
export class ModelRunIndex {
  private readonly runs = new Map<string, Entry>();
  private readonly open = new Map<string, Entry>();
  private readonly inputs = new Map<string, Entry>();
  private readonly attempts = new Map<number, Entry>();
  private readonly withdrawn = new Set<string>();

  update(run: ModelRun): void {
    const entry = this.runs.get(run.id) ?? {run, order: this.runs.size};
    entry.run = run;
    this.runs.set(run.id, entry);
    if (run.state === 'completed') this.open.delete(run.id);
    else this.open.set(run.id, entry);
    for (const id of run.inputs) this.remember(this.inputs, id, entry);
    for (const {turn} of run.attempts) this.remember(this.attempts, turn, entry);
    for (const id of run.withdrawn ?? []) this.withdrawn.add(id);
  }

  private remember<Key>(index: Map<Key, Entry>, key: Key, entry: Entry): void {
    // An earlier run can acquire inputs after a later run already owns them.
    if ((index.get(key)?.order ?? -1) < entry.order) index.set(key, entry);
  }

  all(): ModelRun[] {
    return [...this.runs.values()].map(entry => entry.run);
  }

  get hasActive(): boolean {
    return this.open.size > 0;
  }

  active(): ModelRun[] {
    return [...this.open.values()].map(entry => entry.run);
  }

  latestActive(predicate: (run: ModelRun) => boolean): ModelRun | undefined {
    let last: Entry | undefined;
    for (const entry of this.open.values())
      if ((!last || last.order < entry.order) && predicate(entry.run)) last = entry;
    return last?.run;
  }

  forInput(id: string): ModelRun | undefined {
    return this.inputs.get(id)?.run;
  }

  forAttempt(turn: number): ModelRun | undefined {
    return this.attempts.get(turn)?.run;
  }

  wasWithdrawn(id: string): boolean {
    return this.withdrawn.has(id);
  }
}
