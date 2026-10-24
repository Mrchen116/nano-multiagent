import { mkdtemp, mkdir, symlink, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { workspaceFileAllowed } from '../src/policy/cc-workspace.js';
import { approvalDefaults } from '../../product-contracts/src/approval.js';

it('limits workspace file exemption to ordinary lexical and real targets, including new paths', async () => {
  const root = await mkdtemp(join(tmpdir(), 'approval-paths-'));
  const cwd = join(root, '.nanoassistant/workspaces/agent');
  const policy = { ...approvalDefaults, rules: 'nano' as const, globalRoot: root };
  const allows = (file_path: string, name = 'write', overrides = {}) => workspaceFileAllowed(cwd, name, { file_path }, { ...policy, ...overrides });
  try {
    await mkdir(join(cwd, '.git'), { recursive: true });
    await mkdir(join(cwd, '.claude/worktrees/feature'), { recursive: true });
    await writeFile(join(root, 'outside.txt'), 'private');
    await symlink(root, join(cwd, 'outside'));
    await symlink(join(root, 'absent.txt'), join(cwd, 'dangling'));
    await symlink(join(cwd, '.git'), join(cwd, 'ordinary'));
    await symlink(cwd, join(root, 'workspace-alias'));
    expect(await allows('notes/new.txt')).toBe(true);
    expect(await allows('notes.md', 'edit')).toBe(true);
    expect(await allows(join(root, 'workspace-alias', 'notes.md'))).toBe(false);
    expect(await allows('../outside.txt')).toBe(false);
    expect(await allows('outside/new.txt')).toBe(false);
    expect(await allows('dangling')).toBe(false);
    expect(await allows('ordinary/config')).toBe(false);
    for (const path of ['.git/config', '.codex/config.toml', '.claude/settings.json', '.ripgreprc', '.zshrc.backup', 'sub/AGENTS.md', 'CLAUDE.md']) expect(await allows(path), path).toBe(false);
    expect(await allows('.claude/worktrees/feature/notes.md')).toBe(true);
    expect(await allows('.claude/worktrees/feature/.git/config')).toBe(false);
    expect(await allows('notes.md', 'bash')).toBe(false);
    expect(await allows('notes.md', 'write', { enabled: false })).toBe(false);
    expect(await allows('notes.md', 'write', { rules: 'dsh' })).toBe(false);
    expect(await allows('notes.md', 'write', { hardDeny: ['Never write notes'] })).toBe(false);
    expect(await allows('notes.md', 'write', { allow: ['$defaults'] })).toBe(true);
  } finally { await rm(root, { recursive: true, force: true }); }
});

it('runs workspace writes without judge calls but preserves downstream restrictions and outside review', async () => {
  const { prepareProfile, RuntimeClient } = await import('../lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'approval-workspace-runtime-'));
  const workspace = join(home, 'workspace');
  let client: InstanceType<typeof RuntimeClient> | undefined;
  const { readFile } = await import('node:fs/promises');
  try {
    await mkdir(workspace);
    await writeFile(join(home, 'protected.txt'), 'unchanged');
    await symlink(join(home, 'protected.txt'), join(workspace, 'looks-local.txt'));
    await writeFile(join(home, 'fixture.mjs'), `import {appendFile} from 'node:fs/promises';
export const name='workspace-approval-fixture'; export const inject=['llm','tools'];
export function apply(ctx) {
 const seen=new Set();
 ctx.on('tools/pre-execute',(exec,next)=>exec.name==='write'&&exec.arguments.file_path==='blocked.txt'?{kind:'deny',reason:'Host restriction'}:next());
 ctx.on('llm/stream',async function*(options) {
  if(options.system){await appendFile(process.env.DSH_HOME+'/reviews.jsonl','review\\n');yield{type:'block-end',index:0,block:{type:'text',text:'<block>yes</block><reason>outside fixture denied</reason>'}};yield{type:'finish',reason:{kind:'stop'}};return;}
  const user=options.messages.findLast(m=>m.role==='user'&&m.source?.kind==='user'&&'actorId'in m.source);
  if(!seen.has(user.id)){seen.add(user.id);yield{type:'block-end',index:0,block:{type:'tool-call',id:'write-'+user.id,name:'write',arguments:JSON.stringify({file_path:user.content[0].text,content:'proof'})}};yield{type:'finish',reason:{kind:'tool-calls'}};return;}
  yield{type:'block-end',index:0,block:{type:'text',text:'done'}};yield{type:'finish',reason:{kind:'stop'}};
 });
}`);
    await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'fixture' }] } } } }, { insert: [{ id: 'workspace-approval-fixture', name: join(home, 'fixture.mjs') }] }]);
    client = new RuntimeClient({ home, cwd: workspace, env: { NANO_TEST_KEY: 'fixture' } });
    await client.rpc.request('initialize', { protocol: 1, agents: [{ agentId: 'agent', revision: '1', provider: 'fixture', model: 'fixture', mode: 'global', toolAllowlist: ['write'], approval: { ...approvalDefaults, rules: 'nano', globalRoot: home } }], bindings: [] });
    await client.rpc.request('session.ensure', { sessionId: 'test', agentId: 'agent', revision: '1', ownerId: 'owner', cwd: workspace });
    for (const [id, path] of [['ordinary', 'proof.txt'], ['blocked', 'blocked.txt'], ['outside', join(home, 'outside.txt')], ['symlink', 'looks-local.txt']]) {
      await client.rpc.request('session.submit', { sessionId: 'test', inputId: id, mode: 'followup', content: [{ type: 'text', text: path }], source: { kind: 'human', actorId: 'owner', channel: 'test', messageId: id } });
      await expect.poll(async () => (await client!.rpc.request('session.lookup', { sessionId: 'test', inputId: id }) as { terminal?: unknown }).terminal).toBeTruthy();
    }
    expect(await readFile(join(workspace, 'proof.txt'), 'utf8')).toBe('proof');
    await expect(readFile(join(workspace, 'blocked.txt'))).rejects.toMatchObject({ code: 'ENOENT' });
    await expect(readFile(join(home, 'outside.txt'))).rejects.toMatchObject({ code: 'ENOENT' });
    expect(await readFile(join(home, 'protected.txt'), 'utf8')).toBe('unchanged');
    expect((await readFile(join(home, 'reviews.jsonl'), 'utf8')).trim().split('\n')).toHaveLength(4);
    const observed = await client.rpc.request('session.observe', { sessionId: 'test' }) as { approvals: { source: string }[] };
    expect(observed.approvals.filter(row => row.source === 'workspace_file')).toHaveLength(1);
  } finally { if (client) await client.shutdown(); await rm(home, { recursive: true, force: true }); }
}, 30_000);
