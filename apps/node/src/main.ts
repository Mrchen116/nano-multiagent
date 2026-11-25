import { typedRuntimeRequest } from '@nano/product-contracts/runtime-rpc';
import {isCurrentSkillUsage,isNodeCommand,nodeCommands,type NodeHandlers,type NodeParams,type NodeReply} from '@nano/product-contracts/node-rpc';
import {dispatchNodeCommand} from './node-rpc.js';
import {definitionsForRole, effectiveFeatures, validateCapabilities} from '@nano/product-contracts/capabilities';
import { parseEnv } from 'node:util';
import { windowsHost } from './windows-platform.js';
import { createInterface } from 'node:readline';
import { execFileSync } from 'node:child_process';
import { AgentDeletionLedger, NodeAgentDeletions } from './agent-deletion.js';
import { NodeAgentLifecycle } from './agent-lifecycle.js';
import { requestIm, type ImRequestOptions } from './im-http.js';
import { uploadScreenshot } from './screenshot-upload.js';
import { uploadAttachment, downloadAttachment } from './file-transfer.js';
import { randomUUID } from 'node:crypto';
import { readFile, mkdir, writeFile, rm } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { RuntimePartitions, type RuntimePartition } from './runtime-partitions.js';
import { NodeConfiguration } from './configuration.js';
import { installedPackageManager, loadNodeRelease } from './release.js';
import { NodeUpdater, updatePath } from './node-updater.js';
import {claimGateway,applyGatewayEnvironment} from './lifecycle.js';
import { providerProfiles } from './providers.js';
import { ModelSetup } from './model-setup.js';
import {CapabilityRequests} from './capability-requests.js';
import { NodeTrajectory } from './trajectory.js';
import { WebRelayConnection, FeishuConnection, ChannelKey } from '@nano/channels';
import { WorkSync, NodeStore, TaskExecution, TaskContext, ScheduleDeletions, SingleThread, GlobalAgent, InboxStore, ConfigurationOperations, Heartbeat, ProactiveCoordinator, isProactivePlanningEnabled, ExternalChannels, ManagedChannels, KnowledgeUpdates, WorkflowResults, ConversationHistory, installBuiltinSkills, needsAttention, type HeartbeatSettings, type ProductCall } from '@nano/personal-assistant';
import type { AgentConfiguration, AgentDeletionIntent, AgentLifecycleSnapshot, ProactiveSyncObservationsInput, RelayInput } from '@nano/product-contracts';
import { prepareProfile, RuntimeSupervisor, ConfigurationInspector } from '@nano/dsh-integration/client';
import { LogicalClockController } from './logical-clock.js';

const configIndex = process.argv.indexOf('--config');
if (configIndex < 0 || !process.argv[configIndex + 1]) throw new Error('Usage: node apps/node/lib/main.js --config <gateway.yaml>');
const configPath = resolve(process.argv[configIndex + 1]!);
try {
  const migration = JSON.parse(await readFile(join(dirname(configPath), 'migration-report.json'), 'utf8')) as {blockers: string[]};
  if(migration.blockers.length)throw new Error(`Migration has ${migration.blockers.length} unreconciled operations; inspect migration-report.json before starting`);
} catch(error) { if((error as NodeJS.ErrnoException).code !== 'ENOENT')throw error; }
const deletionLedger = new AgentDeletionLedger(`${configPath}.deletions.sqlite3`);
const configuration = await NodeConfiguration.read(configPath,deletionLedger.states());
const config = configuration.value;
const release = await loadNodeRelease();
let updateHolding: string | undefined;
let relayRecoveryTimer: ReturnType<typeof setTimeout> | undefined;
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
const machineBoot = process.platform === 'win32' ? await windowsHost('boot') : process.platform === 'darwin' ? execFileSync('/usr/sbin/sysctl', ['-n', 'kern.boottime'], {encoding:'utf8'}).trim() : (await readFile('/proc/sys/kernel/random/boot_id','utf8')).trim();
await installBuiltinSkills(join(configuration.ownerRoot, 'skills'));
for (const agent of config.agents) {
  // Persisted explicit tool restrictions may leave new Dreaming or legacy PA proactive_planning unavailable after upgrade.
  const roleFeatures = definitionsForRole(Boolean(agent.personal_agent)).filter(
    feature => feature.key !== 'dreaming' && (feature.key !== 'proactive_planning' || agent.features?.proactive_planning !== undefined),
  );
  const invalid = validateCapabilities(agent, {features: roleFeatures});
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
let proactiveCoordinator: ProactiveCoordinator;
let logicalClock: LogicalClockController | undefined;
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
type ReadyRecovery = {generation:string; timer?:ReturnType<typeof setTimeout>; resume?:()=>void};
const readyRecovery = new Map<string,ReadyRecovery>();
const readyRecoveryTasks = new Set<Promise<void>>();
let registrationGeneration=0;
function recoverAfterReady(key:string,generation:string,current:()=>boolean,restore:()=>Promise<void>): void {
  const previous=readyRecovery.get(key);
  if (!current() || previous?.generation===generation) return;
  clearTimeout(previous?.timer);
  const recovery:ReadyRecovery={generation};
  readyRecovery.set(key,recovery);
  let delay=1000;
  const run=()=>{
    if (!current() || readyRecovery.get(key)!==recovery) return;
    if (updateHolding) {recovery.resume=run;return;}
    recovery.resume=undefined;
    const task=admitted(restore).catch(error=>{
      reportError(error);
      if (!current() || readyRecovery.get(key)!==recovery) return;
      recovery.timer=setTimeout(run,delay);
      recovery.timer.unref();
      delay=Math.min(delay*2,30_000);
    }).finally(()=>{readyRecoveryTasks.delete(task);});
    readyRecoveryTasks.add(task);
  };
  queueMicrotask(run);
}
function schedulePartitionRecovery(partition:RuntimePartition,generation:string,current:()=>boolean):void {
  const key=`partition:${partition.key}`;
  for(const {agentId} of partition.agents) {
    const available=()=>current() && runtime.availableFor(agentId);
    recoverAfterReady(`${key}:${agentId}`,generation,available,async()=>{
      await agentLifecycle.waitFor(agentId);
      if(!available())return;
      if(relay.ready) {
        const scope=[agentId];
        await tasks.recoverStops(scope);
        if(!available())return;
        await scheduleDeletions.recover(scope);
        if(!available())return;
        await tasks.recover(scope);
      }
      if(!available())return;
      await product.recover(!relay.ready,[agentId]);
      if(!available())return;
      await Promise.all([globalProduct.recoverForAgent(agentId),external.recover(agentId)]);
      if(available() && partition.agents.some(agent=>agent.agentId===agentId && agent.personal))
        await globalProduct.recoverPersonalObservations();
    });
  }
  recoverAfterReady(key,generation,current,async()=>{
    const knowledge=knowledgeByPartition.get(partition.key);
    if(relay.ready)await knowledge?.migrateSkills();
    if(current())await Promise.all([knowledge?.recover(),workflowsByPartition.get(partition.key)?.recover()]);
  });
}
const runtime = new RuntimePartitions({ agents, bindings: () => store.bindings(), onError: reportError,
  allowed: agentId => agentLifecycle?.allowed(agentId) === true,
  retired: agentId => !!deletionLedger.read(agentId),
  execution: (agentId, action, revision) => store.lifecycle.run(agentId, revision, action),
  create: partition => {
    const partitionHome = partition.key === 'ordinary' ? home : join(home, 'pa', Buffer.from(partition.key).toString('base64url'));
    const supervisor = new RuntimeSupervisor({ home: partitionHome, cwd: partitionHome, env, inspector,
      onLog: text => process.stderr.write(text),
      initialize: async rpc => {
        await writeFile(join(partitionHome, 'runtime.pid'), String(supervisor.process!.pid));
        await Promise.all(partition.agents.filter(agent=>agentLifecycle.allowed(agent.agentId))
          .map(agent=>agentLifecycle.launching(agent.agentId,supervisor.processInstanceId!)));
        if (partition.key !== 'ordinary') {
          const snapshot = await runtime.partitions.get('ordinary')!.runtime.request('model.setup.snapshot', {});
          await rpc.request('model.setup.sync', snapshot);
        }
        const frozen = await Promise.all(partition.agents.map(agent => relay.request('task.execution.frozen_schedules', {node_id:config.node.node_id,agent_id:agent.agentId}, {priority:'control'})));
        const states = Object.fromEntries(partition.agents.map(agent => {
          const state = store.lifecycle.snapshot(agent.agentId)!;
          return [agent.agentId, {revision:state.revision, disabled:state.desired==='disabled', disabledThroughRevision:state.disabled_through_revision}];
        }));
        const stops = store.controls().filter(intent => intent.action === 'task-stop' && partition.agents.some(agent => agent.agentId === intent.binding.agentId));
        await rpc.request('initialize', { protocol: 1, recoveryMarkers: true,
          ownerTimezone: proactiveCoordinator.effectiveTimeZone(),
          ...(logicalClock ? { initialLogicalNowMs: logicalClock.now() } : {}),
          blockedScheduleIds: frozen.flatMap(frame => frame.payload.schedule_ids ?? []), lifecycle: states, taskStopFences:stops.map(i=>({sessionId:i.binding.sessionId,stoppedAt:i.stoppedAt??i.input.message.created_at})), taskStops:stops.filter(i=>!i.text).map(i=>i.binding.sessionId), packageManager: installedPackageManager(release), agents: partition.agents,
          providers: providerProfiles(config.llm).providers,
          pendingConfigurations: operations?.pending().filter(item => partition.agents.some(agent => agent.agentId === item.candidate.agent_id)).map(item => ({operationId: item.intent.operation_id, fingerprint: item.intent.candidate_fingerprint, config: configuration.runtime(item.candidate)})) ?? [],
          bindings: store.bindings().filter(binding => partition.agents.some(agent => agent.agentId === binding.agentId)).map(({ conversationId: _, ...binding }) => binding) });
      },
      onReady: async () => {
        installPartitionConsumers(partition);
        if (!updateHolding) await admitted(async () => {
          if (partition.key === 'ordinary') await modelSetup.recover();
          if (operations) {
            if (partition.key === 'ordinary') await operations.recover();
            else queueMicrotask(() => { void operations.recover().catch(reportError); });
          }
        });
        for (const agent of partition.agents) if (store.lifecycle.snapshot(agent.agentId)?.desired==='disabled')
          void agentLifecycle.recoverStop(agent.agentId).catch(reportError);
        await Promise.all(partition.agents.filter(agent=>agentLifecycle.allowed(agent.agentId))
          .map(agent=>agentLifecycle.ready(agent.agentId,supervisor.processInstanceId!)));
        await reportPersonalAvailability(partition,true);
        if (partition.key === 'ordinary') await lifecycle.ready(supervisor.process!.pid!);
        const generation=partition.generation,registration=registrationGeneration;
        const current=()=>!stopping && partition.generation===generation && registrationGeneration===registration && partition.runtime.available;
        schedulePartitionRecovery(partition,`${generation}:${registration}`,current);
      },
      onError: reportError,
      onUnavailable: async () => {
        globalProduct?.runtimeUnavailable(partition.agents.filter(agent => agent.mode === 'global').map(agent => agent.agentId));
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
      start: async () => { await mkdir(partitionHome, {recursive:true, mode:0o700}); await prepareProfile(partitionHome, [{id:'llm-pi-ai', config:{providers:providerProfiles(config.llm).providers}}], {agentDeletion:partition.key==='ordinary'}); await supervisor.start(); },
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
    ...channelKey.registration, capabilities: { channel_bootstrap: true, model_setup: true, agent_lifecycle_v1: true, agent_deletion_v1: true },
  } }),
  heartbeatPayload: () => ({ node_id: config.node.node_id, status: 'online', agent_count: agents.length, version: release.version }),
  onFrame: async frame => {
    const payload = frame.payload;
    if (frame.type === 'node.request.cancel') {capabilityRequests.cancel(payload.target_request_id);return;}
    const command = isNodeCommand(frame.type) ? frame.type : undefined;
    if (command && nodeCommands[command].inspection) {await admitted(()=>dispatch(command,payload));return;}
    if (frame.type === 'agent.deletion.apply') {
      void deletions.apply(payload as unknown as AgentDeletionIntent).catch(reportError);
      return;
    }
    if (command === 'agent.deletion.preview') {await dispatch(command,payload);return;}
    if (frame.type === 'agent.lifecycle.apply') { await agentLifecycle.apply(payload as unknown as AgentLifecycleSnapshot); return; }
    if (frame.type === 'relay.message' && agentLifecycle.synchronized && typeof payload.agent_id === 'string')
      await agentLifecycle.waitFor(payload.agent_id);
    else await lifecycleSync;
    if (frame.type === 'pa.observations.available') { await globalProduct.recoverPersonalObservations(); return; }
    if (frame.type === 'user.timezone') {
      store.setOwnerTimezone(String(payload.timezone));
      void syncRuntimeTimeZone();
      return;
    }
    if (frame.type === 'node.update.request') { await updater.request(String(payload.operation_id)); return; }
    const permission = frame.type === 'node.streaming_delta' && payload.kind === 'permission_response';
    if (updateHolding && !permission) return; // Unacknowledged relays remain in IM and are replayed after release.
    admissions++;
    try {
    if (command) {await dispatch(command,payload);return;}
    if(frame.type==='task.execution.changed'){await tasks.recover([String(payload.agent_id)]);return;}
    if (frame.type === 'trajectory.prepare') { trajectory.prepare(payload.scope as Parameters<NodeTrajectory['prepare']>[0], String(payload.ticket)); return; }
    if (frame.type === 'trajectory.close') { trajectory.close(String(payload.observer_id)); return; }
    if (['channels.bootstrap.request', 'channel.reconcile', 'channel.reconnect'].includes(frame.type)) await managed.handle(frame);
    if (frame.type === 'heartbeat.trigger') await heartbeat.tick(String(payload.agent_id), true);
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
    clearTimeout(relayRecoveryTimer);
    if (state !== 'ready') {
      capabilityRequests.cancelAll();
      await lifecycle.connected(false);
      trajectory?.closeAll();
      if (state === 'revoked') { workAvailable=false; managed.revoke(); }
      return;
    }
    const registration = relay.registration;
    if (!registration) return;
    const generation=++registrationGeneration;
    const warmPartitions=[...runtime.partitions.values()].filter(partition=>partition.runtime.available)
      .map(partition=>({partition,runtimeGeneration:partition.generation}));
    const current = () => !stopping && relay.ready && relay.registration === registration;
    let initialized = false;
    let delay = 1000;
    const recover = async () => {
      if (!current()) return;
      try {
        if (!initialized) {
          const transitions=agentLifecycle.synchronize(registration.agent_lifecycles as AgentLifecycleSnapshot[]);
          lifecycleSync=transitions;
          // Target-specific Relay dispatch can proceed as soon as its transition
          // completes. Start Work transport before waiting on the rest of the node.
          void transitions.catch(()=>{});
          for(const {partition,runtimeGeneration} of warmPartitions) {
            const runtimeCurrent=()=>current() && partition.generation===runtimeGeneration && partition.runtime.available;
            schedulePartitionRecovery(partition,`${runtimeGeneration}:${generation}`,runtimeCurrent);
          }
          await runtime.start();
          if (!current()) return;
          workAvailable=true;workSync.signal();
          await transitions;
          if (!current()) return;
          for (const intent of (registration.agent_deletions ?? []) as AgentDeletionIntent[])
            void deletions.apply(intent).catch(reportError);
          if (typeof registration.owner_timezone === 'string') {
            store.setOwnerTimezone(registration.owner_timezone);
            await syncRuntimeTimeZone();
          }
          initialized = true;
        }
        recoverAfterReady('relay-registration',String(generation),current,async()=>{
          for(const partition of runtime.partitions.values())await reportPersonalAvailability(partition,partition.runtime.available);
          if(current())await managed.flush();
        });
        if (current()) await lifecycle.connected(true);
      } catch (error) {
        reportError(error);
        // The transport reports callback failures but keeps the connection. Retry
        // the durable cut on this registration before reporting it recovered.
        if (current()) {
          relayRecoveryTimer = setTimeout(() => { void recover(); },delay);
          relayRecoveryTimer.unref();
          delay = Math.min(delay * 2,30_000);
        }
      }
    };
    await recover();
  },
  onError: reportError,
  onDiagnostic: event => { process.stderr.write(`${JSON.stringify({ ...event, node_id: config.node.node_id, component: 'im_relay' })}\n`); },
});
const capabilityRequests = new CapabilityRequests({configuration,inspector,packageManager:installedPackageManager(release)});
function handleConfiguration(kind:'create'|'apply',input:NodeParams<'agent.create'>) {
  return operations.handle(kind,input).catch(error=>{reportError(error);return operations.status(input.operation_id);});
}
function workspaceAgent(input:NodeParams<'node.cron.jobs.request'>) {
  const agent = agents.find(agent=>agent.agentId===input.agent_id || !input.agent_id && agent.workspace===input.workspace_root);
  if (!agent) throw new Error('Request has no Agent on this node');
  return agent;
}
function scheduleJobs(agentId:string) {
  return runtime.product.request('schedule.command',{agentId,action:'jobs'});
}
const handlers:NodeHandlers = {
  'agent.create':input=>handleConfiguration('create',input),
  'agent.config.apply':input=>handleConfiguration('apply',input),
  'agent.config.operation.status':input=>operations.status(input.operation_id),
  'agent.config.get':input=>({agent_id:input.agent_id,agent:configuration.current(input.agent_id) ?? null}),
  'agent.capabilities.resolve':(input,context,reply)=>capabilityRequests.catalog(input,context,reply),
  'node.capabilities.resolve':(input,context,reply)=>capabilityRequests.catalog(input,context,reply),
  'agent.prompt.preview.request':(input,context,reply)=>capabilityRequests.preview(input,context,reply),
  'node.prompt.preview.request':(input,context,reply)=>capabilityRequests.preview(input,context,reply),
  'node.approval.resolve':input=>({inherited_approval_rules:configuration.inheritedApproval(resolve(input.workspace_root)).rules}),
  'node.plugins.request':async input=>{
    try {
      if (!config.agents.some(agent=>agent.agent_id===input.agent_id)) throw new Error('Plugin request has no Agent on this node');
      const plugins = await runtime.request('plugins.manage',{agentId:input.agent_id,action:input.action,
        target:'target' in input ? input.target : undefined,enabled:'enabled' in input ? input.enabled : undefined}) as NonNullable<NodeReply<'node.plugins.request'>['plugins']>;
      if (input.action !== 'list_bundles') publishCatalogChange();
      return {plugins};
    } catch (error) {return {error:String(error)};}
  },
  'node.skills.usage.request':async input=>{
    const usage = await runtime.request('knowledge.usage',{agentId:input.agent_id});
    if (!isCurrentSkillUsage(usage)) throw new Error('Invalid skill usage result');
    return {usage:{agent_id:input.agent_id,node_id:config.node.node_id,...usage}};
  },
  'agent.capability-usage.request':async input=>{
    try {
      const usage = await runtime.request('configuration.usage',{agentId:input.agent_id}) as NonNullable<NodeReply<'agent.capability-usage.request'>['usage']>;
      if (heartbeat.busyFor(input.agent_id)) usage.busy.push({kind:'feature',name:'heartbeat'});
      if (proactiveCoordinator.busyFor(input.agent_id)) usage.busy.push({kind:'feature',name:'proactive_planning'});
      return {agent_id:input.agent_id,usage};
    } catch {return {agent_id:input.agent_id,error:{code:'capability_usage_unavailable',message:'Unable to confirm capability usage'}};}
  },
  'node.heartbeat.md.request':async input=>{
    const content = await readFile(join(workspaceAgent(input).workspace,'.nanoassistant','HEARTBEAT.md'),'utf8')
      .catch(error=>{if(error.code==='ENOENT') return '';throw error;});
    return {content};
  },
  'node.agent.role.request':async input=>{
    try {
      const workspace = await configuration.roleWorkspace(input.agent_id);
      if (!workspace) return {error:'role_unavailable'};
      const response = await runtime.request('configuration.role',{agentId:input.agent_id,workspace,...(input.update ? {update:input.update} : {})}) as
        NonNullable<NodeParams<'node.agent.role.request'>['update']> | {error:'role_conflict'|'role_unavailable'|'role_too_long'};
      return 'error' in response ? {error:response.error} : {role:response};
    } catch {return {error:'role_unavailable'};}
  },
  'node.cron.jobs.request':async input=>({jobs:await scheduleJobs(workspaceAgent(input).agentId)}),
  'node.cron.delete.request':async input=>{
    const {agentId} = workspaceAgent(input);
    const job = (await scheduleJobs(agentId)).find(job=>job.id===input.job_id);
    const result = job && await scheduleDeletions.delete({agentId,scheduleId:job.id,operationId:input.operation_id,actor:{kind:'user',id:input.actor_user_id}});
    return {deleted:result?.deleted===true};
  },
  'node.setup.request':input=>modelSetup.handle(input).catch(()=>({error_code:'setup_invalid',message:'Model setup is unavailable'})),
  'node.distill.prompt.request':input=>history.distill(input).catch(error=>({error_code:'runtime_unavailable',message:String(error)})),
  'session.fork.request':input=>history.fork(input),
  'agent.work.permission':()=>({ok:false,error:'request_ended'}),
  'agent.deletion.preview':async input=>{
    const workspace = await configuration.deletionWorkspace(input.agent_id,operations.pending().map(row=>row.candidate));
    return workspace ? {workspace} : {};
  },
  'task.execution.state':async input=>{
    const result = await runtime.request('task.execution.state',{agentId:input.agent_id}).catch(()=>({state:'unknown'}));
    return nodeCommands['task.execution.state'].result.parse(result);
  },
  'task.wait.validate':input=>tasks.inspect(input).catch(error=>({error:String(error)})),
};
function dispatch(command:keyof NodeHandlers,payload:Record<string,unknown>):Promise<void> {
  return dispatchNodeCommand(command,payload,handlers,config.node.node_id,(type,result)=>relay.request(type,result));
}
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

async function im(path: string, options?: ImRequestOptions): Promise<unknown> {
    return requestIm(config.im_service.url, relay.registration?.gateway_access_token ?? config.im_service.token, path, options);
}

external = new ExternalChannels(join(home, 'external.sqlite3'), { nodeId: config.node.node_id, ownerId: config.node.user_id, store, relay,
  ownerOnly: id => agents.find(agent => agent.agentId === id)?.collaborationScope === 'owner_only',
  personalAgent: id => !!agents.find(agent => agent.agentId === id)?.personal,
  globalAgent: id => agents.some(agent => agent.agentId === id && agent.mode === 'global' && !agent.personal),
  personalDelivery: delivery => globalProduct.externalDelivery(delivery),
  onError: reportError, runtimeFooter: config.display?.platforms?.feishu?.runtime_footer?.enabled ?? config.display?.runtime_footer?.enabled,
  attention: input => needsAttention(input, agents.find(agent => agent.agentId === input.agent_id)!),
  receive: input => admitted(() => agents.find(agent => agent.agentId === input.agent_id)?.mode === 'global' ? globalProduct.receive(input) : product.receive(input)),
  permission: payload => product.permission(payload),
  im,
});
managed = new ManagedChannels(join(home, 'channels.sqlite3'), { nodeId: config.node.node_id, ownerId: config.node.user_id, key: channelKey, relay,
  hasAgent: id => agents.some(agent => agent.agentId === id), retired: id=>!!deletionLedger.read(id), onError: reportError,
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
tasks=new TaskExecution({nodeId:config.node.node_id,ownerId:config.node.user_id,agents,store,runtime: runtime.product,relay,context:binding=>taskContext.prepare({sessionId:binding.sessionId,agentId:binding.agentId,ownerId:binding.ownerId}),
  drain:async sessionId=>{await Promise.allSettled([...productCalls.values()].filter(c=>c.sessionId===sessionId).map(c=>c.promise));},
});
product = new SingleThread({
  nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, runtime: runtime.product, relay: external, onError: reportError,
  image: downloadImage, taskStop:(binding,input)=>tasks.stop(binding,input),
  queueMessageReceipt: (input, read) => {
    try {
      inbox.queueNativeReceipt(input, read);
      globalProduct.scheduleReceipts();
    } catch (error) { reportError(error); }
  },
  recoveryGeneration: binding => {
    const channelAvailable = binding.conversationId.startsWith('external:') ? external.canRecoverConversation(binding.agentId,binding.conversationId) : relay.ready;
    if (!stopping && !updateHolding && channelAvailable && runtime.availableFor(binding.agentId))
      return supervisors.get(runtime.forAgent(binding.agentId).key)?.processInstanceId;
  },
});
runtime.handle('session.recovery.mark', value => {
  const {sessionId, agentId} = value as {sessionId: string; agentId: string};
  const binding = store.bindingForSession(sessionId);
  const generation = supervisors.get(runtime.forAgent(agentId).key)?.processInstanceId;
  if (!generation || binding?.agentId !== agentId) throw new Error('Invalid writable Session recovery identity');
  store.markSessionWritable(sessionId, generation);
  return {marked: true};
});
let workAvailable=false;
const workSync=new WorkSync({nodeId:config.node.node_id,inbox,url:config.im_service.url,credentials:()=>config.im_service.token,available:()=>workAvailable,onError:reportError,
  readyAgents: () => inbox.readyWorkAgents(agents.filter(agent => agent.mode === 'global').map(agent => agent.agentId),
    session => store.bindingForSession(session)?.agentId),
});
globalProduct = new GlobalAgent({ nodeId: config.node.node_id, ownerId: config.node.user_id, agents, store, inbox, runtime: runtime.product, relay: external, image: downloadImage, uploadScreenshot: input => uploadScreenshot(im, input), uploadAttachment: input => uploadAttachment(im, input), downloadAttachment: input => downloadAttachment({ baseUrl: config.im_service.url, token: () => relay.registration?.gateway_access_token ?? config.im_service.token, nodeHome: home }, input), onError: reportError, onWork:()=>workSync.signal(), onProactiveActivity: agentId => proactiveCoordinator?.recordActivity(agentId), clockNow: () => logicalClock ? logicalClock.now() : Date.now(), authorityEpoch:()=>relay.registration?.node_epoch,taskStop:(binding,input)=>tasks.stop(binding,input) });
async function syncRuntimeTimeZone(): Promise<void> {
  const timezone = proactiveCoordinator.effectiveTimeZone();
  await settlePartitions(
    [...runtime.partitions.values()]
      .filter(partition => partition.runtime.available)
      .map(partition => partition.runtime.request('runtime.timezone', { timezone })),
  );
}
runtime.handle('configuration.workflow', async value => {
  const {agentId, guideline} = value as {agentId: string; guideline: string};
  const next = await configuration.setWorkflowGuideline(agentId, guideline);
  await runtime.request('configuration.apply', next);
  Object.assign(agents.find(agent => agent.agentId === agentId)!, next);
  return {effective: true};
});
runtime.handle('model.check', value => product.modelCheck(value as { sessionId: string; turn: number }));
runtime.handle('knowledge.role.workspace', async value => ({
  workspace: await configuration.roleWorkspace((value as {agentId: string}).agentId),
}));
const scheduleDeletions=new ScheduleDeletions({ownerId:config.node.user_id,agents,store,runtime: runtime.product,onError:reportError,
 notify:async intent=>{
  await runtime.request('schedule.deleted.notify',{agentId:intent.agentId,sessionId:intent.sessionId,inputId:intent.changeInputId,content:[{type:'text',text:'The user deleted the Schedule identified below. It will no longer wake you as planned. Account for this change when checking your existing arrangements. This is a Schedule change, not a new task or permission, and it does not resume paused work.\n'+JSON.stringify({schedule_id:intent.scheduleId,title:intent.title,agent_id:intent.agentId,session_id:intent.sessionId,deleted_at:intent.deletedAt,actor:intent.actor})}]});
 }});
const taskContext=new TaskContext({nodeId:config.node.node_id,ownerId:config.node.user_id,agents,store,inbox,runtime: runtime.product,relay,refreshSources:agentId=>globalProduct.prepareSystemContext(agentId)});
runtime.handle('product.task_context.prepare',value=>taskContext.prepare(value as Parameters<TaskContext['prepare']>[0]));
runtime.handle('product.task_context.commit',value=>taskContext.commit(value as Parameters<TaskContext['commit']>[0]));
runtime.handle('product.task_execution.snapshot', value=>tasks.snapshot(value as Parameters<TaskExecution['snapshot']>[0]));
runtime.handle('product.task_execution.ack', value=>tasks.ackDoing(value as Parameters<TaskExecution['ackDoing']>[0]));
runtime.handle('product.proactive.sync_observations', value=>proactiveCoordinator.syncObservations(value as ProactiveSyncObservationsInput));
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
  resolve: (candidate, creating) => {
    if (deletionLedger.read(candidate.agent_id)) throw new Error('Agent deletion requested');
    return configuration.resolve(candidate, creating);
  },
  persist: candidate => configuration.persist(candidate),
  prepare: async (candidate, intent) => {
    const previous = agents.find(agent => agent.agentId === candidate.agent_id);
    const withdrawHeartbeat = previous?.features?.heartbeat === true && candidate.features.heartbeat !== true;
    if (withdrawHeartbeat && !heartbeat.hold(candidate.agent_id, intent.operation_id)) {
      heartbeat.release(candidate.agent_id, intent.operation_id);
      return {ready: false, error_code: 'capability_in_use', message: 'Heartbeat is active', blocks: [{code: 'capability_busy', target: {kind: 'feature', name: 'heartbeat'}}]};
    }
    const candidateProactive = effectiveFeatures(candidate.features, definitionsForRole(Boolean(candidate.personal_agent)), candidate).proactive_planning === true;
    const withdrawProactive = Boolean(previous && isProactivePlanningEnabled(previous) && !candidateProactive);
    if (withdrawProactive && !proactiveCoordinator.hold(candidate.agent_id, intent.operation_id)) {
      heartbeat.release(candidate.agent_id, intent.operation_id);
      proactiveCoordinator.release(candidate.agent_id, intent.operation_id);
      return {ready: false, error_code: 'capability_in_use', message: 'Proactive planning is active', blocks: [{code: 'capability_busy', target: {kind: 'feature', name: 'proactive_planning'}}]};
    }
    // A persisted creation may already have a later user edit: only initialize before the first config write.
    const initialRole = configuration.current(candidate.agent_id) ? undefined : intent.initial_role;
    try {
      if (initialRole !== undefined && !await configuration.creationRoleWorkspace(candidate)) {
        heartbeat.release(candidate.agent_id, intent.operation_id);
        proactiveCoordinator.release(candidate.agent_id, intent.operation_id);
        return {ready:false, error_code:'role_unavailable', message:'Initial role requires an exclusive document workspace'};
      }
      return await runtime.request('configuration.prepare', {operationId: intent.operation_id, fingerprint: intent.candidate_fingerprint,
        config: configuration.runtime(candidate), ...(initialRole === undefined ? {} : {initialRole})}) as import('@nano/personal-assistant').ConfigurationPreparation;
    } catch (error) {
      heartbeat.release(candidate.agent_id, intent.operation_id);
      proactiveCoordinator.release(candidate.agent_id, intent.operation_id);
      // Initial ROLE may already be on disk when the runtime reply is lost. Keep the creation pending for the same intent.
      if (initialRole !== undefined) throw error;
      return {ready: false, error_code: 'capability_usage_unavailable', message: 'Unable to confirm capability usage'};
    }
  },
  release: async (candidate, intent) => {
    heartbeat.release(candidate.agent_id, intent.operation_id);
    proactiveCoordinator.release(candidate.agent_id, intent.operation_id);
    configuration.releaseWorkspace(candidate.agent_id);
    if (runtime.availableFor(candidate.agent_id)) await runtime.request('configuration.release', {agentId: candidate.agent_id, operationId: intent.operation_id});
  },
  apply: async (candidate, intent) => {
    const next = configuration.runtime(candidate);
    const previous = agents.find(agent => agent.agentId === next.agentId);
    if (previous && next.collaborationScope === 'owner_only') {
      previous.collaborationScope = 'owner_only';
      external.restrictToOwner(next.agentId);
      const changes = [...globalProduct.restrictToOwner(next.agentId), ...product.restrictToOwner(next.agentId)];
      const {withdrawn} = await runtime.request('configuration.restrictChat', {agentId:next.agentId, operationId:intent.operation_id, changes}) as {withdrawn:Array<{sessionId:string;inputId?:string}>};
      globalProduct.confirmRestricted(next.agentId,withdrawn);
      product.confirmRestricted(withdrawn.filter((row): row is {sessionId:string;inputId:string} => !!row.inputId));
    }
    const applied = await runtime.request('configuration.apply', {...next, operationId: intent.operation_id, fingerprint: intent.candidate_fingerprint}) as {effective: boolean; message?: string};
    if (!applied.effective) throw new Error(applied.message ?? 'Configuration was not applied');
    if (previous) Object.assign(previous, next); else agents.push(next);
    if (runtime.availableFor(next.agentId)) {
      if (next.personal) await reportPersonalAvailability(runtime.forAgent(next.agentId), true);
      await tasks.recoverStops([next.agentId]);
      await scheduleDeletions.recover([next.agentId]);
      await tasks.recover([next.agentId]);
    }
  },
});

history = new ConversationHistory({ agents, store, runtime: runtime.product, externalConversation: (agentId, source, chatId) => external.historyConversation(agentId, source, chatId) });
for (const partition of runtime.partitions.values()) installPartitionConsumers(partition);
heartbeat = new Heartbeat(join(home, 'heartbeat.sqlite3'), { agents, runtime: runtime.product, lifecycle: store.lifecycle, onError: reportError,
  settings: agentId => ({ ...(config.agents.find(agent => agent.agent_id === agentId)?.heartbeat ?? {}), timezone: store.ownerTimezone }) as HeartbeatSettings,
  binding: agent => agent.mode === 'global' ? globalProduct.heartbeatBinding(agent) : product.heartbeatBinding(agent),
  beforeAdmit: (agent, binding) => globalProduct.syncProactiveObservations(agent, binding),
  available: agentId => !updateHolding && runtime.availableFor(agentId) && (relay.ready || external.available(agentId) && (agents.find(agent => agent.agentId === agentId)?.mode === 'global' || store.canonical(agentId)?.conversationId.startsWith('external:') === true)),
});
proactiveCoordinator = new ProactiveCoordinator({
  ownerId: config.node.user_id,
  agents,
  store,
  inbox,
  runtime: runtime.product,
  binding: agent => globalProduct.heartbeatBinding(agent),
  available: agentId => !updateHolding && runtime.availableFor(agentId) && relay.ready,
  syncObservations: (agent, binding) => globalProduct.syncProactiveObservations(agent, binding),
  onError: reportError,
});
logicalClock = LogicalClockController.fromEnvironment({
  advancePartitions: async (nowMs, settle) => {
    await settlePartitions(
      [...runtime.partitions.values()]
        .filter(partition => partition.runtime.available)
        .map(partition => partition.runtime.request('runtime.clock.advance', { nowMs, settle })),
    );
  },
  tickNode: async nowMs => {
    await heartbeat.tick(undefined, false, nowMs);
    await proactiveCoordinator.tick(nowMs);
  },
  isNodeBusy: () => admissions > 0 || product.busy || globalProduct.busy || heartbeat.busy || proactiveCoordinator.busy || knowledge.busy || workflows.busy,
});
if (logicalClock) {
  const readLogicalNow = () => logicalClock!.now();
  heartbeat.useClock(readLogicalNow);
  proactiveCoordinator.useClock(readLogicalNow);
}
runtime.onNotification((method, value) => { if (method === 'configuration.catalog.changed' || method === 'knowledge.changed') publishCatalogChange(); if (method === 'heartbeat.subscription') { const data = value as { agentId: string; enabled: boolean }; heartbeat.subscription(data.agentId, data.enabled); } });
const updater = new NodeUpdater(configuration, {
  onError: reportError,
  prepare: async operationId => {
    if (updateHolding && updateHolding !== operationId) return false;
    updateHolding = operationId;
    const busy = () => admissions > 0 || inspector.metrics().preview_active > 0 || modelSetup.busy || product.busy || globalProduct.busy || heartbeat.busy || proactiveCoordinator.busy || operations.busy || knowledge.busy || workflows.busy;
    if (!runtime.available || busy()) return false;
    const result = await runtime.request('update.prepare', {operationId}) as {ready: boolean};
    return result.ready && !busy();
  },
  resume: async operationId => {
    if (updateHolding && updateHolding !== operationId) return;
    if (runtime.available) await runtime.request('update.release', {operationId});
    updateHolding = undefined;
    for(const recovery of readyRecovery.values())recovery.resume?.();
    if (runtime.available && !stopping) await admitted(async () => {
      if (relay.ready) await tasks.recoverStops(agents.filter(agent => runtime.availableFor(agent.agentId)).map(agent => agent.agentId));
      await external.recover(); await product.recover(!relay.ready); await globalProduct.recover();
      await knowledge.recover(); await workflows.recover();
    });
  },
});
const deletions = new NodeAgentDeletions(deletionLedger,{
  assertStopped: intent => {
    const state=store.lifecycle.snapshot(intent.agent_id);
    if (state?.revision!==intent.revision || state.applied_revision!==intent.revision || state.desired!=='disabled' || state.observed!=='disabled')
      throw new Error('Agent stop has not been confirmed on this node');
    if (!agents.some(agent=>agent.agentId===intent.agent_id && !agent.personal)) throw new Error('Unknown deletable Agent');
  },
  plan: async intent => {
    const workspace=intent.workspace;
    if (workspace) {
      const current=await configuration.deletionWorkspace(intent.agent_id,operations.pending().map(row=>row.candidate));
      if (current?.path!==workspace.path || current.witness!==workspace.witness) throw new Error('Workspace is no longer exclusive');
    }
    const knownSessionIds=[...new Set([...store.bindings().filter(row=>row.agentId===intent.agent_id).map(row=>row.sessionId),
      ...inbox.deletionSessionIds(intent.agent_id)])];
    const result = await supervisors.get('ordinary')!.request('agent.deletion.plan',{agentId:intent.agent_id,revision:intent.revision,knownSessionIds});
    return result as {sessionIds:string[]};
  },
  purge: async (intent,plan) => {
    await supervisors.get('ordinary')!.request('agent.deletion.purge',{agentId:intent.agent_id,revision:intent.revision,operationId:intent.operation_id,plan});
  },
  finalize: async (intent,plan) => {
    const agentId=intent.agent_id;
    const manifest=inbox.deletionWork(agentId);
    for (let i=0;i<manifest.entries.length;i+=250) {
      await relay.request('agent.deletion.work',{node_id:config.node.node_id,agent_id:agentId,operation_id:intent.operation_id,
        manifest:{journal_id:manifest.journal_id,entries:manifest.entries.slice(i,i+250)}},{priority:'control'});
    }
    inbox.purgeAgent(agentId,plan.sessionIds);
    workSync.redacted();
    await managed.purgeAgent(agentId);
    external.purgeAgent(agentId);
    heartbeat.purgeAgent(agentId);
    operations.purgeAgent(agentId);
    store.purgeAgent(agentId,plan.sessionIds);
    await configuration.removeAgent(agentId,intent.operation_id,intent.workspace,()=>operations.pending().map(row=>row.candidate));
    runtime.removeAgent(agentId);
    const index=agents.findIndex(agent=>agent.agentId===agentId);
    if (index!==-1) agents.splice(index,1);
  },
  report: async (intent,state,errorDetail) => {
    await relay.request('agent.deletion.report',{node_id:config.node.node_id,agent_id:intent.agent_id,operation_id:intent.operation_id,
      state,...(errorDetail ? {error_detail:errorDetail.slice(0,500)} : {})},{priority:'control'});
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
      const revision=store.lifecycle.snapshot(agentId)!.revision;
      const result=await supervisor.disableAgent(agentId,revision);
      if (result.confirmed) {
        agentLifecycle.recordCleanup(agentId,revision,result.processInstanceId);
        await globalProduct.recordStopped(agentId,revision,typedRuntimeRequest(supervisor.request.bind(supervisor)));
      }
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
    if (!updateHolding) await admitted(async () => {
      if (relay.ready) await tasks.recoverStops([agentId]);
      await product.recover(!relay.ready, [agentId]);
    });
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
if (logicalClock) await logicalClock.start();
void relay.start().catch(reportError);
heartbeat.start();
proactiveCoordinator.start();
const taskWatch=setInterval(()=>{
  if(relay.ready&&!updateHolding)void tasks.watch().catch(reportError);
},60_000);taskWatch.unref();
process.stdout.write(`Node ${config.node.node_id} ready; DSH hosts=${runtime.partitions.size}\n`);
async function stop() {
  if (stopping) return;
  stopping = true;
  clearTimeout(relayRecoveryTimer);
  for(const recovery of readyRecovery.values())clearTimeout(recovery.timer);
  clearInterval(taskWatch);
  trajectory.closeAll();
  try { await logicalClock?.close(); capabilityRequests.cancelAll(); await deletions.close(); await inspector.close(); await workSync.stop(); await updater.close(); await modelSetup.stop(); await managed.stop(); await proactiveCoordinator.stop(); await heartbeat.stop(); await knowledge.stop(); await workflows.stop(); await runtime.shutdown(); for (const agent of agents) agentLifecycle.recordStopped(agent.agentId); await relay.stop(); await product.stop(); await globalProduct.stop(); await Promise.allSettled(readyRecoveryTasks); await operations.close(); await external.stop(); inbox.close(); store.close(); }
  catch (error) { reportError(error); process.exitCode = 1; }
  finally {await lifecycle.close();}
}
process.once('SIGTERM', () => { void stop(); });
process.once('SIGINT', () => { void stop(); });

// Only the supervising host owns the write end of this inherited anonymous pipe.
if (process.platform === 'win32' && process.env.CREWDEN_SUPERVISED_GATEWAY === '1') {
  const control = createInterface({input: process.stdin});
  control.on('line', line => { if (line === 'stop') { control.close(); process.stdin.pause(); void stop(); } });
}
