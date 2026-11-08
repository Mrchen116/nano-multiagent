import type { DatabaseSync } from 'node:sqlite';
import type { InteractionContext } from '@nano/product-contracts';

import { fail, now, one, type Row } from './context.js';
import type { Interactions } from './interactions.js';

/** Maximum UTF-8 size of the complete JSON background array, not just draft state. */
export const MAX_INTERACTION_BACKGROUND_BYTES = 64 * 1024;

/** Derive the pending private backgrounds for one human in one conversation.
 *
 * Ownership: the centre is the only place that can see private drafts, the user's own
 * sent messages and the leave watermark at once, so "carry this card once" is decided
 * here instead of by each client's in-memory cache. Clients keep only the ability to save
 * a draft after real input.
 */
export class InteractionBackground {
  constructor(private readonly db: DatabaseSync, private readonly interactions: Interactions) {}

  /** Collect every valid card edited since this user's common consumption boundary.
   *
   * Args:
   *   user: Authenticated human principal (`{id, username}`, no `kind` — do not test for one).
   *   cid: Conversation being written to; already access-checked by the sender.
   * Returns:
   *   One latest state per pending card, in stable server save order.
   * Throws:
   *   Error: A recoverable 422 when the complete serialized group exceeds its budget.
   */
  pending(user: Row, cid: string): InteractionContext[] {
    if (user.kind === 'gateway' || user.username?.startsWith('agent:')) return [];
    const conversation = one(this.db, 'SELECT type,external_source,dissolved_at FROM conversations WHERE id=?', cid);
    // A shadow conversation has no client, so nobody sent anything by hand there.
    if (!conversation || conversation.type !== 'direct' || conversation.external_source || conversation.dissolved_at) return [];
    const floor = [this.localHumanAt(user.id, cid), this.discardedThrough(user.id, cid)].filter(value => typeof value === 'string' && value).sort().at(-1) ?? '';
    const candidates = this.db.prepare(`SELECT d.source_message_id,d.updated_at,d.state_json FROM interaction_drafts d
      JOIN messages m ON m.id=d.source_message_id
      JOIN message_interactive i ON i.message_id=d.source_message_id
      WHERE d.user_id=? AND m.conversation_id=?
        AND d.updated_at IS NOT NULL AND d.submission_message_id IS NULL
        AND d.updated_at>?
      ORDER BY d.updated_at ASC, m.rowid ASC`).iterate(user.id, cid, floor);
    const contexts: InteractionContext[] = [];
    let bytes = 2; // The surrounding JSON array is part of the model-visible budget.
    for (const candidate of candidates) {
      const background = this.interactions.background(user, cid, String(candidate.source_message_id), String(candidate.state_json));
      if (!background) continue; // One invalid card must not suppress other pending edits.
      const context = {...background, interacted_at: Date.parse(String(candidate.updated_at))};
      bytes += Buffer.byteLength(JSON.stringify(context), 'utf8') + (contexts.length ? 1 : 0);
      // Fail before any message is created: silently returning a prefix would consume the
      // omitted cards as well. Iterate instead of loading an unbounded group into memory.
      if (bytes > MAX_INTERACTION_BACKGROUND_BYTES) fail(422, {
        code: 'interaction_background_too_large',
        message: 'Card background is too large; the message was not sent. Reduce card content and retry, or leave this chat on the devices where you edited cards to clear their pending backgrounds. Your message and card edits are kept.',
      });
      contexts.push(context);
    }
    return contexts;
  }

  /** Advance the "left this conversation" watermark; monotonic and never retroactive.
   *
   * Args:
   *   user: Authenticated human who passed write access.
   *   cid: Conversation being left.
   *   through: Highest draft `updated_at` this client confirmed saving, or anything else.
   * Returns:
   *   `{applied:false}` when the request could not name what it clears, otherwise the
   *   effective watermark after the write.
   */
  discard(user: Row, cid: string, through: unknown): {applied: false} | {applied: true; discarded_through: string} {
    if (user.kind === 'gateway' || user.username?.startsWith('agent:')) fail(403, 'Human viewer required');
    // A device with no watermark cannot know what it would erase; pushing `now()` there
    // would wipe another device's unsent edit.
    if (typeof through !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(through)
      || Number.isNaN(Date.parse(through))) return {applied: false};
    // Only canonical UTC strings share the draft/message ordering. Comparing an accepted
    // ISO offset verbatim would clear edits that happened after the named instant.
    const canonical = new Date(through).toISOString(), currentTime = now();
    const value = canonical < currentTime ? canonical : currentTime;
    const previous = this.discardedThrough(user.id, cid);
    const effective = previous && previous > value ? previous : value;
    this.db.prepare(`INSERT INTO interaction_background_discards(conversation_id,user_id,discarded_through) VALUES(?,?,?)
      ON CONFLICT(conversation_id,user_id) DO UPDATE SET discarded_through=excluded.discarded_through`).run(cid, user.id, effective);
    return {applied: true, discarded_through: effective};
  }

  /** Current watermark for one viewer, or null when they never left this conversation. */
  discardedThrough(userId: string, cid: string): string | null {
    return one(this.db, 'SELECT discarded_through FROM interaction_background_discards WHERE conversation_id=? AND user_id=?', cid, userId)?.discarded_through ?? null;
  }

  /** Time of the last message this user sent by hand in this conversation.
   *
   * Every excluded write also stores `sender_user_id = owner` with `sender_type='user'`,
   * so each exclusion below removes a real way the background would be silently eaten:
   * PA representation, external channel mirrors, shadow-conversation sends and notices.
   */
  private localHumanAt(userId: string, cid: string): string | null {
    return one(this.db, `SELECT MAX(m.created_at) AS at FROM messages m
      WHERE m.conversation_id=? AND m.sender_user_id=? AND m.sender_type='user' AND m.sender_source_id IS NULL
        AND NOT EXISTS (SELECT 1 FROM pa_delegated_messages d WHERE d.message_id=m.id AND d.representation_operation_id IS NOT NULL)`,
      cid, userId)?.at ?? null;
  }
}
