import { readInteractionDraft, saveInteractionDraft } from './chat-api';
import type { DraftFailureReason } from './interaction-background';
import type { InteractionReplyInput } from './interactive/types';

interface DraftRecordOwner {
  current(): boolean;
  saved(updatedAt: string | undefined, left: boolean): void;
  failed(reason: DraftFailureReason | null): void;
  idle(): void;
}

/** Own an unsaved private edit independently of the renderer that happens to show it. */
export class InteractionDraftRecord {
  state: Record<string, unknown> = {};
  revision = 0;
  loaded = false;
  done = false;
  dirty = false;
  failure: DraftFailureReason | null = null;
  savedAt: string | undefined;
  loadFailed = false;
  renderVersion = 0;
  request: Promise<string | undefined> | null = null;
  private pending: {input: InteractionReplyInput; key: string} | null = null;
  private sending = false;
  private reading: Promise<boolean> | null = null;
  private live = true;
  private left = false;
  private editVersion = 0;
  private readVersion = 0;
  private version = 0;
  private views = new Set<symbol>();
  private listeners = new Set<() => void>();

  constructor(readonly conversationId: string, readonly messageId: string, private owner: DraftRecordOwner, private syncConflicts: boolean) {}

  get current(): boolean { return this.live && this.owner.current(); }
  get unsaved(): boolean { return this.dirty || !!this.failure || !!this.request; }
  get attached(): boolean { return this.views.size > 0; }
  get hasPendingSubmission(): boolean { return this.pending !== null; }
  get submitting(): boolean { return this.sending; }
  snapshot = (): number => this.version;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  /** Detaching conceals the view, not the edit; a clean detached record needs no cache. */
  attach(): () => void {
    const lease = Symbol();
    this.views.add(lease);
    return () => { this.views.delete(lease); this.releaseIfClean(); };
  }

  private releaseIfClean(): void {
    if (!this.attached && !this.unsaved && !this.pending) this.owner.idle();
  }

  private notify(): void {
    this.version += 1;
    for (const listener of this.listeners) listener();
    this.releaseIfClean();
  }

  /** Parser updates are not edits; repeated renderer notifications must not re-arm saving. */
  update(value: Record<string, unknown>, edited = false): boolean {
    if (!this.current) return false;
    const changed = JSON.stringify(this.state) !== JSON.stringify(value);
    this.state = value;
    if (!edited || !changed) return false;
    this.editVersion += 1;
    this.dirty = true;
    this.done = false;
    this.notify();
    return true;
  }

  async load(adopting = false): Promise<boolean> {
    if (!this.current) return false;
    if (this.pending) return !adopting && this.loaded;
    if (!adopting && this.unsaved) return this.loaded;
    if (!adopting && this.reading) return this.reading;
    const readVersion = ++this.readVersion, editVersion = this.editVersion;
    this.loadFailed = false;
    const operation = (async () => {
      try {
        // An adoption cannot race a PUT whose acknowledgement still owns the revision.
        if (adopting) await this.request;
        if (!this.current || readVersion !== this.readVersion) return false;
        const draft = await readInteractionDraft(this.conversationId, this.messageId);
        if (!this.current || readVersion !== this.readVersion || editVersion !== this.editVersion) return false;
        if (this.pending) return !adopting && this.loaded;
        if (!adopting && this.unsaved) return this.loaded;
        this.applyDraft(draft);
        return true;
      } catch {
        if (this.current && readVersion === this.readVersion) { this.loadFailed = true; this.notify(); }
        return false;
      }
    })();
    this.reading = operation;
    try { return await operation; }
    finally { if (this.reading === operation) this.reading = null; }
  }

  private applyDraft(draft: Awaited<ReturnType<typeof readInteractionDraft>>): void {
    this.state = draft.state;
    this.revision = draft.draft_revision;
    this.loaded = true;
    this.done = Boolean(draft.submission_message_id);
    this.dirty = false;
    this.failure = null;
    this.renderVersion += 1;
    this.owner.failed(null);
    this.notify();
  }

  private async syncLatest(): Promise<void> {
    try {
      const draft = await readInteractionDraft(this.conversationId, this.messageId);
      // Reading a draft from another device never gives this device a discard watermark.
      if (this.current && !this.pending) this.applyDraft(draft);
    } catch { /* Keep the local edit and retry the read on the next send or reconnect. */ }
  }

  /** Serialize PUTs across replacement views; a late acknowledgement never replaces newer input. */
  save(): Promise<string | undefined> {
    if (this.request) return this.request;
    if (!this.current || this.pending || !this.dirty) return Promise.resolve(this.savedAt);
    const operation = this.saveEdits().finally(() => {
      if (this.request === operation) this.request = null;
      this.notify();
    });
    this.request = operation;
    this.notify();
    return operation;
  }

  private async saveEdits(): Promise<string | undefined> {
    while (this.current && this.dirty) {
      if (this.syncConflicts && this.failure === 'conflict') {
        await this.syncLatest();
        break;
      }
      this.dirty = false;
      const value = this.state;
      try {
        const result = await saveInteractionDraft(this.conversationId, this.messageId, this.revision, value);
        if (!this.owner.current()) return undefined;
        // A real leave forgets the local edit, but its already-started successful PUT still
        // advances this device's watermark and follows the existing late-leave discard chain.
        this.owner.saved(result.updated_at ?? undefined, this.left);
        if (!this.live) return undefined;
        this.revision = result.draft_revision;
        this.savedAt = result.updated_at ?? undefined;
        this.failure = null;
        this.owner.failed(null);
        this.notify();
      } catch (error) {
        if (!this.current) return undefined;
        this.dirty = true;
        this.failure = (error as {status?: number}).status === 409 ? 'conflict' : 'transient';
        this.owner.failed(this.failure);
        this.notify();
        if (this.syncConflicts && this.failure === 'conflict') await this.syncLatest();
        break;
      }
    }
    return this.savedAt;
  }

  async flush(): Promise<{updatedAt?: string; reason?: DraftFailureReason}> {
    await this.save();
    if (!this.current) return {reason: 'transient'};
    if (this.dirty || this.request || this.failure) return {reason: this.failure ?? 'transient'};
    return this.savedAt ? {updatedAt: this.savedAt} : {};
  }

  async syncSubmitted(): Promise<void> {
    const draft = await readInteractionDraft(this.conversationId, this.messageId);
    if (!this.current) return;
    this.revision = Math.max(this.revision, draft.draft_revision);
    this.done = JSON.stringify(this.state) === JSON.stringify(draft.state);
    this.notify();
  }

  /** Share the frozen request and its save lock with any replacement renderer. */
  beginSubmission(input: () => InteractionReplyInput): {input: InteractionReplyInput; key: string} {
    if (this.sending) throw new Error('A request is already pending');
    const pending = this.pending ??= {input: input(), key: crypto.randomUUID()};
    this.sending = true;
    this.readVersion += 1;
    this.notify();
    return pending;
  }

  /** Settle an admitted request even when the original renderer has detached. */
  finishSubmission(outcome: 'accepted' | 'rejected' | 'unknown'): void {
    this.sending = false;
    if (outcome !== 'unknown') {
      this.pending = null;
      this.dirty = false;
    }
    if (outcome === 'accepted' && this.current) {
      this.done = true;
      this.failure = null;
      this.owner.failed(null);
    }
    this.notify();
  }

  /** Forget ownership on an explicit leave/revocation, never on a temporary view detach. */
  forget(left = false): void {
    this.left ||= left;
    this.live = false;
    this.pending = null;
    this.readVersion += 1;
    this.state = {};
    this.dirty = false;
    this.failure = null;
    this.notify();
  }
}
