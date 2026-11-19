import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RuntimeClient } from '../src/client.js';
import { openCliWorker, type CliWorkerOptions } from '../src/local-workers/drivers.js';
import { cliEnvironmentRestoration, nativeCliEnvironment } from '../src/local-workers/cli-environment.js';

let cwd: string;
let cli: Awaited<ReturnType<typeof openCliWorker>> | undefined;
const onReport = vi.fn<CliWorkerOptions['onReport']>(async () => {});
const onEnd = vi.fn<CliWorkerOptions['onEnd']>(async () => {});
const mcp = { command: 'mcp-bridge', args: ['parent-socket'], env: {} };
async function fakeCli(runtime: 'codex' | 'claude', code: string, sessionId?: string) {
  const script =
    `#!${process.execPath}\n` +
    `
    const fs = require('node:fs');
    const emit = value => console.log(JSON.stringify(value));
    fs.writeFileSync('args', JSON.stringify(process.argv.slice(2)));
    require('node:readline').createInterface({input: process.stdin}).on('line', line => {
      const m = JSON.parse(line);
      fs.appendFileSync('frames', line+'\\n');
      ${code}
    });`;
  await writeFile(join(cwd, runtime), script, { mode: 0o755 });
  return (cli = await openCliWorker({
    runtime,
    cwd,
    instructions: 'Help the parent',
    mcp,
    onReport,
    onEnd,
    sessionId,
  }));
}
async function frames() {
  return (await readFile(join(cwd, 'frames'), 'utf8'))
    .trim()
    .split('\n')
    .map((line) => JSON.parse(line));
}
beforeEach(async () => {
  cwd = await mkdtemp(join(tmpdir(), 'nano-cli-protocol-'));
  vi.stubEnv('PATH', `${cwd}:${process.env.PATH}`);
  vi.clearAllMocks();
});
afterEach(async () => {
  await cli?.close();
  cli = undefined;
  vi.unstubAllEnvs();
  await rm(cwd, { recursive: true, force: true });
});

it('restores CLI settings shadowed by DSH and strips runtime-only keys', () => {
  vi.stubEnv('ANTHROPIC_BASE_URL', 'http://native');
  vi.stubEnv('OTHER_MODEL_TOKEN', undefined);
  vi.stubEnv('NANO_PROVIDER_41_KEY', 'router');
  const overrides = { ANTHROPIC_BASE_URL: 'http://router', OTHER_MODEL_TOKEN: 'router-only' };
  for (const [key, value] of Object.entries({ ...cliEnvironmentRestoration(overrides), ...overrides }))
    vi.stubEnv(key, value);
  const env = nativeCliEnvironment();
  expect(env.ANTHROPIC_BASE_URL).toBe('http://native');
  expect(env.OTHER_MODEL_TOKEN).toBeUndefined();
  expect(Object.keys(env).some((key) => key.startsWith('NANO_') || key.startsWith('DSH_'))).toBe(false);
});

it('passes the native CLI settings through the real DSH launch boundary', async () => {
  vi.stubEnv('ANTHROPIC_BASE_URL', 'http://cli.test');
  vi.stubEnv('ROUTER_ONLY_TOKEN', undefined);
  const preload = `import {writeFileSync} from 'node:fs';
    const original = JSON.parse(process.env.NANO_WORKER_ENV_ORIGINALS);
    writeFileSync('observed',JSON.stringify([process.env.ANTHROPIC_BASE_URL, original.ANTHROPIC_BASE_URL, original.ROUTER_ONLY_TOKEN]));
    process.exit(0);`;
  const runtime = new RuntimeClient({
    home: cwd,
    cwd,
    env: {
      NODE_OPTIONS: `--import=data:text/javascript;base64,${Buffer.from(preload).toString('base64')}`,
      ANTHROPIC_BASE_URL: 'http://router.test',
      ROUTER_ONLY_TOKEN: 'temporary',
    },
  });
  expect((await runtime.exited).code).toBe(0);
  expect(JSON.parse(await readFile(join(cwd, 'observed'), 'utf8'))).toEqual([
    'http://router.test',
    'http://cli.test',
    null,
  ]);
});

it('binds Codex review, steering and confirmed interruption to the original thread and turn', async () => {
  const worker = await fakeCli(
    'codex',
    `
    const answer = result => emit({id:m.id, result});
    const notify = (method,p) => emit({method, params:{threadId:'saved',turnId:'turn-1', ...p}});
    if(m.method==='initialize') answer({});
    if(m.method==='thread/resume') answer({thread:{id:'saved'}});
    if(m.method==='turn/start') {
      answer({turn:{id:'turn-1'}});
      emit({id:78,method:'item/commandExecution/requestApproval',params:{threadId:'saved',turnId:'turn-1',itemId:'tool',command:'ls',cwd:'/tmp',reason:'extra access'}});
      notify('item/autoApprovalReview/completed',{reviewId:'audit',review:{status:'denied',rationale:'outside original scope'},action:{type:'networkAccess',host:'local.test'}});
    }
    if(m.method==='turn/steer') answer({turnId:'turn-1'});
    if(m.method==='turn/interrupt') {answer({});setTimeout(()=>notify('turn/completed',{turn:{id:'turn-1',status:'interrupted'}}),30);}
  `,
    'saved',
  );
  await worker.send('Inspect');
  await expect.poll(() => onReport.mock.calls.length).toBe(2);
  await worker.send('Only inspect the listing');
  await worker.stop();
  const wire = await frames();
  const common = wire.find((f) => f.method === 'thread/resume').params;
  expect(common).toMatchObject({
    threadId: 'saved',
    sandbox: 'workspace-write',
    approvalPolicy: 'on-request',
    approvalsReviewer: 'auto_review',
    cwd,
  });
  expect(common.model).toBeUndefined();
  expect(common.modelProvider).toBeUndefined();
  expect(common.config['mcp_servers.nano-parent']).toMatchObject(mcp);
  expect(wire).toContainEqual({ id: 78, result: { decision: 'decline' } });
  expect(wire.find((f) => f.method === 'turn/steer').params).toMatchObject({
    expectedTurnId: 'turn-1',
    threadId: 'saved',
  });
  expect(onReport.mock.calls.map(([, text]) => text).join('\n')).toMatch(
    /extra access[\s\S]*outside original scope/,
  );
  expect(onEnd.mock.calls).toEqual([['turn-1', 'interrupted', 'Codex turn interrupted']]);
});

it('forwards a Claude control denial, native denial and final answer once while consuming a queued correction', async () => {
  const worker = await fakeCli(
    'claude',
    `
    if(m.type==='control_request') emit({type:'control_response',response:{subtype:'success',request_id:m.request_id,response:{}}});
    if(m.type==='user' && m.message.content==='first') {
      emit({type:'user',isReplay:true,uuid:m.uuid,session_id:'original'});
      emit({type:'control_request',request_id:'q',request:{subtype:'can_use_tool',tool_use_id:'one',tool_name:'Read',input:{file_path:'/work/a'},blocked_path:'/work/a',decision_reason:'outside workspace'}});
    }
    if(m.type==='user' && m.message.content==='amend') {
      emit({type:'result',session_id:'original',uuid:'r1',subtype:'success',result:'partial',permission_denials:[{tool_use_id:'one',tool_name:'Read',tool_input:{}}]});
      emit({type:'user',isReplay:true,uuid:m.uuid,session_id:'original'});
      emit({type:'result',session_id:'original',uuid:'r2',subtype:'success',result:'done',permission_denials:[{tool_use_id:'two',tool_name:'Write',tool_input:{path:'file',content:'private body'}}]});
    }
  `,
    'original',
  );
  await worker.send('first');
  await expect.poll(() => onReport.mock.calls.length).toBe(1);
  await worker.send('amend');
  await expect.poll(() => onEnd.mock.calls.length).toBe(1);
  expect(onEnd.mock.calls).toEqual([['r2', 'completed', 'done']]);
  expect(onReport.mock.calls.map(([id]) => id)).toEqual(['request:one', 'r1', 'request:two']);
  expect(onReport.mock.calls.at(-1)?.[1]).toContain('file');
  expect(onReport.mock.calls.at(-1)?.[1]).not.toContain('private body');
  const wire = await frames();
  expect(wire.some((f) => f.request?.subtype === 'set_permission_mode' && f.request.mode === 'auto')).toBe(
    true,
  );
  expect(wire.find((f) => f.type === 'control_response')).toMatchObject({
    response: { request_id: 'q', subtype: 'success', response: { behavior: 'deny' } },
  });
  expect(wire.filter((f) => f.type === 'user').map((f) => f.session_id)).toEqual(['original', 'original']);
  const args: string[] = JSON.parse(await readFile(join(cwd, 'args'), 'utf8'));
  expect(args[args.indexOf('--resume') + 1]).toBe('original');
  expect(args[args.indexOf('--permission-mode') + 1]).toBe('auto');
  expect(args).not.toContain('--model');
  expect(args).not.toContain('--strict-mcp-config');
});

it('confirms exit after Claude acknowledges interruption and blocks queued input', async () => {
  const worker = await fakeCli(
    'claude',
    `
    if(m.type==='control_request') emit({type:'control_response',response:{subtype:'success',request_id:m.request_id}});
  `,
  );
  await worker.send('work');
  await worker.stop();
  expect((await frames()).at(-1).request.subtype).toBe('interrupt');
  expect(onEnd.mock.calls).toHaveLength(1);
  expect(onEnd.mock.calls[0]?.[1]).toBe('interrupted');
  await expect(worker.send('late')).rejects.toThrow(/exited|closing/);
});

it('surfaces a native resume error without opening a replacement session', async () => {
  await expect(
    fakeCli(
      'codex',
      `
    if(m.method==='initialize') emit({id:m.id,result:{}});
    if(m.method==='thread/resume') emit({id:m.id,error:{message:'Original thread missing'}});
  `,
      'original',
    ),
  ).rejects.toThrow('Original thread missing');
  expect((await frames()).map((f) => f.method)).toEqual(['initialize', 'initialized', 'thread/resume']);
});
