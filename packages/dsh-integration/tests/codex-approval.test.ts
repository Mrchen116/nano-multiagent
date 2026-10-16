import { expect, it } from 'vitest';
import { mkdtemp, writeFile, rm, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseCodexDecision, reviewInput, tokenCost, codexPolicy } from '../src/policy/codex-context.js';
import { inspectionTools } from '../src/policy/codex-inspection.js';

it('requires a complete Guardian verdict and never accepts critical allow', () => {
  expect(parseCodexDecision('{"outcome":"allow","risk_level":"high","user_authorization":"high","rationale":"Authorized narrow update"}')).toMatchObject({behavior:'allow',risk:'high',authorization:'high'});
  for (const value of ['{}','{"outcome":"allow"}','{"outcome":"allow","risk_level":"critical","user_authorization":"high","rationale":"yes"}','{"outcome":"allow","risk_level":"high","user_authorization":"unknown","rationale":"yes"}']) expect(parseCodexDecision(value)).toBeUndefined();
});

it('budgets evidence with authorization priority and never truncates the pending action', () => {
  const rows = [{user:'human permits only one target',origin:{kind:'human'}}, ...Array.from({length:60},(_,i)=>({tool_result:'untrusted '+i+'x'.repeat(10000)}))];
  const input = reviewInput(rows,{tool:'write',arguments:{path:'/outside/x',text:'complete action'}},2000);
  expect(tokenCost(input)).toBeLessThanOrEqual(2000);
  expect(input).toContain('human permits only one target');
  expect(input).toContain('guardian_truncated');
  expect(input).toContain('complete action');
  expect(()=>reviewInput(rows,{arguments:'x'.repeat(50000)},200)).toThrow(/action|budget/i);
  const authorization='Explicit authorization '.repeat(2500);
  expect(reviewInput([{user:authorization,origin:{kind:'user-approval'}}],{},30000)).toContain(authorization);
});

it('assembles pinned policy with actual restrictions and source provenance', async () => {
  const policy = await codexPolicy({allow:['custom allow'],hardDeny:['never delete'],softDeny:[],environment:[]} as any);
  expect(policy).toContain('custom allow');expect(policy).toContain('never delete');
  expect(policy).toContain('observation=restored');
  expect(policy).not.toContain('The coding-agent is running in a sandbox');
});

it('bounds read-only inspection and rejects non-regular files even through symlinks', async () => {
  const cwd = await mkdtemp(join(tmpdir(),'guardian-inspect-'));
  try {
    await writeFile(join(cwd,'a'),'hello');await symlink('/dev/zero',join(cwd,'device'));
    const tools = inspectionTools(cwd,()=>new AbortController().signal);
    const run = (name:string,args:unknown)=>tools.find(t=>t.name===name)!.execute(args,{signal:new AbortController().signal} as any);
    expect(await run('guardian_read',{path:'a'})).toMatchObject({text:'hello',truncated:false});
    await expect(run('guardian_read',{path:'device'})).rejects.toThrow(/regular/);
    expect(await run('guardian_list',{path:'.'})).toMatchObject({entries:expect.arrayContaining(['a','device'])});
    const abort=new AbortController();abort.abort();
    await expect(tools[0]!.execute({path:'a'},{signal:abort.signal} as any)).rejects.toThrow();
  } finally { await rm(cwd,{recursive:true,force:true}); }
});
