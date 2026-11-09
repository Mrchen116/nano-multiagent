import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { RelayInput } from '@nano/product-contracts';
import { GlobalAgent, type ProductCall } from '../../personal-assistant/src/global-agent.js';
import { Heartbeat } from '../../personal-assistant/src/heartbeat.js';
import { InboxStore } from '../../personal-assistant/src/inbox.js';
import { NodeStore } from '../../personal-assistant/src/store.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

function writeFault(directory: string, marker: string): string {
  return `
import { existsSync, writeFileSync } from 'node:fs';
import fs from 'node:fs/promises';
import { syncBuiltinESMExports } from 'node:module';
const fault = ${JSON.stringify(marker)};
const open = fs.open;
fs.open = async (path, ...args) => {
  if (String(path).includes(${JSON.stringify('/' + directory + '/.')}) && existsSync(fault)) {
    throw Object.assign(new Error('ENOSPC: no space left on device, open ' + path), {code: 'ENOSPC'});
  }
  return open(path, ...args);
};
syncBuiltinESMExports();
`;
}

it.each(['user message', 'heartbeat'])('resumes model writes on the next %s', async activation => {
  const home = await mkdtemp(join(tmpdir(), 'nano-storage-recovery-'));
  const store = new NodeStore(':memory:', 'owner');
  const inbox = new InboxStore(':memory:');
  const fault = join(home, 'fail-writes');
  let client: RuntimeClient | undefined;
  let product: GlobalAgent | undefined;
  let heartbeat: Heartbeat | undefined;
  const errors: string[] = [];
  const submissions: string[] = [];
  try {
    await writeFile(join(home, 'fixture.mjs'), `${writeFault('nano_model_runs/runs', fault)}
export const inject = ['llm'];
export function apply(ctx) {
  ctx.on('llm/stream', async function* (request) {
    await fs.appendFile(${JSON.stringify(join(home, 'model-requests'))}, 'model called\\n');
    if (request.messages.some(message => message.source?.channel === 'heartbeat')) {
      yield {type: 'block-end', index: 0, block: {type: 'text', text: 'HEARTBEAT_OK'}};
      yield {type: 'finish', reason: {kind: 'stop'}};
      return;
    }
    const read = request.messages.find(message => message.role === 'tool');
    if (read && !JSON.stringify(read).includes('New work')) {
      throw new Error('New Inbox content missing from model context');
    }
    const block = read
      ? {type: 'text', text: 'Handled the new Inbox message'}
      : {type: 'tool-call', id: 'read-inbox', name: 'inbox', arguments: JSON.stringify({action: 'read', target: 'c_test'})};
    yield {type: 'block-end', index: 0, block};
    yield {type: 'finish', reason: {kind: read ? 'stop' : 'tool-calls'}};
  });
}`);
    await prepareProfile(home, [{insert: [{id: 'fixture', name: join(home, 'fixture.mjs')}]}]);
    const runtime = client = new RuntimeClient({home, cwd: home, onLog: value => errors.push(value)});
    registerNoopTaskHosts(runtime);
    const config = {
      agentId: 'a', workspace: home, revision: '1', mode: 'global' as const,
      provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['inbox', 'read'],
      features: {heartbeat: true},
      approval: {dangerouslySkipPermissions: true},
    };
    const binding = {
      agentId: 'a', sessionId: 'main', conversationId: 'global:a', ownerId: 'owner', cwd: home, revision: '1',
    };
    store.bind(binding);
    const port = {
      onNotification: runtime.rpc.onNotification.bind(runtime.rpc),
      request: async (method: string, params: unknown) => {
        const result = await runtime.rpc.request(method, params);
        if (method === 'session.submit') submissions.push((params as {inputId: string}).inputId);
        return result;
      },
    };
    const global = product = new GlobalAgent({
      nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox, image: async () => '',
      onError: error => errors.push(String(error)),
      runtime: port,
      relay: { request: async (type, payload) => ({
        type: 'ack', payload: type === 'conversation.query'
          ? {ok: true, result: payload.action === 'describe'
            ? {conversations: [{target: 'c_test', name: 'Fixture chat'}]}
            : {name: 'Fixture chat'}}
          : {},
      }) },
    });
    runtime.rpc.handle('product.call', value => global.call(value as ProductCall));
    await runtime.rpc.request('initialize', {protocol: 1, agents: [config], bindings: []});
    await runtime.rpc.request('session.ensure', binding);
    await writeFile(fault, '');
    const input: RelayInput = {
      agent_id: 'a', conversation_id: 'c_test', relay_task_id: 'relay', idempotency_key: 'once',
      metadata: {conversation_type: 'direct', channel: 'web'},
      message: {id: 'original', content: 'Please handle this', sender_type: 'user', sender_user_id: 'owner', attachments: []},
    };
    await global.receive(input);
    await expect.poll(async () => {
      const result = await runtime.rpc.request('session.observe', {sessionId: 'main'}) as {modelRuns: unknown[]};
      return result.modelRuns;
    }).toEqual(expect.arrayContaining([expect.objectContaining({
      terminal: {kind: 'error', error: expect.objectContaining({message: expect.stringContaining('ENOSPC')})},
    })]));
    expect(inbox.unreadAttention('a')).toBe(1);
    await expect(readFile(join(home, 'model-requests'), 'utf8')).rejects.toMatchObject({code: 'ENOENT'});
    expect(submissions).toEqual(['inbox-wake:a:1']);

    await rm(fault);
    await global.recover();
    expect(submissions).toEqual(['inbox-wake:a:1']);
    await expect(readFile(join(home, 'model-requests'), 'utf8')).rejects.toMatchObject({code: 'ENOENT'});

    if (activation === 'user message') {
      await global.receive({...input, relay_task_id: 'relay-2', idempotency_key: 'new',
        message: {...input.message, id: 'new', content: 'New work'}});
      await expect.poll(() => inbox.unreadAttention('a')).toBeUndefined();
    } else {
      await mkdir(join(home, '.nanoassistant'), {recursive: true});
      await writeFile(join(home, '.nanoassistant/HEARTBEAT.md'), 'Check the heartbeat fixture');
      heartbeat = new Heartbeat(':memory:', {
        agents: [config], runtime: port, settings: () => ({every: '10m'}),
        available: () => true, binding: agent => global.heartbeatBinding(agent),
        onError: error => errors.push(String(error)),
      });
      heartbeat.subscription('a', true);
      await heartbeat.tick(undefined, false, 1_200_000);
    }
    expect(submissions).toEqual(['inbox-wake:a:1', activation === 'user message'
      ? 'inbox-wake:a:2' : expect.stringMatching(/^heartbeat:a:1200000:/)]);
    await expect.poll(async () => {
      const result = await runtime.rpc.request('session.observe', {sessionId: 'main'}) as {modelRuns: {terminal?: unknown}[]};
      return result.modelRuns.at(-1)?.terminal;
    }).toEqual({kind: 'completed'});
    expect(await readFile(join(home, 'model-requests'), 'utf8'))
      .toBe('model called\n'.repeat(activation === 'user message' ? 2 : 1));
  } catch (error) {
    throw new Error(`${error}\n${errors.slice(-8).join('\n')}`, {cause: error});
  } finally {
    await rm(fault, {force: true});
    await heartbeat?.stop();
    await product?.stop();
    if (client) {
      client.process.kill('SIGKILL');
      await client.exited;
    }
    inbox.close();
    store.close();
    await rm(home, {recursive: true, force: true});
  }
}, 20_000);

it('restores the durable tool view after a result write fails without rerunning the tool', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-tool-storage-recovery-'));
  const fault = join(home, 'fail-writes');
  const executions = join(home, 'tool-executions');
  let client: RuntimeClient | undefined;
  try {
    await writeFile(join(home, 'fixture.mjs'), `${writeFault('nano_tool_views/calls', fault)}
export const inject = ['llm', 'tools'];
export function apply(ctx) {
  ctx.tools.register({
    name: 'view_probe', description: 'Probe tool view recovery',
    parameters: {type: 'object', properties: {}},
    output: {schema: {type: 'object'}, render: () => [{type: 'text', text: 'tool result'}]},
    execute: async () => {
      await fs.appendFile(${JSON.stringify(executions)}, 'executed\\n');
      writeFileSync(fault, '');
      return {};
    },
    presentCall: () => ({card: 'generic', title: 'Tool started'}),
    presentResult: () => ({card: 'generic', title: 'Tool finished'}),
  });
  ctx.on('llm/stream', async function* (request) {
    const finished = request.messages.some(message => message.role === 'tool');
    const block = finished
      ? {type: 'text', text: 'Done'}
      : {type: 'tool-call', id: 'probe-call', name: 'view_probe', arguments: '{}'};
    yield {type: 'block-end', index: 0, block};
    yield {type: 'finish', reason: {kind: finished ? 'stop' : 'tool-calls'}};
  });
}`);
    await prepareProfile(home, [{insert: [{id: 'fixture', name: join(home, 'fixture.mjs')}]}]);
    const runtime = client = new RuntimeClient({home, cwd: home});
    registerNoopTaskHosts(runtime);
    await runtime.rpc.request('initialize', {protocol: 1, agents: [{
      agentId: 'a', workspace: home, revision: '1', provider: 'deepseek-official',
      model: 'deepseek-flash', toolAllowlist: ['view_probe'], approval: {dangerouslySkipPermissions: true},
    }], bindings: []});
    await runtime.rpc.request('session.ensure', {sessionId: 's', agentId: 'a', ownerId: 'owner', cwd: home, revision: '1'});
    await runtime.rpc.request('session.submit', {
      sessionId: 's', inputId: 'input', mode: 'followup', content: [{type: 'text', text: 'Run the tool'}],
      source: {kind: 'human', actorId: 'owner', channel: 'test', messageId: 'input'},
    });
    await expect.poll(async () => {
      const evidence = await runtime.rpc.request('session.lookup', {sessionId: 's', inputId: 'input'}) as {terminal?: unknown};
      return evidence.terminal;
    }).toEqual({kind: 'completed'});
    const observe = () => runtime.rpc.request('session.observe', {sessionId: 's'});
    await expect(observe()).rejects.toThrow('ENOSPC');

    await rm(fault);
    await expect(observe()).rejects.toThrow('ENOSPC');
    await runtime.rpc.request('session.submit', {
      sessionId: 's', inputId: 'next', mode: 'followup', content: [{type: 'text', text: 'New request'}],
      source: {kind: 'human', actorId: 'owner', channel: 'test', messageId: 'next'},
    });
    await expect.poll(async () => {
      const evidence = await runtime.rpc.request('session.lookup', {sessionId: 's', inputId: 'next'}) as {terminal?: unknown};
      return evidence.terminal;
    }).toEqual({kind: 'completed'});
    await expect(observe()).resolves.toMatchObject({events: expect.arrayContaining([
      expect.objectContaining({type: 'tool/result', data: expect.objectContaining({
        nanoToolView: {callId: 'probe-call', call: {card: 'generic', title: 'Tool started'}, result: {card: 'generic', title: 'Tool finished'}},
      })}),
    ])});
    expect(await readFile(executions, 'utf8')).toBe('executed\n');
  } finally {
    if (client) {
      client.process.kill('SIGKILL');
      await client.exited;
    }
    await rm(home, {recursive: true, force: true});
  }
}, 15_000);
