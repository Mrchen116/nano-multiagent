import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import type { RelayInput } from '@nano/product-contracts';
import { GlobalAgent, type ProductCall } from '../../personal-assistant/src/global-agent.js';
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

it('retries the original unread Global Inbox wake after model-run storage becomes writable', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-storage-recovery-'));
  const store = new NodeStore(':memory:', 'owner');
  const inbox = new InboxStore(':memory:');
  const fault = join(home, 'fail-writes');
  let client: RuntimeClient | undefined;
  let product: GlobalAgent | undefined;
  const errors: string[] = [];
  const submissions: string[] = [];
  try {
    await writeFile(join(home, 'fixture.mjs'), `${writeFault('nano_model_runs/runs', fault)}
export const inject = ['llm'];
export function apply(ctx) {
  ctx.on('llm/stream', async function* (request) {
    await fs.appendFile(${JSON.stringify(join(home, 'model-requests'))}, 'model called\\n');
    const read = request.messages.find(message => message.role === 'tool');
    if (read && !JSON.stringify(read).includes('Please handle this')) {
      throw new Error('Original Inbox content missing from recovered model context');
    }
    const block = read
      ? {type: 'text', text: 'Handled the original Inbox message'}
      : {type: 'tool-call', id: 'read-original', name: 'inbox', arguments: JSON.stringify({action: 'read', target: 'c_test'})};
    yield {type: 'block-end', index: 0, block};
    yield {type: 'finish', reason: {kind: read ? 'stop' : 'tool-calls'}};
  });
}`);
    await prepareProfile(home, [{insert: [{id: 'fixture', name: join(home, 'fixture.mjs')}]}]);
    const runtime = client = new RuntimeClient({home, cwd: home, onLog: value => errors.push(value)});
    registerNoopTaskHosts(runtime);
    const config = {
      agentId: 'a', workspace: home, revision: '1', mode: 'global' as const,
      provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['inbox'],
      approval: {dangerouslySkipPermissions: true},
    };
    const binding = {
      agentId: 'a', sessionId: 'main', conversationId: 'global:a', ownerId: 'owner', cwd: home, revision: '1',
    };
    store.bind(binding);
    const global = product = new GlobalAgent({
      nodeId: 'node', ownerId: 'owner', agents: [config], store, inbox, image: async () => '',
      onError: error => errors.push(String(error)),
      runtime: {
        onNotification: runtime.rpc.onNotification.bind(runtime.rpc),
        request: async (method, params) => {
          if (method === 'session.submit') submissions.push((params as {inputId: string}).inputId);
          return runtime.rpc.request(method, params);
        },
      },
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
    await expect.poll(() => inbox.unreadAttention('a'), {timeout: 8_000}).toBeUndefined();
    await global.recover();
    expect(submissions).toEqual(['inbox-wake:a:1', expect.stringMatching(/^inbox-wake:a:1:recovery:\d+$/)]);
    await expect.poll(async () => {
      const result = await runtime.rpc.request('session.observe', {sessionId: 'main'}) as {modelRuns: {terminal?: unknown}[]};
      return result.modelRuns.at(-1)?.terminal;
    }).toEqual({kind: 'completed'});
    expect(await readFile(join(home, 'model-requests'), 'utf8')).toBe('model called\nmodel called\n');
  } catch (error) {
    throw new Error(`${error}\n${errors.slice(-8).join('\n')}`, {cause: error});
  } finally {
    await rm(fault, {force: true});
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
