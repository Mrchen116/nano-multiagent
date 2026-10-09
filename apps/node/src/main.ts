import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { NodeConfiguration } from './configuration.js';
import { WebRelayConnection, FeishuConnection } from '@nano/channels';
import { NodeStore, SingleThread, GlobalAgent, InboxStore, ConfigurationOperations, Heartbeat, ExternalChannels, needsAttention, type HeartbeatSettings, type ProductCall } from '@nano/personal-assistant';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';
import { prepareProfile, RuntimeSupervisor } from '@nano/dsh-integration/client';

const configIndex = process.argv.indexOf('--config');
if (configIndex < 0 || !process.argv[configIndex + 1]) throw new Error('Usage: node apps/node/lib/main.js --config <gateway.yaml>');
const configPath = resolve(process.argv[configIndex + 1]!);
const configuration = await NodeConfiguration.read(configPath);
const config = configuration.value;
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
const agents: AgentConfiguration[] = config.agents.map(agent => configuration.runtime(agent));
await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers } }]);
const store = new NodeStore(join(home, 'node.sqlite3'), config.node.user_id);
const inbox = new InboxStore(join(home, 'global.sqlite3'));
let product: SingleThread;
let globalProduct: GlobalAgent;
let operations: ConfigurationOperations;
let heartbeat: Heartbeat;
let external: ExternalChannels;
const feishu = new Map<string, FeishuConnection>();
const reportError = (error: unknown) => process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
const runtime = new RuntimeSupervisor({ home, cwd: home, env, onLog: text => process.stderr.write(text),
  initialize: async rpc => {
    await writeFile(join(home, 'runtime.pid'), String(runtime.process!.pid));
    await rpc.request('initialize', { protocol: 1, agents, bindings: store.bindings().map(({ conversationId: _, ...binding }) => binding) });
  },
  onReady: async () => { if (operations) await operations.recover(); if (product) { await product.recover(!relay.ready); await globalProduct.recover(); if (external) await external.recover(); } },
  onError: reportError,
});
const relay = new WebRelayConnection({
  url: config.im_service.url,
  credentials: () => ({ accessToken: config.im_service.token, registration: {
    node_id: config.node.node_id, node_name: config.node.node_id, version: 'nano-dsh/0.1.0',
    agents: agents.map(agent => agent.agentId), user_id: config.node.user_id,
    agent_workspaces: Object.fromEntries(agents.map(agent => [agent.agentId, agent.workspace])),
    agent_work_modes: Object.fromEntries(agents.map(agent => [agent.agentId, agent.mode])),
    agent_skills: Object.fromEntries(config.agents.map(agent => [agent.agent_id, agent.skills ?? []])),
    agent_skills_selection_modes: Object.fromEntries(config.agents.map(agent => [agent.agent_id, configuration.current(agent.agent_id)?.skills_selection_mode])),
    agent_tool_allowlist: Object.fromEntries(config.agents.map(agent => [agent.agent_id, agent.tool_allowlist ?? []])),
    capabilities: {},
  } }),
  heartbeatPayload: () => ({ node_id: config.node.node_id, status: 'online', agent_count: agents.length, version: 'nano-dsh/0.1.0' }),
  onFrame: async frame => {
    const payload = frame.payload;
    if (frame.type === 'heartbeat.trigger') await heartbeat.tick(String(payload.agent_id), true);
    if (frame.type === 'node.heartbeat.md.request') {
      const agent = agents.find(agent => agent.agentId === payload.agent_id || !payload.agent_id && agent.workspace === payload.workspace_root);
      if (!agent) throw new Error('Heartbeat request has no Agent on this node');
      const content = await readFile(join(agent.workspace, '.nanoassistant', 'HEARTBEAT.md'), 'utf8').catch(error => { if (error.code === 'ENOENT') return ''; throw error; });
      await relay.request('node.heartbeat.md', { node_id: config.node.node_id, request_id: payload.request_id, content });
    }
    if (frame.type === 'agent.config.get') await relay.request('agent.config', { node_id: config.node.node_id, request_id: payload.request_id, agent_id: payload.agent_id, agent: configuration.current(String(payload.agent_id)) ?? null });
    if (frame.type === 'agent.config.apply' || frame.type === 'agent.create') {
      const result = await operations.handle(frame.type === 'agent.create' ? 'create' : 'apply', payload as unknown as Parameters<ConfigurationOperations['handle']>[1]).catch(error => { reportError(error); return operations.status(String(payload.operation_id)); });
      await relay.request(frame.type === 'agent.create' ? 'agent.created' : 'agent.config.apply.result', { request_id: payload.request_id, node_id: config.node.node_id, ...result });
    }
    if (frame.type === 'agent.config.operation.status') await relay.request('agent.config.operation.status.result', { request_id: payload.request_id, node_id: config.node.node_id, ...operations.status(String(payload.operation_id)) });
    if (frame.type === 'node.cron.jobs.request' || frame.type === 'node.cron.delete.request') {
      const agent = agents.find(agent => agent.agentId === payload.agent_id || !payload.agent_id && agent.workspace === payload.workspace_root);
      if (!agent) throw new Error('Cron request has no Agent on this node');
      const jobs = await runtime.request('schedule.command', { agentId: agent.agentId, action: 'catalog' }) as { id: string; sessionId: string }[];
      if (frame.type === 'node.cron.jobs.request') await relay.request('node.cron.jobs', { request_id: payload.request_id, node_id: config.node.node_id, jobs });
      else {
        const job = jobs.find(job => job.id === payload.job_id);
        const deleted = job ? await runtime.request('schedule.command', { agentId: agent.agentId, sessionId: job.sessionId, action: 'delete', args: { id: job.id } }) : false;
        await relay.request('node.cron.delete', { request_id: payload.request_id, node_id: config.node.node_id, deleted: !!deleted });
      }
    }
    if (frame.type === 'relay.message') {
      const input = frame.payload as unknown as RelayInput;
      if (agents.find(agent => agent.agentId === input.agent_id)?.mode === 'global') await globalProduct.receive(input);
      else await product.receive(input);
    }
    if (frame.type === 'node.streaming_delta' && frame.payload.kind === 'permission_response') await product.permission(frame.payload);
  },
  onState: async state => { if (state === 'ready') { await external.recover(); await product.recover(); await globalProduct.recover(); } },
  onError: reportError,
});
async function downloadImage(url: string, agentId: string) {
    if (url.startsWith('external:')) return external.image(url, agentId).data.toString('base64');
    const target = new URL(url, config.im_service.url);
    if (target.origin !== new URL(config.im_service.url).origin) throw new Error('Image must come from the authenticated IM media service');
    target.searchParams.set('agent_id', agentId);
    const response = await fetch(target, { headers: { Authorization: `Bearer ${relay.registration?.gateway_access_token ?? config.im_service.token}` } });
    if (!response.ok) throw new Error(`Image download failed: ${response.status}`);
    return Buffer.from(await response.arrayBuffer()).toString('base64');
}

external = new ExternalChannels(join(home, 'external.sqlite3'), { nodeId: config.node.node_id, ownerId: config.node.user_id, store, relay,
  onError: reportError, runtimeFooter: config.display?.platforms?.feishu?.runtime_footer?.enabled ?? config.display?.runtime_footer?.enabled,
  attention: input => needsAttention(input, agents.find(agent => agent.agentId === input.agent_id)!),
  receive: input => agents.find(agent => agent.agentId === input.agent_id)?.mode === 'global' ? globalProduct.receive(input) : product.receive(input),
  permission: payload => product.permission(payload),
  im: async (path, options) => {
    const url = new URL(path, config.im_service.url); url.protocol = url.protocol === 'wss:' ? 'https:' : url.protocol === 'ws:' ? 'http:' : url.protocol;
    const response = await fetch(url, { ...options, signal: AbortSignal.timeout(10000), headers: { ...options?.headers, Authorization: `Bearer ${relay.registration?.gateway_access_token ?? config.im_service.token}` } });
    if (!response.ok) throw new Error(`IM external projection failed: ${response.status}`);
    return response.json();
  },
});
for (const channel of config.channels ?? []) {
  if (channel.enabled === false || !channel.name.startsWith('feishu:')) continue;
  const agentId = channel.name.slice(7); const settings = channel.settings;
  if (!agents.some(agent => agent.agentId === agentId)) throw new Error('Feishu channel has no Agent');
  const connection = new FeishuConnection({ appId: settings.appId!, appSecret: settings.appSecret!, botOpenId: settings.botOpenId!, ownerOpenId: settings.ownerOpenId, domain: settings.domain }, {
    receive: message => external.receive(agentId, message), card: value => external.card(agentId, value), onError: reportError,
    status: state => process.stderr.write(`Feishu ${agentId}: ${state}\n`),
  });
  feishu.set(agentId, connection); external.add(agentId, connection);
}
product = new SingleThread({
  nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, runtime, relay: external, onError: reportError,
  image: downloadImage,
});
globalProduct = new GlobalAgent({ nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, inbox, runtime, relay: external, image: downloadImage, onError: reportError });
runtime.handle('product.call', call => globalProduct.call(call as ProductCall));
operations = new ConfigurationOperations(join(home, 'configuration.sqlite3'), {
  current: agentId => configuration.current(agentId),
  resolve: (candidate, creating) => configuration.resolve(candidate, creating),
  persist: candidate => configuration.persist(candidate),
  apply: async candidate => {
    const next = configuration.runtime(candidate);
    await runtime.request('configuration.apply', next);
    const previous = agents.find(agent => agent.agentId === next.agentId);
    if (previous) Object.assign(previous, next); else agents.push(next);
  },
});
heartbeat = new Heartbeat(join(home, 'heartbeat.sqlite3'), { agents, runtime, onError: reportError,
  settings: agentId => (config.agents.find(agent => agent.agent_id === agentId)?.heartbeat ?? {}) as HeartbeatSettings,
  binding: agent => agent.mode === 'global' ? globalProduct.heartbeatBinding(agent) : product.heartbeatBinding(agent),
  available: () => relay.ready && runtime.available,
});
runtime.onNotification((method, value) => { if (method === 'heartbeat.subscription') { const data = value as { agentId: string; enabled: boolean }; heartbeat.subscription(data.agentId, data.enabled); } });
await runtime.start();
await Promise.all([...feishu.values()].map(connection => connection.start()));
void relay.start().catch(reportError);
heartbeat.start();
process.stdout.write(`Node ${config.node.node_id} ready; DSH pid=${runtime.process!.pid}\n`);
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  try { for (const connection of feishu.values()) connection.stop(); await heartbeat.stop(); await runtime.shutdown(); await product.stop(); await globalProduct.stop(); await operations.close(); await external.stop(); await relay.stop(); inbox.close(); store.close(); }
  catch (error) { reportError(error); process.exitCode = 1; }
}
process.once('SIGTERM', () => { void stop(); });
process.once('SIGINT', () => { void stop(); });
