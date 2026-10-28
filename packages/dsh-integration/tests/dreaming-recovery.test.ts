import {expect,it,vi} from 'vitest';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {Context} from '@deepseek-ai/cordis';
import {LocalFileSystem} from '@deepseek-ai/dsh-fs-local';
import {MemoryDocuments} from '../src/knowledge/memory-documents.js';
import {Dreaming} from '../src/knowledge/dreaming.js';

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
