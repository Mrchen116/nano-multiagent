import { builtinSkillsRoot } from '@nano/personal-assistant';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { EvaluationHistory, EvaluationLimits } from '@nano/product-contracts';
import type { NanoEvaluationOptions } from '../../src/evaluation.js';
import { createNanoProduct } from '../../../../evals/memory/nano-product.js';

export const limits: EvaluationLimits = { timeoutMs: 45000, maxModelCalls: 100, maxOutputTokens: 2048 };
export const history: EvaluationHistory = { caseKey: 'synthetic-case', sessions: [
  { id: 'history-one', date: '2024/01/01', timestamp: Date.UTC(2024, 0, 1), turns: [
    { role: 'user', content: 'I live in Berlin. UNRELATED_HISTORY_ONLY ' + 'A long message. '.repeat(500) + 'LONG_MESSAGE_END' },
    { role: 'assistant', content: 'I noted your address.' },
  ] },
  { id: 'history-two', date: '2024/01/02 01:00', timestamp: Date.UTC(2024, 0, 2, 1), turns: [
    { role: 'user', content: 'I moved to Paris.' }, { role: 'assistant', content: 'Your new city is Paris.' },
  ] },
  { id: 'history-three', date: '2024/01/03 01:00', timestamp: Date.UTC(2024, 0, 3, 1), turns: [
    { role: 'user', content: 'I moved to Rome. UNTRIGGERED_LAST_UPDATE' },
  ] },
  { id: 'history-four', date: '2024/01/03 01:00', timestamp: Date.UTC(2024, 0, 3, 1), turns: [
    { role: 'user', content: 'UNTRIGGERED_SAME_TIME: preserve the order of these messages.' },
  ] },
] };

export async function fixtureOptions(root: string): Promise<NanoEvaluationOptions> {
  const path = join(root, 'fixture.mjs');
  await writeFile(path, `import { readdirSync, writeFileSync } from 'node:fs';
export const name='memory-evaluation-fixture';
export const inject=['llm','sessionPersistence'];
export function apply(ctx){
  const steps=new Map(),cities=new Map(),targets=new Map();
  const open=ctx.sessionPersistence.open.bind(ctx.sessionPersistence);
  ctx.sessionPersistence.open=async(...args)=>{
    const h=await open(...args);
    if(args[1]==='write'&&!String(args[0]).startsWith('dreaming-')){
      const close=h.close.bind(h);let closed=false;
      h.close=async()=>{if(closed)return;closed=true;const {events}=await h.read();
        writeFileSync(process.env.EVALUATION_ROOT+'/imported-root.json',JSON.stringify({header:h.header,events}));await close();};
    }
    return h;
  };
  ctx.on('llm/stream',async function*(o){
    if(process.env.EVALUATION_HANG==='1'){await new Promise(resolve=>o.signal.addEventListener('abort',resolve,{once:true}));return;}
    const n=steps.get(o.sessionId)||0;steps.set(o.sessionId,n+1);
    const all=JSON.stringify(o.messages);
    let call;
    if(String(o.sessionId).startsWith('dreaming-')){
      const plain=o.messages.map(m=>(m.content||[]).filter(b=>b.type==='text').map(b=>b.text).join('')).join('\\n');
      const stage=plain.match(/Editable copy: (.+?)\\. Only edit/)[1];
      if(all.includes('I moved to Paris.'))cities.set(o.sessionId,'Paris');
      else if(!cities.has(o.sessionId)&&all.includes('I live in Berlin.'))cities.set(o.sessionId,'Berlin');
      else if(!cities.has(o.sessionId)){const known=all.match(/You live in (Berlin|Paris)\\./);if(known)cities.set(o.sessionId,known[1]);}
      const chat=JSON.parse(plain.match(/IM source directory \\(data\\): (\\[[^\\n]*\\])/)[1])[0];
      const source=JSON.parse(plain.match(/Source directory \\(data\\): (\\[[^\\n]*\\])/)[1])[0].session_id;
      const found=o.messages.findLast(m=>m.role==='tool'&&m.toolCallId==='fixture-1');
      const item=found&&!found.isError?JSON.parse(found.content[0].text).items[0]:undefined;
      call=[['source_history',{action:'list_windows',session_id:source}],
        ['source_history',{action:'search',session_id:source,query:'LONG_MESSAGE_END',limit:10,max_chars_per_item:4000}],
        item?['source_history',{action:'read',session_id:source,window_id:item.window_id,item_id:item.item_id,limit_chars:20000}]:['source_history',{action:'list_windows',session_id:source}],
        ['notes',{action:'write',path:'progress.md',text:'EVALUATION_RECOVERY: review the supplied dialogue and current memory.'}],
        ['new_context',{}],['notes',{action:'read',path:'progress.md'}],
        ['history',{action:'list_windows'}],
        ['read',{file_path:stage+'/MEMORY.md'}],['read',{file_path:stage+'/knowledge/city.md'}],
        cities.has(o.sessionId)?['write',{file_path:stage+'/knowledge/city.md',content:'You live in '+cities.get(o.sessionId)+'. Former city: Berlin.'}]:undefined,
        cities.has(o.sessionId)?['write',{file_path:stage+'/MEMORY.md',content:'# Personal memory\\n\\n[Current city: '+cities.get(o.sessionId)+'](knowledge/city.md)'}]:undefined,
        ['conversations',{action:'search',target:chat,query:'LONG_MESSAGE_END'}],
        ['conversations',{action:'search',target:chat,query:'UNTRIGGERED_LAST_UPDATE'}]
      ][n];
    }else if(process.env.EVALUATION_CHAT_ONLY){
      const result=id=>{const m=o.messages.findLast(m=>m.role==='tool'&&m.toolCallId===id);return m&&!m.isError?JSON.parse(m.content[0].text):undefined;};
      const checked=result('fixture-0');if(checked)targets.set(o.sessionId,checked.sources[0]?.target);
      const target=targets.get(o.sessionId),first=result('fixture-2'),second=result('fixture-3');
      const text=[...(first?.messages||[]),...(second?.messages||[])].map(m=>m.content[0].text).join('\\n');
      call=[['inbox',{action:'check'}],['inbox',{action:'read',target}],
        ['conversations',{action:'search',target,query:'CASE_MARKER',limit:1}],
        ['conversations',{action:'search',target,query:'CASE_MARKER',limit:1,cursor:first?.next_cursor}],
        ['send_message',{target,text}]][n];
    }else if(process.env.EVALUATION_DELEGATE_ROOT&&o.sessionId!==process.env.EVALUATION_DELEGATE_ROOT){
      if(n===0)call=['read',{file_path:process.cwd()+'/.nanoassistant/memory/knowledge/city.md'}];
      if(n===1){
        await new Promise(resolve=>setTimeout(resolve,1200));
        call=['send_message',{agent_id:process.env.EVALUATION_DELEGATE_ROOT,message:'DELEGATED_RESULT: '+all.match(/You live in (?:Berlin|Paris|Rome)\\./)?.at(-1)}];
      }
    }else{
      const memory=process.cwd()+'/.nanoassistant/memory';
      const checked=o.messages.findLast(m=>m.role==='tool'&&m.toolCallId==='fixture-0');
      if(checked&&!checked.isError)targets.set(o.sessionId,JSON.parse(checked.content[0].text).sources[0]?.target);
      const target=targets.get(o.sessionId);
      const city=all.match(/You live in (?:Berlin|Paris|Rome)\\./g)?.at(-1)||'I do not know your city.';
      call=[['inbox',{action:'check'}],['inbox',{action:'read',target}],
        ['read',{file_path:process.env.EVALUATION_ROOT+'/'+readdirSync(process.env.EVALUATION_ROOT).find(n=>n.startsWith('prepare-'))+'/runtime'}],
        ['glob',{path:memory,pattern:'../../../**/*'}],
        ['read',{file_path:memory+'/knowledge/city.md'}],
        ['skill',{name:'nano-memory'}],['conversations',{action:'info',target}],
        ['notes',{action:'write',path:'reply.md',text:'ANSWER_RECOVERY: '+city+' Reply in '+target}],
        ['new_context',{}],['notes',{action:'read',path:'reply.md'}],
        ['history',{action:'list_windows'}],['history',{action:'search',query:'UNRELATED_HISTORY_ONLY'}],
        ['inbox',{action:'check'}],['conversations',{action:'read',target}],
        process.env.EVALUATION_DELEGATE_ROOT?['subagent',{description:'Read the saved city',prompt:'Read memory/knowledge/city.md and report the city to your parent.'}]:['send_message',{target,text:city}],
        undefined,['send_message',{target,text:city}]
      ][n];
    }
    if(call){yield {type:'block-end',index:0,block:{type:'tool-call',id:'fixture-'+n,name:call[0],arguments:JSON.stringify(call[1])}};yield {type:'finish',reason:{kind:'tool-calls'}};}
    else{yield {type:'block-end',index:0,block:{type:'text',text:'Delivered the answer.'}};yield {type:'finish',reason:{kind:'stop'}};}
  });
}`);
  const forbidden = join(root, 'forbidden.txt'); await writeFile(forbidden, 'HISTORY_MUST_NOT_LEAK');
  return { id: 'deterministic-nano', root, builtinSkillsRoot, createProduct: createNanoProduct, allowModelCalls: true, provider: 'fixture', model: 'test',
    environment: { NANO_TEST_KEY: 'fixture', EVALUATION_FORBIDDEN_PATH: forbidden, EVALUATION_ROOT: root },
    providerPatch: [{ id: 'llm-pi-ai', config: { providers: { fixture: { api: 'openai-completions', baseURL: 'http://127.0.0.1:9', apiKeyEnv: 'NANO_TEST_KEY', models: [{ id: 'test' }] } } } },
      { insert: [{ id: 'evaluation-fixture', name: path }] }],
    knowledge: { dreaming: { maxInputTokens: 1000 } },
  };
}
