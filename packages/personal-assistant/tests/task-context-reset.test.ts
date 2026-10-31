import {expect,it} from 'vitest';
import {NodeStore} from '../src/store.js';

it('transfers only prepared originals on session reset, rejecting late ACKs from the old session',()=>{
 const store=new NodeStore(':memory:','owner');
 try {
  for(const id of ['pending','consumed','revoked'])store.prepareSystemContext('a',id,'chat','old','digest');
  expect(store.commitSystemContext('old','consumed','digest',1)).toBe(true);
  store.revokeSystemContext('a','revoked','chat');
  for(const id of ['pending','consumed','revoked'])store.prepareSystemContext('a',id,'chat','new','digest');
  expect(store.commitSystemContext('old','pending','digest',2)).toBe(false);
  expect(store.commitSystemContext('new','pending','digest',3)).toBe(true);
  expect(store.systemContextInputs('a')).toEqual(expect.arrayContaining([
   expect.objectContaining({message_id:'pending',session_id:'new',state:'consumed',turn:3}),
   expect.objectContaining({message_id:'consumed',session_id:'old',state:'consumed',turn:1}),
   expect.objectContaining({message_id:'revoked',session_id:'old',state:'revoked'}),
  ]));
 } finally {store.close();}
});
