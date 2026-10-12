import {expect,it} from 'vitest';
import {once} from 'node:events';
import {start,bind,connect} from './helpers.js';

it('counts terminal native turns once per scope across reconnect, including global turns without chat bubbles',async()=>{
  const f=await start(),g=await bind(f);
  const chat=await f.http('POST','/im/v1/conversations',{title:'Usage',type:'direct',participants:[{type:'agent',id:'assistant'}]},f.tokens.alice);
  const report={node_id:g.node,agent_id:'assistant',conversation_id:chat.body.id,run_id:'native-child:1',status:'completed',usage:{prompt_tokens:10,completion_tokens:4,total_tokens:14}};
  expect((await g.frames.send('node.report',report)).type).toBe('ack');
  expect((await g.frames.send('node.report',report)).type).toBe('ack');
  expect((await g.frames.send('node.report',{...report,agent_id:'global',conversation_id:undefined,run_id:'global:1'})).type).toBe('ack');
  const read=()=>f.http('GET','/im/v1/metrics/usage',undefined,f.tokens.alice);
  const rows=(await read()).body;
  expect(rows.find((r:any)=>r.scope==='owner')).toMatchObject({turns:2,total_tokens:28});
  expect(rows.find((r:any)=>r.scope==='conversation')).toMatchObject({turns:1,total_tokens:14});
  expect(rows.filter((r:any)=>r.scope==='agent')).toHaveLength(2);
  expect((await f.http('GET','/im/v1/metrics/usage',undefined,f.tokens.outsider)).body).toEqual([]);
  f.child.kill('SIGTERM');await once(f.child,'exit');
  const restored=await start(f.dbPath),again=await connect(restored,g.node,g.runtime);
  expect((await again.frames.send('node.report',report)).type).toBe('ack');
  const after=await restored.http('GET','/im/v1/metrics/usage',undefined,restored.tokens.alice);
  expect(after.body.find((r:any)=>r.scope==='owner')).toMatchObject({turns:2,total_tokens:28});
});
