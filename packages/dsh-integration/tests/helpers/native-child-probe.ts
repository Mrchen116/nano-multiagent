import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

export const childProbe = {id:'native-child-probe', name:fileURLToPath(new URL('./native-child-probe.mjs', import.meta.url))};

type Child = {id:string; parentId:string; events:{type:string; data:any; surfaceOp?:unknown}[]};

/** Observe child behavior independently of whether it has a user-readable Work trace. */
export async function nativeChildren(home:string):Promise<Child[]> {
  const log = await readFile(join(home,'native-child-events.jsonl'),'utf8').catch(error => {
    if (error.code !== 'ENOENT') throw error;
    return '';
  });
  const children = new Map<string,Child>();
  for (const line of log.trimEnd().split('\n').filter(Boolean)) {
    const {id,parentId,event} = JSON.parse(line);
    const child = children.get(id) ?? {id,parentId,events:[]};
    child.events.push(event);
    children.set(id,child);
  }
  return [...children.values()];
}
