import { createServer, type ServerResponse } from 'node:http';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { prepareProfile, RuntimeClient } from '../lib/client.js';
import { registerNoopTaskHosts } from './helpers/noop-task-hosts.js';

it('confirms only notices in a responding model request, across queueing, failure, cancellation and restart', async () => {
  const home = await mkdtemp(join(tmpdir(), 'nano-inbox-wire-'));
  const requests: {body: any; response: ServerResponse}[] = [];
  const server = createServer(async (request, response) => {
    let body = ''; for await (const part of request) body += part;
    requests.push({body:JSON.parse(body),response});
  });
  let client: RuntimeClient | undefined;
  const binding = {sessionId:'root',agentId:'a',revision:'1',ownerId:'owner',cwd:home};
  const start = async () => {
    client = new RuntimeClient({home,cwd:home,env:{NANO_TEST_KEY:'fixture'}});
    registerNoopTaskHosts(client);
    await client.rpc.request('initialize', {protocol:1,agents:[{agentId:'a',revision:'1',mode:'global',workspace:home,provider:'fixture',model:'fixture',toolAllowlist:[],features:{dreaming:false},approval:{dangerouslySkipPermissions:true}}],bindings:[binding]});
    await client.rpc.request('session.ensure',binding);
  };
  const submit = (id: string, channel = 'inbox') => client!.rpc.request('session.submit', {
    sessionId:'root',inputId:id,mode:'steer',content:[{type:'text',text:`Notification ${id}`}],
    source:{kind:'system',actorId:'a',channel,messageId:id},
  });
  const observe = async () => await client!.rpc.request('session.observe',{sessionId:'root'}) as {status:string;events:{type:string;data:any}[]};
  const receipts = async () => ((await client!.rpc.request('session.work.root',{sessionId:'root'}) as {inboxDelivered:string[]}).inboxDelivered);
  const confirm = (inputIds:string[]) => client!.rpc.request('session.inbox-delivered.confirm',{sessionId:'root',inputIds});
  const respond = (index: number) => {
    const res = requests[index]!.response;
    res.writeHead(200,{'content-type':'text/event-stream'});
    const emit = (type: string, data: object) => res.write(`event: ${type}\ndata: ${JSON.stringify({type,...data})}\n\n`);
    emit('message_start',{message:{id:'reply',type:'message',role:'assistant',model:'fixture',content:[],stop_reason:null,usage:{input_tokens:20,output_tokens:0}}});
    emit('content_block_start',{index:0,content_block:{type:'text',text:''}});
    emit('content_block_delta',{index:0,delta:{type:'text_delta',text:'Done.'}});
    emit('content_block_stop',{index:0});
    emit('message_delta',{delta:{stop_reason:'end_turn',stop_sequence:null},usage:{output_tokens:2}});
    emit('message_stop',{}); res.end();
  };
  try {
    await new Promise<void>(resolve => server.listen(0,'127.0.0.1',resolve));
    await prepareProfile(home,[{id:'llm-pi-ai',config:{providers:{fixture:{api:'anthropic-messages',baseURL:`http://127.0.0.1:${(server.address() as {port:number}).port}`,apiKeyEnv:'NANO_TEST_KEY',models:[{id:'fixture',contextWindow:100000}],retryPolicy:{mode:'normal',maxRetries:0}}}}}]);
    await start();
    await submit('inbox-wake:a:failed');
    await expect.poll(() => requests.length).toBe(1);
    expect(JSON.stringify(requests[0]!.body.messages)).toContain('Notification inbox-wake:a:failed');
    expect(await receipts()).toEqual([]);
    requests[0]!.response.writeHead(500,{'content-type':'application/json'});
    requests[0]!.response.end(JSON.stringify({error:{type:'server_error',message:'unavailable'}}));
    await expect.poll(async () => (await observe()).status).toBe('idle');
    expect(await receipts()).toEqual([]);

    await submit('inbox-wake:a:cancelled');
    await expect.poll(() => requests.length).toBe(2);
    await client!.rpc.request('session.cancel',{sessionId:'root'});
    expect(await receipts()).toEqual([]);

    await submit('inbox-wake:a:3:recovery:17');
    await expect.poll(() => requests.length).toBe(3);
    await submit('inbox-background:a:4','inbox-background');
    expect(JSON.stringify(requests[2]!.body.messages)).toContain('Notification inbox-wake:a:3:recovery:17');
    expect(JSON.stringify(requests[2]!.body.messages)).not.toContain('Notification inbox-background:a:4');
    expect(await receipts()).toEqual([]);
    respond(2);
    await expect.poll(receipts).toContain('inbox-wake:a:3:recovery:17');
    expect(await receipts()).not.toContain('inbox-background:a:4');
    await confirm(await receipts());
    await expect.poll(() => requests.length).toBe(4);
    expect(JSON.stringify(requests[3]!.body.messages)).toContain('Notification inbox-background:a:4');
    respond(3);
    await expect.poll(async () => (await observe()).status).toBe('idle');
    expect(await receipts()).toEqual(['inbox-background:a:4']);

    await client!.shutdown(); client = undefined;
    await start();
    expect(await receipts()).toEqual(['inbox-background:a:4']);
    await confirm(await receipts());
    await submit('unrelated-source','other');
    await expect.poll(() => requests.length).toBe(5);
    respond(4);
    await expect.poll(async () => (await observe()).status).toBe('idle');
    expect(await receipts()).toEqual([]);
    await client!.shutdown(); client = undefined;
  } finally {
    if (client) {client.process.kill('SIGKILL');await client.exited;}
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    await rm(home,{recursive:true,force:true});
  }
},30000);
