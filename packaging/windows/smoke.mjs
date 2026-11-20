// Run outside the checkout using only the relocated version's private Node and packages.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { mkdirSync } from 'node:fs';
const [version, home] = process.argv.slice(2);
const fromNode = createRequire(join(version, 'apps/node/lib/cli.js'));
const { prepareProfile, RuntimeClient } = await import(pathToFileURL(fromNode.resolve('@nano/dsh-integration/client')).href);
mkdirSync(home, { recursive: true });
await prepareProfile(home);
const runtime = new RuntimeClient({home, cwd:home, onLog: text => process.stderr.write(text)});
const timer = setTimeout(() => { runtime.process.kill(); throw new Error('Installed DSH did not initialize'); }, 120_000);
try {
  const result = await runtime.rpc.request('initialize', {protocol:1, agents:[], bindings:[]});
  assert.equal(result.protocol, 1);
  console.log('Installed DSH initialized', result.version);
  await runtime.rpc.request('runtime.health', {});
  await runtime.shutdown();
} finally {
  clearTimeout(timer);
  runtime.process.kill();
}
