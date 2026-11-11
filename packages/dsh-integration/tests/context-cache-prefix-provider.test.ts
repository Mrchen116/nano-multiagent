import {createServer} from 'node:http';
import {mkdtemp, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect, it} from 'vitest';
import {prepareProfile, RuntimeClient} from '../lib/client.js';
import {registerNoopTaskHosts} from './helpers/noop-task-hosts.js';

const png = 'iVBORw0KGgoAAAANSUhEUgAAAKAAAABaCAIAAACwpMoFAAABNklEQVR4nO3ZwQmAMBQFwVRjY5ZtB9qD2ILkILgZ+PdJ2OMb235N33He08f9xh2rfXg1V+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrvjj4/mvj+B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx37cFxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx117cNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBx1x4cdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNy1B8ddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdx+RTJHLcoVInQAAAABJRU5ErkJggg==';

function content(message: any): any[] {
  return typeof message.content === 'string' ? [{type:'text', text:message.content}] : message.content;
}

function withoutCacheHint(blocks: any[]) {
  return blocks.map(({cache_control: _hint, ...block}) => block);
}

function expectPrefix(before: any, after: any) {
  expect(after.model).toBe(before.model);
  expect(JSON.stringify(withoutCacheHint(after.tools))).toBe(JSON.stringify(withoutCacheHint(before.tools)));
  expect(JSON.stringify(withoutCacheHint(after.system))).toBe(JSON.stringify(withoutCacheHint(before.system)));
  const normalize = (messages: any[]) => messages.map(message => ({
    ...message, content:withoutCacheHint(content(message)),
  }));
  expect(JSON.stringify(normalize(after.messages.slice(0,before.messages.length))))
    .toBe(JSON.stringify(normalize(before.messages)));
}

it.each([false, true])('checks Anthropic wire prefixes including images within the route budget (PA=%s)', async personal => {
  const home = await mkdtemp(join(tmpdir(),'nano-cache-wire-'));
  const requests: any[] = [];
  let client: RuntimeClient | undefined;
  let logs = '';
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const chunk of req) chunks.push(Buffer.from(chunk));
    const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    requests.push(body);
    const n = requests.length;
    // The failed HTTP request is still a real attempt at the same prefix.
    if (n === 1) {
      res.writeHead(529,{'content-type':'application/json'});
      res.end(JSON.stringify({type:'error',error:{type:'overloaded_error',message:'retry this request'}}));
      return;
    }
    const batch = n === 2;
    res.writeHead(200,{'content-type':'text/event-stream'});
    const emit = (type: string, data: object) => res.write('event: '+type+'\ndata: '+JSON.stringify({type,...data})+'\n\n');
    emit('message_start',{message:{id:'fixture-'+n,type:'message',role:'assistant',model:'fixture',content:[],stop_reason:null,usage:{input_tokens:40,output_tokens:0}}});
    const blocks = batch ? [
      {type:'tool_use',id:'batch-a',name:'cache_probe',input:{}},
      {type:'tool_use',id:'batch-b',name:'cache_probe',input:{}},
    ] : [{type:'text',text:'WIRE_REPLY_'+n}];
    for (const [index,block] of blocks.entries()) {
      emit('content_block_start',{index,content_block:block});
      if (batch) emit('content_block_delta',{index,delta:{type:'input_json_delta',partial_json:JSON.stringify({id:index===0?'a':'b'})}});
      emit('content_block_stop',{index});
    }
    emit('message_delta',{delta:{stop_reason:batch?'tool_use':'end_turn',stop_sequence:null},usage:{output_tokens:4}});
    emit('message_stop',{});res.end();
  });

  try {
    await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
    await writeFile(join(home,'fixture.mjs'),`
export const inject=['tools'];
export function apply(ctx) {
  ctx.on('agent/created',({agent})=>{agent.ctx.tools.presentAs('native');});
  let unblock;
  const bFinished = new Promise(resolve => { unblock = resolve; });
  ctx.tools.register({
    name:'cache_probe', description:'Fixture forces B to finish before A',
    parameters:{type:'object',properties:{id:{type:'string'}},required:['id']},
    isConcurrencySafe:()=>true,
    output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},
    async execute({id}) {
      if (id==='a') { await bFinished; return 'result-a'; }
      unblock(); throw Error('result-b failed');
    },
  });
}`);
    const port = (server.address() as {port:number}).port;
    await prepareProfile(home, [
      {id:'llm-pi-ai',config:{providers:{wire:{api:'anthropic-messages',apiKeyEnv:'NANO_TEST_KEY',
        baseURL:'http://127.0.0.1:'+port,cacheRetention:'short',
        retryPolicy:{mode:'normal',maxRetries:1},
        models:[{id:'fixture',contextWindow:200000,input:['text','image']}]}}}},
      {insert:[{id:'cache-wire-fixture',name:join(home,'fixture.mjs')}]},
    ]);
    client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture-only'},onLog:line=>{logs+=line;}});
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize',{protocol:1,bindings:[],agents:[{
      agentId:'a',displayName:'Cache wire',revision:'1',workspace:home,mode:'global',provider:'wire',model:'fixture',
      displayName:'CACHE_WIRE_SYSTEM',toolAllowlist:['cache_probe'],features:{dreaming:false},
      approval:{dangerouslySkipPermissions:true},
      ...(personal?{personal:{bindingId:'binding',ownerId:'owner',conversationId:'dm',epoch:1}}:{}),
    }]});
    await client.rpc.request('session.ensure',{sessionId:'root',agentId:'a',ownerId:'owner',revision:'1',cwd:home});
    const submit = async (id: string, image = false, state = false) => {
      await client!.rpc.request('session.submit',{sessionId:'root',inputId:id,mode:'followup',
        content:[{type:'text',text:'WIRE_'+id},...(image?[{type:'image',data:png,mediaType:'image/png'}]:[])],
        source:{kind:state?'system':'human',actorId:state?'a':'owner',channel:state?'personal-state':'test',messageId:id}});
      await expect.poll(async()=>(await client!.rpc.request('session.lookup',{sessionId:'root',inputId:id}) as any).terminal,{timeout:15000}).toBeTruthy();
    };

    await submit('batch');
    expect(requests, JSON.stringify(await client.rpc.request('session.lookup',{sessionId:'root',inputId:'batch'}))).toHaveLength(3);
    expectPrefix(requests[0],requests[1]);
    expectPrefix(requests[1],requests[2]);
    const results = requests[2].messages.flatMap(content).filter(block=>block.type==='tool_result');
    expect(results.map(block=>block.tool_use_id)).toEqual(['batch-a','batch-b']);
    expect(results[0].is_error).not.toBe(true);
    expect(results[1].is_error).toBe(true);
    await submit(personal?'source-change':'followup',false,personal);
    expectPrefix(requests[2],requests[3]);
    expect(JSON.stringify(requests[3].messages)).toContain(personal?'WIRE_source-change':'WIRE_followup');

    await submit('image-one',true);
    const before = requests.at(-1);
    expectPrefix(requests[3],before);
    expect(before.messages.flatMap(content).filter((block:any)=>block.type==='image')).toHaveLength(1);
    await submit('image-two',true);
    const after = requests.at(-1);
    expectPrefix(before,after);
    expect(after.messages.flatMap(content).filter((block:any)=>block.type==='image')).toHaveLength(2);
  } catch (error) {
    throw new Error(String(error)+'\n'+logs,{cause:error});
  } finally {
    if (client) await client.shutdown();
    await new Promise<void>(resolve=>{server.close(()=>resolve());server.closeAllConnections();});
    await rm(home,{recursive:true,force:true});
  }
},45000);
