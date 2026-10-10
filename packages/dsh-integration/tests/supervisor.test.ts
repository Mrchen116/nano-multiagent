import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeSupervisor } from '../src/client.js';

it('keeps the node port stable across a runtime crash and recovers persisted input without replay', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-supervisor-'));
  const binding = { sessionId: 'recover', agentId: 'test', revision: '1', ownerId: 'owner', cwd: join(home, 'workspace') };
  let recovered!: () => void;
  const restarted = new Promise<void>(resolve => { recovered = resolve; });
  let generations = 0;
  const supervisor = new RuntimeSupervisor({ home, cwd: home,
    initialize: async rpc => {
      await rpc.request('initialize', { protocol: 1, agents: [{ agentId: 'test', revision: '1', provider: 'deepseek-official', model: 'deepseek-flash' }], bindings: [binding] });
      await rpc.request('session.ensure', binding);
    },
    onReady: async () => { if (++generations === 2) recovered(); },
    onError: () => {},
  });
  try {
    await prepareProfile(home);
    await supervisor.start();
    const pid = supervisor.process!.pid;
    await supervisor.request('session.submit', { sessionId: 'recover', inputId: 'one', mode: 'inject',
      content: [{ type: 'text', text: 'retained' }], source: { kind: 'system', actorId: 'owner', channel: 'test', messageId: 'one' } });
    supervisor.process!.kill('SIGKILL');
    await restarted;
    expect(supervisor.process!.pid).not.toBe(pid);
    expect(await supervisor.request('session.lookup', { sessionId: 'recover', inputId: 'one' })).toMatchObject({ accepted: true, pending: true });
  } finally {
    await supervisor.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);
