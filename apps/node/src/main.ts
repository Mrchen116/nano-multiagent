import {featureDependencies, validateCapabilities} from '@nano/product-contracts/capabilities';
import { parseEnv } from 'node:util';
import { execFileSync } from 'node:child_process';
import { NodeAgentLifecycle } from './agent-lifecycle.js';
import { requestIm } from './im-http.js';
import { randomUUID } from 'node:crypto';
import { readFile, mkdir, writeFile, rm } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { RuntimePartitions, type RuntimePartition } from './runtime-partitions.js';
import { NodeConfiguration } from './configuration.js';
import { installedPackageManager, loadNodeRelease } from './release.js';
import { NodeUpdater, updatePath } from './node-updater.js';
import {claimGateway,applyGatewayEnvironment} from './lifecycle.js';
import { providerProfiles } from './providers.js';
import { ModelSetup, type SetupRequest } from './model-setup.js';
import {CapabilityRequests} from './capability-requests.js';
import { NodeTrajectory } from './trajectory.js';
import { WebRelayConnection, FeishuConnection, ChannelKey } from '@nano/channels';
import { WorkSync, NodeStore, TaskExecution, TaskContext, ScheduleDeletions, SingleThread, GlobalAgent, InboxStore, ConfigurationOperations, Heartbeat, ExternalChannels, ManagedChannels, KnowledgeUpdates, WorkflowResults, ConversationHistory, installBuiltinSkills, needsAttention, type HeartbeatSettings, type ProductCall } from '@nano/personal-assistant';
import type { AgentConfiguration, AgentLifecycleSnapshot, RelayInput } from '@nano/product-contracts';
import { prepareProfile, RuntimeSupervisor, ConfigurationInspector } from '@nano/dsh-integration/client';

const configIndex = process.argv.indexOf('--config');
if (configIndex < 0 || !process.argv[configIndex + 1]) throw new Error('Usage: node apps/node/lib/main.js --config <gateway.yaml>');
const configPath = resolve(process.argv[configIndex + 1]!);
try {
  const migration = JSON.parse(await readFile(join(dirname(configPath), 'migration-report.json'), 'utf8')) as {blockers: string[]};
  if(migration.blockers.length)throw new Error(`Migration has ${migration.blockers.length} unreconciled operations; inspect migration-report.json before starting`);
} catch(error) { if((error as NodeJS.ErrnoException).code !== 'ENOENT')throw error; }
const configuration = await NodeConfiguration.read(configPath);
const config = configuration.value;
const release = await loadNodeRelease();
let updateHolding: string | undefined;
let admissions = 0;
async function admitted<T>(action: () => Promise<T>): Promise<T> {
  if (updateHolding) throw new Error('Computer is preparing to update');
  admissions++;
  try { return await action(); } finally { admissions--; }
}
applyGatewayEnvironment(config);
const imOverride=process.argv.indexOf('--im-service-url');if(imOverride>=0)config.im_service.url=process.argv[imOverride+1]!;
const lifecycle=await claimGateway(configPath);
if (!config.node.user_id || !config.im_service.token) throw new Error('Bind this node before starting its runtime');
const home = join(dirname(configPath), '.dsh-runtime', config.node.node_id);
await mkdir(home, { recursive: true });
const { providers, env } = providerProfiles(config.llm);
const modelEnvironment = await readFile(join(home, '.env'), 'utf8').catch(error => { if (error.code === 'ENOENT') return ''; throw error; });
Object.assign(env, parseEnv(modelEnvironment));
const inspector = new ConfigurationInspector({root:join(home,'.configuration-inspections'),env,onLog:text=>process.stderr.write(text)});
// Failed inspection recovery must not prevent durable conversation runtimes from starting.
await inspector.initialize().catch(error => process.stderr.write(`${String(error)}\n`));
const machineBoot = process.platform === 'darwin' ? execFileSync('/usr/sbin/sysctl', ['-n', 'kern.boottime'], {encoding:'utf8'}).trim() : (await readFile('/proc/sys/kernel/random/boot_id','utf8')).trim();
await installBuiltinSkills(join(configuration.ownerRoot, 'skills'));
for (const agent of config.agents) {
  // Persisted explicit tool restrictions may leave new Dreaming unavailable after upgrade.
  const invalid = validateCapabilities(agent, {features:featureDependencies.filter(feature => feature.key !== 'dreaming')});
  if (invalid.length) throw new Error(`Invalid capability dependencies for ${agent.agent_id}: ${JSON.stringify(invalid)}`);
}
const agents: AgentConfiguration[] = config.agents.map(agent => configuration.runtime(agent));
const store = new NodeStore(join(home, 'node.sqlite3'), config.node.user_id);
const inbox = new InboxStore(join(home, 'global.sqlite3'));
let agentLifecycle: NodeAgentLifecycle;
let lifecycleSync: Promise<void> = Promise.resolve();
const supervisors = new Map<string, RuntimeSupervisor>();
let product: SingleThread;
let tasks:TaskExecution;
const productCalls=new Map<string,{sessionId:string;promise:Promise<unknown>}>();
let globalProduct: GlobalAgent;
let operations: ConfigurationOperations;
let heartbeat: Heartbeat;
let external: ExternalChannels;
let managed: ManagedChannels;
const knowledgeByPartition = new Map<string, KnowledgeUpdates>();
const knowledge = { get busy() { return [...knowledgeByPartition.values()].some(item => item.busy); },
  recover: () => settlePartitions([...knowledgeByPartition].filter(([key]) => runtime.partitions.get(key)?.runtime.available).map(([, item]) => item.recover())),
  migrateSkills: () => settlePartitions([...knowledgeByPartition].filter(([key]) => runtime.partitions.get(key)?.runtime.available).map(([, item]) => item.migrateSkills())),
  stop: () => Promise.all([...knowledgeByPartition.values()].map(item => item.stop())) };
let history: ConversationHistory;
const workflowsByPartition = new Map<string, WorkflowResults>();
const workflows = { get busy() { return [...workflowsByPartition.values()].some(item => item.busy); },
  recover: () => settlePartitions([...workflowsByPartition].filter(([key]) => runtime.partitions.get(key)?.runtime.available).map(([, item]) => item.recover())),
  stop: () => Promise.all([...workflowsByPartition.values()].map(item => item.stop())) };
let trajectory: NodeTrajectory;
const channelKey = await ChannelKey.load(join(dirname(configPath), 'channel-credentials-v1.pem'));
const reportError = (error: unknown) => process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
async function settlePartitions(tasks: Promise<unknown>[]): Promise<void> {
  for (const result of await Promise.allSettled(tasks)) if (result.status === 'rejected') reportError(result.reason);
}
function installPartitionConsumers(partition: RuntimePartition): void {
  if (!product || knowledgeByPartition.has(partition.key)) return;
  const port = runtime.scoped(partition);
  const partitionKey = partition.key === 'ordinary' ? undefined : partition.key;
  knowledgeByPartition.set(partition.key, new KnowledgeUpdates({ nodeId: config.node.node_id, agents: partition.agents,
    runtime: port, partitionKey, store, inbox, relay: external, im, onError: reportError, onWork:()=>workSync.signal() }));
  workflowsByPartition.set(partition.key, new WorkflowResults({ agents: partition.agents, store, runtime: port, partitionKey,
    receive: (sessionId, input) => product.background(sessionId, input), onError: reportError }));
}
async function reportPersonalAvailability(partition: RuntimePartition, available: boolean) {
  if(!relay.ready)return;
  for(const agent of partition.agents) if(agent.personal) await relay.request('pa.runtime.status',{
    request_id:randomUUID(),node_id:config.node.node_id,agent_id:agent.agentId,binding_id:agent.personal.bindingId,epoch:agent.personal.epoch,available,
  }).catch(reportError);
}
const runtime = new RuntimePartitions({ agents, bindings: () => store.bindings(), onError: reportError,
  allowed: agentId => agentLifecycle?.allowed(agentId) === true,
  execution: (agentId, action, revision) => store.lifecycle.run(agentId, revision, action),
  create: partition => {
    const partitionHome = partition.key === 'ordinary' ? home : join(home, 'pa', Buffer.from(partition.key).toString('base64url'));
    const supervisor = new RuntimeSupervisor({ home: partitionHome, cwd: partitionHome, env, inspector,
      onLog: text => process.stderr.write(text),
      initialize: async rpc => {
        await writeFile(join(partitionHome, 'runtime.pid'), String(supervisor.process!.pid));
        for (const agent of partition.agents) if (agentLifecycle.allowed(agent.agentId)) await agentLifecycle.launching(agent.agentId, supervisor.processInstanceId!);
        if (partition.key !== 'ordinary') {
          const snapshot = await runtime.partitions.get('ordinary')!.runtime.request('model.setup.snapshot', {});
          await rpc.request('model.setup.sync', snapshot);
        }
        const frozen = await Promise.all(partition.agents.map(agent => relay.request('task.execution.frozen_schedules', {node_id:config.node.node_id,agent_id:agent.agentId}, {priority:'control'})));
        const states = Object.fromEntries(partition.agents.map(agent => {
          const state = store.lifecycle.snapshot(agent.agentId)!;
          return [agent.agentId, {revision:state.revision, disabled:state.desired==='disabled', disabledThroughRevision:state.disabled_through_revision}];
        }));
        await rpc.request('initialize', { protocol: 1, blockedScheduleIds: frozen.flatMap(frame => frame.payload.schedule_ids ?? []), lifecycle: states, taskStopFences:store.controls().filter(i=>i.action==='task-stop'&&partition.agents.some(a=>a.agentId===i.binding.agentId)).map(i=>({sessionId:i.binding.sessionId,stoppedAt:i.stoppedAt??i.input.message.created_at})), taskStops:store.controls().filter(i=>i.action==='task-stop'&&!i.text&&partition.agents.some(a=>a.agentId===i.binding.agentId)).map(i=>i.binding.sessionId), packageManager: installedPackageManager(release), agents: partition.agents,
          providers: providerProfiles(config.llm).providers,
          pendingConfigurations: operations?.pending().filter(item => partition.agents.some(agent => agent.agentId === item.candidate.agent_id)).map(item => ({operationId: item.intent.operation_id, fingerprint: item.intent.candidate_fingerprint, config: configuration.runtime(item.candidate)})) ?? [],
          bindings: store.bindings().filter(binding => partition.agents.some(agent => agent.agentId === binding.agentId)).map(({ conversationId: _, ...binding }) => binding) });
      },
      onReady: async () => {
        for (const agent of partition.agents) if (agentLifecycle.allowed(agent.agentId)) await agentLifecycle.ready(agent.agentId, supervisor.processInstanceId!);
        installPartitionConsumers(partition);
        await reportPersonalAvailability(partition,true);
        if (!updateHolding) await admitted(async () => {
          if (partition.key === 'ordinary') await modelSetup.recover();
          if (operations) {
            if (partition.key === 'ordinary') await operations.recover();
            else queueMicrotask(() => { void operations.recover().catch(reportError); });
          }
          if (relay.ready) await knowledgeByPartition.get(partition.key)?.migrateSkills();
          if (product) {
            if(relay.ready){await tasks.recoverStops(partition.agents.filter(a=>runtime.availableFor(a.agentId)).map(a=>a.agentId));await scheduleDeletions.recover(partition.agents.filter(a=>runtime.availableFor(a.agentId)).map(a=>a.agentId));await tasks.recover(partition.agents.filter(a=>runtime.availableFor(a.agentId)).map(a=>a.agentId));}
            await settlePartitions([product.recover(!relay.ready), globalProduct.recover(), external.recover(),
              knowledgeByPartition.get(partition.key)!.recover(), workflowsByPartition.get(partition.key)!.recover()]);
          }
        });
        if (partition.key === 'ordinary') await lifecycle.ready(supervisor.process!.pid!);
      },
      onError: reportError,
      onUnavailable: async () => {
        await reportPersonalAvailability(partition,false);
        for (const observer of runtime.unavailable(partition)) trajectory?.close(observer);
        if (partition.key === 'ordinary') { await rm(updatePath(configPath, '.node-update-handoff.json'), {force:true}); await lifecycle.unavailable(); }
      },
    });
    supervisors.set(partition.key, supervisor);
    return { get available() { return supervisor.available; },
      request: (method, params) => supervisor.request(method, params),
      onNotification: listener => supervisor.onNotification(listener),
      handle: (method, handler) => supervisor.handle(method, handler),
      start: async () => { await mkdir(partitionHome, {recursive:true, mode:0o700}); await prepareProfile(partitionHome, [{id:'llm-pi-ai', config:{providers:providerProfiles(config.llm).providers}}]); await supervisor.start(); },
      shutdown: () => supervisor.shutdown(),
    };
  },
});
const modelSetup = new ModelSetup(configuration, runtime);
const relay = new WebRelayConnection({
  url: config.im_service.url,
  requiredCapabilities:['relay_request_ids','work_sync_http','agent_lifecycle_v1'],
  credentials: () => ({ accessToken: config.im_service.token, registration: {
    node_id: config.node.node_id, node_name: config.node.node_name ?? config.node.node_id, version: release.version, release,
    agents: agents.map(agent => agent.agentId), user_id: config.node.user_id,
    agent_configurations: Object.fromEntries(config.agents.map(agent => [agent.agent_id, configuration.current(agent.agent_id)])),
    agent_workspaces: Object.fromEntries(agents.map(agent => [agent.agentId, agent.workspace])),
    agent_work_modes: Object.fromEntries(agents.map(agent => [agent.agentId, agent.mode])),
    agent_skills: Object.fromEntries(config.agents.map(agent => [agent.agent_id, agent.skills ?? []])),
    agent_skills_selection_modes: Object.fromEntries(config.agents.map(agent => [agent.agent_id, configuration.current(agent.agent_id)?.skills_selection_mode])),
    agent_tool_allowlist: Object.fromEntries(config.agents.map(agent => [agent.agent_id, agent.tool_allowlist ?? []])),
    ...channelKey.registration, capabilities: { channel_bootstrap: true, model_setup: true, agent_lifecycle_v1: true },
  } }),
  heartbeatPayload: () => ({ node_id: config.node.node_id, status: 'online', agent_count: agents.length, version: release.version }),
  onFrame: async frame => {
    const payload = frame.payload;
    if (frame.type === 'node.request.cancel') {await capabilityRequests.handle(frame);return;}
    if (capabilityRequests.accepts(frame.type)) {await admitted(()=>capabilityRequests.handle(frame));return;}
    if (frame.type === 'agent.lifecycle.apply') { await agentLifecycle.apply(payload as unknown as AgentLifecycleSnapshot); return; }
    await lifecycleSync;
    if (frame.type === 'pa.observations.available') { await globalProduct.recoverPersonalObservations(); return; }
    if (frame.type === 'user.timezone') { store.setOwnerTimezone(String(payload.timezone)); return; }
    if (frame.type === 'node.update.request') { await updater.request(String(payload.operation_id)); return; }
    const permission = frame.type === 'node.streaming_delta' && payload.kind === 'permission_response';
    if (updateHolding && !permission) return; // Unacknowledged relays remain in IM and are replayed after release.
    admissions++;
    try {
    if (frame.type === 'node.setup.request') {
      const status = await modelSetup.handle(payload as unknown as SetupRequest).catch(error => ({ error_code: 'setup_invalid', message: 'Model setup is unavailable' }));
      await relay.request('node.setup', { request_id: payload.request_id, node_id: config.node.node_id, ...status });
      return;
    }
    if(frame.type==='task.execution.state') {
      const result=await runtime.request('task.execution.state',{agentId:String(payload.agent_id)}).catch(()=>({state:'unknown'})) as import('@nano/product-contracts').TaskExecutionState;
      await relay.request('task.execution.state.result',{...result,request_id:payload.request_id,node_id:config.node.node_id});return;
    }
    if(frame.type==='task.wait.validate') {
      const result=await tasks.inspect(payload as unknown as Parameters<TaskExecution['inspect']>[0]).catch(error=>({error:String(error)}));
      await relay.request('task.wait.validate.result',{...result,request_id:payload.request_id,node_id:config.node.node_id});return;
    }
    if(frame.type==='task.execution.changed'){await tasks.recover([String(payload.agent_id)]);return;}
    if (frame.type === 'trajectory.prepare') { trajectory.prepare(payload.scope as Parameters<NodeTrajectory['prepare']>[0], String(payload.ticket)); return; }
    if (frame.type === 'trajectory.close') { trajectory.close(String(payload.observer_id)); return; }
    if (frame.type === 'session.fork.request') await relay.request('session.fork.result', { request_id: payload.request_id, node_id: config.node.node_id, ...await history.fork(payload) });
    if (frame.type === 'node.distill.prompt.request') await relay.request('node.distill.prompt', { request_id: payload.request_id, node_id: config.node.node_id,
      ...await history.distill(payload).catch(error => ({ error_code: 'runtime_unavailable', message: String(error) })) });
    if (frame.type === 'node.approval.resolve') {
      const workspace = resolve(String(payload.workspace_root));
      await relay.request('node.approval.resolve.result', {request_id: payload.request_id, node_id: config.node.node_id,
        inherited_approval_rules: configuration.inheritedApproval(workspace).rules});
      return;
    }
    if (['channels.bootstrap.request', 'channel.reconcile', 'channel.reconnect'].includes(frame.type)) await managed.handle(frame);
    if (frame.type === 'node.plugins.request') {
      const result = await (async () => {
        const agentId = String(payload.agent_id);
        if (!config.agents.some(agent => agent.agent_id === agentId)) throw new Error('Plugin request has no Agent on this node');
        return {plugins: await runtime.request('plugins.manage', {agentId, action: payload.action, target: payload.target, enabled: payload.enabled})};
      })().catch(error => ({error: String(error)}));
      if (payload.action !== 'list_bundles' && !('error' in result)) publishCatalogChange();
      await relay.request('node.plugins', {request_id: payload.request_id, node_id: config.node.node_id, ...result});
    }
    if (frame.type === 'agent.capability-usage.request') {
      const agentId = String(payload.agent_id);
      const result = await (async () => {
        const usage = await runtime.request('configuration.usage', {agentId}) as {checked_at: string; active_schedules: number; busy: {kind: string; name: string}[]};
        if (heartbeat.busyFor(agentId)) usage.busy.push({kind: 'feature', name: 'heartbeat'});
        return {usage};
      })().catch(() => ({error: {code: 'capability_usage_unavailable', message: 'Unable to confirm capability usage'}}));
      await relay.request('agent.capability-usage', {request_id: payload.request_id, node_id: config.node.node_id, agent_id: agentId, ...result});
    }
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
      const jobs = await runtime.request('schedule.command', { agentId: agent.agentId, action: 'jobs' }) as { id: string; sessionId: string }[];
      if (frame.type === 'node.cron.jobs.request') await relay.request('node.cron.jobs', { request_id: payload.request_id, node_id: config.node.node_id, jobs });
      else {
        const job = jobs.find(job => job.id === payload.job_id);
        const result = job ? await scheduleDeletions.delete({agentId:agent.agentId,scheduleId:job.id,operationId:String(payload.operation_id??''),actor:{kind:'user',id:String(payload.actor_user_id??'')}}) : undefined;
        await relay.request('node.cron.delete', { request_id: payload.request_id, node_id: config.node.node_id, deleted: result?.deleted === true });
      }
    }
    if (frame.type === 'relay.message') {
      const input = frame.payload as unknown as RelayInput;
      if(input.metadata.node_epoch !== undefined && input.metadata.node_epoch!==relay.registration?.node_epoch)throw new Error('Stale relay epoch');
      if (!agents.some(agent=>agent.agentId===input.agent_id))throw new Error('Unknown relay target');
      if (agents.find(agent => agent.agentId === input.agent_id)?.mode === 'global') await globalProduct.receive(input);
      else await product.receive(input);
    }
    if (frame.type === 'node.streaming_delta' && frame.payload.kind === 'permission_response') await product.permission(frame.payload);
    } finally { admissions--; }
  },
  onState: async state => {
    if (state !== 'ready') capabilityRequests.cancelAll();
    if(state==='ready') {
      lifecycleSync = agentLifecycle.synchronize(relay.registration?.agent_lifecycles as AgentLifecycleSnapshot[]);
      await lifecycleSync;
      await runtime.start();
      workAvailable=true;workSync.signal();
      if(typeof relay.registration?.owner_timezone==='string')store.setOwnerTimezone(relay.registration.owner_timezone);
    }
    await lifecycle.connected(state==='ready');
    if(state!=='ready')trajectory?.closeAll();
    if(state==='revoked') {workAvailable=false;managed.revoke();}
    if(state==='ready' && !updateHolding)await admitted(async()=>{
      await tasks.recoverStops(agents.filter(a=>runtime.availableFor(a.agentId)).map(a=>a.agentId));
      await scheduleDeletions.recover(agents.filter(a=>runtime.availableFor(a.agentId)).map(a=>a.agentId));
      await tasks.recover(agents.filter(a=>runtime.availableFor(a.agentId)).map(a=>a.agentId));
      await settlePartitions([globalProduct.recover(), (async()=>{
        for(const partition of runtime.partitions.values())await reportPersonalAvailability(partition,partition.runtime.available);
        await knowledge.migrateSkills();await managed.flush();await external.recover();await product.recover();
        await knowledge.recover();await workflows.recover();
      })()]);
    });
  },
  onError: reportError,
  onDiagnostic: event => { process.stderr.write(`${JSON.stringify({ ...event, node_id: config.node.node_id, component: 'im_relay' })}\n`); },
});
const capabilityRequests = new CapabilityRequests({configuration,inspector,packageManager:installedPackageManager(release),
  reply:(type,payload)=>relay.request(type,payload)});
function publishCatalogChange() {
  inspector.invalidate();
  if (relay.ready) void relay.request('node.capabilities.changed',{node_id:config.node.node_id}).catch(reportError);
}
configuration.onModelsChanged = publishCatalogChange;
trajectory = new NodeTrajectory({ imUrl: config.im_service.url, runtime, valid: scope => {
  const binding = store.bindings().find(binding => binding.sessionId === scope.rootSessionId);
  return relay.ready && scope.nodeId === config.node.node_id && scope.ownerId === config.node.user_id
    && scope.nodeEpoch === relay.registration?.node_epoch && binding?.ownerId === scope.ownerId
    && binding?.agentId === scope.rootAgentId && binding.conversationId === `global:${scope.rootAgentId}`;
} });
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
    return requestIm(config.im_service.url, relay.registration?.gateway_access_token ?? config.im_service.token, path, options);
}

external = new ExternalChannels(join(home, 'external.sqlite3'), { nodeId: config.node.node_id, ownerId: config.node.user_id, store, relay,
  personalAgent: id => !!agents.find(agent => agent.agentId === id)?.personal,
  personalDelivery: delivery => globalProduct.externalDelivery(delivery),
  onError: reportError, runtimeFooter: config.display?.platforms?.feishu?.runtime_footer?.enabled ?? config.display?.runtime_footer?.enabled,
  attention: input => needsAttention(input, agents.find(agent => agent.agentId === input.agent_id)!),
  receive: input => admitted(() => agents.find(agent => agent.agentId === input.agent_id)?.mode === 'global' ? globalProduct.receive(input) : product.receive(input)),
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
tasks=new TaskExecution({nodeId:config.node.node_id,ownerId:config.node.user_id,agents,store,runtime,relay,context:binding=>taskContext.prepare({sessionId:binding.sessionId,agentId:binding.agentId,ownerId:binding.ownerId}),
  drain:async sessionId=>{await Promise.allSettled([...productCalls.values()].filter(c=>c.sessionId===sessionId).map(c=>c.promise));},
});
product = new SingleThread({
  nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, runtime, relay: external, onError: reportError,
  image: downloadImage, taskStop:(binding,input)=>tasks.stop(binding,input),
});
let workAvailable=false;
const workSync=new WorkSync({nodeId:config.node.node_id,inbox,url:config.im_service.url,credentials:()=>config.im_service.token,available:()=>workAvailable,onError:reportError});
globalProduct = new GlobalAgent({ nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, inbox, runtime, relay: external, image: downloadImage, onError: reportError, onWork:()=>workSync.signal(), authorityEpoch:()=>relay.registration?.node_epoch,taskStop:(binding,input)=>tasks.stop(binding,input) });
runtime.handle('configuration.workflow', async value => {
  const {agentId, guideline} = value as {agentId: string; guideline: string};
  const next = await configuration.setWorkflowGuideline(agentId, guideline);
  await runtime.request('configuration.apply', next);
  Object.assign(agents.find(agent => agent.agentId === agentId)!, next);
  return {effective: true};
});
runtime.handle('model.check', value => product.modelCheck(value as { sessionId: string; turn: number }));
const scheduleDeletions=new ScheduleDeletions({ownerId:config.node.user_id,agents,store,runtime,onError:reportError,repair:intent=>tasks.scheduleDeleted(intent),
 notify:async intent=>{
  await runtime.request('schedule.deleted.notify',{agentId:intent.agentId,sessionId:intent.sessionId,inputId:intent.changeInputId,content:[{type:'text',text:'The user deleted the Schedule identified below. It will no longer wake you as planned. Account for this change when checking your existing arrangements. This is a Schedule change, not a new task or permission, and it does not resume paused work.\n'+JSON.stringify({schedule_id:intent.scheduleId,title:intent.title,agent_id:intent.agentId,session_id:intent.sessionId,deleted_at:intent.deletedAt,actor:intent.actor})}]});
 }});
const taskContext=new TaskContext({nodeId:config.node.node_id,ownerId:config.node.user_id,agents,store,inbox,runtime,relay,refreshSources:agentId=>globalProduct.prepareSystemContext(agentId)});
runtime.handle('product.task_context.prepare',value=>taskContext.prepare(value as Parameters<TaskContext['prepare']>[0]));
runtime.handle('product.task_context.commit',value=>taskContext.commit(value as Parameters<TaskContext['commit']>[0]));
runtime.handle('product.task_execution.snapshot', value=>tasks.snapshot(value as Parameters<TaskExecution['snapshot']>[0]));
runtime.handle('product.call', value=>{
  const call=value as ProductCall;
  const promise=call.method==='schedule.delete'?(async()=>{
    const binding=store.bindings().find(binding=>binding.sessionId===(call.rootSessionId??call.sessionId));
    if(!binding||binding.agentId!==call.agentId||binding.ownerId!==call.ownerId||call.ownerId!==config.node.user_id)throw new Error('Invalid Schedule tool identity');
    const args=call.args as {id?:unknown};if(typeof args.id!=='string')throw new Error('Invalid Schedule identity');
    store.lifecycle.assert(call.agentId);
    return scheduleDeletions.delete({operationId:call.operationId,agentId:call.agentId,sessionId:call.sessionId,scheduleId:args.id,actor:{kind:'agent',id:call.agentId}});
  })():globalProduct.call(call);productCalls.set(call.operationId,{sessionId:call.rootSessionId,promise});
  void promise.finally(()=>productCalls.delete(call.operationId)).catch(()=>{});return promise;
});
operations = new ConfigurationOperations(join(home, 'configuration.sqlite3'), {
  current: agentId => configuration.current(agentId),
  resolve: (candidate, creating) => configuration.resolve(candidate, creating),
  persist: candidate => configuration.persist(candidate),
  prepare: async (candidate, intent) => {
    const previous = agents.find(agent => agent.agentId === candidate.agent_id);
    const withdrawHeartbeat = previous?.features?.heartbeat === true && candidate.features.heartbeat !== true;
    if (withdrawHeartbeat && !heartbeat.hold(candidate.agent_id, intent.operation_id)) {
      heartbeat.release(candidate.agent_id, intent.operation_id);
      return {ready: false, error_code: 'capability_in_use', message: 'Heartbeat is active', blocks: [{code: 'capability_busy', target: {kind: 'feature', name: 'heartbeat'}}]};
    }
    try {
      return await runtime.request('configuration.prepare', {operationId: intent.operation_id, fingerprint: intent.candidate_fingerprint, config: configuration.runtime(candidate)}) as import('@nano/personal-assistant').ConfigurationPreparation;
    } catch { heartbeat.release(candidate.agent_id, intent.operation_id); return {ready: false, error_code: 'capability_usage_unavailable', message: 'Unable to confirm capability usage'}; }
  },
  release: async (candidate, intent) => {
    heartbeat.release(candidate.agent_id, intent.operation_id);
    if (runtime.availableFor(candidate.agent_id)) await runtime.request('configuration.release', {agentId: candidate.agent_id, operationId: intent.operation_id});
  },
  apply: async (candidate, intent) => {
    const next = configuration.runtime(candidate);
    const applied = await runtime.request('configuration.apply', {...next, operationId: intent.operation_id, fingerprint: intent.candidate_fingerprint}) as {effective: boolean; message?: string};
    if (!applied.effective) throw new Error(applied.message ?? 'Configuration was not applied');
    const previous = agents.find(agent => agent.agentId === next.agentId);
    if (previous) Object.assign(previous, next); else agents.push(next);
    if (runtime.availableFor(next.agentId)) {
      if (next.personal) await reportPersonalAvailability(runtime.forAgent(next.agentId), true);
      await tasks.recoverStops([next.agentId]);
      await scheduleDeletions.recover([next.agentId]);
      await tasks.recover([next.agentId]);
    }
  },
});

history = new ConversationHistory({ agents, store, runtime, externalConversation: (agentId, source, chatId) => external.historyConversation(agentId, source, chatId) });
for (const partition of runtime.partitions.values()) installPartitionConsumers(partition);
heartbeat = new Heartbeat(join(home, 'heartbeat.sqlite3'), { agents, runtime, lifecycle: store.lifecycle, onError: reportError,
  settings: agentId => ({ ...(config.agents.find(agent => agent.agent_id === agentId)?.heartbeat ?? {}), timezone: store.ownerTimezone }) as HeartbeatSettings,
  binding: agent => agent.mode === 'global' ? globalProduct.heartbeatBinding(agent) : product.heartbeatBinding(agent),
  available: agentId => !updateHolding && runtime.availableFor(agentId) && (relay.ready || external.available(agentId) && (agents.find(agent => agent.agentId === agentId)?.mode === 'global' || store.canonical(agentId)?.conversationId.startsWith('external:') === true)),
});
runtime.onNotification((method, value) => { if (method === 'configuration.catalog.changed' || method === 'knowledge.changed') publishCatalogChange(); if (method === 'heartbeat.subscription') { const data = value as { agentId: string; enabled: boolean }; heartbeat.subscription(data.agentId, data.enabled); } });
const updater = new NodeUpdater(configuration, {
  onError: reportError,
  prepare: async operationId => {
    if (updateHolding && updateHolding !== operationId) return false;
    updateHolding = operationId;
    const busy = () => admissions > 0 || inspector.metrics().preview_active > 0 || modelSetup.busy || product.busy || globalProduct.busy || heartbeat.busy || operations.busy || knowledge.busy || workflows.busy;
    if (!runtime.available || busy()) return false;
    const result = await runtime.request('update.prepare', {operationId}) as {ready: boolean};
    return result.ready && !busy();
  },
  resume: async operationId => {
    if (updateHolding && updateHolding !== operationId) return;
    if (runtime.available) await runtime.request('update.release', {operationId});
    updateHolding = undefined;
    if (runtime.available && !stopping) await admitted(async () => {
      await external.recover(); await product.recover(!relay.ready); await globalProduct.recover();
      await knowledge.recover(); await workflows.recover();
    });
  },
});
let stopping = false;
agentLifecycle = new NodeAgentLifecycle({
  nodeId: config.node.node_id, boot: machineBoot,
  snapshot: agentId => store.lifecycle.snapshot(agentId), save: state => store.lifecycle.save(state),
  proof: agentId => store.lifecycle.proof(agentId),
  saveProof: (agentId, proof) => store.lifecycle.saveProof(agentId, proof),
  host: agentId => {
    const supervisor = supervisors.get(runtime.forAgent(agentId).key)!;
    return {get available() {return supervisor.available;}, get processInstanceId() {return supervisor.processInstanceId;}, disable: async () => {
      await runtime.startAgent(agentId);
      const cursors = Object.fromEntries(store.bindings().filter(binding => binding.agentId === agentId).flatMap(binding => {
        const cuts = inbox.workCheckpoints(binding.sessionId);
        return [[binding.sessionId, store.cursor(binding.sessionId)], ...Object.entries(cuts).map(([id, cut]) => [id, cut.replayFrom - 1])];
      }));
      const result = await supervisor.disableAgent(agentId, store.lifecycle.snapshot(agentId)!.revision, cursors);
      if (result.confirmed) globalProduct.recordStopped(agentId, result.history ?? []);
      return result;
    }};
  },
  start: async agentId => {
    await runtime.startAgent(agentId);
    const state = store.lifecycle.snapshot(agentId)!;
    const frozen = await relay.request('task.execution.frozen_schedules', {node_id:config.node.node_id,agent_id:agentId}, {priority:'control'});
    const supervisor = supervisors.get(runtime.forAgent(agentId).key)!;
    await supervisor.request('agent.enable', {agentId, revision:state.revision, disabledThroughRevision:state.disabled_through_revision, blockedScheduleIds:frozen.payload.schedule_ids ?? []});
    await agentLifecycle.launching(agentId, supervisor.processInstanceId!);
    await agentLifecycle.ready(agentId, supervisor.processInstanceId!);
  },
  cancel: agentId => { store.cancelAgent(agentId); inbox.cancelAgent(agentId); product.cancelAgent(agentId); globalProduct.cancelAgent(agentId); },
  resetHeartbeat: agentId => heartbeat.resetAgent(agentId),
  report: async report => { await relay.request('agent.lifecycle.report', {...report}, {priority:'control'}); },
});
await updater.start();
await managed.start();
workSync.start();
// Empty nodes have no execution intent to reconcile, but still expose the
// management host while the center is unreachable.
if (!agents.length) await runtime.start();
void relay.start().catch(reportError);
heartbeat.start();
const taskWatch=setInterval(()=>{
  if(relay.ready&&!updateHolding)void tasks.watch().catch(reportError);
},60_000);taskWatch.unref();
process.stdout.write(`Node ${config.node.node_id} ready; DSH hosts=${runtime.partitions.size}\n`);
async function stop() {
  if (stopping) return;
  stopping = true;
  clearInterval(taskWatch);
  trajectory.closeAll();
  try { capabilityRequests.cancelAll(); await inspector.close(); await workSync.stop(); await updater.close(); await modelSetup.stop(); await managed.stop(); await heartbeat.stop(); await knowledge.stop(); await workflows.stop(); await runtime.shutdown(); for (const agent of agents) agentLifecycle.recordStopped(agent.agentId); await product.stop(); await globalProduct.stop(); await operations.close(); await external.stop(); await relay.stop(); inbox.close(); store.close(); }
  catch (error) { reportError(error); process.exitCode = 1; }
  finally {await lifecycle.close();}
}
process.once('SIGTERM', () => { void stop(); });
process.once('SIGINT', () => { void stop(); });
