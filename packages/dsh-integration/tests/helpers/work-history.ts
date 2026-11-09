import type { RuntimeWorkCatalog, RuntimeWorkChild, RuntimeWorkPage } from '@nano/product-contracts';

/** Collect pages for assertions. Production consumers commit each page independently. */
export async function workDescendants(rpc: {request(method:string, params:unknown):Promise<unknown>}, input: {
  sessionId:string; cursors?:Record<string,number>; modelVersions?:Record<string,string>; stoppedRevision?:number;
}) {
  const {sessionId, stoppedRevision}=input;
  const rows: (RuntimeWorkChild & Pick<RuntimeWorkPage,'events'|'modelRuns'>)[]=[];
  let afterId:string|undefined;
  do {
    const catalog=await rpc.request('session.work.children',{sessionId,afterId,stoppedRevision}) as RuntimeWorkCatalog;
    for (const child of catalog.children) {
      const row={...child,events:[] as RuntimeWorkPage['events'],modelRuns:[] as RuntimeWorkPage['modelRuns']};
      rows.push(row);
      if(child.kind!=='child')continue;
      let afterSeq=input.cursors?.[child.id], more:boolean;
      do {
        const page=await rpc.request('session.work.child',{sessionId,childId:child.id,afterSeq,stoppedRevision,
          modelVersion:input.modelVersions?.[child.id]}) as RuntimeWorkPage;
        afterSeq=row.throughSeq=page.throughSeq;
        row.modelVersion=page.modelVersion;
        row.events.push(...page.events);
        row.modelRuns.push(...page.modelRuns);
        more=page.more;
      } while(more);
    }
    afterId=catalog.next;
  } while(afterId!==undefined);
  return rows;
}
