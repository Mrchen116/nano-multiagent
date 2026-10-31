import { appendFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { join } from 'node:path';
import { GlobalAgent, InboxStore, NodeStore, TaskContext, type ProductCall } from '@nano/personal-assistant';
import { EvaluationChat } from '@nano/im-server/evaluation';
import type { NanoEvaluationOptions } from '@nano/dsh-integration/evaluation';
import type { RelayInput } from '@nano/product-contracts';
import { parseHistoryDate } from './dataset.js';

/** Compose the ordinary PA with one isolated, durable IM owner chat.
 *
 * Args:
 *   options: Phase runtime, preserved PA relationship, and local delivery sink.
 * Returns:
 *   Product admission, history import/query, snapshot and cleanup ports.
 */
export const createNanoProduct: NanoEvaluationOptions['createProduct'] = options => {
  const { configuration: config, binding, runtime, directory, deliver, nodeId } = options;
  const identity = config.personal!;
  const chat = new EvaluationChat({ path: join(directory, 'chat.sqlite'), snapshot: options.chatSnapshot,
    nodeId, agentId: config.agentId, ownerId: identity.ownerId, bindingId: identity.bindingId,
    conversationId: identity.conversationId, rootSessionId: binding.sessionId, startTime: options.startTime });
  const store = new NodeStore(join(directory, 'node.sqlite'), identity.ownerId);
  const inbox = new InboxStore(join(directory, 'inbox.sqlite'));
  store.bind({ ...binding, conversationId: `global:${config.agentId}` });
  const target = identity.conversationId;
  let questionTime = options.startTime;
  const relay: ConstructorParameters<typeof GlobalAgent>[0]['relay'] = { ready: true, async request(type, args) {
      const ok = (result: unknown = {}) => ({ type: `${type}.result`, payload: { ok: true, result } });
      if (type === 'agent.session.ensure' || type === 'node.delivery_receipt') return ok();
      if (type === 'pa.observations.read') return ok({ items: [], has_more: false });
      if (type === 'pa.sources' && args.action === 'list') return ok(chat.sources());
      if (type === 'pa.source.admit') return ok({ allowed: args.conversation_id === target, is_owner: true,
        delivery: 'participant', conversation_type: 'direct', channel: 'web' });
      if (type === 'agent.message') {
        if (args.to !== `conversation:${target}` || typeof args.text !== 'string') throw new Error('Target is outside the connected owner chat');
        const message = chat.append('assistant', args.text, questionTime);
        await deliver(args.text);
        return { type: 'ack', payload: { message_id: message.id, conversation_id: target } };
      }
      if (type === 'conversation.query') return ok(chat.query(args));
      if (type === 'task.context.sync') return ok(chat.taskContext(args));
      throw new Error(`Operation is unavailable in the isolated owner chat: ${type}`);
    } };
  const product = new GlobalAgent({ nodeId, ownerId: identity.ownerId, agents: [config], store, inbox, runtime, relay,
    image: async () => { throw new Error('This chat has no image attachments'); },
    onError: error => appendFileSync(join(directory, 'product-errors.log'), String(error) + '\n'),
  });
  const taskContext = new TaskContext({ nodeId, ownerId: identity.ownerId, agents: [config], store, inbox, runtime, relay,
    refreshSources: agentId => product.prepareSystemContext(agentId) });
  return {
    importSession: session => chat.importSession(session),
    snapshot: path => chat.snapshot(path),
    async submit(question) {
      questionTime = parseHistoryDate(question.date);
      const saved = chat.append('user', question.text, questionTime);
      const message: RelayInput['message'] = { id: saved.id, content: question.text, sender_type: 'user', sender_user_id: identity.ownerId,
        sender: { display_name: 'Owner' }, attachments: [], created_at: question.date };
      const relayId = randomUUID();
      await product.receive({ agent_id: config.agentId, conversation_id: target, relay_task_id: relayId, idempotency_key: relayId,
        metadata: { conversation_type: 'direct', conversation_title: 'Personal Assistant', channel: 'web' }, message });
      return `inbox-wake:${config.agentId}:${inbox.admittedWake(config.agentId)}`;
    },
    call: value => product.call(value as ProductCall),
    taskContext: {
      prepare: value => taskContext.prepare(value as Parameters<TaskContext['prepare']>[0]),
      commit: value => taskContext.commit(value as Parameters<TaskContext['commit']>[0]),
    },
    async close() { try { await product.stop(); } finally { inbox.close(); store.close(); chat.close(); } },
  };
};
