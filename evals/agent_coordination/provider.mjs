/** Isolated Anthropic wire fixture. Only ordinary delegated workers are scripted. */
import { createServer } from 'node:http';
import { appendFileSync, readFileSync, writeFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { Readable } from 'node:stream';
import { setTimeout as delay } from 'node:timers/promises';

const [runDir, upstream = 'http://127.0.0.1:4000'] = process.argv.slice(2);
const variants = JSON.parse(readFileSync(runDir + '/variants.json', 'utf8'));
const roots = new Map();
const children = new Map();
const pending = new Map();
const path = runDir + '/wire.jsonl';
const record = data => appendFileSync(path, JSON.stringify({ at: Date.now(), ...data }) + '\n');
const redact = (key, value) => key === 'data' && typeof value === 'string' && value.length > 4096 ? '[image bytes]' : value;

function replace(value, entries) {
  if (typeof value === 'string') {
    for (const [before, after] of entries) value = value.replaceAll(before, after);
    return value;
  }
  if (Array.isArray(value)) return value.map(item => replace(item, entries));
  if (value && typeof value === 'object')
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, replace(item, entries)]));
  return value;
}

function event(res, type, data = {}) {
  res.write('event: ' + type + '\ndata: ' + JSON.stringify({ type, ...data }) + '\n\n');
}

async function script(req, res, body, id, root) {
  const state = children.get(id) ?? { root, id, assignment: body.messages.find(m => m.role === 'user')?.content };
  children.set(id, state);
  record({ type: 'child_request', root, id, messages: JSON.parse(JSON.stringify(body.messages, redact)) });
  res.writeHead(200, { 'content-type': 'text/event-stream' });
  event(res, 'message_start', { message: { id: 'fixture-' + randomUUID(), type: 'message', role: 'assistant',
    model: body.model, content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 0, output_tokens: 0 } } });
  if (state.finalCall) {
    const { id: callId, step } = state.finalCall;
    const receipt = body.messages.filter(message => Array.isArray(message.content))
      .flatMap(message => message.content).findLast(block => block.type === 'tool_result' && block.tool_use_id === callId);
    delete state.finalCall;
    if (!receipt || receipt.is_error) {
      record({ type: 'script_final_failed', root, id, step });
      event(res, 'error', { error: { type: 'api_error', message: 'Final result was not accepted by the internal message tool' } });
      res.end();
      return;
    }
    record({ type: 'script_final_sent', root, id, step });
    event(res, 'content_block_start', { index: 0, content_block: { type: 'text', text: '' } });
    event(res, 'content_block_delta', { index: 0, delta: { type: 'text_delta', text: '调查结果已发给主 Agent。' } });
    event(res, 'content_block_stop', { index: 0 });
    event(res, 'message_delta', { delta: { stop_reason: 'end_turn', stop_sequence: null }, usage: { output_tokens: 0 } });
    event(res, 'message_stop');
    res.end();
    return;
  }
  const deadline = Date.now() + 900_000;
  while (!pending.get(id)?.length && !res.destroyed && Date.now() < deadline) {
    event(res, 'ping');
    await delay(1000);
  }
  if (res.destroyed) return;
  const queued = pending.get(id)?.shift();
  if (!queued) {
    record({ type: 'script_timeout', root, id });
    event(res, 'error', { error: { type: 'api_error', message: 'Evaluation worker timed out waiting for a scripted action' } });
    res.end();
    return;
  }
  const input = queued.tool ? { file_path: queued.path } : { agent_id: root, message: queued.text };
  const tool = queued.tool ?? 'send_message';
  const callId = 'fixture-' + randomUUID();
  if (queued.final) state.finalCall = { id: callId, step: queued.step };
  record({ type: 'script_emit', root, id, step: queued.step, tool, input });
  event(res, 'content_block_start', { index: 0, content_block: { type: 'tool_use', id: callId, name: tool, input: {} } });
  event(res, 'content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify(input) } });
  event(res, 'content_block_stop', { index: 0 });
  event(res, 'message_delta', { delta: { stop_reason: 'tool_use', stop_sequence: null }, usage: { output_tokens: 0 } });
  event(res, 'message_stop');
  res.end();
}

function json(res, status, value) {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(value));
}

async function forward(res, body, id, root, kind, arm) {
  const response = await fetch(upstream + '/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'anthropic-version': '2023-06-01',
      'x-api-key': 'nano-local-proxy', 'x-session-id': root, 'x-agent-session-id': id },
    body: JSON.stringify(body),
  });
  record({ type: kind + '_status', root, arm, status: response.status });
  res.writeHead(response.status, { 'content-type': response.headers.get('content-type') ?? 'application/json' });
  if (!response.body) return res.end();
  const stream = Readable.fromWeb(response.body);
  let last = '';
  stream.on('data', chunk => { last = (last + chunk.toString()).slice(-2048); });
  stream.on('end', () => {
    const stop = last.match(/"stop_reason"\s*:\s*"(.*?)"/)?.[1];
    record({ type: kind + '_done', root, arm, stop });
  });
  stream.pipe(res);
}

const server = createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/control') {
      return json(res, 200, { roots: [...roots], children: [...children.values()] });
    }
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || '{}');
    if (req.url === '/control') {
      if (!children.has(body.id)) return json(res, 404, { error: 'Unknown child' });
      const readTool = body.tool === 'read_image' || body.tool === 'read';
      if (!body.step || (readTool ? !body.path || body.final : body.tool || !body.text))
        return json(res, 400, { error: 'Expected a scripted action with content' });
      const queue = pending.get(body.id) ?? [];
      queue.push(body);
      pending.set(body.id, queue);
      return json(res, 200, { accepted: true });
    }
    const id = req.headers['x-agent-session-id'], root = req.headers['x-session-id'];
    if (!id || !root) return json(res, 422, { error: 'No trusted session attribution' });
    const system = JSON.stringify(body.system ?? '');
    // Dreaming uses separate host-created sessions, including extraction sessions.
    if (id.startsWith('dreaming-'))
      return await forward(res, body, id, root, 'dreaming', roots.get(root));
    // The default tool classifier is a real model call, even when it carries the main session's ID.
    if (system.includes('The agent_instructions section contains loaded AGENTS.md guidance'))
      return await forward(res, body, id, root, 'reviewer', roots.get(root));
    if (id !== root) return await script(req, res, body, id, root);
    const arm = system.includes('coord-a') ? 'A' : system.includes('coord-b') ? 'B' : undefined;
    if (!arm || !system.includes('Internal coordination')) throw new Error('Missing expected Global Agent identity or prompt');
    roots.set(id, arm);
    const patched = arm === 'B' ? replace(body, variants.replacements) : body;
    const finalSystem = JSON.stringify(patched.system);
    const newPrompt = finalSystem.includes('quote the relevant original words verbatim');
    if (newPrompt !== (arm === 'B')) throw new Error('Unexpected Prompt treatment on the wire');
    const expected = variants.replacements[0][arm === 'B' ? 1 : 0];
    if (!finalSystem.includes(JSON.stringify(expected).slice(1, -1)))
      throw new Error('Full Global Prompt treatment did not reach the wire');
    const effort = patched.output_config?.effort ?? patched.thinking?.effort;
    const modelContext = JSON.stringify([patched.system, patched.messages]);
    const projectInstructions = modelContext.includes('## 架构红线') && modelContext.includes('## 开工路由');
    record({ type: 'root_request', root, arm, model: patched.model, effort, newPrompt, projectInstructions,
      skillChanged: JSON.stringify(body.messages) !== JSON.stringify(patched.messages), tools: patched.tools?.map(tool => tool.name),
      messages: JSON.parse(JSON.stringify(patched.messages, redact)) });
    if (!projectInstructions) throw new Error('Nano project instructions are missing from the model input');
    if (patched.model !== 'codexOAuth:gpt-6.1-sol' || effort !== 'high')
      throw new Error('Unexpected main model or reasoning effort');
    await forward(res, patched, id, root, 'upstream', arm);
  } catch (error) {
    record({ type: 'fixture_error', message: error.message });
    if (!res.headersSent) json(res, 500, { type: 'error', error: { type: 'api_error', message: error.message } });
    else res.end();
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
writeFileSync(runDir + '/provider.json', JSON.stringify({ url: 'http://127.0.0.1:' + server.address().port, pid: process.pid }));
