import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { prepareProfile, RuntimeClient } from '@nano/dsh-integration/client';

/** Verify candidate credentials and every selected model without changing live Agent routes. */
export async function probeModels(candidate: {provider: string; providers: Record<string, unknown>; models: string[]; api_key?: string}, signal: AbortSignal): Promise<void> {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-probe-'));
  let client: RuntimeClient | undefined;
  const abort = () => { client?.process.kill('SIGKILL'); };
  const deadline = AbortSignal.any([signal, AbortSignal.timeout(30_000 + candidate.models.length * 45_000)]);
  deadline.addEventListener('abort', abort, {once: true});
  try {
    deadline.throwIfAborted();
    await prepareProfile(home, [{id: 'llm-pi-ai', config: {providers: {}}}]);
    client = new RuntimeClient({home, cwd: home});
    deadline.throwIfAborted();
    await client.rpc.request('initialize', {protocol: 1, agents: [], bindings: [], providers: {}});
    await client.rpc.request('model.setup.test', {id: 'probe', ...candidate});
    deadline.throwIfAborted();
  } finally {
    deadline.removeEventListener('abort', abort);
    if (client) { client.process.kill('SIGKILL'); await client.exited; }
    await rm(home, {recursive: true, force: true});
  }
}
