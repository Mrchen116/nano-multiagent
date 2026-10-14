import { createServer } from 'node:http';
import { execFile, execFileSync, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { chmod, mkdtemp, mkdir, readFile, rm, writeFile, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { expect, it } from 'vitest';
import { gatewayState, processBirth } from '../src/lifecycle.js';
import type { NodeUpdateOperation, ReleaseManifest } from '@nano/product-contracts';
const exec = promisify(execFile);
const moduleUrl = (name: string) => JSON.stringify(pathToFileURL(resolve(`apps/node/lib/${name}.js`)).href);

it.each([false, true])('switches actual detached processes and verifies %s rollback (runtime fixture)', async (fail) => {
  const home = await realpath(await mkdtemp(join(tmpdir(), 'nano-process-update-')));
  const oldRoot = join(home, 'releases', 'b'.repeat(64));
  const config = join(home, 'connections/test/config.yaml');
  let operation: NodeUpdateOperation;
  const phases: string[] = [];
  const server = createServer((req, res) => { let body = ''; req.on('data', b => body += b); req.on('end', () => { void (async () => {
    const request = JSON.parse(body);
    if (request.action === 'progress' || request.action === 'terminal') { operation.state = request.state; phases.push(request.state); }
    if (request.action === 'prepare') operation.relay_gated = true;
    if (request.action === 'resume') operation.relay_gated = false;
    if (request.action === 'claim_switch') {operation.state = 'switching'; phases.push('switching');}
    const state = await gatewayState(config);
    res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({operation, registered: {online: !!state?.connected, release: state?.release ?? null}}));
  })().catch(e => {res.statusCode = 500;res.end(String(e));}); }); });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const port = (server.address() as {port: number}).port;
  const bin = join(home, 'bin');
  const cli = join(oldRoot, 'apps/node/lib/cli.js');
  const environment = {...process.env, PATH: `${bin}:${process.env.PATH}`};
  const runCli = (...args: string[]) => exec(process.execPath, [cli, ...args, '--config', config], {env: environment, timeout: 15000});
  // This fixture uses real OS processes, lifecycle stop, controller lease and detached worker.
  // Runtime/registration readiness is deliberately simulated; full DSH is covered by stack acceptance.
  const program = `
import {readFile,rm} from 'node:fs/promises'; import {dirname,resolve,join} from 'node:path';
import {spawn} from 'node:child_process'; import {fileURLToPath} from 'node:url';
import {NodeConfiguration} from ${moduleUrl('configuration')};
import {NodeUpdater} from ${moduleUrl('node-updater')};
import {atomicPrivate,processBirth,manageGateway,gatewayState} from ${moduleUrl('lifecycle')};
import {loadNodeRelease} from ${moduleUrl('release')};
const entry=fileURLToPath(import.meta.url),root=resolve(dirname(entry),'../../..');
const config=await NodeConfiguration.read(process.argv[process.argv.indexOf('--config')+1]);
const release=await loadNodeRelease(root);const action=process.argv[2];
if(action==='stop'){await manageGateway(config.path,config.value,'stop');}
else if(action==='start'){
 if(${fail}&&release.version==='1.2.3')process.exit(2);
 const child=spawn(process.execPath,[entry,'run','--config',config.path],{detached:true,stdio:'ignore',env:process.env});child.unref();
 const until=Date.now()+5000;let ready=false;while(Date.now()<until){const s=await gatewayState(config.path);if(s?.ready){ready=true;break;}await new Promise(r=>setTimeout(r,50));}if(!ready)process.exit(3);
}else{
 const state={pid:process.pid,process_start:await processBirth(process.pid),config_path:config.path,ready:true,connected:true,runtime_pid:process.pid,entry,node_exec:process.execPath,release};
 const updater=new NodeUpdater(config,{prepare:async()=>true,resume:async()=>{}});await updater.start();
 await atomicPrivate(join(dirname(config.path),'.gateway-state.json'),state);
 const timer=setInterval(()=>{},1000);process.on('SIGTERM',async()=>{clearInterval(timer);await updater.close();await rm(join(dirname(config.path),'.gateway-state.json'),{force:true});process.exit(0);});
}
`;
  try {
    await mkdir(dirname(config), {recursive: true}); await mkdir(dirname(cli), {recursive: true}); await mkdir(bin);
    await writeFile(config, JSON.stringify({node:{node_id:'fixture',user_id:'owner'}, im_service:{url:`http://127.0.0.1:${port}`,token:'token'},agents:[],llm:{default_model:'',providers:[]},gateway:{autostart:false,startup_timeout_seconds:3}}));
    const oldManifest: ReleaseManifest = {version:'1.2.2',source_commit:'a'.repeat(40),sha256:'b'.repeat(64),package:'nano-node.tgz',node_major:24,pnpm_version:'11.7.0',updater_protocol:1,data_epoch:1,download_url:'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.2.2/nano-node.tgz'};
    for (const [file, value] of Object.entries({'package.json':{type:'module'},'.nano-release.json':{source_commit:'a'.repeat(40),updater_protocol:1,data_epoch:1},'.release-manifest.json':oldManifest})) await writeFile(join(oldRoot,file),JSON.stringify(value));
    await writeFile(cli,program);
    const payload=join(home,'payload');await mkdir(join(payload,'apps/node/lib'),{recursive:true});
    await writeFile(join(payload,'apps/node/lib/cli.js'),program);await writeFile(join(payload,'package.json'),'{"type":"module"}');
    await writeFile(join(payload,'.nano-release.json'),JSON.stringify({source_commit:'c'.repeat(40),updater_protocol:1,data_epoch:1}));
    const archive=join(home,'fixture.tgz');execFileSync('tar',['-czf',archive,'-C',payload,'.']);
    const target={...oldManifest,version:'1.2.3',source_commit:'c'.repeat(40),sha256:createHash('sha256').update(await readFile(archive)).digest('hex'),download_url:'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.2.3/nano-node.tgz'};
    operation={id:'op',request_id:'req',node_id:'fixture',owner_id:'owner',node_epoch:1,target,state:'requested',cancel_requested:false,relay_gated:false,updated_at:new Date().toISOString()};
    await mkdir(join(home,'tooling/node_modules/pnpm/bin'),{recursive:true});await writeFile(join(home,'tooling/node_modules/pnpm/bin/pnpm.cjs'),'');
    await writeFile(join(bin,'curl'),`#!${process.execPath}\nconst fs=require('fs'),a=process.argv.slice(2);if(!a.includes('${target.download_url}'))process.exit(8);fs.copyFileSync(${JSON.stringify(archive)},a[a.indexOf('-o')+1]);`);await chmod(join(bin,'curl'),0o700);
    await runCli('start');const before=(await gatewayState(config))!;
    await exec(process.execPath,[resolve('apps/node/lib/update-worker.js'),config,'op'],{env:environment,timeout:25000});
    expect(operation.state).toBe(fail?'rolled_back':'succeeded');
    const after=(await gatewayState(config))!;
    expect(after.pid).not.toBe(before.pid);expect(await processBirth(before.pid)).toBeUndefined();
    expect(after.release?.sha256).toBe(fail?oldManifest.sha256:target.sha256);
    expect(phases).toContain('switching');expect(phases).toContain(fail?'rolling_back':'verifying');
  } finally { await runCli('stop').catch(()=>{});server.close();await rm(home,{recursive:true,force:true}); }
}, 40000);
