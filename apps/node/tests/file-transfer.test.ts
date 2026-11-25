import { createServer } from 'node:http';
import { mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';
import { expect, it } from 'vitest';
import { downloadAttachment, uploadAttachment } from '../src/file-transfer.js';

it('uploads generic attachments idempotently and recovers after response and source file loss', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'file-upload-'));
  const filePath = join(directory, 'report.csv');
  const signal = new AbortController().signal;
  const attachment = { url: '/im/v1/conversations/chat/attachments/one', file_name: 'report.csv', content_type: 'text/csv' };
  let saved = false;
  let uploads = 0;
  try {
    await writeFile(filePath, 'col1,col2\n1,2\n');
    const request: Parameters<typeof uploadAttachment>[0] = async (url, options) => {
      if (options?.method === 'POST') {
        expect(new URL(url, 'http://im').searchParams.get('file')).toBe('1');
        expect(new Headers(options.headers).get('idempotency-key')).toBe('main:send:file:0');
        expect(options.timeoutMs).toBe(60_000);
        expect(Buffer.from(options.body as Uint8Array).toString()).toBe('col1,col2\n1,2\n');
        uploads++;
        saved = true;
        await rm(filePath);
        throw new Error('Response lost');
      }
      expect(new URL(url, 'http://im').searchParams.get('upload_key')).toBe('main:send:file:0');
      return { attachment: saved ? attachment : null };
    };
    const input = { agentId: 'agent', conversationId: 'chat', operationId: 'main:send', index: 0, path: filePath, lifecycleRevision: 1, signal };
    await expect(uploadAttachment(request, input)).resolves.toEqual(attachment);
    await expect(uploadAttachment(request, input)).resolves.toEqual(attachment);
    expect(uploads).toBe(1);

    // Rejects relative paths, empty files, and > 25 MiB files.
    const emptyLookup: Parameters<typeof uploadAttachment>[0] = async () => ({ attachment: null });
    await expect(uploadAttachment(emptyLookup, { ...input, path: 'relative.csv' })).rejects.toThrow('absolute local file path');
    const emptyPath = join(directory, 'empty.txt');
    await writeFile(emptyPath, '');
    await expect(uploadAttachment(emptyLookup, { ...input, operationId: 'op-empty', path: emptyPath })).rejects.toThrow('empty');
    const hugePath = join(directory, 'huge.bin');
    await writeFile(hugePath, Buffer.alloc(25 * 1024 * 1024 + 1));
    await expect(uploadAttachment(emptyLookup, { ...input, operationId: 'op-huge', path: hugePath })).rejects.toThrow('25 MiB');
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

it('streams authorized attachments to managed workspace dir, sanitizes traversal names, enforces 25 MiB cap, and rejects external/revoked URLs', async () => {
  const root = await mkdtemp(join(tmpdir(), 'file-download-'));
  const workspace = join(root, 'ws');
  const nodeHome = join(root, 'node-home');
  const payload = Buffer.from([0x50, 0x4b, 0x03, 0x04, 0x11, 0x22, 0x33, 0x44]);
  let mode: 'ok' | 'inline-png' | 'no-disposition-png' | 'forbidden' | 'oversized' = 'ok';
  const server = createServer((req, res) => {
    expect(req.headers.authorization).toBe('Bearer test-token');
    expect(new URL(req.url ?? '/', 'http://127.0.0.1').searchParams.get('agent_id')).toBe('agent-a');
    if (mode === 'inline-png') {
      res.writeHead(200, {
        'content-type': 'image/png',
        'content-disposition': `inline; filename="shot.png"; filename*=UTF-8''shot.png`,
      });
      res.end(payload);
      return;
    }
    if (mode === 'no-disposition-png') {
      res.writeHead(200, { 'content-type': 'image/png' });
      res.end(payload);
      return;
    }
    if (mode === 'forbidden') {
      res.writeHead(403, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ detail: 'not a member' }));
      return;
    }
    if (mode === 'oversized') {
      res.writeHead(200, { 'content-type': 'application/octet-stream', 'content-disposition': 'attachment; filename="big.bin"' });
      const chunk = Buffer.alloc(1024 * 1024);
      for (let i = 0; i < 26; i++) res.write(chunk);
      res.end();
      return;
    }
    res.writeHead(200, {
      'content-type': 'application/zip',
      'content-disposition': `attachment; filename="fallback.zip"; filename*=UTF-8''${encodeURIComponent('../../evil/path/report 2026.zip')}`,
    });
    res.end(payload);
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as { port: number };
  const baseUrl = `http://127.0.0.1:${port}`;
  const config = { baseUrl, token: () => 'test-token', nodeHome };
  const signal = new AbortController().signal;
  try {
    const result = await downloadAttachment(config, {
      agentId: 'agent-a',
      workspace,
      attachmentId: 'a_123456',
      url: '/im/v1/conversations/c1/attachments/id-1',
      signal,
    });
    expect(result.local_path.startsWith(join(workspace, '.nano-downloads'))).toBe(true);
    expect(basename(result.local_path)).toBe('a_123456-report 2026.zip');
    expect(result.file_name).toBe('report 2026.zip');
    expect(result.content_type).toBe('application/zip');
    expect(result.byte_size).toBe(payload.length);
    expect(await readFile(result.local_path)).toEqual(payload);

    // Repeat download overwrites idempotently without leaving temp files.
    const repeat = await downloadAttachment(config, {
      agentId: 'agent-a',
      workspace,
      attachmentId: 'a_123456',
      url: '/im/v1/conversations/c1/attachments/id-1',
      signal,
    });
    expect(repeat.local_path).toBe(result.local_path);
    expect(await readdir(join(workspace, '.nano-downloads'))).toEqual(['a_123456-report 2026.zip']);

    // Falls back to <nodeHome>/downloads/<agentId> when workspace is empty.
    const fallback = await downloadAttachment(config, {
      agentId: 'agent-a',
      workspace: '',
      attachmentId: 'a_abcdef',
      url: '/im/v1/conversations/c1/attachments/id-2',
      signal,
    });
    expect(fallback.local_path.startsWith(join(nodeHome, 'downloads', 'agent-a'))).toBe(true);
    expect((await stat(fallback.local_path)).size).toBe(payload.length);

    // Inline raster PNG preserves original file_name and .png extension; missing disposition falls back with MIME extension.
    mode = 'inline-png';
    const inlinePng = await downloadAttachment(config, {
      agentId: 'agent-a',
      workspace,
      attachmentId: 'a_png001',
      url: '/im/v1/conversations/c1/images/deadbeef12345678',
      signal,
    });
    expect(basename(inlinePng.local_path)).toBe('a_png001-shot.png');
    expect(inlinePng.file_name).toBe('shot.png');
    expect(await readFile(inlinePng.local_path)).toEqual(payload);

    mode = 'no-disposition-png';
    const fallbackExtPng = await downloadAttachment(config, {
      agentId: 'agent-a',
      workspace,
      attachmentId: 'a_png002',
      url: '/im/v1/conversations/c1/images/deadbeef12345678',
      signal,
    });
    expect(basename(fallbackExtPng.local_path)).toBe('a_png002-deadbeef12345678.png');
    expect(fallbackExtPng.file_name).toBe('deadbeef12345678.png');

    // Rejects non-native external URLs without hitting HTTP.
    await expect(downloadAttachment(config, {
      agentId: 'agent-a',
      workspace,
      attachmentId: 'a_ext001',
      url: 'https://evil.example/file.zip',
      signal,
    })).rejects.toThrow('Only native Nano IM attachments');

    // Surfaces revoked access errors cleanly.
    mode = 'forbidden';
    await expect(downloadAttachment(config, {
      agentId: 'agent-a',
      workspace,
      attachmentId: 'a_revoked',
      url: '/im/v1/conversations/c1/attachments/revoked',
      signal,
    })).rejects.toThrow('403');

    // Enforces 25 MiB streaming cap and cleans up temp file.
    mode = 'oversized';
    await expect(downloadAttachment(config, {
      agentId: 'agent-a',
      workspace,
      attachmentId: 'a_toobig',
      url: '/im/v1/conversations/c1/attachments/big',
      signal,
    })).rejects.toThrow('25 MiB');
    expect((await readdir(join(workspace, '.nano-downloads'))).sort()).toEqual([
      'a_123456-report 2026.zip',
      'a_png001-shot.png',
      'a_png002-deadbeef12345678.png',
    ]);
  } finally {
    await new Promise<void>(resolve => { server.close(() => resolve()); server.closeAllConnections(); });
    await rm(root, { recursive: true, force: true });
  }
});
