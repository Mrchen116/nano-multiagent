import {expect,it} from 'vitest';
import {join} from 'node:path';
import {start,bind,cleanups} from './helpers.js';
import {openDatabase} from '../../src/db.js';
import {NodeStore} from '../../../../packages/personal-assistant/src/store.js';
import {InboxStore} from '../../../../packages/personal-assistant/src/inbox.js';
import {GlobalAgent} from '../../../../packages/personal-assistant/src/global-agent.js';

// Real authenticated relay and IM process; only the caller of the product tool is controlled.
it('reads frozen PA evidence over the real relay without consuming observation or Inbox state',async()=>{
  const center=await start(),node=await bind(center);
  const create=async(participant:{type:string;id:string})=>{
    const result=await center.http('POST','/im/v1/conversations',{title:'Memory evidence',type:'direct',participants:[participant]},center.tokens.alice);
    expect(result.status,JSON.stringify(result.body)).toBe(201);return result.body.id as string;
  };
  const ownerChat=await create({type:'agent',id:'global'}),source=await create({type:'user',id:'bob'});
  const db=openDatabase(center.dbPath);cleanups.push(()=>db.close());
  const epoch=(db.prepare('SELECT node_epoch FROM node_binding_state WHERE node_id=?').get(node.node) as {node_epoch:number}).node_epoch;
  db.prepare('INSERT INTO personal_agent_bindings VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?)').run('memory-binding','alice','alice','global',node.node,epoch,ownerChat,'PA','create','active',new Date().toISOString());
  db.prepare('INSERT INTO pa_policies(binding_id) VALUES(?)').run('memory-binding');
  const send=async(key:string,content:string)=>{
    const response=await center.http('POST',`/im/v1/conversations/${source}/messages`,{sender_user_id:'alice',content},center.tokens.alice,{'Idempotency-Key':key});
    expect(response.status,response.body).toBe(201);return response.body.id as string;
  };
  const first=await send('first','Hotel condition: free cancellation.');
  const second=await send('second','Hotel outcome: compared, not booked.');
  const cutoff=Date.now();
  const store=new NodeStore(join(center.dir,'memory-node.db'),'alice'),inbox=new InboxStore(join(center.dir,'memory-inbox.db'));
  cleanups.push(()=>store.close(),()=>inbox.close());
  store.bind({agentId:'global',sessionId:'memory-root',conversationId:'global:global',ownerId:'alice',cwd:center.dir,revision:'1'});
  const product=new GlobalAgent({nodeId:node.node,ownerId:'alice',store,inbox,
    agents:[{agentId:'global',workspace:center.dir,revision:'1',provider:'fixture',model:'fixture',mode:'global',personal:{bindingId:'memory-binding',ownerId:'alice',conversationId:ownerChat,epoch}}],
    runtime:{onNotification:()=>()=>{},request:async()=>({})},relay:{ready:true,request:(type,payload)=>node.frames.send(type,payload)},image:async()=>'',onError:error=>{throw error;}});
  cleanups.push(()=>product.stop());
  const snapshot=()=>({reads:db.prepare('SELECT * FROM pa_source_reads').all(),events:db.prepare('SELECT * FROM pa_source_events').all(),inbox:inbox.check('global',true),journal:inbox.journalSeq});
  const before=snapshot();let sequence=0;
  const query=(args:Record<string,unknown>)=>product.call({method:'memory.conversations',agentId:'global',ownerId:'alice',rootSessionId:'memory-root',sessionId:'memory-root',operationId:`read-${sequence}`,callId:`read-${sequence++}`,args:{action:'search',target:source,query:'Hotel',cutoff,afterTime:0,limit:1,...args}}) as Promise<any>;
  const page=await query({});
  expect(page.messages).toMatchObject([{message_id:second,delivery:'observer',version_scope:'verified_at_cutoff',content:[{text:'Hotel outcome: compared, not booked.'}]}]);
  const tail=await query({cursor:page.next_cursor});
  expect(tail.messages).toMatchObject([{message_id:first,content:[{text:'Hotel condition: free cancellation.'}]}]);
  expect(await query({action:'info'})).toMatchObject({target:source,metadata_scope:'current'});
  expect((await query({action:'read',message_id:first})).messages[0].message_id).toBe(first);
  expect(snapshot()).toEqual(before);
  await expect(query({action:'join'})).rejects.toThrow('read-only');
  db.prepare('UPDATE pa_policies SET excluded_json=?,revision=revision+1 WHERE binding_id=?').run(JSON.stringify([source]),'memory-binding');
  await expect(query({cursor:page.next_cursor})).rejects.toThrow('target_not_accessible');
  expect(snapshot()).toEqual(before);
},30000);
