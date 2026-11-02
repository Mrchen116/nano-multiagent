import {mkdtemp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {expect,it} from 'vitest';
import {prepareProfile,RuntimeClient} from '../lib/client.js';
import {registerNoopTaskHosts} from './helpers/noop-task-hosts.js';

it('observes archived evidence without recovering absolute-path Dreaming jobs',async()=>{
  const home=await mkdtemp(join(tmpdir(),'nano-observation-'));
  const original=join(home,'original-evidence');
  let client:RuntimeClient|undefined;let logs='';
  try{
    await mkdir(original);await writeFile(join(original,'input.md'),'keep original');
    const domain=new URL('../lib/knowledge/dreaming-state.js',import.meta.url).href;
    await writeFile(join(home,'seed.mjs'),`import {writeFile} from 'node:fs/promises';
import {dreamingDomain} from ${JSON.stringify(domain)};
export const inject=['storageDomain'];
export async function apply(ctx){const domain=await ctx.storageDomain.open(dreamingDomain);
await domain.table('runs').put('b2xk',{id:'old',agentId:'a',rootSessionId:'root',stage:'extract',state:'completed',at:1,endedAt:1,planRetired:true,receipts:[],directory:${JSON.stringify(original)}});
await writeFile(process.env.DSH_HOME+'/seeded','done');}`);
    await prepareProfile(home,[{id:'nano-runtime',disabled:true},{insert:[{id:'seed',name:join(home,'seed.mjs')}]}]);
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text}});
    await expect.poll(()=>readFile(join(home,'seeded'),'utf8').catch(()=>logs),{timeout:5000}).toBe('done');
    client.process.kill('SIGKILL');await client.exited;client=undefined;
    await prepareProfile(home);
    const config={protocol:1,agents:[{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash'}],bindings:[],lifecycle:{a:{revision:1,disabled:true,disabledThroughRevision:1}}};
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text}});registerNoopTaskHosts(client);
    await expect(client.rpc.request('initialize',{...config,observationOnly:true,lifecycle:{}})).rejects.toThrow('requires disabled agents');
    await client.rpc.request('initialize',{...config,observationOnly:true});
    expect(await readFile(join(original,'input.md'),'utf8')).toBe('keep original');
    await client.shutdown();client=undefined;
    // The same persisted job really is recoverable: ordinary startup performs its cleanup.
    client=new RuntimeClient({home,cwd:home,onLog:text=>{logs+=text}});registerNoopTaskHosts(client);
    await client.rpc.request('initialize',config);
    await expect(readFile(join(original,'input.md'))).rejects.toMatchObject({code:'ENOENT'});
    await client.shutdown();client=undefined;
  }catch(error){throw new Error(String(error)+'\n'+logs,{cause:error})}
  finally{if(client){client.process.kill('SIGKILL');await client.exited}await rm(home,{recursive:true,force:true})}
},20000);
