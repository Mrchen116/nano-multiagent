import { vi } from 'vitest';
import { fixture } from './control-fixture.js';
import { Messaging } from '../src/messaging.js';
import { PersonalAgents } from '../src/personal-agent.js';

export function personalFixture() {
 const f = fixture();
 f.ctx.gateway.broadcast=vi.fn();
 f.ctx.messaging=new Messaging(f.ctx);
 f.db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('n','o1',1)").run();
 f.db.prepare("INSERT INTO personal_agent_bindings VALUES('binding','o1','u1','a','n',1,'chat','Assistant','create','active',NULL,?)").run(new Date().toISOString());
 f.db.prepare("INSERT INTO pa_policies(binding_id) VALUES('binding')").run();
 f.db.prepare("INSERT INTO conversations(id,title,type,created_at) VALUES('peer','Peer','direct',?)").run(new Date().toISOString());
 for(const id of ['u1','u2']) f.db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('peer',?)").run(id);
 f.db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
 const service=new PersonalAgents(f.ctx); f.ctx.personal=service;
 return {...f,service,principal:{node_id:'n',owner_id:'o1',node_epoch:1},args:{agent_id:'a',binding_id:'binding',epoch:1}};
}

/** Record an actual PA-authored owner delivery before testing the peer boundary. */
export function recordOwnerNotice(service:PersonalAgents,principal:Record<string,any>,args:Record<string,any>,incident:Record<string,any>) {
 const message=service.ctx.messaging.insertMessage('chat','a1','agent','A request was refused; your private information was not shared.',[],`pa-incident:${incident.id}:owner`,'completed');
 service.incidentReceipt(principal,{...args,incident_ref:incident.id,message_id:message.id});
 incident.owner_notice_message_id=message.id;
 return message;
}
