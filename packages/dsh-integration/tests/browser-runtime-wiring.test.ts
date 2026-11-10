import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

type Event = { type: string; data: { message?: { toolCallId?: string; content?: { type: string; text?: string }[] }; name?: string } };

it.skipIf(process.platform !== 'darwin')('wires the installed browser gate through injected approval before real driver admission', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-browser-runtime-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    const probeLog = join(home, 'driver-probes.jsonl');
    const driver = join(home, 'fixture-driver.mjs');
    // This executable is only a probe sentinel, never a browser launcher. A
    // reached --version proves that live admission finished before driver I/O.
    await writeFile(driver, `#!/usr/bin/env node
import { appendFileSync } from 'node:fs';
appendFileSync(${JSON.stringify(probeLog)}, JSON.stringify(process.argv.slice(2)) + '\\n');
console.log('fixture-probe-sentinel');
`, { mode: 0o755 });
    const model = join(home, 'fixture-model.mjs');
    await writeFile(model, `export const name = 'browser-wiring-fixture';
export const inject = ['llm'];
export function apply(ctx) {
  ctx.on('llm/stream', async function* (options) {
    const last = options.messages.at(-1);
    if (last?.role === 'tool') {
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Observed the browser result; stopping.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }
    yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'fixture-browser-read', name: 'browser_read', arguments: '{}' } };
    yield { type: 'finish', reason: { kind: 'tool-calls' } };
  });
}
`);
    await prepareProfile(home, [{ insert: [{ id: 'browser-wiring-fixture', name: model }] }]);
    client = new RuntimeClient({ home, cwd: home, env: { ...process.env, NANO_CUA_DRIVER: driver }, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    const config = { agentId: 'browser-wiring', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['browser_read'], knowledge: { memoryMode: 'legacy' }, skillSelection: { mode: 'explicit_allowlist', names: [] } };
    await client.rpc.request('initialize', { protocol: 1, agents: [config], bindings: [] });
    for (const [name, source] of [
      ['system', { kind: 'system', actorId: 'system', channel: 'heartbeat', messageId: 'system' }],
      ['human', { kind: 'human', actorId: 'fixture-owner', channel: 'test', messageId: 'human' }],
    ] as const) {
      const sessionId = `browser-wiring-${name}`;
      await client.rpc.request('session.ensure', { sessionId, agentId: config.agentId, revision: '1', ownerId: 'fixture-owner', cwd: home });
      await client.rpc.request('session.submit', { sessionId, inputId: name, mode: 'followup', source, content: [{ type: 'text', text: 'Read the isolated test browser once and stop.' }] });
      let events: Event[] = [];
      await expect.poll(async () => {
        const observed = await client!.rpc.request('session.observe', { sessionId }) as { status: string; events: Event[] };
        events = observed.events;
        return observed.status;
      }, { timeout: 8_000 }).toBe('idle');
      const results = events.filter(event => event.type === 'tool/result' && event.data.message?.toolCallId === 'fixture-browser-read');
      const text = JSON.stringify(results);
      expect(results.length).toBeGreaterThan(0);
      expect(text).not.toContain('cannot get property');
      if (name === 'system') {
        expect(text).toContain('browser_launch_requires_user_turn');
        await expect(readFile(probeLog, 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
      } else {
        expect(text).toContain('fixture-probe-sentinel');
        expect(await readFile(probeLog, 'utf8')).toBe('["--version"]\n');
      }
    }
    await client.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    // Only the mkdtemp directory created above can be removed by this fixture.
    if (resolve(home).startsWith(resolve(tmpdir(), 'nano-browser-runtime-'))) await rm(home, { recursive: true, force: true });
  }
}, 25_000);
