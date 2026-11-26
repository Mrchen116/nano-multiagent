import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, vi } from 'vitest';
import { openCliWorker, type CliWorkerOptions } from '../../src/local-workers/drivers.js';

export let cwd: string;
let cli: Awaited<ReturnType<typeof openCliWorker>> | undefined;
export const onReport = vi.fn<CliWorkerOptions['onReport']>(async () => {});
const onDetail = vi.fn<CliWorkerOptions['onDetail']>(async () => {});
export const details = () => onDetail.mock.calls.map(([, detail]) => detail);
export const turnTotals = () =>
  details().flatMap(({ turnId, fact }) =>
    fact.type === 'turn_end' ? [[turnId, fact.payload.usage?.total_tokens ?? null]] : [],
  );
export const turnUsages = () =>
  details().flatMap(({ turnId, fact }) =>
    fact.type === 'turn_end' ? [[turnId, fact.payload.usage]] : [],
  );
export const onEnd = vi.fn<CliWorkerOptions['onEnd']>(async () => {});
export const mcp = { command: 'mcp-bridge', args: ['parent-socket'], env: {} };
export async function fakeCli(runtime: CliWorkerOptions['runtime'], code: string, sessionId?: string, computer?: CliWorkerOptions['computer']) {
  const script =
    `#!${process.execPath}\n` +
    `
    const fs = require('node:fs');
    const emit = value => console.log(JSON.stringify(value));
    fs.writeFileSync('args', JSON.stringify(process.argv.slice(2)));
    fs.writeFileSync('env', JSON.stringify(process.env));
    require('node:readline').createInterface({input: process.stdin}).on('line', line => {
      const m = JSON.parse(line);
      fs.appendFileSync('frames', line+'\\n');
      ${code}
    });`;
  await writeFile(join(cwd, runtime === 'antigravity' ? 'agy' : runtime), script, { mode: 0o755 });
  return (cli = await openCliWorker({
    runtime,
    cwd,
    instructions: 'Help the parent',
    mcp,
    computer,
    onReport,
    onDetail,
    onEnd,
    sessionId,
  }));
}
export async function frames() {
  return (await readFile(join(cwd, 'frames'), 'utf8'))
    .trim()
    .split('\n')
    .map((line) => JSON.parse(line));
}
beforeEach(async () => {
  cwd = await mkdtemp(join(tmpdir(), 'nano-cli-protocol-'));
  vi.stubEnv('PATH', `${cwd}:${process.env.PATH}`);
  vi.clearAllMocks();
});
afterEach(async () => {
  await cli?.close();
  cli = undefined;
  vi.unstubAllEnvs();
  await rm(cwd, { recursive: true, force: true });
});
