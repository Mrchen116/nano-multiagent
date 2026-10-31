import { expect, it } from 'vitest';
import { NodeStore } from '../src/store.js';
import { InboxStore } from '../src/inbox.js';
import { GlobalAgent, type ProductCall } from '../src/global-agent.js';

it('binds memory history to the actual root and preserves original message identities',async()=>{
 const store=new NodeStore(':memory:','owner'),inbox=new InboxStore(':memory:');
 store.bind({agentId:'a',sessionId:'main',conversationId:'global:a',ownerId:'owner',cwd:'/tmp',revision:'1'});
 const requests:any[]=[];
 const product=new GlobalAgent({nodeId:'node',ownerId:'owner',agents:[{agentId:'a',workspace:'/tmp',revision:'1',provider:'p',model:'m'}],store,inbox,
  runtime:{onNotification:()=>()=>{},request:async()=>({})},
  relay:{request:async(type,payload)=>{requests.push({type,payload});return {type:'conversation.query.result',payload:{ok:true,result:{messages:[{message_id:'original-message',source:{conversation_id:'original-chat'},content:[{type:'text',text:'raw'}]}]}}};}},image:async()=>'',onError:e=>{throw e;}});
 const call:ProductCall={method:'memory.conversations',agentId:'a',ownerId:'owner',rootSessionId:'main',sessionId:'main',operationId:'read',callId:'read',args:{action:'read',target:'original-chat',cutoff:100,afterTime:0,agent_id:'forged'}};
 try {
  expect(await product.call(call)).toEqual({messages:[{message_id:'original-message',source:{conversation_id:'original-chat'},content:[{type:'text',text:'raw'}]}]});
  expect(requests).toMatchObject([{type:'conversation.query',payload:{agent_id:'a',session_id:'main',memory_cutoff:100,memory_after:0,target:'original-chat'}}]);
  await expect(product.call({...call,sessionId:'child'})).rejects.toThrow('main Agent');
  await expect(product.call({...call,args:{...call.args,action:'join'}})).rejects.toThrow('read-only');
  await expect(product.call({...call,args:{...call.args,afterTime:200}})).rejects.toThrow('bounded');
  expect(requests).toHaveLength(1);
 }finally{await product.stop();inbox.close();store.close();}
});
