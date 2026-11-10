import {expect,it,vi} from 'vitest';
import {execFileSync} from 'node:child_process';
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
  const ctx={llm:{resolveModelInfo:async()=>({context:{contextWindow:256000}})},storageDomain:{open:async()=>({table:(name:string)=>{const rows=name==='owners'?owners:name==='runs'?runs:summaries;return {get:(id:string)=>rows.get(id),put:async(id:string,value:any)=>{rows.set(id,structuredClone(value));},entries:()=>rows.entries()};}})},
    on:()=>{},effect:(f:()=>()=>void)=>cleanup.push(f()),nanoTrajectoryRuns:{finishMaintenance:async()=>{}},sessions:{get:()=>undefined},sessionQuery:{}};
  const config={agentId:'a',revision:'1',workspace,provider:'fixture',model:'test'};
  const make=()=>new Dreaming(ctx as never,{forConfig:async()=>library} as never,{configOf:()=>config,configs:new Map([['a',config]]),bindings:new Map(),notify:()=>{}});
  const directory=join(workspace,'frozen');await mkdir(join(directory,'staging/knowledge'),{recursive:true});
  const lesson='One verified lesson, recorded once.';
  const originalPath='knowledge/old-lesson.md';
  // The destination is still only staged, so the existing page retains the lesson.
  await library.apply({operationId:'initial-lesson',path:originalPath,beforeHash:null,content:lesson});
  await writeFile(join(directory,'staging',originalPath),lesson);
  const versions=await library.versions();
  const output={'knowledge/lesson.md':lesson,'MEMORY.md':'# Memory\n[Lesson](knowledge/lesson.md)'};
  const plan=[];
  for(const [path,content] of Object.entries(output)){
    await writeFile(join(directory,'staging',path),content);
    plan.push({operationId:'frozen:'+path,path,beforeHash:versions[path]??null,afterHash:createHash('sha256').update(content).digest('hex')});
  }
  await writeFile(join(directory,'manifest.json'),JSON.stringify({versions}));
  runs.set('frozen',{id:'frozen',agentId:'a',rootSessionId:'s',mode:'manual',stage:'consolidate',cycleId:'cycle',state:'applying',at:Date.now(),generation:0,directory,
    batch:{id:'frozen',units:[{id:'unit',sessionId:'s',start:-1,through:1,events:[],fingerprints:['source:revision']}],ranges:[{sessionId:'s',start:-1,through:1,observed:1}],blocked:[],filtered:0,inputTokens:0},
    target:{roots:{},children:{},blocked:[],generation:0,activationAt:0},summaries:[],receipts:[],plan,sourcesChecked:true});
  return {workspace,library,owners,runs,make,ctx,lesson,originalPath,parent:{id:'s',ctx:{tools:{get:()=>true}}} as never,
    close:async()=>{for(const fn of cleanup)fn();await library.close();await rm(workspace,{recursive:true,force:true});}};
}

it.each(['generation','third-version'])('retires a stale %s plan without overwriting current documents',async reason=>{
  const f=await fixture();
  try{
    if(reason==='generation')f.runs.get('frozen').generation=-1;
    else await f.library.apply({operationId:'human',path:'knowledge/lesson.md',beforeHash:null,content:'Human correction survives.'});
    await f.library.checkpoint(await f.library.versions(),0);
    const d=f.make();await d.recover();
    expect(await d.start(f.parent,false)).toMatchObject({reason:'no_eligible_increment'});
    expect(f.runs.get('frozen')).toMatchObject({state:'failed',planRetired:true});
    expect(f.owners.get('YQ').streams.s.cursor).toBe(-1);
    if(reason==='third-version')expect(await readFile(join(f.library.root,'knowledge/lesson.md'),'utf8')).toBe('Human correction survives.');
  }finally{await f.close();}
});

it.each(['staging-only','published-body','committed-before-checkpoint'])('preserves real work without automatically completing an interrupted %s batch',async phase=>{
  const f=await fixture();
  try {
    const run=f.runs.get('frozen');
    const git=(...args:string[])=>execFileSync('git',args,{cwd:f.library.root,encoding:'utf8'}).trim();
    if(phase!=='staging-only'){
      const operation=run.plan[0];
      const receipt=await f.library.apply({...operation,content:f.lesson},0,undefined,{recordVersion:false});
      expect(receipt).toMatchObject({saved:true,versionRecorded:false});
      run.receipts=[receipt];
    }
    if(phase==='committed-before-checkpoint'){
      await f.library.commitBatch('Consolidate lesson',await f.library.versions(),0,new AbortController().signal);
      expect(git('log','-1','--format=%s')).toBe('Consolidate lesson');
    }
    const previousHead=git('rev-parse','HEAD');
    const restarted=f.make();
    await restarted.recover();
    expect(f.runs.get('frozen')).toMatchObject({state:phase==='staging-only'?'failed':'partial',planRetired:true});
    expect(f.owners.get('YQ').streams.s.cursor).toBe(-1);
    expect(f.owners.get('YQ').seen).toEqual([]);
    expect(git('rev-parse','HEAD')).toBe(previousHead);
    expect(await readFile(join(f.library.root,f.originalPath),'utf8')).toBe(f.lesson);
    const destination=readFile(join(f.library.root,'knowledge/lesson.md'),'utf8');
    if(phase==='staging-only')await expect(destination).rejects.toMatchObject({code:'ENOENT'});
    else await expect(destination).resolves.toBe(f.lesson);
    if(phase==='published-body'){
      expect(git('status','--porcelain','--untracked-files=all')).toContain('knowledge/lesson.md');
      expect(await restarted.status('a')).toMatchObject({backlog:{state:'pending'}});
    }else expect(git('status','--porcelain','--untracked-files=all')).toBe('');
  } finally { await f.close(); }
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
  const ctx={llm:{resolveModelInfo:async()=>({context:{contextWindow:256000}})},storageDomain:{open:async()=>({table:()=>({entries:()=>runs.entries(),put:async(id:string,value:any)=>{runs.set(id,structuredClone(value));}})})},
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


it('reports unavailable model capacity without advancing or guessing a default',async()=>{
  const f=await fixture();
  try{
    f.runs.clear();
    vi.spyOn(f.ctx.llm,'resolveModelInfo').mockResolvedValue({} as never);
    const dreaming=f.make();
    expect(await dreaming.status('a')).toMatchObject({backlog:{state:'model_capacity_unavailable',scope:'unavailable'}});
    expect(await dreaming.start(f.parent,false)).toMatchObject({state:'failed',reason:expect.stringContaining('declared model context')});
    expect(f.owners.get('YQ').streams.s.cursor).toBe(-1);
    expect(f.runs.size).toBe(0);
  }finally{await f.close();}
});
