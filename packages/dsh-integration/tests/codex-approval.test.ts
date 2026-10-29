import { expect, it } from 'vitest';
import { parseCodexDecision, reviewInput, tokenCost, codexPolicy } from '../src/policy/codex-context.js';
import { inspectionTools } from '../src/policy/codex-inspection.js';
import { parsePersonalDecision } from '../src/personal-security.js';

it('retains full private evidence for disclosure and marks only actual budget recovery', () => {
  const privateBody='start '+'x'.repeat(10000)+' MIDDLE_PRIVATE_CONSTRAINT '+'y'.repeat(10000)+' end';
  const rows=[{context:'PRIVATE_MEMORY',origin:{kind:'runtime-context'}},{tool_result:privateBody,tool:'conversations',trust:'untrusted-evidence'}];
  const action={recipient_ids:['peer'],payload:{content:'Complete public reply'}};
  const complete=reviewInput(rows,action,40000,true,true);
  expect(complete).toContain(privateBody);expect(complete).toContain('PRIVATE_MEMORY');
  expect(complete).not.toContain('guardian_truncated');
  const recovered=reviewInput(rows,action,1500,true,true);
  expect(recovered).toContain('guardian_truncated');expect(recovered).toContain(JSON.stringify(action));
  expect(tokenCost(recovered)).toBeLessThanOrEqual(1500);
  expect(()=>reviewInput(rows,action,1500,false,true)).toThrow(/rebuild/);
  expect(()=>reviewInput(rows,{payload:'x'.repeat(20000)},1500,true,true)).toThrow(/complete pending action/);
});

it('requires a specific PA verdict instead of coding-tool allow defaults', () => {
  for(const raw of ['{"outcome":"allow"}','{"decision":"allow"}','{"decision":"allow","reason":" "}','null','preface {"decision":"allow","reason":"ok"}'])expect(parsePersonalDecision(raw)).toBeUndefined();
  for(const decision of ['allow','deny','needs_owner','unavailable'])expect(parsePersonalDecision(JSON.stringify({decision,reason:'specific evidence'}))).toEqual({decision,reason:'specific evidence'});
});

it('uses the pinned Guardian verdict defaults and accepts a JSON answer inside prose', () => {
  expect(parseCodexDecision('{"outcome":"allow"}')).toEqual({behavior:'allow',risk:'low',authorization:'unknown',reason:'Auto-review returned a low-risk allow decision.'});
  expect(parseCodexDecision('{"outcome":"deny"}')).toEqual({behavior:'deny',risk:'high',authorization:'unknown',reason:'Auto-review returned a deny decision without a rationale.'});
  expect(parseCodexDecision('preface {"outcome":"allow","risk_level":"medium","rationale":"ok"} suffix')).toMatchObject({behavior:'allow',risk:'medium',reason:'ok'});
  expect(parseCodexDecision('{"outcome":"allow","risk_level":"high","user_authorization":"high","rationale":"Authorized narrow update"}')).toMatchObject({behavior:'allow',risk:'high',authorization:'high'});
  for (const value of ['{}','{"outcome":"maybe"}','{"outcome":"allow","risk_level":"unrecognised"}','{"outcome":"allow","rationale":3}']) expect(parseCodexDecision(value)).toBeUndefined();
});

it('budgets evidence with authorization priority and never truncates the pending action', () => {
  const rows = [{user:'human permits only one target',origin:{kind:'human'}}, ...Array.from({length:60},(_,i)=>({tool_result:'untrusted '+i+'x'.repeat(10000)}))];
  const input = reviewInput(rows,{tool:'write',arguments:{path:'/outside/x',text:'complete action'}},8000);
  expect(tokenCost(input)).toBeLessThanOrEqual(8000);
  expect(input).toContain('human permits only one target');
  expect(input).toContain('guardian_truncated');
  expect(input).toContain('complete action');
  expect(()=>reviewInput(rows,{arguments:'x'.repeat(50000)},200)).toThrow(/action|budget/i);
  const authorization='Explicit authorization '.repeat(2500);
  expect(reviewInput([{user:authorization,origin:{kind:'user-approval'}}],{},30000)).toContain(authorization);
});

it('charges user history to the message allowance and keeps required recent tool evidence', () => {
  const permission={user:'authorization '.repeat(7000),origin:{kind:'human'}};
  const input=reviewInput([permission,{assistant:'OLDER_ASSISTANT'},...Array.from({length:6},(_,i)=>({tool_result:`TOOL_${i} `+'x'.repeat(5000)}))],{},40000);
  expect(input).toContain(permission.user);
  expect(input).not.toContain('OLDER_ASSISTANT');
  for(let i=1;i<6;i++)expect(input).toContain(`TOOL_${i}`);
  expect(()=>reviewInput(Array.from({length:5},(_,i)=>({tool_result:`REQUIRED_${i} `+'x'.repeat(5000)})),{},2000)).toThrow(/budget/i);
});

it('shortens older historical bodies only during recovery, retaining provenance and both ends', () => {
  const rows=[{user:'OLD_START '+'x'.repeat(20000)+' OLD_END',origin:{kind:'human',messageId:'original'}},{user:'NEW_RESTRICTION',origin:{kind:'human'}}];
  expect(()=>reviewInput(rows,{},700,false)).toThrow(/budget/i);
  const input=reviewInput(rows,{},700);
  expect(input).toContain('OLD_START');expect(input).toContain('OLD_END');expect(input).toContain('NEW_RESTRICTION');
  expect(input).toContain('"messageId":"original"');expect(input).toContain('guardian_truncated');
  expect(tokenCost(input)).toBeLessThanOrEqual(700);
});

it('drops oversized optional evidence before evicting smaller older evidence', () => {
  const rows=[{tool_result:'OLDER_SMALL'}, {tool_result:'DOOMED_LARGE '+'x'.repeat(10000)},
    ...Array.from({length:5},(_,i)=>({tool_result:`RECENT_${i}`}))];
  const input=reviewInput(rows,{},500);
  expect(input).toContain('OLDER_SMALL');expect(input).not.toContain('DOOMED_LARGE');
  for(let i=0;i<5;i++)expect(input).toContain(`RECENT_${i}`);
  expect(()=>reviewInput([{assistant:'PROTECTED '+'x'.repeat(10000)}],{},500)).toThrow(/budget/i);
});

it('assembles pinned policy with actual restrictions and source provenance', async () => {
  const policy = await codexPolicy({allow:['custom allow'],hardDeny:['never delete'],softDeny:[],environment:[]} as any);
  expect(policy).toContain('custom allow');expect(policy).toContain('never delete');
  expect(policy).toContain('observation=restored');
  expect(policy).not.toContain('The coding-agent is running in a sandbox');
});

it('captures native inspection definitions outside workspace overlays', () => {
  const names=['read','read_image','glob','grep'];
  const native=names.map(name=>({name,parameters:{type:'object'},execute:async()=>name}));
  const scopes:unknown[]=[];
  const tools=inspectionTools({tools:{get:(name:string,scope?:unknown)=>{scopes.push(scope);return native.find(tool=>tool.name===name);}}} as any);
  expect(tools).toEqual(native);expect(scopes).toEqual([undefined,undefined,undefined,undefined]);
  expect(()=>inspectionTools({tools:{get:()=>undefined}} as any)).toThrow(/unavailable/);
});
