import { expect, it } from 'vitest';
import type { RelayInput } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { SingleThread } from '../src/single-thread.js';
import { InboxStore } from '../src/inbox.js';
import { GlobalAgent, type ProductCall } from '../src/global-agent.js';
import { RelayDeliveryError } from '@nano/channels';
import { toolPresentation } from '../src/presentation.js';
import type { RuntimeEvent } from '@nano/product-contracts';

const input: RelayInput = { agent_id:'a',conversation_id:'c',relay_task_id:'choice',idempotency_key:'choice',metadata:{conversation_type:'group',mentioned_agent_ids:['a']},
  message:{id:'choice',content:'先别发送，把语气改得随意一点',sender_type:'user',sender_user_id:'owner',attachments:[],interaction_reply:{
    source_message_id:'card',source_summary:'确认要发给林悦的消息',agent_id:'a',state:{},fields:[{name:'draft',label:'草稿',value:'林悦，周六11点断桥见'}],
  }} };
it('returns compact upstream diagnostics for recovery and allows a corrected new publication', async () => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
  store.bind({agentId:'a',sessionId:'main',conversationId:'c',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const detail={code:'invalid_interactive_source',message:'Correct the errors and retry.',errors:[{source:'parser',code:'type-mismatch',component:'Title',statementId:'heading',path:'/size',message:'Invalid size',hint:'Use sm or md'}]};
  let attempts=0;
  const product=new GlobalAgent({nodeId:'n',ownerId:'owner',store,inbox,agents:[{agentId:'a',revision:'1',provider:'test',model:'test',mode:'single_thread'}],
    runtime:{onNotification:()=>()=>{},request:async()=>({events:[],durable:true})},
    relay:{async request(type){if(type==='agent.session.ensure')throw new Error('invalid_scope');if(type==='agent.message'){
      if(++attempts===1)throw new RelayDeliveryError('rejected','rejected','invalid_interactive_source',detail);
      return {type:'ack',payload:{message_id:'fixed',conversation_id:'c'}};
    }return {type:'result',payload:{ok:true,result:{type:'direct',channel:'web'}}};}},image:async()=>'',onError:error=>{throw error;}});
  const interactive={format:'openui',catalog_version:'nano-iui-1',source:'root = Title("Hello", "huge")'};
  const call:ProductCall={method:'send_message',args:{target:'current',text:'Summary',interactive},operationId:'invalid',callId:'invalid',sessionId:'main',rootSessionId:'main',agentId:'a',ownerId:'owner'};
  try {
    await expect(product.call(call)).rejects.toThrow(JSON.stringify(detail));
    expect(inbox.publication('invalid')?.state).toBe('rejected');
    const fixed={...call,operationId:'fixed',callId:'fixed',args:{...call.args,interactive:{...interactive,source:'root = Title("Hello", "md")'}}};
    expect(await product.call(fixed)).toMatchObject({status:'sent',message_id:'fixed'});
    expect(attempts).toBe(2);
  } finally {await product.stop();store.close();inbox.close();}
});
it.each([
  {incoming:input, expected:'林悦，周六11点断桥见', label:'Attached choices'},
  {incoming:{...input,message:{...input.message,content:'',interaction_reply:undefined,interactive:{format:'openui',catalog_version:'nano-iui-1',source:'root = Col([Text("周六11点断桥见")])',supersedes_message_id:'previous-card',read_only:true}}}, expected:'周六11点断桥见', label:'Interactive UI content from the message sender'},
])('preserves public message content and $label in both Relay and Global Inbox', async ({incoming,expected,label}) => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');const submissions:any[]=[];
  const product=new SingleThread({nodeId:'n',ownerId:'owner',store,agents:[{agentId:'a',revision:'1',mode:'single_thread',provider:'test',model:'test',workspace:'/tmp'}],
    runtime:{onNotification:()=>()=>{},async request(method,args){if(method==='session.submit')submissions.push(args);if(method==='session.lookup')return{accepted:false};return{events:[],durable:true};}},
    relay:{request:async()=>({type:'ack',payload:{}})},image:async()=>'',onError:error=>{throw error;}});
  try{
    await product.receive(incoming);inbox.receive(incoming,true);
    const page=inbox.read('a','main','read',{target:'c'});
    for(const content of [JSON.stringify(submissions[0].content),JSON.stringify(page)]) {
      expect(content).toContain(incoming.message.content);expect(content).toContain(expected);expect(content).toContain(label);
      if ('interactive' in incoming.message) {
        expect(content).toContain('previous-card');
        expect(content).not.toMatch(/catalog_version|nano-iui-1|openui|read_only/);
      }
    }
    expect(store.inputs(store.bindingFor('a','c')!.sessionId)[0].input.message.content).toBe(incoming.message.content);
  }finally{await product.stop();store.close();inbox.close();}
});
it.each([['web',''],['web','摘要'],['feishu','摘要']])('publishes immutable UI identities for %s with optional text %j', async (channel,text) => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');const sent:any[]=[];
  store.bind({agentId:'a',sessionId:'main',conversationId:'c',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const agents=[{agentId:'a',revision:'1',provider:'test',model:'test',mode:'single_thread' as const,features:{intelligent_ui:true}}];
  const product=new GlobalAgent({nodeId:'n',ownerId:'owner',store,inbox,agents,runtime:{onNotification:()=>()=>{},request:async()=>({events:[],durable:true})},
    relay:{async request(type,payload){if(type==='agent.session.ensure')throw new Error('invalid_scope');if(type==='agent.message'){sent.push(payload);return{type:'ack',payload:{message_id:'card',conversation_id:'c'}};}return{type:'result',payload:{ok:true,result:{type:'direct',channel}}};}},image:async()=>'',onError:error=>{throw error;}});
  store.recordEvents('main',[{seq:1,time:1,type:'tool/call',data:{turn:1,callId:'send-card',name:'send_message',arguments:'{}'}}]);
  const interactive={format:'openui',catalog_version:'nano-iui-1',source:'root = Stack([TextContent("选项")])'};
  const call:ProductCall={method:'send_message',args:{target:'current',text,interactive},operationId:'send-card',callId:'send-card',sessionId:'main',rootSessionId:'main',agentId:'a',ownerId:'owner'};
  try{
    agents[0].features.intelligent_ui=false;
    await product.call(call);await product.call(call);expect(sent).toHaveLength(1);
    expect(store.command('interactive-delivered:main:1')).toBeTruthy();
    expect(sent[0].text).toBe(text);expect(sent[0].interactive).toEqual(channel==='web'?interactive:undefined);
    await expect(product.call({...call,args:{...call.args,interactive:{...interactive,source:'root = Stack([TextContent("不同选项")])'}}})).rejects.toThrow('identity conflict');
  }finally{await product.stop();store.close();inbox.close();}
});
it('closes a delivered interactive reply without streaming or publishing its closing sentinel', async () => {
  const store=new NodeStore(':memory:','owner');const frames:any[]=[];let submitted=false;let events:any[]=[];let notify:any;
  const product=new SingleThread({nodeId:'n',ownerId:'owner',store,agents:[{agentId:'a',revision:'1',mode:'single_thread',provider:'test',model:'test',workspace:'/tmp'}],
    runtime:{onNotification(listener){notify=listener;return()=>{};},async request(method){if(method==='session.submit')submitted=true;if(method==='session.lookup')return{accepted:submitted,turn:1};return{events,durable:true};}},
    relay:{async request(_type,payload){frames.push(payload);return{type:'ack',payload:{message_id:'process'}};}},image:async()=>'',onError:error=>{throw error;}});
  try {
    await product.receive({...input,metadata:{conversation_type:'direct'}});
    const sessionId=store.bindingFor('a','c')!.sessionId;
    store.saveCommand(`interactive-delivered:${sessionId}:1`,JSON.stringify({message_id:'card'}));
    notify('session.stream',{sessionId,frame:{type:'start',attemptId:'closing',turn:1}});
    notify('session.stream',{sessionId,frame:{type:'chunk',attemptId:'closing',turn:1,chunk:{type:'text-delta',text:'NO_REPLY'}}});
    notify('session.stream',{sessionId,frame:{type:'end',attemptId:'closing',turn:1}});
    events=[{seq:1,time:1,type:'assistant/message',data:{turn:1,message:{id:'closing',content:[{type:'text',text:'NO_REPLY'}]}}},{seq:2,time:2,type:'turn/end',data:{turn:1,reason:{kind:'completed'}}}];
    await product.recover();
    expect(frames.some(f=>f.kind==='message_delta' && f.delta_text==='NO_REPLY')).toBe(false);
    expect(frames.some(f=>f.kind==='message_completed' && f.final_content==='NO_REPLY')).toBe(false);
    expect(frames).toContainEqual(expect.objectContaining({kind:'message_discarded',reason:'explicit_reply_delivered'}));
    expect(store.delivery(sessionId,1)?.state).toBe('confirmed');
  } finally {await product.stop();store.close();}
});


it('supplies private background as optional non-authorizing data in both agent modes', async () => {
  const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');const submissions:any[]=[];
  const background={source_message_id:'card',source_summary:'对比',agent_id:'a',state:{'$step':'2'},fields:[{name:'step',label:'步骤',value:'2'}]};
  const natural={...input,message:{...input.message,content:'为什么这一步不同？',interaction_reply:undefined},metadata:{conversation_type:'direct',interaction_contexts:[background]}};
  const product=new SingleThread({nodeId:'n',ownerId:'owner',store,agents:[{agentId:'a',revision:'1',mode:'single_thread',provider:'test',model:'test',workspace:'/tmp'}],
    runtime:{onNotification:()=>()=>{},async request(method,args){if(method==='session.submit')submissions.push(args);if(method==='session.lookup')return{accepted:false};return{events:[],durable:true};}},
    relay:{request:async()=>({type:'ack',payload:{}})},image:async()=>'',onError:error=>{throw error;}});
  try{
    await product.receive(natural);inbox.receive(natural,true);
    const page=inbox.read('a','main','natural-read',{target:'c'});
    for(const content of [JSON.stringify(submissions[0].content),JSON.stringify(page)]) {
      expect(content).toContain('为什么这一步不同？');expect(content).toContain('$step');
      expect(content).toContain('not authorization');expect(content).toContain('Ignore');
    }
  }finally{await product.stop();store.close();inbox.close();}
});

it.each(['unknown','not-sent'] as const)('publishes screenshot attachments and preserves %s dispatch receipts', async delivery => {
  const store = new NodeStore(':memory:', 'owner'), inbox = new InboxStore(':memory:');
  store.bind({agentId:'a', sessionId:'main', conversationId:'c', ownerId:'owner', cwd:'/tmp', revision:'1'});
  const image = {url:'/im/v1/conversations/c/images/one', content_type:'image/png', file_name:'before.png'};
  const sent: Record<string, unknown>[] = [];
  let uploads = 0;
  let receiptAvailable = false;
  const product = new GlobalAgent({nodeId:'n', ownerId:'owner', store, inbox,
    agents:[{agentId:'a', revision:'1', provider:'test', model:'test', mode:'single_thread'}],
    runtime:{onNotification:()=>()=>{}, request:async()=>({events:[], durable:true})},
    relay:{async request(type, payload) {
      if (type === 'agent.message') {
        sent.push(payload);
        throw new RelayDeliveryError('No receipt', delivery);
      }
      if (type === 'agent.message.status') return {type:'ack', payload:{found:receiptAvailable, message_id:'m', conversation_id:'c'}};
      return {type:'result', payload:{ok:true, result:{type:'direct', channel:'web'}}};
    }},
    image:async()=>'', uploadScreenshot:async () => { uploads++; return image; },
    onError:error=>{throw error;},
  });
  const interactive = {format:'openui', catalog_version:'nano-iui-1', source:'root = AttachmentImage(1, "Before")'};
  const call: ProductCall = {method:'send_message', args:{target:'current', text:'Before', local_images:['/tmp/before.png'], interactive},
    operationId:'main:send', callId:'send', sessionId:'main', rootSessionId:'main', agentId:'a', ownerId:'owner'};
  try {
    await expect(product.call(call)).resolves.toMatchObject(delivery === 'unknown'
      ? {status:'unknown', operation_id:'main:send'} : {status:'not_sent'});
    expect(sent).toEqual([expect.objectContaining({attachments:[image], interactive})]);
    receiptAvailable = true;
    await expect(product.call({...call, operationId:'main:check', callId:'check',
      args:{target:'current', receipt_of:'main:send'}})).resolves.toMatchObject(delivery === 'unknown'
        ? {status:'sent', message_id:'m'} : {status:'not_sent'});
    expect(sent).toHaveLength(1);
    expect(uploads).toBe(1);
  } finally {await product.stop(); store.close(); inbox.close();}
});

it('keeps screenshot paths out of public tool process in both call and failure projections', () => {
  const path = '/private/work/secret-demo.png';
  const call: RuntimeEvent = {seq:1,time:1,type:'tool/call',data:{callId:'send',name:'send_message',
    arguments:JSON.stringify({target:'current',text:'Demo',local_images:[path]})}};
  const failure: RuntimeEvent = {seq:2,time:2,type:'tool/result',data:{message:{toolCallId:'send',isError:true,
    content:[{type:'text',text:`Could not read ${path}`}]}}};
  expect(toolPresentation(call,[call])).toMatchObject({input:{image_count:1}});
  expect(toolPresentation(failure,[call,failure])).toMatchObject({status:'failed'});
  for (const args of [call.data.arguments, JSON.stringify({target:'current',local_images:path}), `{"local_images":["${path}"`]) {
    const attempt = {...call,data:{...call.data,arguments:args}};
    expect(JSON.stringify([toolPresentation(attempt,[attempt]),toolPresentation(failure,[attempt,failure])])).not.toContain(path);
  }
});
