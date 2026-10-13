import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { NodeConfiguration } from '../src/configuration.js';
import { ModelSetup } from '../src/model-setup.js';

async function fixture(run: (f: Awaited<ReturnType<typeof create>>) => Promise<void>) {
  const f = await create(); try {await run(f);} finally {await f.setup.stop(); await rm(f.home, {recursive: true, force: true});}
}
async function create() {
  const home = await mkdtemp(join(tmpdir(), 'nano-model-management-'));
  const path = join(home, 'config.yaml');
  await writeFile(path, JSON.stringify({node: {node_id: 'n', user_id: 'u', workspace_base: home}, im_service: {url: 'https://im.test', token: 'preserve'}, agents: [], llm: {default_model: '', providers: []}}));
  const config = await NodeConfiguration.read(path);
  let record: any = null;
  const runtime = {request: vi.fn(async (method: string, value: any): Promise<any> => {
    if (method === 'model.setup.catalog') return [{provider: 'openai', models: [{id: 'test'}]}];
    if (method === 'model.setup.credential') return {record};
    if (method === 'model.setup.stage') record = value.api_key ? {kind: 'api-key', key: value.api_key} : null;
    if (method === 'model.setup.restore') record = value.record;
    return {};
  }), onNotification: () => () => {}};
  const probe = vi.fn(async (_value: any, _signal: AbortSignal) => {});
  const setup = new ModelSetup(config, runtime, probe);
  const save = (extra = {}) => setup.handle({action: 'save', revision: config.modelRevision, source: 'custom', display_name: 'My API', protocol: 'openai-completions', base_url: 'http://localhost:1234/v1', api_key: 'initial-secret', models: [{id: 'shared-model'}], ...extra});
  const done = async (state = 'succeeded') => {await expect.poll(async () => (await setup.handle({action: 'status'})).operation?.state).toBe(state);};
  return {home, path, config, runtime, probe, setup, save, done};
}

it('probes away from live routes, supports duplicate wire IDs, edits blank-key credentials and persists stable references', async () => fixture(async f => {
  let release!: () => void;
  f.probe.mockImplementationOnce(async () => new Promise<void>(resolve => {release = resolve;}));
  const started = await f.save();
  expect(started.operation?.state).toBe('testing');
  expect(JSON.stringify(started)).not.toContain('initial-secret');
  await expect.poll(() => typeof release).toBe('function');
  expect(f.runtime.request.mock.calls.some(([method]) => method === 'model.setup.stage')).toBe(false);
  release(); await f.done();
  const provider = f.config.value.llm.providers[0]!;
  const reference = provider.models[0]!.name;
  await f.save({provider: provider.name, api_key: '', base_url: 'http://localhost:2345/v1', models: [{id: 'shared-model', display_name: 'Renamed'}, {id: 'second'}]}); await f.done();
  expect(f.probe.mock.calls.at(-1)?.[0].api_key).toBe('initial-secret');
  expect(f.config.value.llm.providers[0]?.models[0]?.name).toBe(reference);
  await f.save(); await f.done();
  expect(f.config.value.llm.providers).toHaveLength(2);
  expect(f.config.value.llm.providers[1]?.models[0]?.name).not.toBe(reference);
  const saved = await readFile(f.path, 'utf8');
  expect(saved).not.toContain('initial-secret');
  expect((await NodeConfiguration.read(f.path)).value.im_service.token).toBe('preserve');
}));

it('preserves existing routes on failed probes, cancellation, busy operations and stale drafts', async () => fixture(async f => {
  await f.save(); await f.done();
  const original = JSON.stringify(f.config.value.llm);
  f.probe.mockRejectedValueOnce(new Error('secret upstream response'));
  await f.save({provider: f.config.value.llm.providers[0]!.name, api_key: 'bad'}); await f.done('failed');
  expect(JSON.stringify(await f.setup.handle({action: 'status'}))).not.toContain('secret upstream');
  expect(JSON.stringify(f.config.value.llm)).toBe(original);
  f.probe.mockImplementationOnce(async (_v, signal) => new Promise<void>((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')), {once: true})));
  await f.save(); await expect.poll(() => f.probe.mock.calls.length).toBe(3);
  expect((await f.save()).error?.code).toBe('busy');
  await f.setup.handle({action: 'cancel'}); await f.done('cancelled');
  expect(JSON.stringify(f.config.value.llm)).toBe(original);
  expect((await f.save({revision: 'outdated'})).error?.code).toBe('conflict');
}));

it('blocks used model removal and rolls back live credentials if YAML publication fails', async () => fixture(async f => {
  await f.save(); await f.done();
  const provider = f.config.value.llm.providers[0]!;
  f.config.value.agents.push({agent_id: 'agent', title: 'Helper', default_model: provider.models[0]!.name, workspace_root: f.home});
  const removal = await f.setup.handle({action: 'remove', provider: provider.name, revision: f.config.modelRevision});
  expect(removal.error).toMatchObject({code: 'in_use', dependencies: [{agent_id: 'agent', display_name: 'Helper'}]});
  f.config.value.agents = [];
  const write = vi.spyOn(f.config as any, 'writeFile').mockRejectedValueOnce(new Error('disk failed'));
  await f.save({provider: provider.name, api_key: 'rotated'}); await f.done('failed');
  expect(f.runtime.request.mock.calls.findLast(([method]) => method === 'model.setup.restore')?.[1].record.key).toBe('initial-secret');
  write.mockRestore();
  await f.setup.handle({action: 'remove', provider: provider.name, revision: f.config.modelRevision}); await f.done();
  expect(f.config.value.llm.providers).toEqual([]);
}));

it('restores a staged key after the child exits before config publication', async () => fixture(async f => {
  await f.save(); await f.done();
  const provider = f.config.value.llm.providers[0]!;
  const original = f.runtime.request.getMockImplementation()!;
  let unavailable = true;
  f.runtime.request.mockImplementation(async (method, value) => {
    if (method === 'model.setup.stage' && unavailable) {await original(method, value); throw new Error('child exited');}
    if (method === 'model.setup.restore' && unavailable) throw new Error('unavailable');
    return original(method, value);
  });
  await f.save({provider: provider.name, api_key: 'rotated'});
  await expect.poll(() => f.runtime.request.mock.calls.some(([method]) => method === 'model.setup.restore')).toBe(true);
  expect((await f.save()).error?.code).toBe('busy');
  unavailable = false; await f.setup.recover(); await f.done('failed');
  await f.save({provider: provider.name, api_key: ''}); await f.done();
  expect(f.probe.mock.calls.at(-1)?.[0].api_key).toBe('initial-secret');
}));


it('opens legacy protocol defaults correctly and migrates an inline key without changing old model references', async () => fixture(async f => {
  f.config.value.llm = {default_model: 'legacy-model', providers: [{name: 'anthropic', base_url: 'http://localhost:1234', api_key: 'legacy-key', models: [{name: 'legacy-model', reasoning: {default: 'high', levels: ['high']}}]}]};
  const status = await f.setup.handle({action: 'status'});
  expect(status.services[0]).toMatchObject({protocol: 'anthropic-messages', credential_stored: true, models: [{name: 'legacy-model', id: 'legacy-model'}]});
  await f.save({provider: 'anthropic', api_key: '', protocol: 'anthropic-messages', models: [{id: 'legacy-model'}]}); await f.done();
  expect(f.probe.mock.calls[0]?.[0].api_key).toBe('legacy-key');
  expect(f.config.value.llm.providers[0]).not.toHaveProperty('api_key');
  expect(f.config.value.llm.providers[0]?.models[0]).toMatchObject({name: 'legacy-model', id: 'legacy-model', reasoning: {default: 'high', levels: ['high']}});
  expect(f.runtime.request.mock.calls.find(([method]) => method === 'model.setup.stage')?.[1].providers.anthropic).not.toHaveProperty('apiKeyEnv');
}));
