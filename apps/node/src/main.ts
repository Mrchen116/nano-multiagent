import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { NodeConfiguration } from './configuration.js';
import {claimGateway,applyGatewayEnvironment} from './lifecycle.js';
import { providerProfiles } from './providers.js';
import { projectCapabilities } from './capabilities.js';
import { WebRelayConnection, FeishuConnection, ChannelKey } from '@nano/channels';
import { NodeStore, SingleThread, GlobalAgent, InboxStore, ConfigurationOperations, Heartbeat, ExternalChannels, ManagedChannels, KnowledgeUpdates, WorkflowResults, UsageReports, ConversationHistory, installBuiltinSkills, needsAttention, type HeartbeatSettings, type ProductCall } from '@nano/personal-assistant';
import type { AgentConfiguration, RelayInput } from '@nano/product-contracts';
import { prepareProfile, RuntimeSupervisor } from '@nano/dsh-integration/client';

const configIndex = process.argv.indexOf('--config');
if (configIndex < 0 || !process.argv[configIndex + 1]) throw new Error('Usage: node apps/node/lib/main.js --config <gateway.yaml>');
const configPath = resolve(process.argv[configIndex + 1]!);
try {
  const migration = JSON.parse(await readFile(join(dirname(configPath), 'migration-report.json'), 'utf8')) as {blockers: string[]};
  if(migration.blockers.length)throw new Error(`Migration has ${migration.blockers.length} unreconciled operations; inspect migration-report.json before starting`);
} catch(error) { if((error as NodeJS.ErrnoException).code !== 'ENOENT')throw error; }
const configuration = await NodeConfiguration.read(configPath);
const config = configuration.value;
applyGatewayEnvironment(config);
const imOverride=process.argv.indexOf('--im-service-url');if(imOverride>=0)config.im_service.url=process.argv[imOverride+1]!;
const lifecycle=await claimGateway(configPath);
if (!config.node.user_id || !config.im_service.token) throw new Error('Bind this node before starting its runtime');
const home = join(dirname(configPath), '.dsh-runtime', config.node.node_id);
await mkdir(home, { recursive: true });
const { providers, env } = providerProfiles(config.llm);
await installBuiltinSkills(join(configuration.ownerRoot, 'skills'));
const agents: AgentConfiguration[] = config.agents.map(agent => configuration.runtime(agent));
await prepareProfile(home, [{ id: 'llm-pi-ai', config: { providers } }]);
const store = new NodeStore(join(home, 'node.sqlite3'), config.node.user_id);
const inbox = new InboxStore(join(home, 'global.sqlite3'));
let product: SingleThread;
let globalProduct: GlobalAgent;
let operations: ConfigurationOperations;
let heartbeat: Heartbeat;
let external: ExternalChannels;
let managed: ManagedChannels;
let knowledge: KnowledgeUpdates;
let history: ConversationHistory;
let workflows: WorkflowResults;
let usage: UsageReports;
const channelKey = await ChannelKey.load(join(dirname(configPath), 'channel-credentials-v1.pem'));
const reportError = (error: unknown) => process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
const runtime = new RuntimeSupervisor({ home, cwd: home, env, onLog: text => process.stderr.write(text),
  initialize: async rpc => {
    await writeFile(join(home, 'runtime.pid'), String(runtime.process!.pid));
    await rpc.request('initialize', { protocol: 1, agents, bindings: store.bindings().map(({ conversationId: _, ...binding }) => binding) });
  },
  onReady: async () => { if (operations) await operations.recover(); if (product) { await product.recover(!relay.ready); await globalProduct.recover(); if (external) await external.recover(); if (knowledge) await knowledge.recover(); if (workflows) await workflows.recover(); if (usage) await usage.recover(); } await lifecycle.ready(runtime.process!.pid!); },
  onError: reportError,
  onUnavailable: () => lifecycle.unavailable(),
});
const relay = new WebRelayConnection({
  url: config.im_service.url,
  credentials: () => ({ accessToken: config.im_service.token, registration: {
    node_id: config.node.node_id, node_name: config.node.node_id, version: 'nano-dsh/0.1.0',
    agents: agents.map(agent => agent.agentId), user_id: config.node.user_id,
    agent_configurations: Object.fromEntries(config.agents.map(agent => [agent.agent_id, configuration.current(agent.agent_id)])),
    agent_workspaces: Object.fromEntries(agents.map(agent => [agent.agentId, agent.workspace])),
    agent_work_modes: Object.fromEntries(agents.map(agent => [agent.agentId, agent.mode])),
    agent_skills: Object.fromEntries(config.agents.map(agent => [agent.agent_id, agent.skills ?? []])),
    agent_skills_selection_modes: Object.fromEntries(config.agents.map(agent => [agent.agent_id, configuration.current(agent.agent_id)?.skills_selection_mode])),
    agent_tool_allowlist: Object.fromEntries(config.agents.map(agent => [agent.agent_id, agent.tool_allowlist ?? []])),
    ...channelKey.registration, capabilities: { channel_bootstrap: true },
  } }),
  heartbeatPayload: () => ({ node_id: config.node.node_id, status: 'online', agent_count: agents.length, version: 'nano-dsh/0.1.0' }),
  onFrame: async frame => {
    const payload = frame.payload;
    if (frame.type === 'session.fork.request') await relay.request('session.fork.result', { request_id: payload.request_id, node_id: config.node.node_id, ...await history.fork(payload) });
    if (frame.type === 'node.distill.prompt.request') await relay.request('node.distill.prompt', { request_id: payload.request_id, node_id: config.node.node_id,
      ...await history.distill(payload).catch(error => ({ error_code: 'runtime_unavailable', message: String(error) })) });
    if (['agent.capabilities.resolve', 'node.capabilities.resolve', 'agent.prompt.preview.request', 'node.prompt.preview.request'].includes(frame.type)) {
      const agentId = typeof payload.agent_id === 'string' ? payload.agent_id : undefined;
      const current = config.agents.find(agent => agent.agent_id === agentId);
      if (agentId && !current) throw new Error('Capability request has no Agent on this node');
      const preview = frame.type.endsWith('preview.request');
      const workspace = current?.workspace_root ?? (typeof payload.workspace_root === 'string' && payload.workspace_root
        ? payload.workspace_root : join(config.node.workspace_base ?? join(home, 'workspaces'), String(payload.agent_id_hint ?? 'preview')));
      const candidate = configuration.runtime({ ...current, agent_id: agentId ?? 'preview', workspace_root: workspace,
        ...(preview ? { features: payload.features as Record<string, boolean>, custom_prompt: payload.custom_prompt as string,
          tool_allowlist: payload.tool_ids ?? [], skills: payload.skill_ids ?? [], skills_selection_mode: 'explicit_allowlist', work_mode: payload.work_mode as 'single_thread' | 'global' } : {}),
      });
      if (preview || !current) {
        const result = await runtime.request('configuration.preview', { config: candidate, cwd: workspace }) as { prompt: string; section_count: number; catalog: Parameters<typeof projectCapabilities>[0] };
        await relay.request(preview ? frame.type.replace('.request', '') : 'node.capabilities', { request_id: payload.request_id, node_id: config.node.node_id,
          ...(preview ? { preview: { prompt: result.prompt, section_count: result.section_count } } : { capabilities: projectCapabilities(result.catalog, config) }) });
      } else {
        const catalog = await runtime.request('configuration.catalog', { agentId, cwd: workspace }) as Parameters<typeof projectCapabilities>[0];
        await relay.request('agent.capabilities', { request_id: payload.request_id, node_id: config.node.node_id, agent_id: agentId, workspace_root: workspace,
          capabilities: projectCapabilities(catalog, config, candidate) });
      }
    }
    if (['channels.bootstrap.request', 'channel.reconcile', 'channel.reconnect'].includes(frame.type)) await managed.handle(frame);
    if (frame.type === 'node.skills.usage.request') {
      const agentId = String(payload.agent_id);
      const usage = await runtime.request('knowledge.usage', { agentId }) as Record<string, unknown>;
      await relay.request('node.skills.usage', { request_id: payload.request_id, node_id: config.node.node_id, usage: { agent_id: agentId, node_id: config.node.node_id, ...usage } });
    }
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
      if (store.priorRelay(input.idempotency_key)) return;
      if (agents.find(agent => agent.agentId === input.agent_id)?.mode === 'global') await globalProduct.receive(input);
      else await product.receive(input);
    }
    if (frame.type === 'node.streaming_delta' && frame.payload.kind === 'permission_response') await product.permission(frame.payload);
  },
  onState: async state => { if (state === 'revoked') managed.revoke(); if (state === 'ready') { await managed.flush(); await external.recover(); await product.recover(); await globalProduct.recover(); if (knowledge) await knowledge.recover(); if (workflows) await workflows.recover(); if (usage) await usage.recover(); } },
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

async function im(path: string, options?: RequestInit): Promise<unknown> {
    const url = new URL(path, config.im_service.url); url.protocol = url.protocol === 'wss:' ? 'https:' : url.protocol === 'ws:' ? 'http:' : url.protocol;
    const response = await fetch(url, { ...options, signal: AbortSignal.timeout(10000), headers: { ...options?.headers, Authorization: `Bearer ${relay.registration?.gateway_access_token ?? config.im_service.token}` } });
    if (!response.ok) throw new Error(`IM external projection failed: ${response.status}`);
    return response.json();
}

external = new ExternalChannels(join(home, 'external.sqlite3'), { nodeId: config.node.node_id, ownerId: config.node.user_id, store, relay,
  onError: reportError, runtimeFooter: config.display?.platforms?.feishu?.runtime_footer?.enabled ?? config.display?.runtime_footer?.enabled,
  attention: input => needsAttention(input, agents.find(agent => agent.agentId === input.agent_id)!),
  receive: input => agents.find(agent => agent.agentId === input.agent_id)?.mode === 'global' ? globalProduct.receive(input) : product.receive(input),
  permission: payload => product.permission(payload),
  im,
});
managed = new ManagedChannels(join(home, 'channels.sqlite3'), { nodeId: config.node.node_id, ownerId: config.node.user_id, key: channelKey, relay,
  hasAgent: id => agents.some(agent => agent.agentId === id), onError: reportError,
  remove: agentId => external.remove(agentId),
  create: (channel, secret, callbacks) => {
    const connection = new FeishuConnection({ appId: channel.config.app_id, appSecret: secret.app_secret!, botOpenId: channel.provider_runtime.bot_open_id, ownerOpenId: channel.provider_runtime.owner_open_id }, {
      receive: message => external.receive(channel.agent_id, message), card: value => external.card(channel.agent_id, value), onError: reportError,
      metadata: callbacks.metadata,
      status: state => { callbacks.status(state); process.stderr.write(`Feishu ${channel.agent_id}: ${state}\n`); },
    });
    external.add(channel.agent_id, connection); return connection;
  },
});
// Disabled local placeholders have no provider identity to enroll.
managed.seed((config.channels ?? []).filter(channel => channel.name.startsWith('feishu:') && (channel.enabled !== false || channel.settings.appId)).map(channel => ({
  agentId: channel.name.slice(7), enabled: channel.enabled !== false, appId: channel.settings.appId!, appSecret: channel.settings.appSecret!, botOpenId: channel.settings.botOpenId, ownerOpenId: channel.settings.ownerOpenId,
})));
product = new SingleThread({
  nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, runtime, relay: external, onError: reportError,
  image: downloadImage,
});
globalProduct = new GlobalAgent({ nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, inbox, runtime, relay: external, image: downloadImage, onError: reportError });
runtime.handle('configuration.workflow', async value => {
  const {agentId, guideline} = value as {agentId: string; guideline: string};
  const next = await configuration.setWorkflowGuideline(agentId, guideline);
  await runtime.request('configuration.apply', next);
  Object.assign(agents.find(agent => agent.agentId === agentId)!, next);
  return {effective: true};
});
runtime.handle('model.check', value => product.modelCheck(value as { sessionId: string; turn: number }));
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
usage = new UsageReports({nodeId: config.node.node_id, store, runtime, relay, onError: reportError});
workflows = new WorkflowResults({agents,store,runtime,receive: (sessionId,input)=>product.background(sessionId,input),onError:reportError});
history = new ConversationHistory({ agents, store, runtime, externalConversation: (agentId, source, chatId) => external.historyConversation(agentId, source, chatId) });
knowledge = new KnowledgeUpdates({ nodeId: config.node.node_id, agents, runtime, store, inbox, relay: external, im, onError: reportError });
heartbeat = new Heartbeat(join(home, 'heartbeat.sqlite3'), { agents, runtime, onError: reportError,
  settings: agentId => (config.agents.find(agent => agent.agent_id === agentId)?.heartbeat ?? {}) as HeartbeatSettings,
  binding: agent => agent.mode === 'global' ? globalProduct.heartbeatBinding(agent) : product.heartbeatBinding(agent),
  available: agentId => runtime.available && (relay.ready || external.available(agentId) && (agents.find(agent => agent.agentId === agentId)?.mode === 'global' || store.canonical(agentId)?.conversationId.startsWith('external:') === true)),
});
runtime.onNotification((method, value) => { if (method === 'heartbeat.subscription') { const data = value as { agentId: string; enabled: boolean }; heartbeat.subscription(data.agentId, data.enabled); } });
await runtime.start();
await managed.start();
await external.recover();
await product.recover(true);
void relay.start().catch(reportError);
heartbeat.start();
process.stdout.write(`Node ${config.node.node_id} ready; DSH pid=${runtime.process!.pid}\n`);
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  try { await managed.stop(); await heartbeat.stop(); await knowledge.stop(); await workflows.stop(); await runtime.shutdown(); await usage.stop(); await product.stop(); await globalProduct.stop(); await operations.close(); await external.stop(); await relay.stop(); inbox.close(); store.close(); }
  catch (error) { reportError(error); process.exitCode = 1; }
  finally {await lifecycle.close();}
}
process.once('SIGTERM', () => { void stop(); });
process.once('SIGINT', () => { void stop(); });
