/** Run from repository root with Node 24: node <this-file> seed|baseline|fixed|failure <fresh-output-directory>.
 * Uses synthetic public DSH persistence; never reads a production home.
 * Seed once, then benchmark each mode in a new RuntimeClient process.
 */
import { mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout } from 'node:timers/promises';
const root = process.cwd();
const { prepareProfile, RuntimeClient } = await import(pathToFileURL(join(root,'packages/dsh-integration/lib/client.js')));
const mode = process.argv[2], output = process.argv[3] && resolve(process.argv[3]);
if (!['seed','baseline','fixed','failure'].includes(mode) || !output) throw new Error('Usage: seed|baseline|fixed|failure <dedicated-output-directory>');
const home = join(output,'home'), result = join(output,`${mode}.json`);
if (mode === 'seed' && await stat(home).catch(()=>undefined)) throw new Error('Seed requires a fresh home; choose a new output directory');
if (await stat(result).catch(()=>undefined)) throw new Error('Result exists; choose a fresh output directory or preserve and move the prior result');
await mkdir(home,{recursive:true});
await prepareProfile(home,[{insert:[{id:'cold-history-probe',name:join(dirname(fileURLToPath(import.meta.url)),'cold-history-fixture.mjs')}]}]);
let logs='';
const client = new RuntimeClient({home,cwd:home,env:{PROBE_MODE:mode,PROBE_RESULT:result,PROBE_CHILDREN:process.env.PROBE_CHILDREN??'400',PROBE_PREFIX:process.env.PROBE_PREFIX??'2000',PROBE_READER:join(root,'packages/dsh-integration/lib/descendants.js')},onLog:text=>{logs+=text;}});
try {
  const binding={sessionId:'probe-root',agentId:'probe',revision:'1',ownerId:'owner',cwd:home};
  await client.rpc.request('initialize',{protocol:1,agents:[{agentId:'probe',revision:'1',provider:'deepseek-official',model:'deepseek-flash',toolAllowlist:[],knowledge:{enabled:false}}],bindings:[binding]});
  await client.rpc.request('session.ensure',binding);
  let payload;
  for(let i=0;i<1200;i++){try{payload=await readFile(result,'utf8');break;}catch{await setTimeout(500);}}
  if(!payload)throw new Error('No result within ten minutes');
  console.log(payload);
  if(JSON.parse(payload).error)throw new Error('Fixture failed; see result JSON');
} finally {
  await writeFile(join(output,`${mode}.log`),logs);
  if(client.process.exitCode===null)await client.shutdown();
}
