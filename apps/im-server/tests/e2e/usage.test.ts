import {expect,it} from 'vitest';
import {start,bind} from './helpers.js';

it('retires the unused cumulative query and report protocol',async()=>{
  const f=await start(),g=await bind(f);
  expect((await f.http('GET','/im/v1/metrics/usage',undefined,f.tokens.alice)).status).toBe(404);
  expect(await g.frames.send('node.report',{node_id:g.node,agent_id:'assistant',run_id:'retired:1',usage:{total_tokens:14}}))
    .toMatchObject({type:'error',payload:{code:'unsupported_message_type'}});
});
