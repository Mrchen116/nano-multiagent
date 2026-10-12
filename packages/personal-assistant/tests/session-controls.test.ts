import { expect, it } from 'vitest';
import type { AgentConfiguration, RelayInput, SessionBinding } from '@nano/product-contracts';
import { NodeStore } from '../src/store.js';
import { SessionControls, sessionControl } from '../src/session-controls.js';

it('reserves command order and recovers the same result after delivery failed', async () => {
  const store = new NodeStore(':memory:', 'owner'); const binding: SessionBinding = { agentId:'a', sessionId:'s', conversationId:'chat', cwd:'/tmp', revision:'1', ownerId:'owner' }; store.bind(binding);
  const input: RelayInput = { agent_id:'a',conversation_id:'chat',relay_task_id:'relay',idempotency_key:'input',metadata:{conversation_type:'direct'},message:{id:'input',content:'/compact focus',sender_type:'user',sender_user_id:'owner',attachments:[]} };
  let release!: () => void; const gate = new Promise<void>(resolve=>{release=resolve;}); let commands=0; let fail=true;
  const frames: Record<string,unknown>[]=[];
  const options={nodeId:'node',store,runtime:{onNotification:()=>()=>{},request:async(method:string)=>{if(method==='session.command'){commands++;await gate;return{text:'Compacted original context'};}return{};}},relay:{request:async(_type:string,payload:Record<string,unknown>)=>{frames.push(payload);if(fail)throw new Error('offline');return{type:'ack',payload:{message_id:'result'}};}}};
  let controls=new SessionControls(options);
  try {
    const pending=controls.run(binding,input,'compact','focus'); const rejected=expect(pending).rejects.toThrow('offline');
    let later=false; const next=controls.wait('s').then(()=>{later=true;});await Promise.resolve();expect(later).toBe(false);
    release();await rejected;await next;expect(commands).toBe(1);await controls.stop();
    controls=new SessionControls(options);fail=false;await controls.recover('a');expect(commands).toBe(1);
    expect(store.control('a:input')).toMatchObject({text:'Compacted original context',delivered:true});
    expect(frames.filter(frame=>frame.kind==='turn_start').map(frame=>frame.idempotency_key)).toEqual(['command:a:input','command:a:input']);
  }finally{release();await controls.stop();store.close();}
});

it('requires group addressing even under ALWAYS and preserves original command text', () => {
  const config: AgentConfiguration={agentId:'a',revision:'1',workspace:'/tmp',mode:'single_thread',provider:'p',model:'m',groupReplyPolicy:'always'};
  const input: RelayInput={agent_id:'a',conversation_id:'group',relay_task_id:'r',idempotency_key:'r',metadata:{conversation_type:'group',mentioned_agent_ids:[]},message:{id:'r',content:'/compact 保留认证方案',sender_type:'user',sender_user_id:'u',attachments:[]}};
  expect(sessionControl(input,config)).toBeUndefined();
  input.metadata.mentioned_agent_ids=['a'];expect(sessionControl(input,config)).toEqual({action:'compact',argument:'保留认证方案'});
  input.message.sender_type='agent';expect(sessionControl(input,config)).toBeUndefined();
});
