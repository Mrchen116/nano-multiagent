import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';

it('reads cold native history without activating an Agent and replaces the observer generation on normal activation', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-trajectory-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  const binding = { sessionId: 'native-history', agentId: 'a', revision: '1', ownerId: 'owner', cwd: home };
  const configuration = { protocol: 1, agents: [{ agentId: 'a', revision: '1', mode: 'global', provider: 'deepseek-official', model: 'deepseek-flash' }], bindings: [binding] };
  const scope = { observerId: 'viewer', rootAgentId: 'a', rootSessionId: binding.sessionId, sessionId: binding.sessionId, ownerId: 'owner', nodeId: 'node', nodeEpoch: 1 };
  const imageData = 'iVBORw0KGgoAAAANSUhEUgAAAKAAAABaCAIAAACwpMoFAAABNklEQVR4nO3ZwQmAMBQFwVRjY5ZtB9qD2ILkILgZ+PdJ2OMb235N33He08f9xh2rfXg1V+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrvjj4/mvj+B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx37cFxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx117cNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBx1x4cdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNy1B8ddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdx+RTJHLcoVInQAAAABJRU5ErkJggg==';
  const source = { kind: 'chat', conversationId: 'private-chat', messageId: 'input', url: '/im/v1/conversations/private-chat/images/photo' };
  const start = async () => {
    client = new RuntimeClient({ home, cwd: home, onLog: value => { logs += value; } });
    await client.rpc.request('initialize', configuration);
  };
  try {
    await writeFile(join(home, 'lifecycle.mjs'), `import{appendFile}from'node:fs/promises';export const name='trajectory-lifecycle';export const inject=['agents'];export function apply(ctx){ctx.on('agent/created',async({agent})=>{await appendFile(process.env.DSH_HOME+'/created',agent.id+'\\n')});}`);
    await prepareProfile(home, [{ insert: [{ id: 'trajectory-lifecycle', name: join(home, 'lifecycle.mjs') }] }]);
    await start();
    await client!.rpc.request('session.ensure', binding);
    await client!.rpc.request('session.submit', { sessionId: binding.sessionId, inputId: 'cold-input', mode: 'inject', content: [{ type: 'text', text: 'Read without waking' }, { type: 'image', data: imageData, mediaType: 'image/png' }], attachmentSources: [null, source], source: { kind: 'system', actorId: 'owner', channel: 'test', messageId: 'input' } });
    await client!.shutdown();
    const before = await readFile(join(home, 'created'), 'utf8');
    await start();
    expect(await client!.rpc.request('trajectory.prepare', scope)).toMatchObject({ version: '0.2.1-alpha.1' });
    await expect(client!.rpc.request('trajectory.prepare', { ...scope, observerId: 'wrong', rootAgentId: 'other' })).rejects.toThrow(/scope/i);
    const opened = await client!.rpc.request('trajectory.open', { observerId: 'viewer', method: 'session/follow', params: { args: { request: { assistantStream: true, maxMessages: 50 } } } }) as { streamId: string };
    const batch = await client!.rpc.request('trajectory.next', { observerId: 'viewer', streamId: opened.streamId }) as { frames: any[] };
    expect(batch.frames[0]).toMatchObject({ type: 'snapshot', header: { id: binding.sessionId }, assistantStream: { revision: 0 } });
    const cursor = batch.frames[0].cursor;
    const page = await client!.rpc.request('trajectory.call', { observerId: 'viewer', method: 'session/page', params: { args: { request: { throughSeq: cursor, maxMessages: 50 } } } }) as any;
    expect(page.ok).toBe(true);
    expect(page.value.records.length).toBeGreaterThan(0);
    const refs: string[] = [];
    const collect = (value: any) => { if (value?.type === 'image' && value.attachment) refs.push(value.attachment.attachmentId); if (value && typeof value === 'object') Object.values(value).forEach(collect); };
    collect(page.value.records);
    expect(refs.length).toBeGreaterThan(0);
    const params = { args: { request: { attachmentId: refs[0] } } };
    const provenance = await client!.rpc.request('trajectory.call', { observerId: 'viewer', method: 'trajectory/attachment-source', params }) as any;
    expect(provenance.value.sources).toContainEqual(source);
    await expect(client!.rpc.request('trajectory.call', { observerId: 'viewer', method: 'session/attachment', params })).rejects.toThrow(/附件/);
    const image = await client!.rpc.request('trajectory.call', { observerId: 'viewer', method: 'session/attachment', params, attachmentAuthorized: true }) as any;
    expect(image.ok).toBe(true);
    expect(JSON.stringify(image.value)).toContain('image/png');
    await expect(client!.rpc.request('trajectory.call', { observerId: 'viewer', method: 'session/cancel', params: {} })).rejects.toThrow(/read.only/i);
    expect(await readFile(join(home, 'created'), 'utf8')).toBe(before);
    // Only normal business activation may acquire an Agent owner.
    await client!.rpc.request('session.ensure', binding);
    await expect(client!.rpc.request('trajectory.next', { observerId: 'viewer', streamId: opened.streamId })).rejects.toThrow(/generation_changed/);
    await client!.rpc.request('trajectory.close', { observerId: 'viewer' });
    await expect(client!.rpc.request('trajectory.call', { observerId: 'viewer', method: 'session/list', params: {} })).rejects.toThrow(/observer/i);
    await client!.shutdown(); client = undefined;
  } catch (error) { throw new Error(`${String(error)}\n${logs}`, { cause: error }); }
  finally { if (client && client.process.exitCode === null) { client.process.kill('SIGKILL'); await client.exited; } await rm(home, { recursive: true, force: true }); }
}, 30_000);
