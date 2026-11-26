import { randomUUID } from 'node:crypto';
import { mkdir, readFile, rm } from 'node:fs/promises';
import { dirname } from 'node:path';
import { createInterface } from 'node:readline/promises';
import { Writable } from 'node:stream';
import { atomicPrivate } from './lifecycle.js';

async function promptToken() {
  if (!process.stdin.isTTY) {
    let token = '';
    for await (const chunk of process.stdin) {
      token += String(chunk);
      if (token.length > 512) throw new Error('Invalid Playwright Extension token.');
    }
    return token.trim();
  }
  process.stderr.write('Paste the token from the official Playwright Extension (input hidden): ');
  const sink = new Writable({
    write(_chunk, _encoding, done) {
      done();
    },
  });
  const lines = createInterface({ input: process.stdin, output: sink, terminal: true });
  try {
    return (await lines.question('')).trim();
  } finally {
    lines.close();
    process.stderr.write('\n');
  }
}

/** Pair, inspect, or disconnect the local extension without sending its token to IM. */
export async function browserCommand(action: string, file: string, profile: string) {
  if (action === 'disconnect') {
    await rm(file, { force: true });
    await rm(file + '.status', { force: true });
    return { state: 'not_paired' };
  }
  if (action === 'status') {
    let id: string;
    try {
      id = JSON.parse(await readFile(file, 'utf8')).id;
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code === 'ENOENT')
        return { state: 'not_paired', next: 'Run browser pair on this computer.' };
      throw new Error('Cannot read pairing. Run browser pair to replace it.');
    }
    try {
      const status = JSON.parse(await readFile(file + '.status', 'utf8'));
      if (status.id === id && ['verified', 'reconnect'].includes(status.state))
        return { state: status.state, lastCheckedAt: status.at };
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw err;
    }
    return { state: 'paired', next: 'Verification occurs on the first authorized browser operation.' };
  }
  if (action !== 'pair') throw new Error('Usage: browser pair|status|disconnect [--profile Default]');
  if (!/^(Default|Profile [0-9]+)$/.test(profile))
    throw new Error('Use the Chrome profile directory name, such as Default or Profile 1.');
  const token = await promptToken();
  if (!/^[A-Za-z0-9_-]{20,256}$/.test(token)) throw new Error('Invalid Playwright Extension token.');
  await mkdir(dirname(file), { mode: 0o700, recursive: true });
  await atomicPrivate(file, { id: randomUUID(), profile, token });
  return { state: 'paired', profile };
}
