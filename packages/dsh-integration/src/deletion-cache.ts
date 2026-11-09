import { SessionProjectionCache, projectionCacheDomainSpec } from '@deepseek-ai/dsh-session-projection-cache';
import type { Session, SessionId } from '@deepseek-ai/dsh-session';

/** Adds per-session retirement to the official projection cache. */
export default class DeletionCache extends SessionProjectionCache {
  private readonly retired = new Set<string>();
  private readonly writes = new Map<string, Set<Promise<void>>>();

  override async write(session: Session): Promise<void> {
    if (this.retired.has(session.id)) return;
    const pending = this.writes.get(session.id) ?? new Set<Promise<void>>();
    this.writes.set(session.id, pending);
    const write = super.write(session);
    pending.add(write);
    try { await write; }
    finally {
      pending.delete(write);
      if (!pending.size) this.writes.delete(session.id);
    }
  }

  override coldSnapshot(...args: Parameters<SessionProjectionCache['coldSnapshot']>): ReturnType<SessionProjectionCache['coldSnapshot']> {
    if (this.retired.has(args[0].id)) throw new Error('Session execution was deleted');
    return super.coldSnapshot(...args);
  }

  /** Reject new writebacks before waiting on any already accepted checkpoint. */
  fence(ids: readonly string[]): void {
    for (const id of ids) this.retired.add(id);
  }

  /** Remove a single durable checkpoint after its outstanding writes drain. */
  async forget(id: SessionId): Promise<void> {
    this.fence([id]);
    await Promise.allSettled(this.writes.get(id) ?? []);
    // coldSnapshot queues its synchronous writeback before returning.
    const domain = this.ctx.storageDomain.get(projectionCacheDomainSpec.name);
    if (!domain) throw new Error('Session projection cache domain is unavailable');
    const sessions = domain.table('sessions');
    await sessions.delete(id);
    if (sessions.get(id) !== undefined) throw new Error('Session projection cache still exists');
  }
}
