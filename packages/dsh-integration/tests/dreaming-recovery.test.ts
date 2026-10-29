import {expect,it,vi} from 'vitest';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {Context} from '@deepseek-ai/cordis';
import {LocalFileSystem} from '@deepseek-ai/dsh-fs-local';
import {MemoryDocuments} from '../src/knowledge/memory-documents.js';
import {Dreaming} from '../src/knowledge/dreaming.js';
import {Session,SessionId} from '@deepseek-ai/dsh-session';
import {createUserMessage} from '@deepseek-ai/dsh-llm';
import {foldSubagentDescriptor} from '@deepseek-ai/dsh-subagent';

it.each(['generation','third-version'])('retires a stale %s plan and processes the same backlog against current files',async reason=>{
  const workspace=await mkdtemp(join(tmpdir(),'dreaming-recovery-'));
  const library=await MemoryDocuments.open(workspace,'expert',new LocalFileSystem(new Context(),{cwd:workspace,diffBasisMaxBytes:10485760}));
  const owner={activationAt:0,streams:{s:{baseline:-1,cursor:-1}},seen:[],rotation:0,failures:0};
  const prior=await library.apply({operationId:'human',path:'knowledge/p.md',beforeHash:null,content:'Human correction survives.'});
  const stale:any={id:'stale',agentId:'a',rootSessionId:'s',mode:'manual',state:'partial',at:0,generation:reason==='generation'?-1:0,directory:join(workspace,'stale'),
    batch:{id:'stale',units:[],ranges:[],blocked:[],filtered:0,inputTokens:0},receipts:[prior],reviewed:[],plan:[{operationId:'old',path:'knowledge/p.md',beforeHash:null,afterHash:'oldhash'}]};
  const owners=new Map([['YQ',owner]]),runs=new Map([['stale',stale]]); const cleanup:Array<()=>void>=[];
  const ctx={storageDomain:{open:async()=>({table:(name:string)=>{const rows=name==='owners'?owners:runs;return {get:(id:string)=>rows.get(id),put:async(id:string,value:any)=>{rows.set(id,structuredClone(value));},entries:()=>rows.entries()};}})},on:()=>{},effect:(f:()=>()=>void)=>cleanup.push(f()),nanoTrajectoryRuns:{finishMaintenance:async()=>{}}};
  const config={agentId:'a',revision:'1',workspace,provider:'fixture',model:'test'};
  const documents={forConfig:async()=>library};
  const d=new Dreaming(ctx as never,documents as never,{configOf:()=>config,configs:new Map([['a',config]]),bindings:new Map(),notify:()=>{}});
  const internals=d as any;
  vi.spyOn(internals.sources,'baseline').mockResolvedValue({});
  vi.spyOn(internals.sources,'freeze').mockResolvedValue({id:'fresh',units:[{id:'unit',sessionId:'s',start:-1,through:1,events:[],fingerprints:[]}],ranges:[{sessionId:'s',start:-1,through:1,observed:1}],blocked:[],filtered:0,inputTokens:0});
  const model=vi.spyOn(internals,'model').mockImplementation(async(_p,_c,_w,run:any)=>{run.plan=[];run.reviewed=['unit'];});
  try {
    const result:any=await d.start({ctx:{tools:{get:()=>true}}} as never,false,'request');
    expect(result.state).toBe('completed');expect(model).toHaveBeenCalledOnce();
    expect(runs.get('stale')).toMatchObject({state:'failed',receipts:[prior]});
    expect(await readFile(join(library.root,'knowledge/p.md'),'utf8')).toBe('Human correction survives.');
    expect(owners.get('YQ')!.streams.s.cursor).toBe(1);
    // Replaying completed receipt metadata after restart never reruns the model.
    owners.get('YQ')!.streams.s.cursor=-1;
    await d.recover();expect(owners.get('YQ')!.streams.s.cursor).toBe(1);expect(model).toHaveBeenCalledOnce();
  } finally {for(const fn of cleanup)fn();await library.close();await rm(workspace,{recursive:true,force:true});}
});

it.each(['before-first-file','after-body','after-entry'])('resumes the frozen plan after interruption %s without rewriting saved bytes',async phase=>{
  const workspace=await mkdtemp(join(tmpdir(),'dreaming-apply-recovery-'));
  const library=await MemoryDocuments.open(workspace,'expert',new LocalFileSystem(new Context(),{cwd:workspace,diffBasisMaxBytes:10485760}));
  const owner={activationAt:0,streams:{s:{baseline:-1,cursor:-1}},seen:[],rotation:0,failures:0};
  const owners=new Map<string,any>([['YQ',owner]]),runs=new Map<string,any>();const cleanup:Array<()=>void>=[];
  const ctx={storageDomain:{open:async()=>({table:(name:string)=>{const rows=name==='owners'?owners:runs;return {get:(id:string)=>rows.get(id),put:async(id:string,value:any)=>{rows.set(id,structuredClone(value));},entries:()=>rows.entries()};}})},on:()=>{},effect:(f:()=>()=>void)=>cleanup.push(f()),nanoTrajectoryRuns:{finishMaintenance:async()=>{}}};
  const config={agentId:'a',revision:'1',workspace,provider:'fixture',model:'test'};
  const make=()=>new Dreaming(ctx as never,{forConfig:async()=>library} as never,{configOf:()=>config,configs:new Map([['a',config]]),bindings:new Map(),notify:()=>{}});
  const d=make();const internals=d as any;
  vi.spyOn(internals.sources,'baseline').mockResolvedValue({});
  vi.spyOn(internals.sources,'freeze').mockResolvedValue({id:'frozen',units:[{id:'unit',sessionId:'s',start:-1,through:1,events:[],fingerprints:['source:revision']}],ranges:[{sessionId:'s',start:-1,through:1,observed:1}],blocked:[],filtered:0,inputTokens:0});
  const {createHash}=await import('node:crypto');const {writeFile,mkdir}=await import('node:fs/promises');
  const model=vi.spyOn(internals,'model').mockImplementation(async(_p,_c,_w,run:any)=>{
    const versions=await library.versions();
    const output={'knowledge/lesson.md':'One verified lesson, recorded once.','MEMORY.md':'# Memory\n[Lesson](knowledge/lesson.md)'};
    await mkdir(join(run.directory,'staging/knowledge'),{recursive:true});
    run.plan=[];run.reviewed=['unit'];
    for(const [path,content] of Object.entries(output)){
      await writeFile(join(run.directory,'staging',path),content);
      run.plan.push({operationId:'frozen:'+path,path,beforeHash:versions[path]??null,afterHash:createHash('sha256').update(content).digest('hex')});
    }
  });
  const apply=library.apply.bind(library);let calls=0;let fired=false;
  const fault=vi.spyOn(library,'apply').mockImplementation(async(...args)=>{
    calls++;
    if(phase==='before-first-file'&&!fired){fired=true;throw new Error('Interrupted before first application');}
    const receipt=await apply(...args);
    if(phase==='after-body'&&calls===1){fired=true;throw new Error('Interrupted after saved body, before run receipt');}
    return receipt;
  });
  const checkpoint=library.checkpoint.bind(library);
  const checkpointFault=vi.spyOn(library,'checkpoint').mockImplementation(async(...args)=>{
    if(phase==='after-entry'&&!fired){fired=true;throw new Error('Interrupted after entry, before checkpoint');}
    return checkpoint(...args);
  });
  const parent={ctx:{tools:{get:()=>true}}} as never;
  try{
    expect(await d.start(parent,false)).toMatchObject({state:'partial'});expect(owners.get('YQ').streams.s.cursor).toBe(-1);
    const savedBefore=(await library.status()).receipts.filter(receipt=>receipt.saved);
    const restarted=make();const noModel=vi.spyOn(restarted as any,'model');
    await restarted.recover();
    expect(await restarted.start(parent,false)).toMatchObject({state:'completed'});
    expect(model).toHaveBeenCalledOnce();expect(noModel).not.toHaveBeenCalled();
    expect(owners.get('YQ').streams.s.cursor).toBe(1);expect(owners.get('YQ').seen).toEqual(['source:revision']);
    expect(await readFile(join(library.root,'knowledge/lesson.md'),'utf8')).toBe('One verified lesson, recorded once.');
    for(const receipt of savedBefore)expect((await library.status()).receipts.find(item=>item.operationId===receipt.operationId)).toEqual(receipt);
    const beforeNoIncrement=calls;
    vi.spyOn((restarted as any).sources,'baseline').mockResolvedValue({});
    vi.spyOn((restarted as any).sources,'freeze').mockResolvedValue({id:'empty',units:[],ranges:[],blocked:[],filtered:0,inputTokens:0});
    expect(await restarted.start(parent,false)).toEqual({completed:false,reason:'no_eligible_increment',blocked:[]});
    expect(calls).toBe(beforeNoIncrement);expect(noModel).not.toHaveBeenCalled();
  }finally{fault.mockRestore();checkpointFault.mockRestore();for(const fn of cleanup)fn();await library.close();await rm(workspace,{recursive:true,force:true});}
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
