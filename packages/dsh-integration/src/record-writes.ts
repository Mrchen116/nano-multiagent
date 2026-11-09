/** Serialize durable record updates and retain failed snapshots for the next checkpoint. */
export class RecordWrites<T> {
  private readonly pending = new Map<string, T>();
  private tail = Promise.resolve();

  constructor(private readonly write: (key: string, value: T) => Promise<void>) {}

  get busy(): boolean { return this.pending.size > 0; }

  put(key: string, value: T): Promise<void> {
    this.pending.set(key, value);
    return this.flush();
  }

  flush(): Promise<void> {
    if (!this.busy) return this.tail;
    const attempt = this.tail.then(async () => {
      for (const [key, value] of this.pending) {
        await this.write(key, value);
        // A newer snapshot can arrive while this write is in flight.
        if (this.pending.get(key) === value) this.pending.delete(key);
      }
    });
    this.tail = attempt.catch(() => {});
    return attempt;
  }

  settled(): Promise<void> { return this.tail; }
}
