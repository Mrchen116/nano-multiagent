import {expect,it} from 'vitest';
import {NodeStore} from '../src/store.js';
import {UsageReports} from '../src/usage.js';

it('replays an ambiguous report with the same native ID and never recharges an acknowledged turn',async()=>{
  const store=new NodeStore(':memory:','owner');
  store.bind({sessionId:'root',agentId:'a',conversationId:'old-uuid-chat',ownerId:'owner',cwd:'/tmp',revision:'1'});
  const calls: Record<string,unknown>[]=[];
  let fail=true;
  const options={nodeId:'node',store,runtime:{onNotification:()=>()=>{},async request(){return [{sessionId:'child',turn:1,time:1000,usage:{prompt_tokens:12,completion_tokens:3,total_tokens:15}}];}},
    relay:{ready:true,async request(_type:string,payload:Record<string,unknown>){calls.push(payload);if(fail){fail=false;throw Error('ack lost');}return {type:'ack',payload:{}};}},onError:()=>{}};
  const first=new UsageReports(options);
  await expect(first.recover()).rejects.toThrow('ack lost');
  expect(store.pendingUsage()).toHaveLength(1);
  await first.stop();
  const second=new UsageReports(options);
  await second.recover();
  await second.recover();
  expect(calls).toHaveLength(2);
  expect(calls[0]).toEqual(calls[1]);
  expect(calls[0]).toMatchObject({run_id:'child:1',agent_id:'a',conversation_id:'old-uuid-chat'});
  expect(store.pendingUsage()).toEqual([]);
  await second.stop();store.close();
});
