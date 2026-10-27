import type { FastifyInstance } from 'fastify';
import { canonicalJson } from '@nano/product-contracts';
import { fail, one, params, type ImContext, type Row } from './context.js';

/** Freeze the normalized ordinary-send payload independently of transient delivery state.
 *
 * Args:
 *   input: Request after content and attachment references have been normalized.
 * Returns:
 *   Canonical JSON used by the message creation transaction and retry comparison.
 */
export function messageAttemptPayload(input: Row): string {
  return canonicalJson({content:input.content ?? '', attachments:input.attachments ?? [], interaction_contexts:input.interaction_contexts ?? []});
}

/** Reject key reuse by another sender or with different immutable message data.
 *
 * Args:
 *   existing: Full persisted message row, including caller_payload_json.
 *   senderId: Authenticated sender resolved by the ordinary create path.
 *   senderType: Resolved sender kind.
 *   payload: Canonical request returned by messageAttemptPayload.
 * Raises:
 *   Error: HTTP 409 when the key identifies a different sender or payload.
 */
export function assertMessageAttempt(existing: Row, senderId: string, senderType: string, payload: string): void {
  const saved = existing.caller_payload_json ?? messageAttemptPayload({content:existing.content,attachments:JSON.parse(existing.attachments_json ?? '[]')});
  if (existing.sender_user_id !== senderId || existing.sender_type !== senderType || saved !== payload) {
    fail(409, {code:'message_attempt_conflict', message:'This request key was already used with different message data'});
  }
}

/** Register the sender-only status lookup.
 *
 * Args:
 *   app: IM server receiving ordinary authenticated browser requests.
 *   ctx: Existing identity, membership and message projection owners.
 */
export function registerMessageAttemptRoutes(app: FastifyInstance, ctx: ImContext): void {
  app.get('/im/v1/conversations/:conversation_id/message-attempts/:key', async request => {
    const principal = ctx.messaging.principal(request);
    if (principal.kind === 'gateway' || principal.username?.startsWith('agent:')) fail(403, 'Human sender required');
    const {conversation_id:cid, key} = params(request);
    const access = ctx.messaging.access(principal, cid);
    if (!access.is_member) fail(404, 'message attempt not found');
    const message = one(ctx.db, 'SELECT id FROM messages WHERE conversation_id=? AND caller_idempotency_key=? AND sender_user_id=? AND sender_type=\'user\'', cid, key, principal.id);
    if (!message) fail(404, 'message attempt not found');
    return ctx.messaging.message(message.id);
  });
}
