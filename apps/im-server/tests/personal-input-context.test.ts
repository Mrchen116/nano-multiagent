import { expect,it } from 'vitest';
import { personalFixture } from './personal-fixture.js';
import { personalInputContext } from '../src/personal-input-context.js';

it('freezes input context at source order and supplements only an accessible direct reply',()=>{
 const {ctx,db,service,principal,args}=personalFixture();
 {
  const messages=Array.from({length:24},(_,i)=>ctx.messaging.insertMessage('peer',i%2?'u1':'u2','user',`message ${i}`));
  const current=ctx.messaging.insertMessage('peer','u2','user','current');
  db.prepare('UPDATE messages SET interaction_reply_json=? WHERE id=?').run(JSON.stringify({source_message_id:messages[0].id}),current.id);
  ctx.messaging.insertMessage('peer','u1','user','future context must stay out');
  const binding=service.authority(principal,args);
  const result=personalInputContext(db,current.id,m=>service.sourceAllowed(binding,m.conversation_id),m=>service.messageEvidence(binding,m));
  expect(result.current.content).toBe('current');
  expect(result.previous.map((m:any)=>m.content)).toEqual(Array.from({length:20},(_,i)=>`message ${i+4}`));
  expect(result.reply_target.id).toBe(messages[0].id);expect(result.omissions).toContainEqual({reason:'history_window',limit:20});
  const unavailable=personalInputContext(db,current.id,m=>m.id!==messages[0].id,m=>service.messageEvidence(binding,m));
  expect(unavailable.reply_target).toBeUndefined();expect(unavailable.omissions).toContainEqual({reason:'reply_target_unavailable',message_id:messages[0].id});
  expect(()=>personalInputContext(db,current.id,()=>false,m=>m)).toThrow('not accessible');
 }
});
