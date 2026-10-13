import {createServer} from 'node:http';
import {readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {expect, it} from 'vitest';
import {probeModels} from '../src/model-probe.js';

it('uses isolated real DSH for all candidate models and removes its private home after success and cancellation', async () => {
  const calls: {model: string; key?: string}[] = [];
  let hanging = false;
  const server = createServer(async (req, res) => {
    let raw = ''; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw); calls.push({model: body.model, key: req.headers.authorization});
    if (hanging) return;
    res.writeHead(200, {'content-type': 'text/event-stream'});
    res.write(`data: ${JSON.stringify({id: 'probe', object: 'chat.completion.chunk', created: 1, model: body.model, choices: [{index: 0, delta: {content: 'READY'}, finish_reason: null}]})}\n\n`);
    res.end(`data: ${JSON.stringify({id: 'probe', object: 'chat.completion.chunk', created: 1, model: body.model, choices: [{index: 0, delta: {}, finish_reason: 'stop'}]})}\n\ndata: [DONE]\n\n`);
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const homes = async () => (await readdir(tmpdir())).filter(name => name.startsWith('nano-model-probe-')).sort();
  const before = await homes();
  const candidate = {provider: 'test-service', providers: {'test-service': {api: 'openai-completions', baseURL: `http://127.0.0.1:${(server.address() as {port: number}).port}/v1`, models: [{id: 'one'}, {id: 'two'}], retryPolicy: {mode: 'normal', maxRetries: 0}}}, models: ['one', 'two'], api_key: 'probe-key'};
  try {
    await probeModels(candidate, new AbortController().signal);
    expect(calls).toEqual([{model: 'one', key: 'Bearer probe-key'}, {model: 'two', key: 'Bearer probe-key'}]);
    expect(await homes()).toEqual(before);
    hanging = true;
    const abort = new AbortController();
    const cancelled = probeModels(candidate, abort.signal).then(() => undefined, error => error);
    try {await expect.poll(() => calls.length, {timeout: 10_000}).toBe(3);}
    finally {abort.abort();}
    expect(await cancelled).toBeInstanceOf(Error);
    expect(await homes()).toEqual(before);
  } finally {server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve()));}
}, 30_000);
