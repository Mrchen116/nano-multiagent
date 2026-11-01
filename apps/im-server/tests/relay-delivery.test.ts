import {expect,it} from 'vitest';
import {fixture} from './control-fixture.js';
import {Messaging} from '../src/messaging.js';
import type {Row} from '../src/context.js';

it('rotates by the remaining Agents and cancels a revoked recipient within the same drain',()=>{
  const {db,ctx}=fixture();
  ctx.messaging=new Messaging(ctx);
  for (const agent of ['b','c']) {
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES(?,?,?,'o1','now','active')").run(agent,'agent:'+agent,agent);
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,created_at,updated_at) VALUES(?,'o1','n',?,?,'now','now')").run(agent,agent,'/'+agent);
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)").run(agent);
  }
  db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at) VALUES('m','chat','u1','user','test','pending','now')").run();
  const agents=['a','b','c','b','a',...Array<string>(40).fill('a'),...Array<string>(40).fill('b'),'c'];
  for (const [i,agent] of agents.entries()) {
    const id=String(i).padStart(3,'0');
    db.prepare("INSERT INTO relay_tasks VALUES(?,'m','chat','n',?,?,'queued',NULL,NULL,?,?)")
      .run(id,JSON.stringify({agent_id:agent,relay_task_id:id}),id,id,id);
  }
  const sent:Row[]=[];
  ctx.gateway.isOnline=()=>true;
  ctx.gateway.send=(_node,frame)=>{
    sent.push(frame.payload);
    if (frame.payload.agent_id==='c') db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='c'").run();
    return true;
  };
  ctx.messaging.delivery.drain('n');
  expect(sent.slice(0,5).map(p=>p.relay_task_id)).toEqual(['000','001','004','002','003']);
  expect(sent).toHaveLength(32);
  expect(db.prepare("SELECT status FROM relay_tasks WHERE relay_task_id='085'").get()?.status).toBe('cancelled');
  ctx.messaging.delivery.drain('n');
  expect(sent).toHaveLength(32);
});
