import { mkdtemp, readFile, rm, writeFile, chmod } from 'node:fs/promises';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { NodeConfiguration } from '../src/configuration.js';
import { providerProfiles } from '../src/providers.js';
import { ModelSetup, discoverLocalModels } from '../src/model-setup.js';

it('keeps native Codex auth and protocol in the installed catalog', () => {
  const profile = providerProfiles({ default_model: 'gpt-6-sol', providers: [{ name: 'openai-codex', native: true, models: [{ name: 'gpt-6-sol' }] }] });
  expect(profile.providers).toEqual({ 'openai-codex': { models: [{ id: 'gpt-6-sol', contextWindow: undefined }] } });
  expect(profile.env).toEqual({});
});

it('returns a queryable operation before testing, saves only verified nonsecret routes and preserves existing fields', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-setup-'));
  try {
    const path = join(home, 'config.yaml');
    await writeFile(path, JSON.stringify({ node: { node_id: 'n', user_id: 'u', workspace_base: home }, im_service: { url: 'https://im.test', token: 'preserve' }, agents: [], llm: { default_model: '', providers: [] } }));
    const config = await NodeConfiguration.read(path);
    let finish!: () => void;
    const requests: { method: string; value: any }[] = [];
    const runtime = {
      request: async (method: string, value: any): Promise<any> => {
        requests.push({ method, value });
        if (method === 'model.setup.catalog') return [];
        if (method === 'model.setup.test') await new Promise<void>(resolve => { finish = resolve; });
        return {};
      },
      onNotification: () => () => {},
    };
    const setup = new ModelSetup(config, runtime, async () => ({ codex: false }));
    const pending = await setup.handle({ action: 'configure', provider: 'custom', protocol: 'openai-completions', base_url: 'http://127.0.0.1:4000/v1', model: 'test', api_key: 'secret-must-stay-local' });
    expect(pending.operation?.state).toBe('testing');
    expect(config.value.llm.providers).toEqual([]);
    expect(JSON.stringify(pending)).not.toContain('secret-must-stay-local');
    await expect.poll(() => typeof finish).toBe('function'); finish();
    await expect.poll(async () => (await setup.handle({ action: 'status' })).operation?.state).toBe('succeeded');
    const saved = await readFile(path, 'utf8');
    expect(saved).not.toContain('secret-must-stay-local');
    expect((await NodeConfiguration.read(path)).value).toMatchObject({ im_service: { token: 'preserve' }, llm: { default_model: 'test', providers: [{ protocol: 'openai-completions', models: [{ name: 'test' }] }] } });
    expect(requests.some(call => call.method === 'model.setup.finish' && call.value.commit)).toBe(true);
  } finally { await rm(home, { recursive: true, force: true }); }
});

it('sanitizes provider failures without committing or replacing the existing model', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-setup-failure-'));
  try {
    const path = join(home, 'config.yaml');
    const llm = { default_model: 'existing', providers: [{ name: 'old', base_url: 'http://localhost:4000/v1', models: [{ name: 'existing' }] }] };
    await writeFile(path, JSON.stringify({ node: {}, agents: [], llm }));
    const config = await NodeConfiguration.read(path);
    const setup = new ModelSetup(config, { request: async method => { if (method === 'model.setup.catalog') return []; throw new Error('upstream leaked secret'); }, onNotification: () => () => {} }, async () => ({ codex: false }));
    await setup.handle({ action: 'configure', provider: 'custom', protocol: 'openai-completions', base_url: 'http://localhost:9/v1', model: 'new' });
    await expect.poll(async () => (await setup.handle({ action: 'status' })).operation?.state).toBe('failed');
    expect(JSON.stringify(await setup.handle({ action: 'status' }))).not.toContain('upstream leaked secret');
    expect(config.value.llm).toEqual(llm);
  } finally { await rm(home, { recursive: true, force: true }); }
});

it.each([false, true])('discovers only models compatible with the chosen proxy ingress (OpenAI available: %s)', async openai => {
  const home = await mkdtemp(join(tmpdir(), 'nano-proxy-discovery-'));
  const server = createServer((_req, res) => { res.writeHead(200, { 'content-type': 'application/json' }); res.end('{"ok":true}'); });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const path = join(home, 'upstreams.json');
    await writeFile(path, JSON.stringify({ defaultProfile: 'deepseek', profiles: {
      ...(openai ? { codexOAuth: { defaults: { model: 'gpt-6-luna' }, capabilities: { ingress: ['openai_chat', 'anthropic_messages'] } } } : {}),
      deepseek: { defaults: { model: 'flash' }, capabilities: { ingress: ['anthropic_messages'] }, auth: { secret: 'must-not-project' } },
    } }));
    await writeFile(join(home, 'codex'), '#!/bin/sh\n'); await chmod(join(home, 'codex'), 0o700);
    vi.stubEnv('PATH', home); vi.stubEnv('NANO_LLM_PROXY_CONFIG', path); vi.stubEnv('NANO_LLM_PROXY_URL', `http://127.0.0.1:${(server.address() as { port: number }).port}`);
    const discovered = await discoverLocalModels();
    expect(discovered).toMatchObject({ codex: true, proxy: openai
      ? { protocol: 'openai-completions', models: ['codexOAuth:gpt-6-luna'] }
      : { protocol: 'anthropic-messages', models: ['deepseek:flash'] } });
    expect(JSON.stringify(discovered)).not.toContain('must-not-project');
  } finally { vi.unstubAllEnvs(); await new Promise<void>(resolve => server.close(() => resolve())); await rm(home, { recursive: true, force: true }); }
});

it('discovers a proxy started after the first status without restarting the node', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-discovery-refresh-'));
  try {
    const path = join(home, 'config.yaml');
    await writeFile(path, JSON.stringify({node: {}, agents: [], llm: {default_model: '', providers: []}}));
    let available = false;
    const setup = new ModelSetup(await NodeConfiguration.read(path), {request: async () => [], onNotification: () => () => {}}, async () => ({codex: false, ...(available ? {proxy: {base_url: 'http://localhost:4000/v1', models: ['local'], protocol: 'openai-completions' as const}} : {})}));
    expect((await setup.handle({action: 'status'})).discovered.proxy).toBeUndefined();
    available = true;
    expect((await setup.handle({action: 'status'})).discovered.proxy?.models).toEqual(['local']);
  } finally { await rm(home, {recursive: true, force: true}); }
});
