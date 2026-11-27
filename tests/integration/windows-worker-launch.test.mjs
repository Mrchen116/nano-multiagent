import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { probeDesktopWorkers } from '../../apps/node/lib/local-admin.js';
import { openCliWorker } from '../../packages/dsh-integration/lib/local-workers/drivers.js';

// A harmless worker implements just the native protocols' session handshakes.
const fixture = `
  const fs = require('node:fs');
  const args = process.argv.slice(2);
  const record = {args};
  if (args.includes('--append-system-prompt-file')) {
    record.prompt = fs.readFileSync(args[args.indexOf('--append-system-prompt-file') + 1], 'utf8');
    record.config = JSON.parse(fs.readFileSync(args[args.indexOf('--mcp-config') + 1], 'utf8'));
  }
  fs.writeFileSync('observed.json', JSON.stringify(record));
  require('node:readline').createInterface({input: process.stdin}).on('line', line => {
    const m = JSON.parse(line);
    if (m.type === 'control_request') {
      console.log(JSON.stringify({type:'control_response', response:{subtype:'success', request_id:m.request_id, response:{}}}));
    } else if (m.id !== undefined) {
      const result = m.method === 'thread/start' ? {thread:{id:'fixture-codex'}}
        : m.method === 'session/new' ? {sessionId:'fixture-agy', modes:{availableModes:[{id:'auto'}]}}
        : {};
      console.log(JSON.stringify({id:m.id, result}));
    }
  });
`;

test('desktop-discovered Windows workers open native stdio sessions', {skip: process.platform !== 'win32'}, async t => {
  const root = await mkdtemp(join(tmpdir(), 'nano worker & fixture '));
  const bin = join(root, 'worker bin');
  const cwd = join(root, 'work space');
  const path = process.env.PATH;
  const temp = process.env.TEMP;
  process.env.TEMP = root;
  t.after(async () => {
    process.env.PATH = path;
    if (temp === undefined) delete process.env.TEMP;
    else process.env.TEMP = temp;
    await rm(root, {recursive:true, force:true});
  });
  await mkdir(bin);
  await mkdir(cwd);
  await writeFile(join(bin, 'fixture.cjs'), fixture);
  // Keep system tools for tree cleanup while isolating the worker lookup.
  process.env.PATH = [bin, join(process.env.SystemRoot, 'System32')].join(';');
  const wrapper = `@echo off\r\n"${process.execPath}" "%~dp0fixture.cjs" %*\r\n`;
  for (const file of ['codex.cmd', 'claude.bat', 'agy.cmd']) await writeFile(join(bin, file), wrapper);
  // The original bare spawn cannot start the otherwise discoverable codex.cmd.
  assert.equal(spawnSync('codex', ['app-server'], {cwd, timeout: 3000}).error?.code, 'ENOENT');
  const instructions = 'Read "release notes" & preserve %PATH%!\n第二行';
  const mcp = {command: 'fixture bridge', args: ['two words', 'quoted "value"'], env: {}};
  const noop = async () => {};

  async function launch(runtime, file) {
    const probe = (await probeDesktopWorkers(bin)).find(item => item.runtime === runtime);
    assert.equal(probe.resolved_path, join(bin, file));
    const worker = await openCliWorker({runtime, cwd, instructions, mcp, onReport:noop, onDetail:noop, onEnd:noop});
    try {
      return JSON.parse(await readFile(join(cwd, 'observed.json'), 'utf8'));
    } finally {
      await worker.close();
    }
  }

  assert.deepEqual((await launch('codex', 'codex.cmd')).args, ['app-server', '--listen', 'stdio://']);
  const claude = await launch('claude', 'claude.bat');
  assert.equal(claude.prompt, instructions);
  const promptFile = claude.args[claude.args.indexOf('--append-system-prompt-file') + 1];
  await assert.rejects(readFile(promptFile), {code: 'ENOENT'});
  assert.deepEqual(claude.config.mcpServers['nano-parent'], mcp);
  assert.deepEqual((await launch('antigravity', 'agy.cmd')).args, ['acp', '--process-per-session']);

  // A native .exe takes priority over the adjacent shim. Node consumes app-server as its script.
  await copyFile(process.execPath, join(bin, 'codex.exe'));
  await writeFile(join(cwd, 'app-server'), fixture);
  assert.deepEqual((await launch('codex', 'codex.exe')).args, ['--listen', 'stdio://']);
});
