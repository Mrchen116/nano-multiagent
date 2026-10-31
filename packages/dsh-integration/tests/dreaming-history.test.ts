import {expect,it} from 'vitest';
import {registerDreamingHistory} from '../src/knowledge/dreaming-history.js';
import {MemorySources} from '../src/knowledge/memory-sources.js';

function fixture(){
  const event=(seq:number,type:string,data:unknown)=>({seq,time:seq+100,type,data});
  const human=(seq:number,text:string,conversation='allowed')=>event(seq,'user/message',{id:`m-${seq}`,source:{kind:'user',actorId:'owner',channel:'web',messageId:`m-${seq}`,conversationId:conversation},content:[{type:'text',text}]});
  const events=[human(0,'Before activation'),human(1,'😀新😀事实'),
    event(2,'compaction/start',{compactionId:'window',turn:null}),event(3,'compaction/summary',{compactionId:'window',summary:[],provider:'fixture'}),event(4,'compaction/end',{compactionId:'window',turn:null}),
    human(5,'Current allowed condition'),human(6,'SECRET revoked','revoked'),
    event(7,'assistant/message',{message:{role:'assistant',source:{kind:'model'},content:[{type:'tool-call',id:'read',name:'conversations',arguments:'{}'}]}}),
    event(8,'tool/call',{callId:'read',name:'conversations',arguments:'{}'}),
    event(9,'tool/result',{message:{role:'tool',toolCallId:'read',source:{kind:'tool'},content:[{type:'text',text:JSON.stringify({messages:[{id:'yes',conversation_id:'allowed',content:'Visible mixed record'},{id:'no',conversation_id:'revoked',content:'SECRET mixed record'}]})}]}}),
    human(10,'FUTURE result')];
  const snapshots={sessions:{get:()=>undefined},sessionQuery:{observeSession:async()=>({header:{origin:'root',cwd:'/owner'},inheritedEventCount:0,events,cursor:10,source:'prepared',revision:'stable',[Symbol.dispose]:()=>{}})}};
  const tools=new Map<string,any>();const calls:any[]=[];let generation=1;
  const ctx={tools:{register:(tool:any)=>tools.set(tool.name,tool)}};
  const parent={id:'root',ctx:{tools:{get:()=>true}}};
  const host={nanoProduct:{call:async(method:string,args:unknown,exec:unknown)=>{calls.push({method,args,exec});return {messages:[{id:'original-message',content:'Historical original'}]};}}};
  const library={status:async()=>({generation,sourcesPending:false,sources:{revision:'r',allowed:['allowed'],excluded:['revoked']}})};
  const run={generation:1,target:{roots:{root:{through:9,time:109}},children:{}},batch:{ranges:[{sessionId:'root',through:9}],cutoffs:{root:109},units:[]},summaries:[]};
  const owner={activationAt:101,streams:{root:{baseline:0,cursor:0}}};
  registerDreamingHistory(ctx as never,host as never,parent as never,run as never,owner as never,library as never,new MemorySources(snapshots as never,new Map()),['allowed']);
  return {tools,calls,parent,revoke:()=>{generation++;}};
}

it('preserves native window/item identities, Unicode reads and source filtering before search or pagination',async()=>{
  const f=fixture();const query=(args:any)=>f.tools.get('source_history').execute({session_id:'root',...args});
  const windows=await query({action:'list_windows',recent_first:false});
  expect(windows.items.map((w:any)=>w.window_id)).toEqual(['root:initial','root:2']);
  expect(await query({action:'search',query:'SECRET'})).toMatchObject({items:[]});
  expect(await query({action:'search',query:'FUTURE'})).toMatchObject({items:[]});
  expect(await query({action:'search',query:'Before activation'})).toMatchObject({items:[]});
  const first=await query({action:'list_items',limit:1,recent_first:false});
  expect(first.items[0]).toMatchObject({item_id:'1',window_id:'root:initial',time:101,source:{actorId:'owner'}});
  expect(await query({action:'read',window_id:'root:initial',item_id:'1',offset_chars:1,limit_chars:2})).toMatchObject({content:'新😀',next_offset_chars:3});
  const next=await query({action:'list_items',limit:1,recent_first:false,cursor:first.next_cursor});
  expect(next.items[0]).toMatchObject({item_id:'5',window_id:'root:2'});
  await expect(query({action:'search',query:'changed',limit:1,recent_first:false,cursor:first.next_cursor})).rejects.toThrow('different source');
  const mixed=await query({action:'search',query:'Visible',role:'tool',tool_name:'conversations'});
  expect(mixed.items).toHaveLength(1);expect(JSON.stringify(mixed)).not.toContain('SECRET');
  await expect(query({action:'read',window_id:'root:2',item_id:'6'})).rejects.toThrow('not_found');
  await expect(query({action:'list_items',session_id:'foreign'})).rejects.toThrow('outside');
  f.revoke();await expect(query({action:'read',window_id:'root:initial',item_id:'1'})).rejects.toThrow('eligibility changed');
});

it('binds read-only IM history to the actual parent, frozen time and activation boundary',async()=>{
  const f=fixture();const exec={agent:{id:'maintenance'},signal:new AbortController().signal,callId:'read'};
  const tool=f.tools.get('conversations');
  expect(await tool.execute({action:'read',target:'allowed',limit:10},exec)).toMatchObject({messages:[{id:'original-message'}]});
  expect(f.calls).toEqual([{method:'memory.conversations',args:{action:'read',target:'allowed',limit:10,cutoff:109,afterTime:101},exec:{...exec,agent:f.parent}}]);
  await expect(tool.execute({action:'read',target:'foreign'},exec)).rejects.toThrow('outside');
  f.revoke();await expect(tool.execute({action:'search',target:'allowed',query:'condition'},exec)).rejects.toThrow('eligibility changed');
  expect(f.calls).toHaveLength(1);
});

it('allows bounded original evidence from a selected task descendant, but not an unrelated root child',async()=>{
  const item=(seq:number,time:number,type:string,data:unknown)=>({seq,time,type,data});
  const snapshots:Record<string,any>={
    task:{header:{id:'task',origin:'subagent',parentSession:'root'},inheritedEventCount:0,events:[item(0,110,'subagent/catalog',{childId:'deep',mode:'continuable',childCreatedAt:110})]},
    deep:{header:{id:'deep',origin:'subagent',parentSession:'task'},inheritedEventCount:0,events:[
      item(0,115,'user/message',{id:'request',source:{kind:'user'},content:[{type:'text',text:'Original delegated condition'}]}),item(1,120,'step/end',{}),
      item(2,160,'user/message',{id:'future',source:{kind:'user'},content:[{type:'text',text:'FUTURE descendant outcome'}]}),item(3,170,'step/end',{})]},
    unrelated:{header:{id:'unrelated',origin:'subagent',parentSession:'root'},inheritedEventCount:0,events:[]},
  };
  const tools=new Map<string,any>();
  const ctx={tools:{register:(tool:any)=>tools.set(tool.name,tool)}};
  const root={id:'root',ctx:{tools:{get:()=>false}}};
  const run={generation:1,target:{roots:{root:{through:10,time:150}},children:{task:{time:150}}},batch:{ranges:[],cutoffs:{},units:[]},summaries:[{sessionId:'task',rootSessionId:'root',baseline:-1,through:0}]};
  const owner={activationAt:100,streams:{root:{baseline:-1,cursor:0}}};
  const library={status:async()=>({generation:1,sourcesPending:false})};
  const sourceContext={sessions:{get:()=>undefined},sessionQuery:{observeSession:async(id:string)=>({...snapshots[id],source:'prepared',revision:'stable',[Symbol.dispose]:()=>{}})}};
  registerDreamingHistory(ctx as never,{} as never,root as never,run as never,owner as never,library as never,new MemorySources(sourceContext as never,new Map()),[]);
  const query=(args:any)=>tools.get('source_history').execute(args);
  const result=await query({action:'search',session_id:'deep',query:'condition'});
  expect(result.items).toHaveLength(1);expect(result.items[0]).toMatchObject({item_id:'0',time:115});
  expect(await query({action:'search',session_id:'deep',query:'FUTURE'})).toMatchObject({items:[]});
  await expect(query({action:'list_items',session_id:'unrelated'})).rejects.toThrow('Only descendants');
});
