import { mkdir, mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { homedir, tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { codexFileAllowed, workspaceFileAllowed } from '../src/policy/file-approval.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

const addPatch = (path: string, line = 'hello') =>
  `*** Begin Patch\n*** Add File: ${path}\n+${line}\n*** End Patch`;

const movePatch = (from: string, to: string, oldLine = 'before', newLine = 'after') =>
  `*** Begin Patch\n*** Update File: ${from}\n*** Move to: ${to}\n@@\n-${oldLine}\n+${newLine}\n*** End Patch`;

it('validates every apply_patch source path, moveTo target, and effectiveCwd against immutable workspaceRoot', async () => {
  // Place outside tmpdir() because Codex Auto intentionally admits system temp roots.
  const root = await mkdtemp(join(homedir(), '.nano-apply-patch-approval-'));
  const cwd = join(root, 'workspace');
  const sub = join(cwd, 'packages', 'sub');
  const ccPolicy = { ...approvalDefaults, rules: 'nano' as const, globalRoot: root };
  const codexPolicy = { ...approvalDefaults, rules: 'codex' as const, globalRoot: root };
  try {
    await mkdir(join(cwd, '.git'), { recursive: true });
    await mkdir(sub, { recursive: true });
    await writeFile(join(cwd, 'src.txt'), 'before\n');
    await writeFile(join(root, 'outside.txt'), 'secret\n');
    await symlink(root, join(cwd, 'escape-dir'));

    for (const [fn, policy] of [[workspaceFileAllowed, ccPolicy], [codexFileAllowed, codexPolicy]] as const) {
      expect(await fn(cwd, 'apply_patch', { input: addPatch('notes/todo.txt') }, policy)).toBe(true);
      expect(await fn(cwd, 'apply_patch', { input: movePatch('src.txt', 'renamed/dst.txt') }, policy)).toBe(true);
      // moveTo escaping workspace or targeting protected paths must be rejected.
      expect(await fn(cwd, 'apply_patch', { input: movePatch('src.txt', '../outside-dst.txt') }, policy)).toBe(false);
      expect(await fn(cwd, 'apply_patch', { input: movePatch('src.txt', 'AGENTS.md') }, policy)).toBe(false);
      expect(await fn(cwd, 'apply_patch', { input: movePatch('src.txt', '.git/config') }, policy)).toBe(false);
      expect(await fn(cwd, 'apply_patch', { input: movePatch('src.txt', '.nanoassistant/config.json') }, policy)).toBe(false);
      expect(await fn(cwd, 'apply_patch', { input: movePatch('src.txt', 'escape-dir/pwned.txt') }, policy)).toBe(false);
      // Malformed, empty, or sandbox-escalated patches fall through to review.
      expect(await fn(cwd, 'apply_patch', { input: '' }, policy)).toBe(false);
      expect(await fn(cwd, 'apply_patch', { input: '*** Begin Patch\nNOT A VALID HEADER\n*** End Patch' }, policy)).toBe(false);
      expect(await fn(cwd, 'apply_patch', { input: addPatch('ok.txt'), sandbox_permissions: 'require_escalated' }, policy)).toBe(false);
    }

    // Relative paths resolve against effectiveCwd while workspaceRoot stays immutable.
    const subLocation = { workspaceRoot: cwd, effectiveCwd: sub };
    expect(await workspaceFileAllowed(subLocation, 'apply_patch', { input: addPatch('../sibling.txt') }, ccPolicy)).toBe(true);
    expect(await workspaceFileAllowed(subLocation, 'apply_patch', { input: addPatch('../../../escaped.txt') }, ccPolicy)).toBe(false);
    expect(await codexFileAllowed(subLocation, 'apply_patch', { input: addPatch('nested.txt') }, codexPolicy)).toBe(true);
    expect(await codexFileAllowed({ workspaceRoot: cwd, effectiveCwd: root }, 'apply_patch', { input: addPatch('outside-via-cwd.txt') }, codexPolicy)).toBe(false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

it('exposes apply_patch by default without widening explicit allowlists or exposing working_directory / AgentTeam / subagent_oar', async () => {
  const home = await mkdtemp(join(tmpdir(), 'apply-patch-runtime-'));
  const workspace = join(home, 'workspace');
  const workspaceExplicit = join(home, 'workspace-explicit');
  let client: RuntimeClient | undefined;
  let logs = '';
  try {
    await mkdir(workspace, { recursive: true });
    await mkdir(workspaceExplicit, { recursive: true });
    await writeFile(join(workspace, 'draft.txt'), 'before\n');
    await writeFile(join(home, 'fixture.mjs'), `import { appendFile } from 'node:fs/promises';
export const name = 'patch-runtime-fixture';
export const inject = ['llm'];
export function apply(ctx) {
  const readDone = new Set();
  const seen = new Set();
  ctx.on('llm/stream', async function*(options) {
    if (options.model === 'reviewer') {
      await appendFile(process.env.DSH_HOME + '/reviews.jsonl', JSON.stringify(options.messages) + '\\n');
      yield { type: 'block-end', index: 0, block: { type: 'text', text: JSON.stringify({ outcome: 'deny', risk_level: 'high', rationale: 'Protected move target' }) } };
      yield { type: 'finish', reason: { kind: 'stop' } };
      return;
    }
    const user = options.messages.findLast(m => m.role === 'user' && m.source?.kind === 'user' && 'actorId' in m.source);
    const patch = user?.content.find(b => b.type === 'text')?.text ?? '';
    if (user && user.id === 'safe-move' && !readDone.has(user.id)) {
      readDone.add(user.id);
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'read-' + user.id, name: 'read', arguments: JSON.stringify({ file_path: 'draft.txt' }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    if (user && !seen.has(user.id)) {
      seen.add(user.id);
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'patch-' + user.id, name: 'apply_patch', arguments: JSON.stringify({ input: patch }) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
      return;
    }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'done' } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  });
}`);
    await prepareProfile(home, [
      { id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'main' }, { id: 'reviewer' }] } } } },
      { insert: [{ id: 'patch-runtime-fixture', name: join(home, 'fixture.mjs') }] },
    ]);
    client = new RuntimeClient({ home, cwd: workspace, env: { NANO_TEST_KEY: 'fixture' }, onLog: text => { logs += text; } });
    registerNoopTaskHosts(client);
    const workspaceDoc = join(home, 'workspace-doc');
    await mkdir(workspaceDoc, { recursive: true });
    await writeFile(join(workspaceDoc, 'note.txt'), 'draft\n');
    await client.rpc.request('initialize', {
      protocol: 1,
      agents: [
        { agentId: 'default-agent', revision: '1', workspace, provider: 'fixture', model: 'main', approval: { ...approvalDefaults, rules: 'codex', globalRoot: home, reviewer: { provider: 'fixture', model: 'reviewer' } } },
        { agentId: 'explicit-agent', revision: '1', workspace: workspaceExplicit, provider: 'fixture', model: 'main', toolAllowlist: ['read'] },
        { agentId: 'doc-agent', revision: '1', workspace: workspaceDoc, provider: 'fixture', model: 'main', knowledge: { enabled: true, memoryMode: 'document' }, approval: { ...approvalDefaults, dangerouslySkipPermissions: true, globalRoot: home } },
      ],
      bindings: [
        { sessionId: 's-doc', agentId: 'doc-agent', revision: '1', ownerId: 'owner', cwd: workspaceDoc },
      ],
    });
    await client.rpc.request('session.ensure', { sessionId: 's-default', agentId: 'default-agent', revision: '1', ownerId: 'owner', cwd: workspace });
    await client.rpc.request('session.ensure', { sessionId: 's-explicit', agentId: 'explicit-agent', revision: '1', ownerId: 'owner', cwd: workspaceExplicit });

    const catalog = await client.rpc.request('configuration.catalog', { agentId: 'default-agent', cwd: workspace }) as { tools: { name: string; default_enabled?: boolean }[] };
    const catalogNames = catalog.tools.map(t => t.name);
    expect(catalogNames).toContain('apply_patch');
    for (const forbidden of ['working_directory', 'subagent_oar', 'team_task_create', 'team_task_list', 'team_task_update']) {
      expect(catalogNames).not.toContain(forbidden);
    }

    const defaultCaps = await client.rpc.request('session.capabilities', { sessionId: 's-default' }) as { tools: string[] };
    expect(defaultCaps.tools).toContain('apply_patch');
    expect(defaultCaps.tools).not.toContain('working_directory');

    const explicitCaps = await client.rpc.request('session.capabilities', { sessionId: 's-explicit' }) as { tools: string[] };
    expect(explicitCaps.tools).not.toContain('apply_patch');

    const submit = async (id: string, patch: string) => {
      await client!.rpc.request('session.submit', {
        sessionId: 's-default',
        inputId: id,
        mode: 'followup',
        content: [{ type: 'text', text: patch }],
        source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id },
      });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 's-default', inputId: id }) as { terminal?: unknown }).terminal).toBeTruthy();
    };

    await submit('safe-move', movePatch('draft.txt', 'moved/final.txt'));
    expect(await readFile(join(workspace, 'moved/final.txt'), 'utf8')).toBe('after\n');
    await expect(readFile(join(home, 'reviews.jsonl'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });

    await submit('protected-move', movePatch('moved/final.txt', 'AGENTS.md', 'after', 'hijack'));
    await expect(readFile(join(workspace, 'AGENTS.md'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
    expect((await readFile(join(home, 'reviews.jsonl'), 'utf8')).trim().split('\n')).toHaveLength(1);

    // DocumentMemory enforces Dreaming-only formal memory writes on apply_patch even under dangerouslySkipPermissions.
    await client.rpc.request('session.ensure', { sessionId: 's-doc', agentId: 'doc-agent', revision: '1', ownerId: 'owner', cwd: workspaceDoc });
    for (const [id, patch] of [
      ['mem-add', addPatch('.nanoassistant/memory/MEMORY.md', 'forged')],
      ['mem-move', movePatch('note.txt', '.nanoassistant/memory/pwn.md', 'draft', 'forged')],
    ] as const) {
      await client.rpc.request('session.submit', {
        sessionId: 's-doc',
        inputId: id,
        mode: 'followup',
        content: [{ type: 'text', text: patch }],
        source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id },
      });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 's-doc', inputId: id }) as { terminal?: unknown }).terminal).toBeTruthy();
    }
    const docObs = await client.rpc.request('session.observe', { sessionId: 's-doc' }) as { events: { type: string; data: any }[] };
    const patchErrors = docObs.events.filter(e => e.type === 'tool/result' && e.data.message.isError);
    expect(patchErrors.length).toBeGreaterThanOrEqual(2);
    expect(JSON.stringify(patchErrors)).toContain('Only Dreaming may update formal memory');
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    await client?.shutdown();
    await rm(home, { recursive: true, force: true });
  }
}, 30_000);
