import { createServer } from 'node:http';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { CapabilityState } from '../src/capability-state.js';
import { ToolSelection } from '../src/capabilities.js';
import { isOfficialDeepSeekRoute, searchProviders } from '../src/web.js';
import { featureDependencies } from '@nano/product-contracts/capabilities';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

const offFeatures = Object.fromEntries(featureDependencies.map(f => [f.key, false]));
const legacyFeatures = Object.fromEntries(featureDependencies.filter(f => f.key !== 'plugin_management').map(f => [f.key, false]));

it('exposes cordis_inspect_* in catalog, preserves pre-feat-791 plugin_manager continuity, supports standalone inspect selection, and locks on withdrawal', async () => {
  const home = await mkdtemp(join(tmpdir(), 'cordis-inspect-'));
  const workspaceDev = join(home, 'workspace-dev');
  const workspaceStandalone = join(home, 'workspace-standalone');
  const workspacePlain = join(home, 'workspace-plain');
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await mkdir(workspaceDev, { recursive: true });
    await mkdir(workspaceStandalone, { recursive: true });
    await mkdir(workspacePlain, { recursive: true });
    await writeFile(join(home, 'fixture.mjs'), `import { writeFile } from 'node:fs/promises';
export const name = 'inspect-fixture';
export const inject = ['llm', 'tools'];
export function apply(ctx) {
  const seen = new Set();
  ctx.on('llm/stream', async function*(options) {
    const user = options.messages.findLast(m => m.role === 'user' && m.source?.kind === 'user');
    if (user && !seen.has(user.id)) {
      seen.add(user.id);
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'list-call', name: 'cordis_inspect_list', arguments: JSON.stringify({}) } };
      yield { type: 'block-end', index: 1, block: { type: 'tool-call', id: 'query-call', name: 'cordis_inspect_query', arguments: JSON.stringify({ platform: 'host', provider: 'Service', method: 'listService', input: { service: 'tools' } }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'inspected' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
  ctx.on('tools/result', (exec, result) => {
    void writeFile(process.env.DSH_HOME + '/' + exec.callId + '.json', JSON.stringify(result));
  });
}`);
    await prepareProfile(home, [{ insert: [{ id: 'inspect-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: workspaceDev, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', {
      protocol: 1,
      agents: [
        { agentId: 'dev', revision: '1', workspace: workspaceDev, provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['plugin_manager'], features: legacyFeatures },
        { agentId: 'standalone', revision: '1', workspace: workspaceStandalone, provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['cordis_inspect_list'], features: offFeatures },
        { agentId: 'plain', revision: '1', workspace: workspacePlain, provider: 'deepseek-official', model: 'deepseek-flash', toolAllowlist: ['read'], features: legacyFeatures },
      ],
      bindings: [],
    });
    await client.rpc.request('session.ensure', { sessionId: 's-dev', agentId: 'dev', revision: '1', ownerId: 'owner', cwd: workspaceDev });
    await client.rpc.request('session.ensure', { sessionId: 's-standalone', agentId: 'standalone', revision: '1', ownerId: 'owner', cwd: workspaceStandalone });
    await client.rpc.request('session.ensure', { sessionId: 's-plain', agentId: 'plain', revision: '1', ownerId: 'owner', cwd: workspacePlain });

    const catalog = await client.rpc.request('configuration.catalog', { agentId: 'dev', cwd: workspaceDev }) as { tools: { name: string }[] };
    expect(catalog.tools.map(t => t.name)).toEqual(expect.arrayContaining(['cordis_inspect_list', 'cordis_inspect_query']));

    const devCaps = await client.rpc.request('session.capabilities', { sessionId: 's-dev' }) as { tools: string[] };
    expect(devCaps.tools).toEqual(expect.arrayContaining(['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query']));

    const standaloneCaps = await client.rpc.request('session.capabilities', { sessionId: 's-standalone' }) as { tools: string[] };
    expect(standaloneCaps.tools).toContain('cordis_inspect_list');
    expect(standaloneCaps.tools).not.toContain('cordis_inspect_query');
    expect(standaloneCaps.tools).not.toContain('plugin_manager');

    const plainCaps = await client.rpc.request('session.capabilities', { sessionId: 's-plain' }) as { tools: string[] };
    expect(plainCaps.tools).not.toContain('cordis_inspect_list');
    expect(plainCaps.tools).not.toContain('cordis_inspect_query');

    // Execute without dangerouslySkipPermissions to prove safeTools fast-allows read-only inspect tools.
    await client.rpc.request('session.submit', {
      sessionId: 's-dev',
      inputId: 'run-inspect',
      mode: 'followup',
      content: [{ type: 'text', text: 'Inspect runtime' }],
      source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: 'run-inspect' },
    });
    await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 's-dev', inputId: 'run-inspect' }) as { terminal?: { kind: string } }).terminal?.kind).toBe('completed');
    const listResult = JSON.parse(await readFile(join(home, 'list-call.json'), 'utf8'));
    const queryResult = JSON.parse(await readFile(join(home, 'query-call.json'), 'utf8'));
    expect(listResult.isError).not.toBe(true);
    expect(queryResult.isError).not.toBe(true);

    // Personal Agent, subagent_fork parity, ordinary subagents, and CapabilityState withdrawal lock checks.
    const fakeCtx = { on: () => () => {}, tools: { schemas: () => [] } } as never;
    const selector = new ToolSelection(fakeCtx);
    const paEnabledSelection = selector.selection({
      agentId: 'pa',
      revision: '1',
      mode: 'global',
      workspace: workspaceDev,
      provider: 'p',
      model: 'm',
      toolAllowlist: ['plugin_manager'],
      personal: { bindingId: 'b', ownerId: 'owner', conversationId: 'dm', epoch: 1 },
    }, ['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query']);
    expect(paEnabledSelection).toEqual(['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query']);
    const forkSelection = selector.selection(
      { agentId: 'standalone', revision: '1', workspace: workspacePlain, provider: 'p', model: 'm', features: offFeatures, toolAllowlist: ['cordis_inspect_list', 'read'] },
      ['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query', 'read'],
      { session: { header: { origin: 'subagent-fork' } } } as never,
    );
    expect(forkSelection).toEqual(['cordis_inspect_list', 'read']);
    const paDisabledSelection = selector.selection({
      agentId: 'pa',
      revision: '1',
      mode: 'global',
      workspace: workspaceDev,
      provider: 'p',
      model: 'm',
      toolAllowlist: ['read'],
      personal: { bindingId: 'b', ownerId: 'owner', conversationId: 'dm', epoch: 1 },
    }, ['read', 'cordis_inspect_list', 'cordis_inspect_query']);
    expect(paDisabledSelection).toEqual(['read']);
    const subagentSelection = selector.selection(
      { agentId: 'dev', revision: '1', workspace: workspaceDev, provider: 'p', model: 'm', toolAllowlist: ['plugin_manager', 'cordis_inspect_list'] },
      ['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query'],
      { session: { header: { origin: 'subagent' } } } as never,
    );
    expect(subagentSelection).not.toContain('cordis_inspect_list');
    const state = new CapabilityState((cfg, names) => selector.selection(cfg, names));
    const before = { agentId: 'dev', revision: '1', workspace: workspaceDev, provider: 'p', model: 'm', features: {...offFeatures, plugin_management: true}, toolAllowlist: ['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query', 'read'], skills: ['nano-plugin-development'], skillsSelectionMode: 'explicit_allowlist' as const };
    const after = { ...before, revision: '2', features: offFeatures, toolAllowlist: ['read'], skills: [] };
    expect(state.begin('in-flight', 'dev', { kind: 'tool', name: 'cordis_inspect_query' })).toBe(true);
    expect(await state.prepare({ operationId: 'op1', fingerprint: '2', config: after }, before, { tools: ['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query', 'read'], skills: ['nano-plugin-development'] }, async () => ({ active_schedules: 0, busy: state.busy('dev') })))
      .toMatchObject({ ready: false, blocks: [{ code: 'capability_busy', target: { kind: 'tool', name: 'cordis_inspect_query' } }] });
    state.end('in-flight');
    expect(await state.prepare({ operationId: 'op1', fingerprint: '2', config: after }, before, { tools: ['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query', 'read'], skills: ['nano-plugin-development'] }, async () => ({ active_schedules: 0, busy: state.busy('dev') })))
      .toMatchObject({ ready: true });
    expect(state.begin('after-prepare', 'dev', { kind: 'tool', name: 'cordis_inspect_list' })).toBe(false);
    state.release('dev', 'op1');
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);

it('selects mutually exclusive search providers, omits ori_question on DeepSeek search, and keeps duckduckgo fallback visible', async () => {
  expect(isOfficialDeepSeekRoute('deepseek', {} as never)).toBe(true);
  expect(isOfficialDeepSeekRoute('custom', { baseURL: 'https://api.deepseek.com/v1' } as never)).toBe(true);
  expect(isOfficialDeepSeekRoute('custom', { baseURL: 'http://api.deepseek.com/v1' } as never)).toBe(false);
  expect(isOfficialDeepSeekRoute('custom', { baseURL: 'https://third-party-proxy.example.com/v1' } as never)).toBe(false);

  const activeIds = (env: NodeJS.ProcessEnv, hasDeepSeek: boolean) =>
    searchProviders(env, { hasOfficialDeepSeekCredential: () => hasDeepSeek }).filter(p => p.available()).map(p => p.id);

  expect(activeIds({ SEARXNG_URL: 'http://127.0.0.1:8080', BRAVE_API_KEY: 'b' }, true)).toEqual(['searxng']);
  expect(activeIds({ BRAVE_API_KEY: 'b' }, true)).toEqual(['brave']);
  expect(activeIds({}, true)).toEqual(['deepseek-search-api']);
  expect(activeIds({}, false)).toEqual(['duckduckgo']);

  const bodies: Record<string, unknown>[] = [];
  const authHeaders: (string | undefined)[] = [];
  const server = createServer(async (req, res) => {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    bodies.push(JSON.parse(raw));
    authHeaders.push(req.headers.authorization);
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ results: [{ url: 'https://deepseek.example/doc', title: 'DSH 0.2.2', snippet: 'Release notes', date: null }] }));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const endpoint = `http://127.0.0.1:${(server.address() as { port: number }).port}/v1/tools/search`;

  const home = await mkdtemp(join(tmpdir(), 'nano-web-fallback-'));
  let client: RuntimeClient | undefined;
  try {
    const dsProvider = searchProviders({}, {
      hasOfficialDeepSeekCredential: () => true,
      resolveOfficialDeepSeekToken: async () => 'sk-official-test',
      deepSeekSearchEndpoint: endpoint,
    }).find(p => p.id === 'deepseek-search-api')!;
    const searchRes = await dsProvider.search({ query: 'dsh 0.2.2 upgrade', maxResults: 5 });
    expect(authHeaders).toEqual(['Bearer sk-official-test']);
    expect(bodies).toEqual([{ query: 'dsh 0.2.2 upgrade', count: 5 }]);
    expect(bodies[0]).not.toHaveProperty('ori_question');
    expect(searchRes.sources[0]?.url).toBe('https://deepseek.example/doc');

    // Verify web_search remains visible when no search env or DeepSeek credential exists (duckduckgo fallback).
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'fixture' }] } } } },
    ]);
    client = new RuntimeClient({
      home,
      cwd: home,
      env: { NANO_TEST_KEY: 'fixture', SEARXNG_URL: '', BRAVE_API_KEY: '', DEEPSEEK_API_KEY: '', DSH_WEB_SEARCH_PROVIDER: '' },
    });
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', {
      protocol: 1,
      agents: [{ agentId: 'no-creds', revision: '1', workspace: home, provider: 'fixture', model: 'fixture', toolAllowlist: ['web_search'] }],
      bindings: [],
    });
    await client.rpc.request('session.ensure', { sessionId: 's-web', agentId: 'no-creds', revision: '1', ownerId: 'owner', cwd: home });
    const caps = await client.rpc.request('session.capabilities', { sessionId: 's-web' }) as { tools: string[]; prompt: { tools: { name: string }[] } };
    expect(caps.tools).toContain('web_search');
    expect(caps.prompt.tools.map(t => t.name)).toContain('web_search');
  } finally {
    await client?.shutdown();
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 25_000);
