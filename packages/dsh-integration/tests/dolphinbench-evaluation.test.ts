import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { builtinSkillsRoot } from '@nano/personal-assistant';
import type { EvaluationLimits } from '@nano/product-contracts';
import { expect, it } from 'vitest';
import { createNanoProduct } from '../../../evals/memory/nano-product.js';
import { NanoDolphinBenchController } from '../lib/evaluation.js';

const testLimits: EvaluationLimits = {
  timeoutMs: 45_000,
  maxModelCalls: 32,
  maxOutputTokens: 2048,
};

async function createMockMcpServerScript(root: string): Promise<{ scriptPath: string; callsLogPath: string }> {
  const scriptPath = join(root, 'mock-mcp-server.mjs');
  const callsLogPath = join(root, 'mcp-calls.jsonl');
  await writeFile(scriptPath, `import { appendFileSync } from 'node:fs';
import { createInterface } from 'node:readline';

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  const msg = JSON.parse(line);
  if (msg.id === undefined) continue;
  if (msg.method === 'initialize') {
    process.stdout.write(JSON.stringify({
      jsonrpc: '2.0',
      id: msg.id,
      result: {
        protocolVersion: msg.params?.protocolVersion ?? '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'mock-dolphin-mcp', version: '1.0.0' },
      },
    }) + '\\n');
  } else if (msg.method === 'tools/list') {
    process.stdout.write(JSON.stringify({
      jsonrpc: '2.0',
      id: msg.id,
      result: {
        tools: [
          {
            name: 'list_coffee_shops',
            description: 'List nearby coffee shops as a JSON array',
            inputSchema: { type: 'object', properties: {} },
          },
          {
            name: 'place_coffee_order',
            description: 'Place a coffee pickup order',
            inputSchema: {
              type: 'object',
              properties: { shop: { type: 'string' }, drink: { type: 'string' } },
              required: ['shop', 'drink'],
            },
          },
        ],
      },
    }) + '\\n');
  } else if (msg.method === 'tools/call') {
    const { name, arguments: args } = msg.params;
    appendFileSync(process.env.MOCK_MCP_LOG, JSON.stringify({ name, args }) + '\\n');
    const payload = name === 'list_coffee_shops'
      ? JSON.stringify(['Blue Bottle', 'Sightglass'])
      : JSON.stringify({ ok: true, shop: args.shop, drink: args.drink });
    process.stdout.write(JSON.stringify({
      jsonrpc: '2.0',
      id: msg.id,
      result: { content: [{ type: 'text', text: payload }], isError: false },
    }) + '\\n');
  }
}
`);
  return { scriptPath, callsLogPath };
}

async function createDeterministicFixturePlugin(root: string, outsideSecretPath: string): Promise<string> {
  const pluginPath = join(root, 'dolphin-fixture.mjs');
  await writeFile(pluginPath, `export const name = 'dolphinbench-deterministic-fixture';
export const inject = ['llm'];
export function apply(ctx) {
  const steps = new Map();
  const targets = new Map();
  const scopes = new Map();
  ctx.on('llm/stream', async function* (o) {
    const step = steps.get(o.sessionId) || 0;
    steps.set(o.sessionId, step + 1);
    const all = JSON.stringify(o.messages);
    let call;
    if (String(o.sessionId).startsWith('dreaming-')) {
      const plain = o.messages.map(m => (m.content || []).filter(b => b.type === 'text').map(b => b.text).join('')).join('\\n');
      if (plain.includes('<memory_repository>')) {
        scopes.set(o.sessionId, plain.match(/<memory_repository>\\n([^\\n]+)\\n<\\/memory_repository>/)[1]);
      }
      const stage = scopes.get(o.sessionId);
      call = [
        ['read', { file_path: stage + '/MEMORY.md' }],
        ['write', { file_path: stage + '/knowledge/coffee.md', content: 'Early departure coffee: Blue Bottle small latte pickup.' }],
        ['write', { file_path: stage + '/MEMORY.md', content: '# Personal memory\\n\\n## 主动性与介入偏好\\n\\n暂无已确认的主动性偏好。\\n\\n## Topics\\n\\n- [Coffee preference: Blue Bottle small latte](knowledge/coffee.md)\\n' }],
        ['bash', { description: 'Commit consolidated coffee preference', command: 'git add -- . && git -c user.name=Nano -c user.email=memory@localhost commit -m coffee' }],
      ][step];
    } else {
      const lastTool = id => {
        const m = o.messages.findLast(item => item.role === 'tool' && item.toolCallId === id);
        return m && !m.isError ? m.content[0]?.text : undefined;
      };
      const checked = lastTool('dbfix-0');
      if (checked) targets.set(o.sessionId, JSON.parse(checked).sources[0]?.target);
      const target = targets.get(o.sessionId);
      const isOrderTest = all.includes('ORDER_EARLY_COFFEE');
      if (!isOrderTest) {
        call = [
          ['inbox', { action: 'check' }],
          ['inbox', { action: 'read', target }],
          ['list_coffee_shops', {}],
          ['send_message', { target, text: 'Noted your coffee routine.' }],
        ][step];
      } else {
        const memoryPath = process.cwd() + '/.nanoassistant/memory/knowledge/coffee.md';
        const hasBlueBottleInMemory = all.includes('Blue Bottle small latte');
        const hasBlueBottleInSearch = all.includes('RAW_HISTORY_BLUE_BOTTLE');
        const chosenShop = (hasBlueBottleInMemory || hasBlueBottleInSearch) ? 'Blue Bottle' : 'UNKNOWN';
        const hasSearchTool = Array.isArray(o.tools) && o.tools.some(t => t.name === 'search_messages');
        call = [
          ['inbox', { action: 'check' }],
          ['inbox', { action: 'read', target }],
          ['read', { file_path: ${JSON.stringify(outsideSecretPath)} }],
          ['read', { file_path: memoryPath }],
          hasSearchTool
            ? ['search_messages', { target, query: 'RAW_HISTORY_BLUE_BOTTLE' }]
            : ['list_coffee_shops', {}],
          ['place_coffee_order', { shop: chosenShop, drink: 'small latte' }],
          ['send_message', { target, text: 'Ordered from ' + chosenShop }],
        ][step];
      }
    }
    if (call) {
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'dbfix-' + step, name: call[0], arguments: JSON.stringify(call[1]) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
    } else {
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Done.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
    }
  });
}
`);
  return pluginPath;
}

it('ingests chronological sessions with MCP tools, rolls windows, dreams at 03:00, and isolates test arms', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-dolphinbench-test-'));
  const outsideSecret = join(root, 'outside-secret.txt');
  await writeFile(outsideSecret, 'DO_NOT_READ_BENCHMARK_ANSWERS');
  const { scriptPath, callsLogPath } = await createMockMcpServerScript(root);
  const pluginPath = await createDeterministicFixturePlugin(root, outsideSecret);

  const controller = new NanoDolphinBenchController({
    provider: 'fixture',
    model: 'test',
    builtinSkillsRoot,
    timeZone: 'America/Los_Angeles',
    mcpToolNames: ['list_coffee_shops', 'place_coffee_order'],
    saveRawRequests: true,
    environment: { NANO_TEST_KEY: 'fixture' },
    providerPatch: [
      {
        id: 'llm-pi-ai',
        config: {
          providers: {
            fixture: {
              api: 'openai-completions',
              baseURL: 'http://127.0.0.1:9',
              apiKeyEnv: 'NANO_TEST_KEY',
              models: [{ id: 'test' }],
            },
          },
        },
      },
      { insert: [{ id: 'dolphinbench-fixture', name: pluginPath }] },
    ],
    createProduct: createNanoProduct,
  });

  const stateDir = join(root, 'state');
  const sealedDir = join(root, 'sealed');
  const day1Ms = Date.parse('2023-01-09T09:00:00-08:00');
  const day2Ms = Date.parse('2023-01-10T09:00:00-08:00');
  const finalNightMs = Date.parse('2023-01-11T03:05:00-08:00');
  const apps = {
    command: process.execPath,
    args: [scriptPath],
    env: { MOCK_MCP_LOG: callsLogPath },
  };

  try {
    await controller.openIngestion(stateDir, day1Ms, testLimits);
    const s1 = await controller.ingestSession({
      sessionId: '000001',
      windowIndex: 0,
      date: '2023/01/09 09:00',
      timestampMs: day1Ms,
      datedMessage: '[2023-01-09] RAW_HISTORY_BLUE_BOTTLE: Early morning coffee is a small latte from Blue Bottle.',
      apps,
      limits: testLimits,
    });
    expect(s1.status).toBe('completed');
    expect(s1.mountedTools).toBe(2);

    const s2 = await controller.ingestSession({
      sessionId: '000002',
      windowIndex: 1,
      date: '2023/01/10 09:00',
      timestampMs: day2Ms,
      datedMessage: '[2023-01-10] Keep my morning calendar clear before 9am.',
      apps,
      limits: testLimits,
    });
    expect(s2.status).toBe('completed');
    expect(s2.dreamingRunsBeforeSession.length).toBeGreaterThanOrEqual(1);
    expect(s2.rollover).toMatchObject({ rolledOver: true });

    const frozen = await controller.freezeIngestion('morgan', sealedDir, finalNightMs);
    const savedCheckpoint = JSON.parse(await readFile(frozen.checkpointPath, 'utf8'));
    expect(savedCheckpoint.workspace).toBe('workspace');
    expect(savedCheckpoint.chatSnapshot).toBe('prepared-chat.sqlite');
    expect(await readFile(join(sealedDir, 'workspace/.nanoassistant/memory/knowledge/coffee.md'), 'utf8'))
      .toContain('Blue Bottle small latte');

    for (const arm of ['memory-only', 'search-only', 'product'] as const) {
      await writeFile(callsLogPath, '');
      const testRes = await controller.runTest({
        checkpointPath: frozen.checkpointPath,
        testDir: join(root, `test-${arm}`),
        testId: `001-${arm}`,
        arm,
        date: '2023/01/15 08:00',
        timestampMs: Date.parse('2023-01-15T08:00:00-08:00'),
        datedMessage: '[2023-01-15] ORDER_EARLY_COFFEE before my flight.',
        apps,
        limits: testLimits,
      });
      expect(testRes.status).toBe('completed');
      expect(testRes.reply).toBe('Ordered from Blue Bottle');
      expect(testRes.usage.deniedTools).toBeGreaterThanOrEqual(1);
      const loggedCalls = (await readFile(callsLogPath, 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      expect(loggedCalls.some(c => c.name === 'place_coffee_order' && c.args.shop === 'Blue Bottle')).toBe(true);
    }
  } finally {
    await controller.closeIngestion();
    await rm(root, { recursive: true, force: true });
  }
}, 90_000);
