import {afterEach, expect, it, vi} from 'vitest';
import {decodeChatStream, type AgentConfiguration, type RuntimePort} from '@nano/product-contracts';
import {NodeStore} from '../src/store.js';
import {WorkerApprovals} from '../src/worker-approvals.js';
import {ExternalChannels} from '../src/external.js';

const cleanup: (() => Promise<void>)[] = [];
afterEach(async () => { for (const close of cleanup.splice(0)) await close(); });

function fixture(personal = false) {
  const store = new NodeStore(':memory:', 'owner');
  const agent: AgentConfiguration = {agentId: 'agent', mode: 'global', revision: '1', workspace: '/tmp', provider: 'p', model: 'm',
    ...(personal ? {personal: {bindingId: 'binding', ownerId: 'owner', conversationId: 'private', epoch: 1}} : {})};
  store.bind({agentId: agent.agentId, sessionId: 'root', ownerId: 'owner', conversationId: 'global:agent', cwd: '/tmp', revision: '1'});
  let notify!: (method: string, params: unknown) => void;
  const rpc = vi.fn(async () => ({answered: true as const}));
  const runtime = {onNotification(listener) {notify = listener; return () => {};}, request: rpc} as RuntimePort;
  const ack = Promise.withResolvers<string>();
  const relay = vi.fn(async (_type: string, payload: Record<string, unknown>) => {
    const fact = decodeChatStream(payload);
    return {type: 'ack', payload: fact.kind === 'worker_permission_request' ? {message_id: await ack.promise} : {}};
  });
  const onError = vi.fn();
  const product = new WorkerApprovals({nodeId: 'node', agents: [agent], store, runtime, relay: {request: relay}, onError});
  cleanup.push(async () => {ack.resolve('card'); await product.stop(); store.close();});
  const request = {
    sessionId: 'root', requestId: 'request', callId: 'call', toolName: 'command',
    worker: {workerId: 'w12', label: 'Reviewer', runtime: 'codex'}, expiresAt: Date.now() + 30_000,
    reason: 'Reviewer (codex, w12) requests chmod +x /tmp/check', toolInput: {arguments: {command: 'chmod +x /tmp/check'}},
  };
  const click = {request_id: 'request', message_id: 'card', lifecycle_revision: 1, decision: 'allow_once'};
  return {product, request, click, ack, relay, onError, rpc, notify, store};
}

it.each([false, true])('delivers an idle Global root Worker request to IM and binds the click to the confirmed message (personal=%s)', async personal => {
  const {product, request, click, ack, relay, rpc, notify, onError} = fixture(personal);
  // Routing data from the originating Feishu conversation is never forwarded.
  notify('approval.request', {...request, conversation_id: 'external:group', to_user_id: 'peer', message_id: 'shadow-output'});
  const create = relay.mock.calls[0]![1];
  expect(create).toMatchObject({kind: 'worker_permission_request', worker: request.worker, agent_id: 'agent',
    run_id: 'root', session_id: 'root', expires_at: request.expiresAt,
    permission_request: {request_id: 'request', call_id: 'call', question: request.reason, tool_input: request.toolInput.arguments}});
  for (const field of ['conversation_id', 'to_user_id', 'message_id']) expect(create).not.toHaveProperty(field);
  const wrongClick = product.answer({...click, message_id: 'shadow-output'});
  const answer = product.answer(click);
  expect(rpc).not.toHaveBeenCalled();
  ack.resolve('card');
  await expect(wrongClick).rejects.toThrow('this card');
  await expect(answer).resolves.toBe(true);
  expect(rpc.mock.calls).toEqual([['approval.answer', {requestId: 'request', decision: 'allowed-once'}]]);
  notify('approval.resolved', {sessionId: 'root', requestId: 'request', outcome: 'allowed-once'});
  await expect.poll(() => relay.mock.calls.at(-1)?.[1]).toMatchObject({
    kind: 'permission_resolved', message_id: 'card', decision: 'allow_once', permission_request: {request_id: 'request'},
  });
  expect(onError).not.toHaveBeenCalled();
});

it.each(['cancel', 'crash'])('closes the private card when %s races its ACK and a waiting click', async cause => {
  const {product, request, click, ack, relay, rpc, notify} = fixture();
  notify('approval.request', request);
  const answer = product.answer(click);
  if (cause === 'crash') product.cancelAgent('agent', 'unavailable');
  else notify('approval.resolved', {sessionId: 'root', requestId: 'request', outcome: 'cancelled'});
  expect(relay).toHaveBeenCalledTimes(1);
  ack.resolve('card');
  await expect(answer).rejects.toThrow('no longer pending');
  await expect.poll(() => relay.mock.calls.at(-1)?.[1]).toMatchObject({kind: 'permission_resolved', message_id: 'card', decision: cause === 'crash' ? 'unavailable' : 'cancelled'});
  expect(rpc).not.toHaveBeenCalled();
  await expect(product.answer(click)).resolves.toBe(false);
});

it('reflects the runtime timeout even if an allow click reached the host', async () => {
  const {product, request, click, ack, relay, rpc, notify} = fixture();
  notify('approval.request', request);
  ack.resolve('card');
  await expect(product.answer({...click, decision: 'allow_always'})).rejects.toThrow('Invalid');
  await expect(product.answer({...click, lifecycle_revision: 2})).rejects.toThrow('this card');
  await product.answer(click);
  expect(rpc).toHaveBeenCalledOnce();
  notify('approval.resolved', {sessionId: 'root', requestId: 'request', outcome: 'timed_out'});
  await expect.poll(() => relay.mock.calls.at(-1)?.[1]).toMatchObject({kind: 'permission_resolved', decision: 'timed_out'});
});

it('rejects a failed private publication through the live independent approval RPC', async () => {
  const {product, request, click, ack, relay, rpc, notify, onError} = fixture();
  notify('approval.request', request);
  ack.reject(new Error('disconnected'));
  await expect.poll(() => rpc.mock.calls).toEqual([['approval.answer', {requestId: 'request', decision: 'rejected', reason: expect.stringContaining('Nano IM')}]]);
  await expect(product.answer(click)).resolves.toBe(false);
  expect(onError).toHaveBeenCalledWith(expect.objectContaining({message: 'disconnected'}));
  expect(relay).toHaveBeenCalledTimes(1);
});

it('keeps a Feishu group trigger and its IM shadow separate from both Worker card frames', async () => {
  const {request, ack, relay, notify, store, rpc} = fixture();
  const send = vi.fn(async () => 'platform');
  const updateCard = vi.fn(async () => {});
  const im = vi.fn(async (path: string, _options?: RequestInit) => ({id: path.includes('find-or-create') ? 'shadow' : 'mirror'}));
  const externalAnswer = vi.fn(async () => {});
  const external = new ExternalChannels(':memory:', {
    nodeId: 'node', ownerId: 'owner', store, relay: {ready: true, request: relay}, im, onError: error => {throw error;},
    receive: async input => {
      expect(input.metadata.channel).toBe('feishu');
      notify('approval.request', request);
    },
    permission: externalAnswer,
  });
  external.add('agent', {config: {appId: 'app', ownerOpenId: 'feishu-owner'}, send, updateCard,
    reaction: async () => undefined, image: async () => ({data: Buffer.alloc(0), mediaType: 'image/png'})});
  try {
    await external.receive('agent', {messageId: 'trigger', chatId: 'group', senderId: 'member', isGroup: true, mentioned: true,
      time: '1000', parts: [{type: 'text', text: 'Please check'}]});
    ack.resolve('card');
    await external.card('agent', {operator: {open_id: 'feishu-owner'}, context: {open_message_id: 'card'},
      action: {value: {request_id: 'request', decision: 'allow_once'}}});
    expect(externalAnswer).not.toHaveBeenCalled();
    expect(rpc).not.toHaveBeenCalled();
    notify('approval.resolved', {sessionId: 'root', requestId: 'request', outcome: 'rejected'});
    await external.recover();
    expect(relay.mock.calls.map(([, frame]) => frame.kind)).toEqual(['worker_permission_request', 'permission_resolved']);
    expect(relay.mock.calls[1]?.[1]).toMatchObject({message_id: 'card', decision: 'deny'});
    expect(send).not.toHaveBeenCalled();
    expect(updateCard).not.toHaveBeenCalled();
    const shadowBodies = im.mock.calls.map(([, init]) => String(init?.body));
    expect(shadowBodies.join(' ')).toContain('Please check');
    expect(shadowBodies.join(' ')).not.toContain('chmod');
  } finally { await external.stop(); }
});
