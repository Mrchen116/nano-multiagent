import {execFileSync, spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {mkdtemp, mkdir, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {afterEach, expect, it} from 'vitest';
import {ConfigurationInspector, prepareProfile, RuntimeClient} from '../lib/client.js';

const cleanups: (()=>Promise<unknown>)[] = [];
afterEach(async()=>{for(const cleanup of cleanups.splice(0).reverse())await cleanup();});
async function fixture(timeoutMs=7000) {
  const home = await mkdtemp(join(tmpdir(),'nano-inspection-test-'));
  cleanups.push(()=>rm(home,{recursive:true,force:true}));
  const root=join(home,'inspections');
  const inspector=new ConfigurationInspector({root,timeoutMs,retryMs:10});
  cleanups.push(()=>inspector.close());
  const input={method:'catalog' as const,cwd:home,config:{agentId:'a',revision:'1',provider:'deepseek-official',model:'deepseek-flash'}};
  return {home,root,inspector,input};
}
async function waitForFile(path:string) {await expect.poll(async()=>readFile(path,'utf8').catch(()=>''),{timeout:5000}).not.toBe('');}

// Reparented exited workers may remain zombies until init reaps them on Linux.
// Only a non-zombie process can still execute or retain the resources we own.
function processAlive(pid: number): boolean {
  try {
    const state = execFileSync('ps', ['-p', String(pid), '-o', 'stat='], {encoding:'utf8'}).trim();
    return state.length > 0 && !state.startsWith('Z');
  } catch (error) {
    if ((error as {status?:number}).status === 1) return false;
    throw error;
  }
}

it('coalesces 30 native checks, lets one waiter cancel, and reclaims every temporary home',async()=>{
  const {root,inspector,input}=await fixture();
  const abort=new AbortController();
  const first=inspector.inspect(input,abort.signal);
  const rejected=expect(first).rejects.toMatchObject({code:'catalog_cancelled'});
  const others=Array.from({length:30},()=>inspector.inspect(input));
  abort.abort();await rejected;
  const results=await Promise.all(others);
  expect(results[0]).toMatchObject({tools:expect.any(Array)});
  expect(results.every(value=>value===results[0])).toBe(true);
  expect(inspector.metrics()).toMatchObject({preview_active:0,catalog_refresh_total:{current:1}});
  expect(await readdir(root)).toEqual([]);
},15000);

it('kills an event-loop-blocked plugin at the deadline, then reads again without restarting the execution runtime',async()=>{
  const {home,root,inspector,input}=await fixture(5000);
  await prepareProfile(join(home,'execution'));
  const runtime=new RuntimeClient({home:join(home,'execution'),cwd:home});
  cleanups.push(async()=>{runtime.process.kill('SIGKILL');await runtime.exited;});
  await runtime.rpc.request('initialize',{protocol:1,agents:[input.config],bindings:[]});
  const pid=runtime.process.pid;
  const plugin=join(home,'hang.mjs'),marker=join(home,'entered');
  await writeFile(plugin,`import {writeFileSync} from 'node:fs'; export const name='blocking-fixture'; export function apply(){writeFileSync(${JSON.stringify(marker)},'entered');while(true){}}`);
  const started=Date.now();
  const hung=inspector.inspect({...input,profilePatch:[{insert:[{id:'blocking-fixture',name:plugin}]}]});
  const rejected=expect(hung).rejects.toMatchObject({code:'catalog_timeout'});
  await waitForFile(marker);await rejected;
  expect(Date.now()-started).toBeLessThan(6500);
  expect(await readdir(root)).toEqual([]);
  expect(inspector.metrics().preview_active).toBe(0);
  await expect(inspector.inspect(input)).resolves.toMatchObject({tools:expect.any(Array)});
  await expect(runtime.rpc.request('configuration.catalog',{agentId:'a',cwd:home})).resolves.toMatchObject({tools:expect.any(Array)});
  expect(runtime.process.pid).toBe(pid);expect(runtime.process.exitCode).toBeNull();
},15000);

it('fences an in-flight generation and releases capacity after last-waiter cancellation',async()=>{
  const {home,root,inspector,input}=await fixture();
  const plugin=join(home,'hang.mjs'),marker=join(home,'entered');
  await writeFile(plugin,`import {writeFileSync} from 'node:fs';export const name='blocking-fixture';export function apply(){writeFileSync(${JSON.stringify(marker)},'entered');while(true){}}`);
  const old=inspector.inspect({...input,profilePatch:[{insert:[{id:'blocking-fixture',name:plugin}]}]});
  const rejected=expect(old).rejects.toMatchObject({code:'catalog_cancelled'});
  await waitForFile(marker);inspector.invalidate();
  const next=inspector.inspect(input);
  await rejected;await expect(next).resolves.toMatchObject({tools:expect.any(Array)});
  expect(await readdir(root)).toEqual([]);
  const controller=new AbortController();
  const cancelled=expect(inspector.inspect(input,controller.signal)).rejects.toMatchObject({code:'catalog_cancelled'});
  controller.abort();await cancelled;
  await expect.poll(()=>inspector.metrics().preview_active).toBe(0);
  expect(await readdir(root)).toEqual([]);
},15000);

it('reclaims a live blocked worker after SIGKILL of its owner, then successfully inspects again',async()=>{
  const {home,root,input}=await fixture();
  const plugin=join(home,'hang.mjs'),marker=join(home,'entered'),ownerFile=join(home,'owner.mjs');
  await writeFile(plugin,`import {writeFileSync} from 'node:fs';export const name='blocking-fixture';export function apply(){writeFileSync(${JSON.stringify(marker)},'entered');while(true){}}`);
  await writeFile(ownerFile,`import {ConfigurationInspector} from ${JSON.stringify(resolve('packages/dsh-integration/lib/client.js'))};const inspector=new ConfigurationInspector({root:${JSON.stringify(root)},timeoutMs:60000});await inspector.inspect(${JSON.stringify({...input,profilePatch:[{insert:[{id:'blocking-fixture',name:plugin}]}]})});`);
  const owner=spawn(process.execPath,[ownerFile],{stdio:'ignore'});
  const exited=new Promise(resolve=>owner.once('exit',resolve));
  cleanups.push(async()=>{owner.kill('SIGKILL');await exited;});
  await waitForFile(marker);
  const directories=await readdir(root);
  const lease=JSON.parse(await readFile(join(root,directories[0]!,'inspection.json'),'utf8'));
  cleanups.push(async()=>{try{process.kill(-lease.pid,'SIGKILL');}catch{}});
  owner.kill('SIGKILL');await exited;
  expect(()=>process.kill(lease.pid,0)).not.toThrow();
  const restarted=new ConfigurationInspector({root});cleanups.push(()=>restarted.close());
  await restarted.initialize();
  expect(processAlive(lease.pid)).toBe(false);
  expect(await readdir(root)).toEqual([]);
  expect(restarted.metrics().preview_orphan_total).toBe(1);
  await expect(restarted.inspect(input)).resolves.toMatchObject({tools:expect.any(Array)});
},15000);

it('retains an orphan with mismatched process identity and refuses new work',async()=>{
  const {root,inspector,input}=await fixture();const id=randomUUID(),home=join(root,`inspection-${id}-fixture`);
  await mkdir(home,{recursive:true});await writeFile(join(home,'inspection.json'),JSON.stringify({id,pid:process.pid}));
  await expect(inspector.initialize()).rejects.toMatchObject({code:'catalog_cleanup_failed'});
  await expect(inspector.inspect(input)).rejects.toMatchObject({code:'catalog_cleanup_failed'});
  expect(await readdir(root)).toEqual([`inspection-${id}-fixture`]);
});

it('reclaims a plugin child that ignores SIGTERM even after its worker leader exits',async()=>{
  const {home,root,inspector,input}=await fixture();
  const marker=join(home,'child-pid'),plugin=join(home,'child.mjs');
  const childSource=`import {writeFileSync} from 'node:fs';process.on('SIGTERM',()=>{});writeFileSync(${JSON.stringify(marker)},String(process.pid));setInterval(()=>{},1000);`;
  await writeFile(plugin,`import {execFileSync, spawn} from 'node:child_process';import {access} from 'node:fs/promises';export const name='child-fixture';export async function apply(){spawn(process.execPath,['--input-type=module','-e',${JSON.stringify(childSource)}],{stdio:'ignore'});while(!await access(${JSON.stringify(marker)}).then(()=>true,()=>false))await new Promise(r=>setTimeout(r,10));}`);
  const result=await inspector.inspect({...input,profilePatch:[{insert:[{id:'child-fixture',name:plugin}]}]});
  expect(result).toMatchObject({tools:expect.any(Array)});
  const pid=Number(await readFile(marker,'utf8'));
  cleanups.push(async()=>{try{process.kill(pid,'SIGKILL');}catch{}});
  expect(processAlive(pid)).toBe(false);
  expect(await readdir(root)).toEqual([]);
  expect(inspector.metrics().preview_active).toBe(0);
},15000);
