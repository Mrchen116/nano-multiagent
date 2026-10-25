import {readFile, readdir} from 'node:fs/promises';
import {join} from 'node:path';

/** Refuse shared legacy homes until the offline migration has published its verified marker. */
export async function requireRuntimeLayout(home: string, nodeId: string): Promise<void> {
  try {
    const marker=JSON.parse(await readFile(join(home,'agent-runtime-layout.json'),'utf8')) as {version:number;nodeId:string};
    if(marker.version!==1||marker.nodeId!==nodeId)throw new Error('Invalid Agent runtime layout marker');
    return;
  } catch(error) { if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error; }
  for(const name of ['sessions','storages','schedules','exports','pa']) {
    const entries=await readdir(join(home,name)).catch(error=>{if(error.code==='ENOENT')return [];throw error;});
    if(entries.length)throw new Error('Agent runtime migration required: stop Node and run scripts/migrate-agent-runtime-partitions.ts plan/apply/verify before starting');
  }
  for(const name of ['.credentials.yaml','.env']) {
    try { await readFile(join(home,name)); }
    catch(error) { if((error as NodeJS.ErrnoException).code==='ENOENT')continue;throw error; }
    throw new Error('Agent runtime migration required: shared model credentials must move to the control host');
  }
}
