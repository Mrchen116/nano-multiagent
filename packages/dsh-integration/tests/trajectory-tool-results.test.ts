import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('streams redacted live toolResults/watch values for resident sessions and returns available=false on cold sessions without waking them', async () => {
  const home = await mkdtemp(join(tmpdir(), 'trajectory-tool-results-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  const secretPngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
  const binding = { sessionId: 'traj-root', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  const config = {
    protocol: 1,
    agents: [{ agentId: 'a', revision: '1', mode: 'global', workspace: home, provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['inline_img_tool', 'send_message', 'inbox', 'conversations'], approval: { dangerouslySkipPermissions: true } }],
    bindings: [binding],
  };
  const scope = { observerId: 'obs-1', rootAgentId: 'a', rootSessionId: binding.sessionId, sessionId: binding.sessionId, ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 };

  const start = async () => {
    client = new RuntimeClient({ home, cwd: home, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', config);
  };

  try {
    await writeFile(join(home, 'fixture.mjs'), `import { appendFile } from 'node:fs/promises';
export const name = 'tool-results-fixture';
export const inject = ['tools', 'llm', 'agents'];
export function apply(ctx) {
  ctx.on('agent/created', ({ agent }) => appendFile(process.env.DSH_HOME + '/created.log', agent.id + '\\n'));
  ctx.tools.register({
    name: 'inline_img_tool',
    description: 'Returns structured raw value with inline image bytes',
    parameters: { type: 'object', properties: {} },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: () => [{ type: 'text', text: 'RENDERED_SUMMARY_TEXT' }],
    },
    async execute() {
      return {
        structuredCount: 42,
        preview: { type: 'image', mediaType: 'image/png', data: ${JSON.stringify(secretPngBase64)} },
      };
    },
  });
  const seen = new Set();
  ctx.on('llm/stream', async function*(options) {
    const user = options.messages.findLast(m => m.role === 'user' && m.source?.kind === 'user');
    if (user && !seen.has(user.id)) {
      seen.add(user.id);
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'img-call-1', name: 'inline_img_tool', arguments: '{}' } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'done' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);
    await prepareProfile(home, [{ insert: [{ id: 'tool-results-fixture', name: join(home, 'fixture.mjs') }] }]);
    await start();
    await client!.rpc.request('session.ensure', binding);
    await client!.rpc.request('session.submit', {
      sessionId: binding.sessionId,
      inputId: 'turn-1',
      mode: 'followup',
      content: [{ type: 'text', text: 'Run inline image tool' }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'turn-1' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: binding.sessionId, inputId: 'turn-1' }) as { terminal?: { kind: string } }).terminal?.kind).toBe('completed');

    const observed = await client!.rpc.request('session.observe', { sessionId: binding.sessionId }) as { events: { seq: number; type: string }[] };
    const toolResultSeqs = observed.events.filter(e => e.type === 'tool/result').map(e => e.seq);
    expect(toolResultSeqs.length).toBeGreaterThanOrEqual(2);
    const activeSurfaceSeq = toolResultSeqs.at(-1)!;

    await client!.rpc.request('trajectory.prepare', scope);
    const liveWatch = await client!.rpc.request('trajectory.open', {
      observerId: 'obs-1',
      method: 'toolResults/watch',
      initialBatch: true,
      params: { args: { request: { sessionId: binding.sessionId, seq: activeSurfaceSeq } } },
    }) as { streamId: string; initialBatch: { frames: any[] } };
    expect(liveWatch.initialBatch.frames[0]).toMatchObject({
      available: true,
      value: { structuredCount: 42 },
    });
    expect(JSON.stringify(liveWatch.initialBatch)).not.toContain(secretPngBase64);
    await expect(client!.rpc.request('trajectory.open', {
      observerId: 'obs-1',
      method: 'toolResults/watch',
      initialBatch: true,
      params: { args: { request: { sessionId: binding.sessionId, seq: -1 } } },
    })).rejects.toThrow(/trajectory_invalid_seq/);

    // Restart cold and verify toolResults/watch returns { available: false } without waking the cold session.
    await client!.shutdown();
    client = undefined;
    await start();
    await client!.rpc.request('trajectory.prepare', scope);
    const coldWatch = await client!.rpc.request('trajectory.open', {
      observerId: 'obs-1',
      method: 'toolResults/watch',
      initialBatch: true,
      params: { args: { request: { sessionId: binding.sessionId, seq: activeSurfaceSeq } } },
    }) as { streamId: string; initialBatch: { frames: any[] } };
    expect(coldWatch.initialBatch.frames[0]).toEqual({ available: false });
    const listAfterColdWatch = await client!.rpc.request('trajectory.call', { observerId: 'obs-1', method: 'session/list', params: { args: { request: {} } } }) as any;
    expect(listAfterColdWatch.value.items[0].agentAvailable).toBe(false);
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);
