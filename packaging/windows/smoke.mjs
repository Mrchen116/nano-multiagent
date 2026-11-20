// Run outside the checkout using only the relocated version's private Node and packages.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';
const [version, home] = process.argv.slice(2);
const fromNode = createRequire(join(version, 'apps/node/lib/cli.js'));
const { prepareProfile, RuntimeClient } = await import(pathToFileURL(fromNode.resolve('@nano/dsh-integration/client')).href);
mkdirSync(home, { recursive: true });
// A reboot can leave the former Gateway PID occupied by an unrelated process.
const {manageGateway, processBirth} = await import(pathToFileURL(join(version, 'apps/node/lib/lifecycle.js')).href);
const configPath = join(home, 'gateway.yaml');
writeFileSync(configPath, '');
const statePath = join(home, '.gateway-state.json');
const recordBirth = birth => writeFileSync(statePath, JSON.stringify({pid:process.pid, config_path:configPath, process_start:birth}));
recordBirth('1'); // Positive Windows FILETIME before the current system boot.
assert.equal((await manageGateway(configPath, {}, 'status')).text, 'NOT RUNNING');
const currentBirth = BigInt(await processBirth(process.pid));
recordBirth(String(currentBirth + 1n));
await assert.rejects(manageGateway(configPath, {}, 'stop'), /PID identity changed/);
console.log('Previous-boot state expired; same-boot PID reuse preserved');

await prepareProfile(home);
const runtime = new RuntimeClient({home, cwd:home, onLog: text => process.stderr.write(text)});
const timer = setTimeout(() => { runtime.process.kill(); throw new Error('Installed DSH did not initialize'); }, 120_000);
try {
  const agent = {agentId:'probe', revision:'1', mode:'global', provider:'deepseek-official', model:'deepseek-flash'};
  runtime.rpc.handle('product.task_context.prepare', () => ({messages:[], revoked:[]}));
  runtime.rpc.handle('product.task_context.commit', () => null);
  runtime.rpc.handle('product.task_execution.snapshot', () => ({kind:'quiescent', tasks:[], repair_task_ids:[]}));
  const result = await runtime.rpc.request('initialize', {protocol:1, agents:[], bindings:[]});
  assert.equal(result.protocol, 1);
  console.log('Installed DSH initialized', result.version);
  await runtime.rpc.request('runtime.health', {});
  // Applying a new configuration spawns and reclaims a native inspection worker.
  const applied = await runtime.rpc.request('configuration.apply', {...agent, workspace:home, features:{intelligent_ui:false, task_graph:false}});
  assert.equal(applied.effective, true, JSON.stringify(applied));
  const sessionId = 'installed-smoke';
  await runtime.rpc.request('session.ensure', {sessionId, agentId:agent.agentId, revision:agent.revision, ownerId:'probe', cwd:home});
  const capabilities = await runtime.rpc.request('session.capabilities', {sessionId});
  assert.ok(capabilities.tools.includes('read'), 'Installed session must offer the file reader');
  console.log('Installed session tools:', capabilities.tools.sort().join(', '));
  await runtime.shutdown();
} finally {
  clearTimeout(timer);
  runtime.process.kill();
}
