import { mkdir, mkdtemp, readdir, rm, utimes, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { SCREENSHOT_LIMIT, SCREENSHOT_TTL_MS, ScreenshotStore, pngSize, resolveScreenshotPath } from '../src/browser/screenshots.js';

function png(width: number, height: number): Buffer {
  const buffer = Buffer.alloc(24);
  buffer.write('PNG', 1, 'ascii');
  buffer.write('IHDR', 12, 'ascii');
  buffer.writeUInt32BE(width, 16);
  buffer.writeUInt32BE(height, 20);
  return buffer;
}

it('writes a workspace-relative screenshot and reads device-pixel dimensions', async () => {
  const workspace = await mkdtemp(join(tmpdir(), 'nano-shot-'));
  try {
    const store = new ScreenshotStore({ now: () => Date.now() });
    const saved = await store.save({ workspace, agentId: 'agent-a', base64: png(2400, 1464).toString('base64'), name: 'screen-capture.png' });
    expect(saved).toEqual({ path: '.nanoassistant/browser/agent-a/screen-capture.png', width: 2400, height: 1464 });
    expect(await readdir(join(workspace, '.nanoassistant', 'browser', 'agent-a'))).toEqual(['screen-capture.png']);
  } finally { await rm(workspace, { recursive: true, force: true }); }
});

it('refuses traversal and missing workspaces without writing a file', async () => {
  const workspace = await mkdtemp(join(tmpdir(), 'nano-shot-'));
  try {
    expect(resolveScreenshotPath(workspace, 'agent-a', '../escape.png')).toBeUndefined();
    expect(resolveScreenshotPath(workspace, '..', 'screen-a.png')).toBeUndefined();
    const store = new ScreenshotStore();
    expect(await store.save({ workspace, agentId: 'agent-a', base64: png(1, 1).toString('base64'), name: '../escape.png' }))
      .toEqual({ omitted: 'outside_workspace' });
    expect(await store.save({ agentId: 'agent-a', base64: png(1, 1).toString('base64') })).toEqual({ omitted: 'outside_workspace' });
    await expect(readdir(join(workspace, '.nanoassistant'))).rejects.toThrow();
  } finally { await rm(workspace, { recursive: true, force: true }); }
});

it('removes expired files and keeps only the newest 20 on the next write', async () => {
  const workspace = await mkdtemp(join(tmpdir(), 'nano-shot-'));
  const now = 1_800_000_000_000;
  const root = join(workspace, '.nanoassistant', 'browser', 'agent-a');
  await mkdir(root, { recursive: true });
  try {
    const names: string[] = [];
    for (let index = 0; index < 25; index += 1) {
      const name = `screen-${String(index).padStart(2, '0')}.png`;
      names.push(name);
      await writeFile(join(root, name), png(10, 10));
      const mtime = index === 0 ? now - SCREENSHOT_TTL_MS - 1 : now - (25 - index) * 1_000;
      await utimes(join(root, name), new Date(mtime), new Date(mtime));
    }
    const store = new ScreenshotStore({ now: () => now });
    const removed = await store.cleanup(root);
    expect(removed).toBe(5);
    const remaining = (await readdir(root)).sort();
    expect(remaining).toHaveLength(SCREENSHOT_LIMIT);
    expect(remaining).not.toContain('screen-00.png');
    expect(remaining).toContain('screen-24.png');
    expect(remaining).not.toContain('screen-04.png');
  } finally { await rm(workspace, { recursive: true, force: true }); }
});

it('sweeps only configured Agent workspaces once and tolerates missing directories', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-shot-'));
  const workspace = join(root, 'workspace-a');
  const outside = join(root, 'outside');
  const now = 1_800_000_000_000;
  const old = new Date(now - SCREENSHOT_TTL_MS - 1_000);
  try {
    for (const directory of [join(workspace, '.nanoassistant', 'browser', 'agent-a'), outside]) {
      await mkdir(directory, { recursive: true });
      await writeFile(join(directory, 'screen-old.png'), png(1, 1));
      await utimes(join(directory, 'screen-old.png'), old, old);
    }
    const store = new ScreenshotStore({ now: () => now });
    const removed = await store.sweep([{ agentId: 'agent-a', workspace }, { agentId: 'gone', workspace: join(root, 'missing') }]);
    expect(removed).toBe(1);
    expect(await readdir(join(workspace, '.nanoassistant', 'browser', 'agent-a'))).toEqual([]);
    expect(await readdir(outside)).toEqual(['screen-old.png']);
  } finally { await rm(root, { recursive: true, force: true }); }
});

it('reads PNG dimensions and ignores unrelated filenames during cleanup', async () => {
  expect(pngSize(png(10, 20))).toEqual({ width: 10, height: 20 });
  expect(pngSize(Buffer.from('not png'))).toEqual({ width: 0, height: 0 });
  const workspace = await mkdtemp(join(tmpdir(), 'nano-shot-'));
  const root = join(workspace, '.nanoassistant', 'browser', 'agent-a');
  try {
    await mkdir(root, { recursive: true });
    await writeFile(join(root, 'keep.txt'), 'not ours');
    const store = new ScreenshotStore({ now: () => 1_800_000_000_000 });
    expect(await store.cleanup(root)).toBe(0);
    expect(await readdir(root)).toEqual(['keep.txt']);
  } finally { await rm(workspace, { recursive: true, force: true }); }
});
