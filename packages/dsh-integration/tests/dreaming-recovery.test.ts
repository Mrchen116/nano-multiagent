import {expect,it,vi} from 'vitest';
import {mkdtemp,rm,readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {Context} from '@deepseek-ai/cordis';
import {LocalFileSystem} from '@deepseek-ai/dsh-fs-local';
import {MemoryDocuments} from '../src/knowledge/memory-documents.js';
import {Dreaming} from '../src/knowledge/dreaming.js';
import {Session,SessionId} from '@deepseek-ai/dsh-session';
import {createUserMessage} from '@deepseek-ai/dsh-llm';
import {foldSubagentDescriptor} from '@deepseek-ai/dsh-subagent';

async function fixture(){
  const workspace=await mkdtemp(join(tmpdir(),'dreaming-recovery-'));
  const library=await MemoryDocuments.open(workspace,'expert',new LocalFileSystem(new Context(),{cwd:workspace,diffBasisMaxBytes:10485760}));
  const owners=new Map<string,any>([['YQ',{protocol:2,activationAt:0,streams:{s:{baseline:-1,cursor:-1}},seen:[],integrated:{},rotation:0,failures:0}]]);
  const runs=new Map<string,any>();const summaries=new Map();const cleanup:Array<()=>void>=[];
  const ctx={storageDomain:{open:async()=>({table:(name:string)=>{const rows=name==='owners'?owners:name==='runs'?runs:summaries;return {get:(id:string)=>rows.get(id),put:async(id:string,value:any)=>{rows.set(id,structuredClone(value));},entries:()=>rows.entries()};}})},
    on:()=>{},effect:(f:()=>()=>void)=>cleanup.push(f()),nanoTrajectoryRuns:{finishMaintenance:async()=>{}},sessions:{get:()=>undefined},sessionQuery:{}};
  const config={agentId:'a',revision:'1',workspace,provider:'fixture',model:'test'};
  const make=()=>new Dreaming(ctx as never,{forConfig:async()=>library} as never,{configOf:()=>config,configs:new Map([['a',config]]),bindings:new Map(),notify:()=>{}});
  const directory=join(workspace,'frozen');await mkdir(join(directory,'staging/knowledge'),{recursive:true});
  const versions=await library.versions();
  const output={'knowledge/lesson.md':'One verified lesson, recorded once.','MEMORY.md':'# Memory\n[Lesson](knowledge/lesson.md)'};
  const plan=[];
  for(const [path,content] of Object.entries(output)){
    await writeFile(join(directory,'staging',path),content);
    plan.push({operationId:'frozen:'+path,path,beforeHash:versions[path]??null,afterHash:createHash('sha256').update(content).digest('hex')});
  }
  await writeFile(join(directory,'manifest.json'),JSON.stringify({versions}));
  runs.set('frozen',{id:'frozen',agentId:'a',rootSessionId:'s',mode:'manual',stage:'consolidate',cycleId:'cycle',state:'applying',at:Date.now(),generation:0,directory,
    batch:{id:'frozen',units:[{id:'unit',sessionId:'s',start:-1,through:1,events:[],fingerprints:['source:revision']}],ranges:[{sessionId:'s',start:-1,through:1,observed:1}],blocked:[],filtered:0,inputTokens:0},
    target:{roots:{},children:{},blocked:[],generation:0,activationAt:0},summaries:[],receipts:[],plan,sourcesChecked:true});
  return {workspace,library,owners,runs,make,parent:{id:'s',ctx:{tools:{get:()=>true}}} as never,
    close:async()=>{for(const fn of cleanup)fn();await library.close();await rm(workspace,{recursive:true,force:true});}};
}

it.each(['generation','third-version'])('retires a stale %s plan without overwriting current documents',async reason=>{
  const f=await fixture();
  try{
    if(reason==='generation')f.runs.get('frozen').generation=-1;
    else await f.library.apply({operationId:'human',path:'knowledge/lesson.md',beforeHash:null,content:'Human correction survives.'});
    await f.library.checkpoint(await f.library.versions(),0);
    const d=f.make();
    expect(await d.start(f.parent,false)).toMatchObject({reason:'no_eligible_increment'});
    expect(f.runs.get('frozen')).toMatchObject({state:'failed',planRetired:true});
    expect(f.owners.get('YQ').streams.s.cursor).toBe(-1);
    if(reason==='third-version')expect(await readFile(join(f.library.root,'knowledge/lesson.md'),'utf8')).toBe('Human correction survives.');
  }finally{await f.close();}
});

it.each(['before-first-file','after-body','after-entry'])('resumes a persisted plan after interruption %s without duplicate application',async phase=>{
  const f=await fixture();let fired=false,calls=0;
  const apply=f.library.apply.bind(f.library);
  const fault=vi.spyOn(f.library,'apply').mockImplementation(async(...args)=>{
    calls++;
    if(phase==='before-first-file'&&!fired){fired=true;throw new Error('Interrupted before first application');}
    const receipt=await apply(...args);
    if(phase==='after-body'&&!fired){fired=true;throw new Error('Interrupted after body before run receipt');}
    return receipt;
  });
  const checkpoint=f.library.checkpoint.bind(f.library);
  const checkpointFault=vi.spyOn(f.library,'checkpoint').mockImplementation(async(...args)=>{
    if(phase==='after-entry'&&!fired){fired=true;throw new Error('Interrupted after entry before checkpoint');}
    return checkpoint(...args);
  });
  try{
    const first:any=await f.make().start(f.parent,false);
    expect(['partial','failed']).toContain(first.state);expect(f.owners.get('YQ').streams.s.cursor).toBe(-1);
    const receipts=(await f.library.status()).receipts.filter(r=>r.saved);
    const restarted=f.make();await restarted.recover();
    expect(await restarted.start(f.parent,false)).toMatchObject({state:'completed'});
    expect(f.owners.get('YQ').streams.s.cursor).toBe(1);expect(f.owners.get('YQ').seen).toEqual(['source:revision']);
    expect(await readFile(join(f.library.root,'knowledge/lesson.md'),'utf8')).toBe('One verified lesson, recorded once.');
    for(const receipt of receipts)expect((await f.library.status()).receipts.find(r=>r.operationId===receipt.operationId)).toEqual(receipt);
    const priorCalls=calls;
    expect(await restarted.start(f.parent,false)).toMatchObject({reason:'no_eligible_increment'});expect(calls).toBe(priorCalls);
    f.owners.get('YQ').streams.s.cursor=-1;
    await restarted.recover();expect(f.owners.get('YQ').streams.s.cursor).toBe(1);
  }finally{fault.mockRestore();checkpointFault.mockRestore();await f.close();}
});

it.each([false,true])('repairs only a recorded legacy Dreaming identity, preserving its original events (wrongParent=%s)',async wrongParent=>{
  const id=SessionId('dreaming-old');
  const session=Session.create(id,[],{...Session.create(id).header,cwd:'/test',origin:'subagent',parentSession:SessionId(wrongParent?'other':'root')});
  session.append('user/message',createUserMessage({content:[{type:'text',text:'Original frozen source manifest'}]}),{surfaceOp:'append'});
  const events=[...session.snapshotEvents()];const original=JSON.stringify(events);
  const run:any={id:'old',agentId:'a',rootSessionId:'root',childSessionId:id,mode:'automatic',state:'failed',at:Date.now(),directory:'/unused',generation:0,
    batch:{id:'old',units:[],ranges:[],blocked:[],filtered:0,inputTokens:0},receipts:[],reviewed:[]};
  const runs=new Map([['old',run]]);const cleanup:Array<()=>void>=[];let durable=false;
  const handle={header:session.header,inheritedEventCount:0,read:async()=>({events}),append:async(batch:any[])=>{events.push(...batch);},flush:async()=>{durable=true;},[Symbol.asyncDispose]:async()=>{}};
  const ctx={storageDomain:{open:async()=>({table:()=>({entries:()=>runs.entries(),put:async(id:string,value:any)=>{runs.set(id,structuredClone(value));}})})},
    sessionPersistence:{stat:async()=>({header:session.header}),open:async()=>handle},on:()=>{},effect:(f:()=>()=>void)=>cleanup.push(f())};
  const dreaming=new Dreaming(ctx as never,{} as never,{configOf:()=>undefined,configs:new Map(),bindings:new Map(),notify:()=>{}});
  try{
    if(wrongParent){
      await expect(dreaming.recover()).rejects.toThrow('does not match');
      expect(JSON.stringify(events)).toBe(original);expect(durable).toBe(false);
    }else{
      await dreaming.recover();
      expect(JSON.stringify(events.slice(0,-1))).toBe(original);
      expect(events.at(-1)).toMatchObject({type:'subagent/descriptor',seq:JSON.parse(original).length});
      expect(events.at(-1)).not.toHaveProperty('surfaceOp');
      expect(foldSubagentDescriptor(events)).toMatchObject({mode:'one-shot',provider:'native'});
      expect(durable).toBe(true);expect(runs.get('old')).toMatchObject({identityRecorded:true,state:'failed',receipts:[]});
      const repaired=JSON.stringify(events);
      await dreaming.recover();expect(JSON.stringify(events)).toBe(repaired);
    }
  }finally{for(const close of cleanup)close();}
});
