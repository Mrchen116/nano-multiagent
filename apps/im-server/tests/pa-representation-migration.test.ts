import {expect,it} from 'vitest';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {applyRepresentationMigration,inspectRepresentationMigration,verifyRepresentationMigration} from '../src/migrate-pa-representation.js';

it('adds only nullable provenance while preserving old messages, operations, events, relays and draft rows',()=>{
  const schema=readFileSync(new URL('../src/schema.sql',import.meta.url),'utf8')
    .replace(',\n representation_operation_id TEXT REFERENCES pa_operations(operation_id)','')
    .replace(/^ AND NOT EXISTS\(SELECT 1 FROM pa_delegated_messages.*\n/m,'');
  const before=new DatabaseSync(':memory:'),after=new DatabaseSync(':memory:');
  try {
    for(const db of [before,after]) {
      db.exec(schema);
      db.exec("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('a','agent:pa','PA','owner','now'); INSERT INTO conversations(id,title,type,created_at) VALUES('c','Legacy','direct','now'); INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at) VALUES('m','c','a','agent','Original PA text','completed','now'); INSERT INTO pa_delegated_messages VALUES('m','b','pa','owner','PA');");
      for(const state of ['prepared','allowed','confirmed'])db.prepare("INSERT INTO pa_operations(operation_id,binding_id,request_key,policy_revision,disclosure_revision,conversation_id,audience_json,payload_json,payload_digest,evidence_json,state,created_at) VALUES(?,?,?,1,0,'c','[]','{}','old','{}',?,'now')").run(state,'b',state,state);
      db.exec("INSERT INTO conversation_events(conversation_id,message_id,event_type,delivery_status,payload_json,created_at) VALUES('c','m','message.created','completed','{\"sender_type\":\"agent\"}','now'); INSERT INTO pa_reply_drafts VALUES('m','c','m','$draft');");
    }
    expect(inspectRepresentationMigration(after).state).toBe('pending');
    expect(applyRepresentationMigration(after).state).toBe('already_migrated');
    expect(verifyRepresentationMigration(after,before)).toMatchObject({verified:true,rows:{messages:1,pa_operations:3,pa_delegated_messages:1,conversation_events:1,pa_reply_drafts:1}});
    expect(after.prepare('SELECT representation_operation_id FROM pa_delegated_messages').get()).toEqual({representation_operation_id:null});
    applyRepresentationMigration(after);
    expect(verifyRepresentationMigration(after,before).verified).toBe(true);
    after.exec("UPDATE messages SET content='changed'");
    expect(()=>verifyRepresentationMigration(after,before)).toThrow('Historical records changed: messages');
  }finally{before.close();after.close();}
});
