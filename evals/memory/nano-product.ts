import { appendFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { join } from 'node:path';
import { GlobalAgent, InboxStore, NodeStore, type ProductCall } from '@nano/personal-assistant';
import type { NanoEvaluationOptions } from '@nano/dsh-integration/evaluation';
import type { RelayInput } from '@nano/product-contracts';
import { parseHistoryDate } from './dataset.js';

/** Run the ordinary PA against one isolated owner chat; no old IM history is connected.
 *
 * Args:
 *   options: Cold runtime, preserved PA relationship, and local delivery sink.
 * Returns:
 *   Product admission, tool dispatch, and cleanup backed by the existing PA implementation.
 */
export const createNanoProduct: NanoEvaluationOptions['createProduct'] = options => {
  const { configuration: config, binding, runtime, directory, deliver } = options;
  const identity = config.personal!;
  const store = new NodeStore(join(directory, 'node.sqlite'), identity.ownerId);
  const inbox = new InboxStore(join(directory, 'inbox.sqlite'));
  store.bind({ ...binding, conversationId: `global:${config.agentId}` });
  const target = identity.conversationId;
  const participants = [{ id: identity.ownerId, name: 'Owner', kind: 'user' }, { id: config.agentId, name: 'Personal Assistant', kind: 'agent', agent_id: config.agentId }];
  const description = { target, name: 'Personal Assistant', kind: 'direct', channel: 'web', participants };
  const messages: RelayInput['message'][] = [];
  const messagePage = (args: Record<string, unknown>) => {
    const query = args.keyword ?? args.query;
    const selected = messages.filter(message => (!query || message.content.toLowerCase().includes(String(query).toLowerCase()))
      && (!args.message_id || message.id === args.message_id)
      && (!args.participant_id || message.sender_user_id === args.participant_id)
      && (!args.before || parseHistoryDate(message.created_at!) < parseHistoryDate(String(args.before)))
      && (!args.after || parseHistoryDate(message.created_at!) >= parseHistoryDate(String(args.after)))).reverse();
    const offset = args.cursor ? Number(args.cursor) : 0;
    if (!Number.isSafeInteger(offset) || offset < 0) throw new Error('invalid_cursor');
    const page = selected.slice(offset, offset + Number(args.limit ?? 20));
    const next = offset + page.length;
    return { target, name: description.name, kind: 'direct', channel: 'web', history_scope: 'im_history',
      messages: page.map(message => ({ message_id: message.id, sender: { id: message.sender_user_id, kind: message.sender_type,
        name: message.sender_type === 'user' ? 'Owner' : 'Personal Assistant', is_owner: message.sender_user_id === identity.ownerId },
        source_time: message.created_at, source: { channel: 'web', conversation_id: target, reply_target: target,
          conversation_type: 'direct', delivery: 'participant', owner_can_read: true },
        part_key: '0', complete_message: true, content: [{ type: 'text', text: message.content }] })),
      has_more: next < selected.length, next_cursor: next < selected.length ? String(next) : null };
  };
  const product = new GlobalAgent({ nodeId: randomUUID(), ownerId: identity.ownerId, agents: [config], store, inbox, runtime,
    image: async () => { throw new Error('This chat has no image attachments'); },
    onError: error => appendFileSync(join(directory, 'product-errors.log'), String(error) + '\n'),
    relay: { ready: true, async request(type, args) {
      const ok = (result: unknown = {}) => ({ type: `${type}.result`, payload: { ok: true, result } });
      if (type === 'agent.session.ensure' || type === 'node.delivery_receipt') return ok();
      if (type === 'pa.observations.read') return ok({ items: [], has_more: false });
      if (type === 'pa.sources' && args.action === 'list') return ok({ policy: { revision: 1 }, items: [{ id: target, excluded: false }] });
      if (type === 'pa.source.admit') return ok({ allowed: args.conversation_id === target, is_owner: true,
        delivery: 'participant', conversation_type: 'direct', channel: 'web' });
      if (type === 'agent.message') {
        if (args.to !== `conversation:${target}` || typeof args.text !== 'string') throw new Error('Target is outside the connected owner chat');
        await deliver(args.text);
        const id = randomUUID();
        messages.push({ id, content: args.text, sender_type: 'agent', sender_user_id: config.agentId, attachments: [], created_at: messages[0]?.created_at });
        return { type: 'ack', payload: { message_id: id, conversation_id: target } };
      }
      if (type === 'conversation.query') {
        if (args.target !== undefined && args.target !== target && args.target !== identity.ownerId
          && args.target !== `conversation:${target}` && args.target !== `user:${identity.ownerId}`) throw new Error('target_not_accessible');
        if (args.action === 'resolve_target') return ok({ target });
        if (args.action === 'describe') return ok({ conversations: (args.targets as string[]).includes(target) ? [description] : [] });
        if (args.action === 'list') return ok({ conversations: args.scope === 'public' ? [] : [{ ...description, visibility: 'private', is_member: true, can_write: true,
          latest_message_at: messages.at(-1)?.created_at ?? null, history_availability: 'im_history' }], has_more: false, next_cursor: null });
        if (args.action === 'info') return ok({ target, name: description.name, type: 'direct', channel: 'web', visibility: 'private',
          is_member: true, can_write: true, dissolved_at: null, members: participants.map(person => ({ user_id: person.id, name: person.name,
            type: person.kind, mention: `<mention type="user" target_id="${person.id}"/>` })) });
        if (args.action === 'read' || args.action === 'search') return ok(messagePage(args));
      }
      throw new Error(`Operation is unavailable in the isolated owner chat: ${type}`);
    } },
  });
  return {
    async submit(question) {
      const message: RelayInput['message'] = { id: randomUUID(), content: question.text, sender_type: 'user', sender_user_id: identity.ownerId,
        sender: { display_name: 'Owner' }, attachments: [], created_at: question.date };
      messages.push(message);
      const relayId = randomUUID();
      await product.receive({ agent_id: config.agentId, conversation_id: target, relay_task_id: relayId, idempotency_key: relayId,
        metadata: { conversation_type: 'direct', conversation_title: description.name, channel: 'web' }, message });
      return `inbox-wake:${config.agentId}:${inbox.admittedWake(config.agentId)}`;
    },
    call: value => product.call(value as ProductCall),
    async close() { await product.stop(); inbox.close(); store.close(); },
  };
};
