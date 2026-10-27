import { writeFile } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import { performance } from 'node:perf_hooks';
export const name = 'cold-history-probe';
export const inject = ['sessions', 'sessionQuery', 'sessionPersistence', 'subagents'];
export function apply(ctx) {
  ctx.on('agent/created', async ({agent}) => {
    if (agent.id !== 'probe-root') return;
    try {
      const root = agent.session;
      const count = Number(process.env.PROBE_CHILDREN ?? 400);
      const prefixCount = Number(process.env.PROBE_PREFIX ?? 2000);
      const mode = process.env.PROBE_MODE;
      if (mode === 'seed') {
        const begun = performance.now();
        for (let i = 0; i < prefixCount; i++) root.append('user/message', { id: `history-${i}`, role:'user',source: {kind:'user'}, content: [{type:'text',text:randomBytes(192).toString('base64')}] }, {surfaceOp:'append'});
        const seed = root.snapshotEvents();
        for (let i = 0; i < count; i++) {
          const id = `probe-child-${i}`;
          const child = ctx.sessions.prepare(id, { seed, inheritedEventCount: seed.length, meta: {cwd:root.header.cwd,parentSession:root.id,isSeeded:true,origin:'subagent',delegationDepth:1} });
          child.append('turn/start', {turn:1});
          child.append('subagent/descriptor', {version:0,provider:'spawn',mode:'one-shot',label:`Child ${i}`});
          child.append('user/message', {id:`input-${i}`,role:'user',source:{kind:'user'},content:[{type:'text',text:`Synthetic child ${i}`}]}, {surfaceOp:'append'});
          child.append('turn/end', {turn:1,reason:{kind:'completed'}});
          await using handle = await ctx.sessionPersistence.create(child.header, {inheritedEventCount:seed.length});
          await handle.append(child.snapshotEvents());
          await handle.flush();
          root.append('subagent/catalog', {version:0,childId:id,childCreatedAt:child.header.createdAt,mode:'one-shot',label:`Child ${i}`});
        }
        if (!await ctx.sessions.flush(root)) throw new Error('root flush failed');
        await writeFile(process.env.PROBE_RESULT, JSON.stringify({mode,count,prefixCount,seedMs:performance.now()-begun}));
        return;
      }
      let reads = 0, stats = 0, observes = 0;
      const persistence = ctx.sessionPersistence;
      const originalOpen = persistence.open.bind(persistence);
      persistence.open = async (...args) => {
        const handle = await originalOpen(...args);
        const read = handle.read.bind(handle);
        handle.read = async (...args) => { reads++; return read(...args); };
        return handle;
      };
      const stat = persistence.stat.bind(persistence);
      persistence.stat = async (...args) => {stats++;return stat(...args);};
      const observe = ctx.sessionQuery.observeSession.bind(ctx.sessionQuery);
      ctx.sessionQuery.observeSession = async (...args) => {observes++;return observe(...args);};
      const measure = async (label, run) => {
        reads = stats = observes = 0;
        const cpu = process.cpuUsage(), begin = performance.now();
        const rows = await run();
        const usage = process.cpuUsage(cpu);
        return {label,ms:performance.now()-begin,cpuMs:(usage.user+usage.system)/1000,reads,stats,observes,children:rows.filter(row=>row.kind==='child').length,events:rows.reduce((n,row)=>n+(row.events?.length??0),0),rows};
      };
      const baseline = async () => {
        const children = await ctx.subagents.listDescendants(root.id), rows = [];
        for (const child of children) {
          if(child.kind!=='child'){rows.push(child);continue;}
          using observation = await ctx.sessionQuery.observeSession(child.id);
          rows.push({...child,throughSeq:observation.cursor,events:observation.events.slice(observation.inheritedEventCount)});
        }
        return rows;
      };
      const results = [];
      if(mode === 'baseline') {
        for(let i=0;i<3;i++) results.push(await measure(i===0?'first':'repeat-'+i,baseline));
        if(results.some(result=>result.children!==count))throw new Error('Baseline dataset child count mismatch');
      } else if(mode === 'failure') {
        const {DescendantReader} = await import(process.env.PROBE_READER);
        const reader = new DescendantReader(ctx), cursors = {};
        const initial = await measure('prime-reader',()=>reader.read(root.id,cursors));results.push(initial);
        for(const row of initial.rows)if(row.throughSeq!==undefined)cursors[row.id]=row.throughSeq;
        const id='probe-child-0', confirmed=cursors[id];
        {
          await using handle = await persistence.open(id,'write');
          const {events}=await handle.read();
          await handle.append([{seq:events.length,time:Date.now(),type:'user/message',surfaceOp:'append',data:{id:'failure-retry',role:'user',source:{kind:'user'},content:[{type:'text',text:'RETRY_VISIBLE'}]}}]);await handle.flush();
        }
        let fail=true;
        ctx.sessionQuery.observeSession=async (...args)=>{
          observes++;
          if(args[0]===id&&fail){fail=false;throw Object.assign(new Error('Controlled temporary read failure'),{code:'SESSION_QUERY_PERSISTENCE_FAILED'});}
          return observe(...args);
        };
        const failed=await measure('failed-child-read',()=>reader.read(root.id,cursors));results.push(failed);
        for(const row of failed.rows)if(row.throughSeq!==undefined)cursors[row.id]=row.throughSeq;
        const unchangedCursor=cursors[id]===confirmed;
        const retried=await measure('retry-child-read',()=>reader.read(root.id,cursors));results.push(retried);
        results.push({checks:{diagnostic:failed.rows.some(row=>row.id===id&&row.kind==='diagnostic'&&row.reason==='unavailable'),unchangedCursor,retryVisible:retried.rows.find(row=>row.id===id)?.events.some(event=>event.data.id==='failure-retry')??false}});
      } else {
        const {DescendantReader} = await import(process.env.PROBE_READER);
        let reader = new DescendantReader(ctx);
        let cursors = {};
        const saveCursors = rows => { for(const row of rows) if(row.throughSeq!==undefined)cursors[row.id]=row.throughSeq; };
        const first = await measure('first',()=>reader.read(root.id,cursors));results.push(first);saveCursors(first.rows);
        for(let i=1;i<=3;i++) {const result=await measure('repeat-'+i,()=>reader.read(root.id,cursors));results.push(result);saveCursors(result.rows);}
        const changedId = 'probe-child-0';
        await using handle = await persistence.open(changedId,'write');
        const {events} = await handle.read();
        const mutation = {seq:events.length,time:Date.now(),type:'user/message',data:{id:'update',role:'user',source:{kind:'user'},content:[{type:'text',text:'UPDATED_CHILD'}]},surfaceOp:'append'};
        await handle.append([mutation]);await handle.flush();
        const updated = await measure('one-updated',()=>reader.read(root.id,cursors));results.push(updated);saveCursors(updated.rows);
        const updateVisible = updated.rows.find(row=>row.id===changedId)?.events.some(event=>event.data.id==='update')??false;
        const unchangedSiblings = updated.rows.filter(row=>row.id!==changedId).every(row=>row.events?.length===0);
        const createExtra = async (id,parentId,depth) => {
          const child = ctx.sessions.prepare(id,{meta:{cwd:root.header.cwd,parentSession:parentId,isSeeded:false,origin:'subagent',delegationDepth:depth}});
          child.append('turn/start',{turn:1});
          child.append('subagent/descriptor',{version:0,provider:'spawn',mode:'one-shot',label:id});
          child.append('user/message',{id:'extra-'+id,role:'user',source:{kind:'user'},content:[{type:'text',text:id}]},{surfaceOp:'append'});
          child.append('turn/end',{turn:1,reason:{kind:'completed'}});
          await using extraHandle = await persistence.create(child.header);
          await extraHandle.append(child.snapshotEvents());await extraHandle.flush();
          return {version:0,childId:id,childCreatedAt:child.header.createdAt,mode:'one-shot',label:id};
        };
        root.append('subagent/catalog',await createExtra('probe-new-child',root.id,1));
        await ctx.sessions.flush(root);
        const grandchild = await createExtra('probe-grandchild',changedId,2);
        await handle.append([{seq:mutation.seq+1,time:Date.now(),type:'subagent/catalog',data:grandchild}]);await handle.flush();
        const added = await measure('new-child-and-grandchild',()=>reader.read(root.id,cursors));results.push(added);saveCursors(added.rows);
        const newVisible = added.rows.some(row=>row.id==='probe-new-child'&&row.parentId===root.id&&row.events?.length===4);
        const nestedVisible = added.rows.some(row=>row.id==='probe-grandchild'&&row.parentId===changedId&&row.depth===2&&row.events?.length===4);
        reader = new DescendantReader(ctx);
        const restored = await measure('new-reader-with-cursors',()=>reader.read(root.id,cursors));results.push(restored);
        const replay = await measure('new-consumer-full-replay',()=>reader.read(root.id,{}));results.push(replay);
        results.push({checks:{updateVisible,unchangedSiblings,newVisible,nestedVisible,restartEmpty:restored.events===0,fullReplay:replay.children===count+2&&replay.events>count}});
      }
      if(results.some(result=>result.checks&&Object.values(result.checks).some(ok=>!ok)))throw new Error('Probe correctness check failed');
      await writeFile(process.env.PROBE_RESULT, JSON.stringify({mode,count,prefixCount,node:process.version,results:results.map(({rows,...result})=>result)},null,2));
    } catch(error) {await writeFile(process.env.PROBE_RESULT,JSON.stringify({error:String(error),stack:error.stack},null,2));}
  });
}
