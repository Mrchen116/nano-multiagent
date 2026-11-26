import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { approvalDefaults } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

// Both fixture CLIs wait until the parent has finished its dispatch turn.
const cli = String.raw`
const fs = require('node:fs');
const name = require('node:path').basename(process.argv[1]);
const emit = frame => process.stdout.write(JSON.stringify(frame)+'\n');
let prompt;
require('node:readline').createInterface({input:process.stdin}).on('line', line => {
  const m=JSON.parse(line);
  const reply = result => emit({jsonrpc:'2.0',id:m.id,result});
  if(m.method==='initialize') reply({protocolVersion:1,agentCapabilities:{}});
  if(m.method==='thread/start') reply({thread:{id:'cli-thread'}});
  if(m.method==='session/new') reply({sessionId:'cli-thread',modes:{availableModes:[{id:'auto'}]}});
  if(m.method==='session/set_mode') reply({});
  if(m.method==='turn/start' || m.method==='session/prompt') {
    prompt=m.id;
    if(name==='codex') reply({turn:{id:'turn1'}});
    const timer=setInterval(()=>{
      if(!fs.existsSync('release-'+name))return;
      clearInterval(timer);
      emit(name==='codex' ? {id:100,method:'item/commandExecution/requestApproval',
        params:{threadId:'cli-thread',turnId:'turn1',itemId:'cmd',command:'ls /review-target',cwd:process.cwd()}}
      : {jsonrpc:'2.0',id:100,method:'session/request_permission',params:{sessionId:'cli-thread',
        toolCall:{toolCallId:'tool1',name:'run_command',kind:'execute',rawInput:{CommandLine:'ls /review-target'}},
        options:[{optionId:'yes',kind:'allow_once'},{optionId:'no',kind:'reject_once'}]}});
    },10);
  }
  if(m.id===100 && m.result) {
    fs.writeFileSync('reply-'+name,JSON.stringify(m.result));
    if(name==='codex')emit({method:'turn/completed',params:{threadId:'cli-thread',turn:{id:'turn1',status:'completed'}}});
    else emit({jsonrpc:'2.0',id:prompt,result:{stopReason:'end_turn'}});
  }
});
`;

it('routes the live CLI request after the root moves to another chat and invalidates an AGY verdict on withdrawal', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-worker-approval-'));
  let client: RuntimeClient | undefined;
  let logs = '';
  const json = (name:string) => readFile(join(home,name),'utf8').then(JSON.parse).catch(()=>undefined);
  try {
    for (const name of ['codex','agy']) await writeFile(join(home,name), '#!'+process.execPath+'\n'+cli, {mode:0o755});
    vi.stubEnv('PATH',home+delimiter+process.env.PATH);
    await writeFile(join(home,'fixture.mjs'), String.raw`
import fs from 'node:fs';
import {setTimeout} from 'node:timers/promises';
export const name='worker-approval-fixture';
export const inject=['llm'];
export function apply(ctx) {
  const started = new Set();
  ctx.on('llm/stream',async function*(options) {
    const home=process.env.DSH_HOME;
    let text='done';
    if (options.model==='review') {
      const prompt=options.messages.at(-1).content[0].text;
      fs.appendFileSync(home+'/reviews',JSON.stringify({prompt,system:options.system})+'\n');
      while (!fs.existsSync(home+'/release-review')) await setTimeout(15,undefined,{signal:options.signal});
      text=fs.existsSync(home+'/deny-review') ? '<block>yes</block><reason>Forbidden by policy</reason>' : '<block>no</block>';
    } else {
      const input=options.messages.findLast(m=>m.role==='user' && (m.source?.kind==='user' || (m.source?.kind==='nano-system' && m.source.channel==='heartbeat')));
      if(input?.content.some(b=>b.text?.startsWith('Dispatch')) && !started.has(input.id)) {
        started.add(input.id);
        yield {type:'block-end',index:0,block:{type:'tool-call',id:'dispatch-'+input.id,name:'delegate_worker',
          arguments:JSON.stringify({action:'start',label:'Inspect directory',message:'Check the fixture directory'})}};
        yield {type:'finish',reason:{kind:'tool-calls'}};return;
      }
    }
    yield {type:'block-end',index:0,block:{type:'text',text}};
    yield {type:'finish',reason:{kind:'stop'}};
  });
}`);
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'openai-completions',
      baseURL:'http://127.0.0.1:9',apiKeyEnv:'NANO_TEST_KEY',models:[{id:'main'},{id:'review',contextWindow:100000}]}}}},
      {insert:[{id:'worker-approval-fixture',name:join(home,'fixture.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'},onLog:text=>{logs+=text;}});
    const runtime=client.rpc;
    registerNoopTaskHosts(client);
    const cards: {requestId:string;sessionId:string;reason:string;worker:{label:string;runtime:string;workerId:string}}[]=[];
    runtime.onNotification((method,data)=>{if(method==='approval.request') cards.push(data as typeof cards[number]);});
    await runtime.request('initialize',{protocol:1,bindings:[],agents:(['codex','antigravity'] as const).map(workerRuntime=>({
      agentId:workerRuntime,knowledge:{memoryMode:'legacy'},revision:'1',mode:'global',provider:'fixture',model:'main',workerRuntime,
      approval:{...approvalDefaults,globalRoot:home,rules:'nano',denyLimit:1,unattendedFallback:workerRuntime==='antigravity'?'allow':'deny',reviewer:{provider:'fixture',model:'review'}},
    }))});
    const submit=async (sessionId:string,inputId:string,channel:string,text:string)=>{
      await runtime.request('session.submit',{sessionId,inputId,mode:'followup',content:[{type:'text',text}],
        source:{kind:channel==='heartbeat'?'system':'human',actorId:channel==='heartbeat'?sessionId:'owner',channel,messageId:inputId}});
      await expect.poll(async()=>(await runtime.request('session.lookup',{sessionId,inputId})).terminal,{timeout:10000}).toBeTruthy();
    };
    for (const sessionId of ['codex','antigravity']) {
      await runtime.request('session.ensure',{sessionId,agentId:sessionId,ownerId:'owner',cwd:home,revision:'1'});
      await submit(sessionId,'launch-'+sessionId,'chat-A','Dispatch the original A-only task');
      await submit(sessionId,'other-'+sessionId,'chat-B','Unrelated instruction B');
      await writeFile(join(home,'release-'+(sessionId==='codex'?'codex':'agy')),'go');
      if (sessionId==='antigravity') {
        await expect.poll(()=>readFile(join(home,'reviews'),'utf8').catch(()=>''),{timeout:8000}).toContain('external_worker_action');
        const reviews=(await readFile(join(home,'reviews'),'utf8')).trim().split('\n').map(line=>JSON.parse(line));
        expect(reviews).toHaveLength(1);
        const pending=JSON.parse(reviews[0].prompt.split('\n').findLast((line:string)=>line.startsWith('{')));
        const evidence=JSON.stringify(pending.external_worker_action.delegation.humanEvidence);
        expect(evidence).toContain('chat-A');
        expect(evidence).not.toContain('chat-B');
        expect(reviews[0].prompt).toContain('Unrelated instruction B');
        await submit(sessionId,'withdraw','chat-A','Withdraw permission for the A task');
        await writeFile(join(home,'release-review'),'go');
      }
      await expect.poll(()=>cards.find(card=>card.sessionId===sessionId),{timeout:8000}).toBeTruthy();
      const card=cards.find(card=>card.sessionId===sessionId)!;
      expect(card.worker).toMatchObject({runtime:sessionId,label:'Inspect directory',workerId:expect.stringMatching(/^worker-/)});
      expect(card.reason).toContain('ls /review-target');
      const decision=sessionId==='codex'?'allowed-once':'rejected';
      await runtime.request('approval.answer',{requestId:card.requestId,decision});
      await expect(runtime.request('approval.answer',{requestId:card.requestId,decision})).rejects.toThrow(/no longer pending/);
      if(sessionId==='codex') {
        await expect.poll(()=>json('reply-codex')).toEqual({decision:'accept'});
        await expect(readFile(join(home,'reviews'),'utf8')).rejects.toMatchObject({code:'ENOENT'});
      } else await expect.poll(()=>json('reply-agy')).toMatchObject({outcome:{optionId:'no'}});
    }
    for (const [runtimeName, channel, reply, expected] of [
      ['codex','heartbeat','reply-codex',{decision:'decline'}],
      ['antigravity','chat-A','reply-agy',{outcome:{optionId:'yes'}}],
    ] as const) {
      await rm(join(home,reply));
      const sessionId=runtimeName+'-next';
      await runtime.request('session.ensure',{sessionId,agentId:runtimeName,ownerId:'owner',cwd:home,revision:'1'});
      await submit(sessionId,'launch-'+sessionId,channel,'Dispatch another directory check');
      await expect.poll(()=>json(reply)).toMatchObject(expected);
    }
    const reviewCount=async ()=>(await readFile(join(home,'reviews'),'utf8')).trim().split('\n').length;
    expect(await reviewCount()).toBe(2);
    for (const scenario of ['withdrawn','blocked']) {
      const sessionId='unattended-'+scenario;
      await rm(join(home,'reply-agy'));
      if (scenario==='withdrawn') await rm(join(home,'release-review'));
      else await writeFile(join(home,'deny-review'),'deny');
      await runtime.request('session.ensure',{sessionId,agentId:'antigravity',ownerId:'owner',cwd:home,revision:'1'});
      await submit(sessionId,'launch-'+scenario,'heartbeat','Dispatch a background check');
      if (scenario==='withdrawn') {
        await expect.poll(reviewCount).toBe(3);
        await submit(sessionId,'withdraw-'+scenario,'chat-A','Cancel authorization for this check');
        await writeFile(join(home,'release-review'),'go');
      }
      await expect.poll(()=>json('reply-agy')).toMatchObject({outcome:{optionId:'no'}});
    }
    expect(cards).toHaveLength(2);
  } catch(error) {
    const state=await client?.rpc.request('session.observe',{sessionId:'codex'}).catch(()=>undefined) as {events?:{type:string;data:unknown}[]}|undefined;
    throw new Error(String(error)+'\n'+JSON.stringify(state?.events?.filter(e=>['tool/result','tool/call','turn/end'].includes(e.type))).slice(-7000)+'\n'+logs,{cause:error});
  }
  finally {await writeFile(join(home,'release-review'),'go');await client?.shutdown();vi.unstubAllEnvs();await rm(home,{recursive:true,force:true});}
},45_000);
