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

it.each([false, true])('updates desktop-darwin-arm64 split archives, reuses cached runtime, updates .desktop-active.json, and rolls back on failure (%s)', async (fail) => {
  if (process.platform !== 'darwin') return;
  const home = await realpath(await mkdtemp(join(tmpdir(), 'nano-desktop-update-')));
  const desktopHome = join(home, 'desktop-home');
  const autostartDir = join(home, 'autostart');
  const oldSha = '1'.repeat(64);
  const oldRoot = join(desktopHome, 'versions', oldSha);
  const config = join(home, 'connections/test/config.yaml');
  let operation: NodeUpdateOperation;
  let runtimeDownloads = 0;

  const assets = new Map<string, Buffer>();
  const server = createServer((req, res) => {
    const url = req.url ?? '/';
    if (req.method === 'GET' && assets.has(url)) {
      res.setHeader('Content-Type', 'application/octet-stream');
      res.end(assets.get(url)!);
      if (url.includes('runtime')) runtimeDownloads++;
      return;
    }
    let body = '';
    req.on('data', b => (body += b));
    req.on('end', () => {
      void (async () => {
        const request = JSON.parse(body);
        if (request.action === 'progress' || request.action === 'terminal') operation.state = request.state;
        if (request.action === 'prepare') operation.relay_gated = true;
        if (request.action === 'resume') operation.relay_gated = false;
        if (request.action === 'claim_switch') operation.state = 'switching';
        const state = await gatewayState(config);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ operation, registered: { online: !!state?.connected, release: state?.release ?? null } }));
      })().catch(e => { res.statusCode = 500; res.end(String(e)); });
    });
  });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const port = (server.address() as { port: number }).port;
  const base = 'https://github.com/Mrchen116/nano-multiagent/releases/download/v2.0.1/';
  const bin = join(home, 'bin');
  const cli = join(oldRoot, 'apps/node/lib/cli.js');
  const environment = {
    ...process.env,
    CREWDEN_DESKTOP_HOME: desktopHome,
    NANO_TEST_AUTOSTART_DIR: autostartDir,
    PATH: `${bin}:${process.env.PATH}`,
  };
  const runCli = (...args: string[]) => exec(process.execPath, [cli, ...args, '--config', config], { env: environment, timeout: 15000 });

  const program = `
import {rm} from 'node:fs/promises'; import {dirname,resolve,join} from 'node:path';
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
 if(${fail}&&release.version==='2.0.1')process.exit(2);
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
    await mkdir(dirname(config), { recursive: true });
    await mkdir(dirname(cli), { recursive: true });
    await mkdir(join(oldRoot, 'ui'), { recursive: true });
    await mkdir(bin, { recursive: true });

    const oldManifest: ReleaseManifest = {
      version: '2.0.0',
      source_commit: 'a'.repeat(40),
      sha256: oldSha,
      package: 'desktop-darwin-arm64.json',
      platform: 'desktop-darwin-arm64',
      size: 256,
      shell_protocol: 2,
      node_major: 24,
      pnpm_version: '11.7.0',
      updater_protocol: 1,
      data_epoch: 1,
      download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v2.0.0/desktop-darwin-arm64.json',
      installer: { download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v2.0.0/Crewden-Desktop-arm64.dmg', size: 1024, sha256: '2'.repeat(64) },
    };
    for (const [file, value] of Object.entries({
      'package.json': { type: 'module' },
      '.nano-release.json': { source_commit: 'a'.repeat(40), updater_protocol: 1, data_epoch: 1, shell_protocol: 2 },
      '.release-manifest.json': oldManifest,
    })) {
      await writeFile(join(oldRoot, file), JSON.stringify(value));
    }
    await writeFile(cli, program);
    await writeFile(join(oldRoot, 'ui/index.html'), 'old-ui');
    await writeFile(
      join(dirname(config), '.desktop-active.json'),
      JSON.stringify({ managed_by: 'crewden-desktop', sha256: oldSha, version: '2.0.0', version_root: oldRoot, ui_root: join(oldRoot, 'ui') }),
    );
    await writeFile(
      config,
      JSON.stringify({
        node: { node_id: 'fixture', user_id: 'owner' },
        im_service: { url: `http://127.0.0.1:${port}`, token: 'token' },
        agents: [],
        llm: { default_model: '', providers: [] },
        gateway: { autostart: true, startup_timeout_seconds: 3 },
      }),
    );

    // Pre-populate runtime cache in runtimes/<runtimeSha>/.ready so runtime download is 0!
    const runtimePayload = join(home, 'runtime-payload');
    await mkdir(runtimePayload, { recursive: true });
    await writeFile(join(runtimePayload, 'dependencies.json'), '{}');
    const runtimeArchive = join(home, 'desktop-runtime-darwin-arm64.tar.gz');
    execFileSync('tar', ['-czf', runtimeArchive, '-C', runtimePayload, '.']);
    const runtimeBytes = await readFile(runtimeArchive);
    const runtimeSha = createHash('sha256').update(runtimeBytes).digest('hex');
    await mkdir(join(desktopHome, 'runtimes', runtimeSha), { recursive: true });
    await writeFile(join(desktopHome, 'runtimes', runtimeSha, '.ready'), '');

    const appPayload = join(home, 'app-payload');
    await mkdir(join(appPayload, 'apps/node/lib'), { recursive: true });
    await mkdir(join(appPayload, 'ui'), { recursive: true });
    await writeFile(join(appPayload, 'apps/node/lib/cli.js'), program);
    await writeFile(join(appPayload, 'ui/index.html'), 'new-ui-2.0.1');
    await writeFile(join(appPayload, 'package.json'), '{"type":"module"}');
    await writeFile(join(appPayload, '.nano-release.json'), JSON.stringify({ source_commit: 'c'.repeat(40), updater_protocol: 1, data_epoch: 1, shell_protocol: 2 }));
    const appArchive = join(home, 'desktop-app-darwin-arm64.tar.gz');
    execFileSync('tar', ['-czf', appArchive, '-C', appPayload, '.']);
    const appBytes = await readFile(appArchive);
    const appSha = createHash('sha256').update(appBytes).digest('hex');

    const descBytes = Buffer.from(
      JSON.stringify({
        version: '2.0.1',
        source_commit: 'c'.repeat(40),
        updater_protocol: 1,
        data_epoch: 1,
        shell_protocol: 2,
        runtime: { name: 'desktop-runtime-darwin-arm64.tar.gz', size: runtimeBytes.length, sha256: runtimeSha, download_url: base + 'desktop-runtime-darwin-arm64.tar.gz' },
        app: { name: 'desktop-app-darwin-arm64.tar.gz', size: appBytes.length, sha256: appSha, download_url: base + 'desktop-app-darwin-arm64.tar.gz' },
      }),
    );
    const descSha = createHash('sha256').update(descBytes).digest('hex');

    assets.set('/desktop-darwin-arm64.json', descBytes);
    assets.set('/desktop-runtime-darwin-arm64.tar.gz', runtimeBytes);
    assets.set('/desktop-app-darwin-arm64.tar.gz', appBytes);

    const target: ReleaseManifest = {
      version: '2.0.1',
      source_commit: 'c'.repeat(40),
      sha256: descSha,
      package: 'desktop-darwin-arm64.json',
      platform: 'desktop-darwin-arm64',
      size: descBytes.length,
      shell_protocol: 2,
      node_major: 24,
      pnpm_version: '11.7.0',
      updater_protocol: 1,
      data_epoch: 1,
      download_url: base + 'desktop-darwin-arm64.json',
      installer: { download_url: base + 'Crewden-Desktop-arm64.dmg', size: 1024, sha256: '4'.repeat(64) },
    };
    operation = { id: 'op-desk', request_id: 'req-desk', node_id: 'fixture', owner_id: 'owner', node_epoch: 1, target, state: 'requested', cancel_requested: false, relay_gated: false, updated_at: new Date().toISOString() };

    await writeFile(
      join(bin, 'curl'),
      `#!${process.execPath}\nconst http=require('http'),fs=require('fs'),a=process.argv.slice(2),out=a[a.indexOf('-o')+1],u=a.find(x=>x.startsWith('${base}'));if(!u)process.exit(8);const name='/'+u.slice('${base}'.length);http.get('http://127.0.0.1:${port}'+name,r=>{if(r.statusCode!==200)process.exit(9);const ws=fs.createWriteStream(out);r.pipe(ws);ws.on('finish',()=>process.exit(0));});`,
    );
    await chmod(join(bin, 'curl'), 0o700);

    await runCli('start');
    await exec(process.execPath, [resolve('apps/node/lib/update-worker.js'), config, 'op-desk'], { env: environment, timeout: 25000 });

    expect(runtimeDownloads).toBe(0);
    expect(operation.state).toBe(fail ? 'rolled_back' : 'succeeded');
    const activePointer = JSON.parse(await readFile(join(dirname(config), '.desktop-active.json'), 'utf8'));
    expect(activePointer.sha256).toBe(fail ? oldSha : descSha);
    expect(await readFile(join(activePointer.ui_root, 'index.html'), 'utf8')).toBe(fail ? 'old-ui' : 'new-ui-2.0.1');
  } finally {
    await runCli('stop').catch(() => {});
    server.close();
    await rm(home, { recursive: true, force: true });
  }
}, 40000);

it('updates desktop-darwin-arm64 from a trusted private-HTTP self-hosted release base with --max-redirs 0', async () => {
  if (process.platform !== 'darwin') return;
  const home = await realpath(await mkdtemp(join(tmpdir(), 'nano-self-hosted-update-')));
  const desktopHome = join(home, 'desktop-home');
  const autostartDir = join(home, 'autostart');
  const oldSha = '5'.repeat(64);
  const oldRoot = join(desktopHome, 'versions', oldSha);
  const config = join(home, 'connections/test/config.yaml');
  let operation: NodeUpdateOperation;
  const curlInvocations: string[][] = [];

  const assets = new Map<string, Buffer>();
  const server = createServer((req, res) => {
    const url = req.url ?? '/';
    if (req.method === 'GET' && assets.has(url)) {
      res.setHeader('Content-Type', 'application/octet-stream');
      res.end(assets.get(url)!);
      return;
    }
    let body = '';
    req.on('data', b => (body += b));
    req.on('end', () => {
      void (async () => {
        const request = JSON.parse(body);
        if (request.action === 'progress' || request.action === 'terminal') operation.state = request.state;
        if (request.action === 'prepare') operation.relay_gated = true;
        if (request.action === 'resume') operation.relay_gated = false;
        if (request.action === 'claim_switch') operation.state = 'switching';
        const state = await gatewayState(config);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ operation, registered: { online: !!state?.connected, release: state?.release ?? null } }));
      })().catch(e => { res.statusCode = 500; res.end(String(e)); });
    });
  });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const port = (server.address() as { port: number }).port;
  const privateBase = 'http://10.24.8.15:9000/releases/v2.1.0/';
  const oldPrivateBase = 'http://10.24.8.15:9000/releases/v2.0.9/';
  const bin = join(home, 'bin');
  const cli = join(oldRoot, 'apps/node/lib/cli.js');
  // Deliberately omit CREWDEN_DESKTOP_HOME on update-worker to prove path-derived lookup works!
  const environment = {
    ...process.env,
    NANO_TEST_AUTOSTART_DIR: autostartDir,
    PATH: `${bin}:${process.env.PATH}`,
  };
  delete (environment as Record<string, unknown>).CREWDEN_DESKTOP_HOME;
  const runCli = (...args: string[]) => exec(process.execPath, [cli, ...args, '--config', config], { env: environment, timeout: 15000 });

  const program = `
import {rm} from 'node:fs/promises'; import {dirname,resolve,join} from 'node:path';
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
    await mkdir(dirname(config), { recursive: true });
    await mkdir(dirname(cli), { recursive: true });
    await mkdir(join(oldRoot, 'ui'), { recursive: true });
    await mkdir(bin, { recursive: true });

    await writeFile(
      join(desktopHome, 'desktop-defaults.json'),
      JSON.stringify({
        default_im_origin: 'http://10.24.8.15:8011',
        trusted_release_base_url: 'http://10.24.8.15:9000/releases',
        allow_private_http_release_base: true,
      }),
    );

    const oldManifest: ReleaseManifest = {
      version: '2.0.9',
      source_commit: 'a'.repeat(40),
      release_base_url: oldPrivateBase,
      sha256: oldSha,
      package: 'desktop-darwin-arm64.json',
      platform: 'desktop-darwin-arm64',
      size: 256,
      shell_protocol: 2,
      node_major: 24,
      pnpm_version: '11.7.0',
      updater_protocol: 1,
      data_epoch: 1,
      download_url: oldPrivateBase + 'desktop-darwin-arm64.json',
      installer: { download_url: oldPrivateBase + 'Crewden-Desktop-arm64.dmg', size: 1024, sha256: '2'.repeat(64) },
    };
    await writeFile(join(oldRoot, 'package.json'), '{"type":"module"}');
    await writeFile(join(oldRoot, '.nano-release.json'), JSON.stringify({ source_commit: 'a'.repeat(40), updater_protocol: 1, data_epoch: 1, shell_protocol: 2 }));
    await writeFile(join(oldRoot, '.release-manifest.json'), JSON.stringify(oldManifest));
    await writeFile(cli, program);
    await writeFile(join(oldRoot, 'ui/index.html'), 'old-private-ui');
    await writeFile(
      join(dirname(config), '.desktop-active.json'),
      JSON.stringify({ managed_by: 'crewden-desktop', sha256: oldSha, version: '2.0.9', version_root: oldRoot, ui_root: join(oldRoot, 'ui') }),
    );
    await writeFile(
      config,
      JSON.stringify({
        node: { node_id: 'fixture', user_id: 'owner' },
        im_service: { url: `http://127.0.0.1:${port}`, token: 'token' },
        agents: [],
        llm: { default_model: '', providers: [] },
        gateway: { autostart: true, startup_timeout_seconds: 3 },
      }),
    );

    const runtimePayload = join(home, 'runtime-payload');
    await mkdir(runtimePayload, { recursive: true });
    await writeFile(join(runtimePayload, 'dependencies.json'), '{}');
    const runtimeArchive = join(home, 'desktop-runtime-darwin-arm64.tar.gz');
    execFileSync('tar', ['-czf', runtimeArchive, '-C', runtimePayload, '.']);
    const runtimeBytes = await readFile(runtimeArchive);
    const runtimeSha = createHash('sha256').update(runtimeBytes).digest('hex');
    await mkdir(join(desktopHome, 'runtimes', runtimeSha), { recursive: true });
    await writeFile(join(desktopHome, 'runtimes', runtimeSha, '.ready'), '');

    const appPayload = join(home, 'app-payload');
    await mkdir(join(appPayload, 'apps/node/lib'), { recursive: true });
    await mkdir(join(appPayload, 'ui'), { recursive: true });
    await writeFile(join(appPayload, 'apps/node/lib/cli.js'), program);
    await writeFile(join(appPayload, 'ui/index.html'), 'new-private-ui-2.1.0');
    await writeFile(join(appPayload, 'package.json'), '{"type":"module"}');
    await writeFile(
      join(appPayload, '.nano-release.json'),
      JSON.stringify({
        source_commit: 'c'.repeat(40),
        updater_protocol: 1,
        data_epoch: 1,
        shell_protocol: 2,
        trusted_release_base_url: privateBase,
        allow_private_http_release_base: true,
      }),
    );
    const appArchive = join(home, 'desktop-app-darwin-arm64.tar.gz');
    execFileSync('tar', ['-czf', appArchive, '-C', appPayload, '.']);
    const appBytes = await readFile(appArchive);
    const appSha = createHash('sha256').update(appBytes).digest('hex');

    const descBytes = Buffer.from(
      JSON.stringify({
        version: '2.1.0',
        source_commit: 'c'.repeat(40),
        updater_protocol: 1,
        data_epoch: 1,
        shell_protocol: 2,
        runtime: { name: 'desktop-runtime-darwin-arm64.tar.gz', size: runtimeBytes.length, sha256: runtimeSha, download_url: privateBase + 'desktop-runtime-darwin-arm64.tar.gz' },
        app: { name: 'desktop-app-darwin-arm64.tar.gz', size: appBytes.length, sha256: appSha, download_url: privateBase + 'desktop-app-darwin-arm64.tar.gz' },
      }),
    );
    const descSha = createHash('sha256').update(descBytes).digest('hex');
    assets.set('/desktop-darwin-arm64.json', descBytes);
    assets.set('/desktop-app-darwin-arm64.tar.gz', appBytes);

    const target: ReleaseManifest = {
      version: '2.1.0',
      source_commit: 'c'.repeat(40),
      release_base_url: privateBase,
      sha256: descSha,
      package: 'desktop-darwin-arm64.json',
      platform: 'desktop-darwin-arm64',
      size: descBytes.length,
      shell_protocol: 2,
      node_major: 24,
      pnpm_version: '11.7.0',
      updater_protocol: 1,
      data_epoch: 1,
      download_url: privateBase + 'desktop-darwin-arm64.json',
      installer: { download_url: privateBase + 'Crewden-Desktop-arm64.dmg', size: 1024, sha256: '4'.repeat(64) },
    };
    operation = { id: 'op-priv', request_id: 'req-priv', node_id: 'fixture', owner_id: 'owner', node_epoch: 1, target, state: 'requested', cancel_requested: false, relay_gated: false, updated_at: new Date().toISOString() };

    const argsLogPath = join(home, 'curl-args.jsonl');
    await writeFile(
      join(bin, 'curl'),
      `#!${process.execPath}\nconst http=require('http'),fs=require('fs'),a=process.argv.slice(2);fs.appendFileSync(${JSON.stringify(argsLogPath)},JSON.stringify(a)+'\\n');if(!a.includes('--max-redirs')||a[a.indexOf('--max-redirs')+1]!=='0')process.exit(12);const out=a[a.indexOf('-o')+1],u=a.find(x=>x.startsWith('${privateBase}'));if(!u)process.exit(8);const name='/'+u.slice('${privateBase}'.length);http.get('http://127.0.0.1:${port}'+name,r=>{if(r.statusCode!==200)process.exit(9);const ws=fs.createWriteStream(out);r.pipe(ws);ws.on('finish',()=>process.exit(0));});`,
    );
    await chmod(join(bin, 'curl'), 0o700);

    await runCli('start');
    await exec(process.execPath, [resolve('apps/node/lib/update-worker.js'), config, 'op-priv'], { env: environment, timeout: 25000 });

    const loggedLines = (await readFile(argsLogPath, 'utf8')).trim().split('\n');
    for (const line of loggedLines) curlInvocations.push(JSON.parse(line));
    expect(curlInvocations.length).toBe(2);
    expect(operation.state).toBe('succeeded');
    const activePointer = JSON.parse(await readFile(join(dirname(config), '.desktop-active.json'), 'utf8'));
    expect(activePointer.sha256).toBe(descSha);
    expect(await readFile(join(activePointer.ui_root, 'index.html'), 'utf8')).toBe('new-private-ui-2.1.0');
  } finally {
    await runCli('stop').catch(() => {});
    server.close();
    await rm(home, { recursive: true, force: true });
  }
}, 40000);
