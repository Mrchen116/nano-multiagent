/** Product commands initiated by IM. Transport correlation and authorization belong to their owners. */
import {z} from 'zod';
import {parseAgentConfigurationFields, type AgentConfigurationFields} from './configuration-rpc.js';

// A valid result must carry one of the alternatives checked by its wire decoder.
type WithField<T, K extends keyof T> = T & {[P in K]-?: Required<Pick<T, P>>}[K];
const text = z.string();
const id = text.regex(/\S/);
const strings = z.array(text);
const record = z.record(text, z.unknown());
const list = z.array(z.unknown());
const agent = z.object({agent_id:id});
const target = agent.extend({workspace_root:text.nullish()});
const workspaceTarget = z.union([target, z.object({workspace_root:id, agent_id:z.undefined().optional()})]);
const role = z.object({content:text,version:text.nullable()});
const errorText = {error:text.optional()};
const failure = {error_code:text.optional(),message:text.optional()};
const inspectionFailure = {error_code:'catalog_failed',message:'Capability inspection could not be completed. Retry shortly.'};
const configuration = z.custom<AgentConfigurationFields>(value => {
  try { parseAgentConfigurationFields(value); return true; } catch { return false; }
});
const intent = z.object({operation_id:id,candidate_fingerprint:id,expected_previous_fingerprint:text.nullable(),
  agent:configuration.and(agent),initial_role:text.optional()});
const receipt = z.object({operation_id:text.optional(),candidate_fingerprint:text.optional(),status:text.optional(),
  agent:configuration.nullish(),blocks:list.optional(),...failure});
const writtenReceipt = receipt.extend({operation_id:id,status:z.enum(['pending','applied','rejected'])});
const capabilities = z.object({models:list.optional(),skills:list.optional(),tools:list.optional(),commands:list.optional(),
  features:list.optional(),fixed_tools:strings.optional(),platform_default_model:text.nullish(),
  default_workspace_template:text.nullish(),inherited_approval_rules:z.unknown().optional()});
export type NodeCapabilities = z.infer<typeof capabilities>;
const catalogRead = capabilities.extend({capabilities:capabilities.optional(),...failure}).refine(value =>
  value.capabilities !== undefined || value.error_code !== undefined || Object.keys(capabilities.shape).some(key=>Object.hasOwn(value,key)));
const catalog = z.union([z.object({capabilities}),z.object({error_code:id,message:text})]);
const previewInput = z.object({features:z.record(text,z.boolean()),tool_ids:strings,skill_ids:strings,
  skills_selection_mode:z.enum(['default_discovery','explicit_allowlist','explicit_denylist']),scenario:text,work_mode:z.enum(['single_thread','global']).optional(),
  workspace_root:text.nullish(),workspace_mode:text.optional(),agent_id_hint:text.nullish(),heartbeat_enabled:z.boolean().optional(),cron_enabled:z.boolean().optional()});
const preview = z.object({preview:z.object({prompt:text,section_count:z.number()}).optional(),
  error:z.object({code:text,detail:text.optional()}).optional(),...failure}).refine((p): p is WithField<typeof p, 'preview' | 'error' | 'error_code'> => !!(p.preview || p.error || p.error_code));
const plugin = z.discriminatedUnion('action',[
  target.extend({action:z.literal('list_bundles')}),
  target.extend({action:z.literal('set_bundle'),target:id,enabled:z.boolean()}),
  target.extend({action:z.literal('remove_bundle'),target:id}),
]);
const pluginText = z.union([text,z.record(text,text)]);
const plugins = z.object({
  workspace:text.optional(),entries:z.array(z.object({name:text,display_name:pluginText.optional(),description:pluginText.optional(),
    version:text.optional(),enabled:z.boolean().optional(),state:text.optional(),rows:z.array(z.object({id:text,name:pluginText})).optional(),
    removable:z.boolean().optional(),diagnostics:strings.optional()})),diagnostics:strings.optional(),error:text.optional(),
  pending:z.object({action:text,target:text,enabled:z.boolean().optional(),phase:z.enum(['waiting','applying'])}).optional(),
});
const job = z.object({id,sessionId:text.optional(),name:text.optional(),instruction:text.optional(),
  schedule:record.optional(),enabled:z.boolean().optional(),delete_after_run:z.boolean().optional()});
const usage = z.object({agent_id:text.optional(),node_id:text.optional(),statistics_since:text.nullish(),period_start:text.optional(),period_end:text.optional(),
  skills:z.array(z.object({name:text.optional(),skill_id:text.optional(),statistics_since:text.nullish(),source:text.optional(),state:text.optional(),
    use_count:z.int().optional(),uses_since_last_B:z.int().optional(),created_at:text.nullish(),last_used_at:text.nullish(),
    archived_at:text.nullish(),archive_error:text.nullish(),trend_buckets:z.array(z.number()).optional(),
    session_refs:z.array(z.object({session_id:text,tool_call_id:text,timestamp:text.optional(),location:text.optional()})).optional()})).optional(),
  heatmap_data:z.array(z.number()).optional(),health:z.object({created_auto_total:z.int().optional(),active_auto_total:z.int().optional(),used_auto_total:z.int().optional()}).optional()});
const legacyUsageReply = z.object({usage:usage.optional(),...errorText})
  .refine((p): p is WithField<typeof p,'usage' | 'error'> => !!p.usage || !!p.error);
const currentSkillUsage = usage.extend({
  statistics_since:text.nullable(), period_start:text, period_end:text,
  skills:z.array(usage.shape.skills.unwrap().element.extend({statistics_since:text.nullable()})),
});
/** Recognize fresh statistics without stripping provider fields from a retained sample. */
export function isCurrentSkillUsage(value:unknown):value is z.output<typeof currentSkillUsage> {
  return currentSkillUsage.safeParse(value).success;
}
const capabilityUsage = z.object({checked_at:text,active_schedules:z.int(),busy:z.array(z.object({kind:text,name:text}))});
const publicError = z.object({code:text,message:text,dependencies:z.array(z.object({agent_id:id,display_name:text})).optional()});
const model = z.object({id:id,display_name:text.optional(),context_window:z.int().positive().optional(),
  max_tokens:z.int().positive().optional(),input:z.array(z.enum(['text','image'])).optional()});
const setupFields = z.object({revision:text.optional(),
  provider:text.optional(),source:text.optional(),display_name:text.optional(),protocol:z.enum(['openai-completions','anthropic-messages','openai-responses']).optional(),
  base_url:text.optional(),model:text.optional(),api_key:text.optional(),models:z.array(model).optional()});
const setupInput = z.discriminatedUnion('action',[
  setupFields.extend({action:z.enum(['status','cancel'])}),
  setupFields.extend({action:z.literal('save'),revision:text,models:z.array(model)}),
  setupFields.extend({action:z.literal('remove'),revision:text,provider:text}),
  setupFields.extend({action:z.literal('login'),revision:text,provider:text,model:text}),
]);
const setup = z.object({revision:text.optional(),catalog_error:text.optional(),default_model:text.optional(),workspace_base:text.optional(),
  services:z.array(z.object({provider:text,display_name:text.optional(),native:z.boolean().optional(),source:text.optional(),
    protocol:text.optional(),base_url:text.optional(),credential_stored:z.boolean().optional(),models:z.array(model.extend({name:text.optional()}))})).optional(),
  models:z.array(z.object({provider:text,model:text,display_name:text.optional()})).optional(),
  catalog:z.array(z.object({provider:text,display_name:text.optional(),models:z.array(z.object({id:text,name:text.optional(),
    contextWindow:z.number().optional(),maxTokens:z.number().optional(),inputModalities:strings.optional()}))})).optional(),
  operation:z.object({id:text,state:z.enum(['waiting','testing','succeeded','failed','cancelled']),code:text.optional(),url:text.optional(),
    message:text.optional(),error:publicError.optional()}).optional(),error:publicError.optional(),...failure
}).refine((value): value is WithField<typeof value, 'revision' | 'error_code' | 'error'> => value.revision !== undefined || !!value.error_code || !!value.error);
const browserStatus = z.object({
  supported:z.boolean(),
  state:z.enum(['unsupported','not_paired','paired','verified','reconnect']),
  chrome_installed:z.boolean(),
  chrome_running:z.boolean(),
  chrome_version_ok:z.boolean(),
  paired_profile:text.optional(),
  selected_profile:text,
  extension_installed:z.boolean(),
  profiles:z.array(z.object({profile:text,extension_installed:z.boolean()})),
  last_checked_at:text.optional(),
});
const browserInput = z.discriminatedUnion('action',[
  z.object({action:z.literal('status'),profile:text.optional()}),
  z.object({action:z.literal('open-guide'),profile:text.optional(),target:z.enum(['auto','store','token']).optional()}),
  z.object({action:z.literal('pair'),profile:text.optional(),token:text}),
  z.object({action:z.literal('disconnect')}),
]);
const browserReply = z.object({
  browser:browserStatus.optional(),
  opened:z.enum(['store','token']).optional(),
  error:publicError.optional(),
  ...failure,
}).refine((value): value is WithField<typeof value, 'browser' | 'error' | 'error_code'> => !!(value.browser || value.error || value.error_code));
const wechatSetupInput = z.discriminatedUnion('action',[
  agent.extend({action:z.literal('start'),editing_channel_id:id.optional()}),
  agent.extend({action:z.literal('status'),setup_id:id}),
  agent.extend({action:z.literal('verify_code'),setup_id:id,code:text.regex(/^\d{1,12}$/)}),
  agent.extend({action:z.literal('cancel'),setup_id:id}),
]);
const wechatSetupResult = z.object({
  setup_id:text.optional(),
  state:z.enum(['waiting_scan','scanned','need_verify_code','confirmed','expired','failed','cancelled']),
  qr_svg:text.optional(),
  expires_at:text.optional(),
  binding:z.object({bot_token:id,bot_id:id,owner_user_id:id,base_url:id}).optional(),
  ...failure,
});
const fork = z.discriminatedUnion('ok',[
  z.object({ok:z.literal(true),new_session_id:text.optional(),id_map:z.record(text,text),error:z.never().optional()}),
  z.object({ok:z.literal(false),error:text,id_map:z.never().optional()}),
]);
const permission = z.object({ok:z.boolean(),error:text.optional()});
const state = z.object({state:z.enum(['running','idle','offline','unknown'])});
const proof = z.object({valid:z.boolean().optional(),checked_at:text.optional(),owner_agent_id:text.optional(),session_id:text.optional(),
  next_check_at:text.optional(),pending_occurrence_id:text.optional(),reason_code:z.enum(['missing','inactive','expired','owner_or_session_mismatch','unavailable']).optional(),...errorText
}).refine((p): p is typeof p & ({error:string} | {valid:boolean;checked_at:string}) => p.error !== undefined || p.valid !== undefined && p.checked_at !== undefined);
function command<const Name extends string,I extends z.ZodType,O extends z.ZodType>(
  responseType:Name,input:I,result:O,invalid?:z.output<NoInfer<O>>,
) { return {responseType,input,result,read:result,invalid,inspection:false as const}; }
function inspection<const Name extends string,I extends z.ZodType,O extends typeof catalog | typeof preview>(responseType:Name,input:I,result:O) {
  return {responseType,input,result,read:result,inspection:true as const,invalid:inspectionFailure};
}

/** The wire names are intentionally explicit, including older irregular spellings. */
export const nodeCommands = {
  'agent.create':{...command('agent.created',intent,writtenReceipt),read:receipt},
  'agent.config.apply':{...command('agent.config.apply.result',intent,writtenReceipt),read:receipt},
  'agent.config.operation.status':{...command('agent.config.operation.status.result',z.object({operation_id:id}),writtenReceipt),read:receipt},
  'agent.config.get':command('agent.config',agent,configuration.and(z.object({agent:configuration.nullish()}))),
  'agent.capabilities.resolve':{...inspection('agent.capabilities',target,catalog),read:catalogRead},
  'node.capabilities.resolve':{...inspection('node.capabilities',z.object({workspace_root:text.optional(),agent_id_hint:text.optional()}),catalog),read:catalogRead},
  'node.approval.resolve':command('node.approval.resolve.result',z.object({workspace_root:id}),z.object({inherited_approval_rules:z.unknown()})),
  'agent.prompt.preview.request':inspection('agent.prompt.preview',previewInput.extend({agent_id:id}),preview),
  'node.prompt.preview.request':inspection('node.prompt.preview',previewInput,preview),
  'node.plugins.request':command('node.plugins',plugin,z.object({plugins:plugins.optional(),...errorText}).refine((p): p is WithField<typeof p, 'plugins' | 'error'> =>!!p.plugins || !!p.error),{error:'Invalid plugin command'}),
  'node.skills.usage.request':{...command('node.skills.usage',target,z.union([
    z.object({usage:currentSkillUsage}),z.object({error:id}),
  ])),read:legacyUsageReply},
  'agent.capability-usage.request':command('agent.capability-usage',agent,z.object({usage:capabilityUsage.optional(),error:publicError.optional()}).refine((p): p is WithField<typeof p, 'usage' | 'error'> =>!!p.usage || !!p.error),
    {error:{code:'capability_usage_unavailable',message:'Unable to confirm capability usage'}}),
  'node.heartbeat.md.request':command('node.heartbeat.md',workspaceTarget,z.object({content:text})),
  'node.agent.role.request':command('node.agent.role',agent.extend({update:role.optional()}),z.union([
    z.object({role,error:z.never().optional()}),z.object({error:z.enum(['role_conflict','role_unavailable','role_too_long']),role:z.never().optional()}),
  ]),{error:'role_unavailable'}),
  'node.cron.jobs.request':command('node.cron.jobs',workspaceTarget,z.object({jobs:z.array(job).optional(),...errorText}).refine((p): p is WithField<typeof p, 'jobs' | 'error'> =>!!p.jobs || !!p.error)),
  'node.cron.delete.request':command('node.cron.delete',target.extend({job_id:id,actor_user_id:id,operation_id:id}),z.object({deleted:z.boolean()})),
  'node.setup.request':command('node.setup',setupInput,setup,{error_code:'setup_invalid',message:'Model setup is unavailable'}),
  'node.browser.request':command('node.browser',browserInput,browserReply,{error_code:'browser_invalid',message:'Browser pairing is unavailable'}),
  'node.wechat.setup.request':command('node.wechat.setup.result',wechatSetupInput,wechatSetupResult,{state:'failed',error_code:'setup_invalid',message:'WeChat setup is unavailable'}),
  'node.distill.prompt.request':command('node.distill.prompt',z.object({sources:z.array(z.object({conversation_id:id,source_agent_id:id,
    external_source:text.optional(),external_chat_id:text.optional()})).nonempty(),execution_agent_id:id,target_scope:z.enum(['agent','global'])}),
    z.object({prompt:text.optional(),...failure}).refine((p): p is WithField<typeof p, 'prompt' | 'error_code'> =>p.prompt !== undefined || !!p.error_code),{error_code:'invalid_request',message:'Invalid distill request'}),
  'session.fork.request':command('session.fork.result',z.object({source_conversation_id:id,new_conversation_id:id,agent_id:id,
    fork_point:z.object({message_id:id}),source_external_source:text.optional(),source_external_chat_id:text.optional()}),fork,{ok:false,error:'Invalid fork request'}),
  'agent.work.permission':command('agent.work.permission.result',z.object({root_agent_id:id,lifecycle_revision:z.int().optional(),
    session_id:id,decision:id,reason:text}),permission,{ok:false,error:'request_ended'}),
  'agent.deletion.preview':command('agent.deletion.preview.result',agent,z.object({workspace:z.object({path:text,witness:text}).optional()})),
  'task.execution.state':{...command('task.execution.state.result',agent,state),read:z.object({state:text.optional()})},
  'task.wait.validate':command('task.wait.validate.result',z.object({agent_id:id,conversation_id:id,graph_id:id,node_id:id,schedule_id:id}),proof,{error:'Invalid task wait request'}),
} as const;

export type NodeCommand = keyof typeof nodeCommands;
type Spec<K extends NodeCommand> = (typeof nodeCommands)[K];
export type NodeParams<K extends NodeCommand> = z.output<Spec<K>['input']>;
export type NodeInput<K extends NodeCommand> = NodeParams<K> & {request_id?:string; deadline_at?:number};
export type NodeOutput<K extends NodeCommand> = z.output<Spec<K>['read']>;
export type NodeReply<K extends NodeCommand> = z.output<Spec<K>['result']>;
export type NodeRequest = <K extends NodeCommand>(nodeId:string,command:K,payload:NodeInput<NoInfer<K>>,signal?:AbortSignal)=>Promise<NodeOutput<K>>;
export type ConfigurationCommand = 'agent.create' | 'agent.config.apply' | 'agent.config.operation.status';
export type ConfigurationRequest = <K extends ConfigurationCommand>(nodeId:string,command:K,payload:NodeInput<NoInfer<K>>)=>Promise<NodeOutput<K>>;
export interface NodeRequestContext {requestId:string; deadlineAt?:number}
type HandlerResult<K extends NodeCommand> = Spec<K>['inspection'] extends true ? void : NodeReply<K>;
export type NodeHandlers = {[K in NodeCommand]: (
  input:NodeParams<K>, context:NodeRequestContext, reply:(result:NodeReply<K>)=>Promise<void>
) => HandlerResult<K> | Promise<HandlerResult<K>>};

export const inspectionReplies: ReadonlySet<string> = new Set(Object.values(nodeCommands).filter(c=>c.inspection).map(c=>c.responseType));
export function isNodeCommand(type:string): type is NodeCommand { return Object.hasOwn(nodeCommands,type); }

function checked<S extends z.ZodType>(command:NodeCommand,schema:S,value:unknown): z.output<S> {
  const result = schema.safeParse(value);
  if (!result.success) {
    const fields = result.error.issues[0]?.path ?? [];
    // Dictionary keys in feature selections and provider data can contain user text.
    const path = fields.slice(0,fields.indexOf('features') >= 0 ? fields.indexOf('features')+1 : fields.length).join('.') || '(payload)';
    throw new Error(`Invalid ${command} field ${path}`);
  }
  return result.data;
}
/** Validate the incoming business parameters before invoking the command's handler. */
export function decodeNodeInput<K extends NodeCommand>(command:K,value:unknown): NodeParams<K> {
  return checked(command,nodeCommands[command].input,value) as NodeParams<K>;
}
/** Preserve legacy receipt identity and extensions for the durable configuration owner. */
export function decodeNodeResult<K extends NodeCommand>(command:K,value:unknown): NodeOutput<K> {
  checked(command,nodeCommands[command].read,value);
  return value as NodeOutput<K>;
}
