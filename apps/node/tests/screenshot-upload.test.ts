import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { uploadScreenshot } from '../src/screenshot-upload.js';

it('recovers the original upload after the response and local file are gone', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'screenshot-upload-'));
  const path = join(directory, 'before.png');
  const signal = new AbortController().signal;
  const image = {url:'/im/v1/conversations/chat/images/one', file_name:'before.png', content_type:'image/png'};
  let saved = false;
  let uploads = 0;
  try {
    await writeFile(path, 'original image bytes');
    const request: Parameters<typeof uploadScreenshot>[0] = async (url, options) => {
      if (options?.method === 'POST') {
        expect(new URL(url,'http://im').searchParams.get('screenshot')).toBe('1');
        expect(new Headers(options.headers).get('idempotency-key')).toBe('main:send:0');
        expect(Buffer.from(options.body as Uint8Array).toString()).toBe('original image bytes');
        uploads++;
        saved = true;
        await rm(path);
        throw new Error('Response lost');
      }
      expect(new URL(url,'http://im').searchParams.get('upload_key')).toBe('main:send:0');
      return {attachment:saved ? image : null};
    };
    const input = {agentId:'agent',conversationId:'chat',operationId:'main:send',index:0,path,lifecycleRevision:1,signal};
    await expect(uploadScreenshot(request,input)).resolves.toEqual(image);
    await expect(uploadScreenshot(request,input)).resolves.toEqual(image);
    expect(uploads).toBe(1);
  } finally {
    await rm(directory,{recursive:true,force:true});
  }
});
