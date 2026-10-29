import { expect, it } from 'vitest';
import { personalFixture } from './personal-fixture.js';
import { Work } from '../src/work.js';

it('filters frozen memory reads before pagination and keeps observation consumption untouched', () => {
  const {ctx,db,service,principal,args}=personalFixture();
  const work=new Work(ctx), cutoff=Date.parse('2026-10-20T12:00:00Z');
  const add=(content:string,at:string)=>{
    const m=ctx.messaging.insertMessage('peer','u2','user',content);
    db.prepare('UPDATE messages SET created_at=? WHERE id=?').run(at,m.id);
    db.prepare('UPDATE conversation_events SET created_at=? WHERE message_id=?').run(at,m.id);
    return m;
  };
  const first=add('hotel refundable','2026-10-20T10:00:00Z');
  const second=add('hotel not booked','2026-10-20T11:00:00Z');
  const edited=add('hotel old','2026-10-20T11:30:00Z');
  db.prepare('UPDATE messages SET content=? WHERE id=?').run('hotel future edit',edited.id);
  ctx.messaging.event('peer',edited.id,'message.reconciled',{content:'hotel future edit'});
  add('hotel future','2026-10-20T13:00:00Z');
  const read=(extra:Record<string,unknown>={})=>work.query(principal,{...args,session_id:'root',action:'search',target:'peer',query:'hotel',limit:1,memory_after:Date.parse('2026-10-20T00:00:00Z'),memory_cutoff:cutoff,...extra});
  const sourceState=db.prepare('SELECT * FROM pa_source_events').all();
  const page=read();
  expect(page.messages).toMatchObject([{message_id:second.id,content:[{text:'hotel not booked'}],delivery:'observer',version_scope:'verified_at_cutoff'}]);
  expect(page.messages[0].content_hash).toMatch(/^[a-f0-9]{64}$/);
  expect(page.has_more).toBe(true);
  const tail=read({cursor:page.next_cursor});
  expect(tail.messages).toMatchObject([{message_id:first.id}]);expect(tail.has_more).toBe(false);
  expect(read({query:'future'}).messages).toEqual([]);
  expect(()=>read({cursor:page.next_cursor,memory_cutoff:cutoff+1000})).toThrow('invalid_cursor');
  expect(read({action:'info'}).metadata_scope).toBe('current');
  expect(()=>read({action:'join'})).toThrow('invalid_memory_range');
  expect(db.prepare('SELECT * FROM pa_source_reads').all()).toEqual([]);
  expect(db.prepare('SELECT * FROM pa_source_events').all()).toEqual(sourceState);
  service.updatePolicy('o1',{expected_revision:1,excluded_conversation_ids:['peer']});
  expect(()=>read({cursor:page.next_cursor})).toThrow('target_not_accessible');
});
