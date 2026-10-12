import { Context } from '@deepseek-ai/cordis';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { TrajectoryAttachments } from '../src/trajectory-attachments.js';

it('denies a disappeared image source without poisoning later input admission', async () => {
  const home = await mkdtemp(join(tmpdir(), 'trajectory-source-'));
  const ctx = new Context();
  const records = new Map<string, unknown>();
  ctx.provide('storageDomain', { open: async () => ({ table: () => ({ get: async (key: string) => records.get(key), put: async (key: string, value: unknown) => { records.set(key, value); } }), close: async () => {} }) } as any);
  const sources = new TrajectoryAttachments(ctx);
  try {
    ctx.emit('tools/result', { name: 'read_image', arguments: { file_path: 'deleted.png' }, agent: { id: 's', session: { header: { cwd: home } } } } as any,
      { content: [{ type: 'image', attachment: { attachmentId: 'lost' } }] } as any);
    await sources.record('s', [{ type: 'text', text: 'next ordinary input' }], [null]);
    expect(await sources.read('s', 'lost')).toEqual([]);
    const source = { kind: 'chat' as const, conversationId: 'chat', messageId: 'message', url: '/image' };
    await sources.record('s', [{ type: 'image', attachment: { attachmentId: 'good' } }], [source]);
    expect(await sources.read('s', 'good')).toEqual([source]);
  } finally { await ctx.fiber.dispose(); await rm(home, { recursive: true, force: true }); }
});
