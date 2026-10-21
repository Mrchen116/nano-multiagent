import { expect, it } from 'vitest';
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { finishNativeReview } from './native-review-evidence.js';

function fixture(failAt?: string, original?: unknown) {
  const events: string[] = [];
  const problem = new Error('injected I/O failure');
  let mkdirs = 0;
  const step = async (name: string) => {
    events.push(name);
    if (name === failAt) throw problem;
  };
  const options = {
    home: '/owned/native-home', evidence: '/owned/evidence',
    observe: async () => { await step('observe'); return { approvals: [] }; },
    shutdown: async () => { await step('shutdown'); },
    ...(original !== undefined ? { failure: { error: original } } : {}),
  };
  const io = {
    mkdir: async () => { await step(++mkdirs === 1 ? 'pre-mkdir' : 'post-mkdir'); },
    readFile: async () => { await step('copy-read'); return 'fixture body'; },
    writeFile: async (path: string) => { await step(path.endsWith('observation.json') ? 'observation-write' : 'copy-write'); },
    rm: async (path: string) => { expect(path).toBe(options.home); await step('rm'); },
  };
  return { options, io, events, problem, step };
}

it.each(['pre-mkdir', 'observation-write', 'post-mkdir', 'copy-read', 'copy-write', 'shutdown', 'rm'])(
  'retains the primary failure and reports %s separately while always cleaning up', async failAt => {
    const original = new Error('original test assertion');
    const h = fixture(failAt, original);
    const error = await finishNativeReview(h.options, h.io).catch(error => error);
    expect(h.events).toContain('shutdown');
    expect(h.events.at(-1)).toBe('rm');
    expect(h.events.filter(event => event === 'shutdown')).toHaveLength(1);
    expect(h.events.filter(event => event === 'rm')).toHaveLength(1);
    expect(error).toBeInstanceOf(AggregateError);
    expect(error.cause).toBe(original);
    expect(error.errors[0]).toBe(original);
    expect(error.errors[1].cause).toBe(h.problem);
    expect(error.errors[1].message).toMatch(/observation export|fixture export|shutdown|home cleanup/);
  },
);

it('keeps an otherwise passing test failed when optional export fails', async () => {
  const h = fixture('pre-mkdir');
  const error = await finishNativeReview(h.options, h.io).catch(error => error);
  expect(error).toBeInstanceOf(AggregateError);
  expect(error.errors).toHaveLength(1);
  expect(error.errors[0].cause).toBe(h.problem);
  expect(h.events).toContain('shutdown');
  expect(h.events.at(-1)).toBe('rm');
});

it('collects both export and shutdown failures before removing its own home', async () => {
  const h = fixture('pre-mkdir');
  const shutdownError = new Error('shutdown failure');
  h.options.shutdown = async () => { h.events.push('shutdown'); throw shutdownError; };
  const error = await finishNativeReview(h.options, h.io).catch(error => error);
  expect(error.errors.map((entry: Error) => entry.cause)).toEqual([h.problem, shutdownError]);
  expect(h.events.at(-1)).toBe('rm');
});

it('closes before real EEXIST export diagnostics and removes only its temporary home', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-evidence-cleanup-'));
  const home = join(root, 'home');
  const evidence = join(root, 'existing-file');
  let shutdowns = 0;
  try {
    await mkdir(home);
    await writeFile(evidence, 'untouched output target');
    const error = await finishNativeReview({
      home, evidence, observe: async () => ({}), shutdown: async () => { shutdowns++; },
    }).catch(error => error);
    expect(error).toBeInstanceOf(AggregateError);
    expect(error.errors.map((entry: Error) => (entry.cause as NodeJS.ErrnoException).code)).toEqual(['EEXIST', 'EEXIST']);
    expect(shutdowns).toBe(1);
    await expect(stat(home)).rejects.toMatchObject({ code: 'ENOENT' });
    expect(await readFile(evidence, 'utf8')).toBe('untouched output target');
  } finally {
    // root is this test's mkdtemp parent; never remove the caller's evidence path.
    await rm(root, { recursive: true, force: true });
  }
});

it('preserves the original test error identity when cleanup succeeds', async () => {
  const original = new Error('original test assertion');
  const h = fixture(undefined, original);
  await expect(finishNativeReview(h.options, h.io)).rejects.toBe(original);
  expect(h.events.at(-1)).toBe('rm');
});

it('does not export without opt-in but always shuts down and removes its home', async () => {
  const h = fixture();
  await finishNativeReview({ ...h.options, evidence: undefined }, h.io);
  expect(h.events).toEqual(['shutdown', 'rm']);
});

it('exports available files after shutdown and tolerates only absent fixture files', async () => {
  const h = fixture();
  h.io.readFile = async () => {
    await h.step('copy-read');
    throw Object.assign(new Error('absent'), { code: 'ENOENT' });
  };
  await finishNativeReview(h.options, h.io);
  expect(h.events.indexOf('shutdown')).toBeLessThan(h.events.indexOf('copy-read'));
  expect(h.events).toContain('observation-write');
  expect(h.events.at(-1)).toBe('rm');
});
