import {expect,it,vi} from 'vitest';
import {fixture} from './control-fixture.js';
import {Messaging} from '../src/messaging.js';
import type {Row} from '../src/context.js';

it.each(['selection', 'full'])('counts relay payload parses through drain (%s)', mode => {
  const {ctx,db}=fixture();
  ctx.messaging=new Messaging(ctx);
  if(mode==='selection') vi.spyOn(ctx.messaging,'relayEligible').mockReturnValue(true);
  const sent:Row[]=[];
  const inputs=Array.from({length:256},(_,i)=>({agent_id:'a',relay_task_id:String(i).padStart(3,'0'),message:{content:'payload '+i}}));
  db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at) VALUES('m','chat','u1','user','test','pending','now')").run();
  const serialized=inputs.map(p=>JSON.stringify(p));
  for(const [i,p] of inputs.entries()) db.prepare("INSERT INTO relay_tasks VALUES(?,'m','chat','n',?,?,'queued',NULL,NULL,?,?)").run(p.relay_task_id, serialized[i], p.relay_task_id,p.relay_task_id,p.relay_task_id);
  ctx.gateway.isOnline=()=>true;
  ctx.gateway.send=(_node,frame)=>{sent.push(frame.payload);return true;};
  const strings=new Set(serialized);
  const spy=vi.spyOn(JSON,'parse');
  let count;
  try {
    ctx.messaging.delivery.drain('n');
    count=spy.mock.calls.filter(([raw])=>strings.has(raw)).length;
  } finally {spy.mockRestore();}
  expect(sent).toEqual(inputs.slice(0,32));
  process.stdout.write(mode + ': ' + count + ' payload parses, ' + sent.length + ' matching frames\n');
  expect(count).toBeLessThanOrEqual(256);
});
