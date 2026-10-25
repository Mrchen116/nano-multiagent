import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {expect,it} from 'vitest';
import {requireRuntimeLayout} from '../src/runtime-layout.js';
it('allows new isolated homes but requires a verified offline migration for legacy sessions',async()=>{
  const root=await mkdtemp(join(tmpdir(),'nano-agent-layout-'));
  try {
    await requireRuntimeLayout(root,'node');
    await mkdir(join(root,'sessions'));await writeFile(join(root,'sessions','saved.jsonl'),'original');
    await expect(requireRuntimeLayout(root,'node')).rejects.toThrow('migration required');
    await writeFile(join(root,'agent-runtime-layout.json'),JSON.stringify({version:1,nodeId:'other'}));
    await expect(requireRuntimeLayout(root,'node')).rejects.toThrow('Invalid');
    await writeFile(join(root,'agent-runtime-layout.json'),JSON.stringify({version:1,nodeId:'node'}));
    await requireRuntimeLayout(root,'node');
  } finally {await rm(root,{recursive:true,force:true});}
});
