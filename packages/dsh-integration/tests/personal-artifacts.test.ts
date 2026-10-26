import { mkdtemp, rm, writeFile, symlink, truncate } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { expect, it } from 'vitest';
import { registerTool } from '../src/personal-artifacts.js';

it('publishes actual bounded workspace bytes under host PA identity and refuses children and path escapes', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-artifact-'));
  const outside = await mkdtemp(join(tmpdir(), 'nano-outside-'));
  let tool: any;
  let personal = true;
  const calls: any[] = [];
  const receipt = {url:'/im/v1/conversations/owner/attachments/resource',sha256:'receipt-hash',version:1,receipt:{status:'stored'}};
  const ctx = {tools:{register(value: any){tool=value;}},nanoConfiguration:{forAgent:()=>({personal:personal?{ownerId:'owner'}:undefined,mode:'global',workspace:directory})},nanoProduct:{call:async (...args: any[])=>{calls.push(args);return receipt;}}};
  registerTool(ctx as any);
  const exec = {agent:{id:'root',session:{header:{origin:'root'}}},signal:new AbortController().signal,callId:'call'};
  try {
    await writeFile(join(directory,'plan.md'),'Actual contents');
    expect(await tool.execute({path:'plan.md',idempotency_key:'publish'},exec)).toEqual(receipt);
    expect(calls[0][0]).toBe('publish_artifact');
    expect(calls[0][1]).toEqual({file_name:'plan.md',content_type:'text/markdown',data_base64:Buffer.from('Actual contents').toString('base64'),sha256:createHash('sha256').update('Actual contents').digest('hex'),byte_size:15,idempotency_key:'publish'});
    await expect(tool.execute({path:'plan.md',idempotency_key:'child'}, {...exec,agent:{id:'child',session:{header:{origin:'subagent',parentSession:'root'}}}})).rejects.toThrow(/root/i);
    personal=false;
    await expect(tool.execute({path:'plan.md',idempotency_key:'ordinary'},exec)).rejects.toThrow(/personal/i);
    personal=true;
    await writeFile(join(outside,'secret.txt'),'Private');
    await symlink(outside,join(directory,'escape'));
    for (const path of [join(outside,'secret.txt'),'escape/secret.txt','../secret.txt']) await expect(tool.execute({path,idempotency_key:'escape'},exec)).rejects.toThrow();
    await writeFile(join(directory,'huge.txt'),''); await truncate(join(directory,'huge.txt'),10*1024*1024+1);
    await expect(tool.execute({path:'huge.txt',idempotency_key:'huge'},exec)).rejects.toThrow(/size|large|limit/i);
    expect(calls).toHaveLength(1);
  } finally { await rm(directory,{recursive:true,force:true}); await rm(outside,{recursive:true,force:true}); }
});
