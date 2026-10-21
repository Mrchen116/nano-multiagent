import {expect,it,vi} from 'vitest';
import {fixture} from './control-fixture.js';
import {RelayDelivery} from '../src/relay-delivery.js';
import type {Row} from '../src/context.js';

it('rotates three Agents within the bounded replay window despite two large backlogs',()=>{
 const {db,ctx}=fixture(),sent:Row[]=[];
 db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at) VALUES('m','chat','u1','user','test','pending','now')").run();
 for(const [agent,count] of [['a',40],['b',40],['c',1]] as const)for(let i=0;i<count;i++){
  const id=`${agent}-${i}`;
  db.prepare("INSERT INTO relay_tasks VALUES(?,'m','chat','n',?,?,'queued',NULL,NULL,?,?)").run(id,JSON.stringify({agent_id:agent}),id,id,id);
 }
 ctx.gateway.isOnline=()=>true;
 ctx.gateway.send=(_node,frame)=>{sent.push(frame.payload);return true;};
 ctx.messaging={relayEligible:vi.fn(()=>true)} as any;
 const delivery=new RelayDelivery(ctx);delivery.drain('n');
 expect(sent).toHaveLength(32);
 expect(sent.slice(0,3).map(frame=>frame.agent_id)).toEqual(['a','b','c']);
 delivery.drain('n');expect(sent).toHaveLength(32);
});
