import { builtinSkillsRoot } from '@nano/personal-assistant';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { EvaluationHistory, EvaluationLimits } from '@nano/product-contracts';
import type { NanoEvaluationOptions } from '../../src/evaluation.js';

export const limits: EvaluationLimits = { timeoutMs: 45000, maxModelCalls: 100, maxOutputTokens: 2048 };
export const history: EvaluationHistory = { caseKey: 'synthetic-case', sessions: [
  { id: 'history-one', date: '2024/01/01', timestamp: Date.UTC(2024, 0, 1), turns: [
    { role: 'user', content: 'I live in Berlin. UNRELATED_HISTORY_ONLY ' + 'A long message. '.repeat(500) + 'LONG_MESSAGE_END' },
    { role: 'assistant', content: 'I noted your address.' },
  ] },
  { id: 'history-two', date: '2024/05/01', timestamp: Date.UTC(2024, 4, 1), turns: [
    { role: 'user', content: 'I moved to Paris.' }, { role: 'assistant', content: 'Your new city is Paris.' },
  ] },
] };

export async function fixtureOptions(root: string): Promise<NanoEvaluationOptions> {
  const path = join(root, 'fixture.mjs');
  await writeFile(path, `import { readdirSync } from 'node:fs';
export const name='memory-evaluation-fixture';
export const inject=['llm'];
export function apply(ctx){
  const steps=new Map();
  ctx.on('llm/stream',async function*(o){
    if(process.env.EVALUATION_HANG==='1'){await new Promise(resolve=>o.signal.addEventListener('abort',resolve,{once:true}));return;}
    const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);
    const all=JSON.stringify(o.messages);
    let call;
    if(String(o.sessionId).startsWith('dreaming-')){
      const plain=o.messages.map(m=>(m.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('')).join('\\n');
      const stage=plain.match(/Editable copy: (.+?)\\. Only edit/)[1];
      call=[['source_history',{action:'search',session_id:'history-one',query:'LONG_MESSAGE_END',limit:10}],
        ['notes',{action:'write',path:'progress.md',text:'EVALUATION_RECOVERY: review the supplied dialogue and current memory.'}],
        ['new_context',{}],['notes',{action:'read',path:'progress.md'}],
        ['history',{action:'list_windows'}],
        ['read',{file_path:stage+'/MEMORY.md'}],['read',{file_path:stage+'/knowledge/city.md'}],
        ['write',{file_path:stage+'/knowledge/city.md',content:'You live in Paris. Former city: Berlin.'}],
        ['write',{file_path:stage+'/MEMORY.md',content:'# Personal memory\\n\\n[Current city](knowledge/city.md)'}],
        ['finish',{}]
      ][n];
    }else{
      const memory=process.cwd()+'/.nanoassistant/memory';
      call=[['inbox',{action:'check'}],['inbox',{action:'read',target:'evaluation-question'}],
        ['read',{file_path:process.env.EVALUATION_ROOT+'/'+readdirSync(process.env.EVALUATION_ROOT).find(n=>n.startsWith('prepare-'))+'/runtime'}],
        ['glob',{path:memory,pattern:'../../../**/*'}],
        ['read',{file_path:memory+'/knowledge/city.md'}],
        ['send_message',{target:'evaluation-question',text:'You live in Paris.'}]
      ][n];
    }
    if(call){yield {type:'block-end',index:0,block:{type:'tool-call',id:'fixture-'+n,name:call[0],arguments:JSON.stringify(call[1])}};yield {type:'finish',reason:{kind:'tool-calls'}};}
    else{yield {type:'block-end',index:0,block:{type:'text',text:'Delivered the answer.'}};yield {type:'finish',reason:{kind:'stop'}};}
  });
}`);
  const forbidden = join(root, 'forbidden.txt'); await writeFile(forbidden, 'HISTORY_MUST_NOT_LEAK');
  return { id: 'deterministic-nano', root, builtinSkillsRoot, allowModelCalls: true, provider: 'fixture', model: 'test',
    environment: { NANO_TEST_KEY: 'fixture', EVALUATION_FORBIDDEN_PATH: forbidden, EVALUATION_ROOT: root },
    providerPatch: [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test' }] } } } },
      { insert: [{ id: 'evaluation-fixture', name: path }] }],
    knowledge: { dreaming: { maxInputTokens: 1000 } },
  };
}
