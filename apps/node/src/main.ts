import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { load } from 'js-yaml';
import { WebRelayConnection } from '@nano/channels';
import { NodeStore, SingleThread } from '@nano/personal-assistant';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';
import { prepareProfile, RuntimeSupervisor } from '@nano/dsh-integration/client';

interface Config {
  node: { node_id: string; user_id: string };
  im_service: { url: string; token: string };
  agents: { agent_id: string; workspace_root: string; work_mode?: 'single_thread' | 'global'; default_model?: string; custom_prompt?: string }[];
  llm: { default_model: string; providers: { name: string; base_url: string; api_key?: string; models: { name: string; context_window?: number; reasoning?: { default?: string; levels?: string[] } | string }[] }[] };
}

const configIndex = process.argv.indexOf('--config');
if (configIndex < 0 || !process.argv[configIndex + 1]) throw new Error('Usage: node apps/node/lib/main.js --config <gateway.yaml>');
const configPath = resolve(process.argv[configIndex + 1]!);
const config = load(await readFile(configPath, 'utf8')) as Config;
if (!config.node.user_id || !config.im_service.token) throw new Error('Bind this node before starting its runtime');
const home = join(dirname(configPath), '.dsh-runtime', config.node.node_id);
await mkdir(home, { recursive: true });
const providers: Record<string, unknown> = {};
const env: NodeJS.ProcessEnv = {};
for (const [index, provider] of config.llm.providers.entries()) {
  const credential = `NANO_PROVIDER_${index}_KEY`;
  if (provider.api_key) env[credential] = provider.api_key;
  else if (['127.0.0.1', 'localhost', '[::1]'].includes(new URL(provider.base_url).hostname)) env[credential] = 'nano-local-proxy';
  providers[provider.name] = { api: provider.name === 'anthropic' ? 'anthropic-messages' : 'openai-completions', baseURL: provider.base_url,
    defaultInput: ['text', 'image'],
    ...(env[credential] ? { apiKeyEnv: credential } : {}),
    models: provider.models.map(model => ({ id: model.name, contextWindow: model.context_window,
      ...(typeof model.reasoning === 'object' && model.reasoning.levels ? { reasoningEfforts: Object.fromEntries(model.reasoning.levels.map(level => [level === 'none' ? 'off' : level, level === 'none' ? null : level])) } : {}),
    })),
  };
}
const agents: AgentConfiguration[] = config.agents.map(agent => {
  const model = agent.default_model ?? config.llm.default_model;
  const provider = config.llm.providers.find(provider => provider.models.some(candidate => candidate.name === model));
  if (!provider) throw new Error(`No configured provider for ${model}`);
  const selected = provider.models.find(candidate => candidate.name === model)!;
  return { agentId: agent.agent_id, workspace: agent.workspace_root, mode: agent.work_mode ?? 'single_thread',
    revision: createHash('sha256').update(JSON.stringify(agent)).digest('hex').slice(0, 16), provider: provider.name, model,
    ...(typeof selected.reasoning === 'object' && selected.reasoning.default ? { reasoningEffort: selected.reasoning.default === 'none' ? 'off' : selected.reasoning.default } : {}),
    systemPrompt: agent.custom_prompt,
  };
});
await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers } }]);
const store = new NodeStore(join(home, 'node.sqlite3'), config.node.user_id);
let product: SingleThread;
const reportError = (error: unknown) => process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
const runtime = new RuntimeSupervisor({ home, cwd: home, env, onLog: text => process.stderr.write(text),
  initialize: async rpc => {
    await writeFile(join(home, 'runtime.pid'), String(runtime.process!.pid));
    await rpc.request('initialize', { protocol: 1, agents, bindings: store.bindings().map(({ conversationId: _, ...binding }) => binding) });
  },
  onReady: async () => { if (relay.ready) await product.recover(); },
  onError: reportError,
});
const relay = new WebRelayConnection({
  url: config.im_service.url,
  credentials: () => ({ accessToken: config.im_service.token, registration: {
    node_id: config.node.node_id, node_name: config.node.node_id, version: 'nano-dsh/0.1.0',
    agents: agents.map(agent => agent.agentId), user_id: config.node.user_id,
    agent_workspaces: Object.fromEntries(agents.map(agent => [agent.agentId, agent.workspace])),
    agent_work_modes: Object.fromEntries(agents.map(agent => [agent.agentId, agent.mode])),
    capabilities: {},
  } }),
  heartbeatPayload: () => ({ node_id: config.node.node_id, status: 'online', agent_count: agents.length, version: 'nano-dsh/0.1.0' }),
  onFrame: async frame => {
    if (frame.type === 'relay.message') await product.receive(frame.payload as unknown as RelayInput);
    if (frame.type === 'node.streaming_delta' && frame.payload.kind === 'permission_response') await product.permission(frame.payload);
  },
  onState: async state => { if (state === 'ready') await product.recover(); },
  onError: reportError,
});
product = new SingleThread({
  nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, runtime, relay, onError: reportError,
  image: async (url, agentId) => {
    const target = new URL(url, config.im_service.url);
    if (target.origin !== new URL(config.im_service.url).origin) throw new Error('Image must come from the authenticated IM media service');
    target.searchParams.set('agent_id', agentId);
    const response = await fetch(target, { headers: { Authorization: `Bearer ${relay.registration?.gateway_access_token ?? config.im_service.token}` } });
    if (!response.ok) throw new Error(`Image download failed: ${response.status}`);
    return Buffer.from(await response.arrayBuffer()).toString('base64');
  },
});
await runtime.start();
await relay.start();
process.stdout.write(`Node ${config.node.node_id} ready; DSH pid=${runtime.process!.pid}\n`);
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  try { await runtime.shutdown(); await product.stop(); await relay.stop(); store.close(); }
  catch (error) { reportError(error); process.exitCode = 1; }
}
process.once('SIGTERM', () => { void stop(); });
process.once('SIGINT', () => { void stop(); });
