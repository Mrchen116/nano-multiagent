import {randomUUID} from 'node:crypto';
import {sortedJsonUtf8} from '@nano/product-contracts/serialization';
import {featureClosure, featureDependencies} from '@nano/product-contracts/capabilities';
import {all, one, fail, now, type Row} from './context.js';
import type {PersonalAgents} from './personal-agent.js';
import {createAgent, readNodeCreationCapabilities, requireOwnedNode} from './agent-creation.js';
import {parseConfigurationInput} from './configuration-input.js';
import {readConfigOperation} from './configuration-records.js';
import {requireSettingsNodeOnline} from './agent-settings.js';

const fields = {
  agent_id:'Required stable unique Agent ID. Keep it unchanged while recovering this request.',
  display_name:'Required visible name.',description:'Short purpose description.',custom_prompt:'Complete agreed responsibilities and instructions; do not copy unrelated private history.',
  work_mode:'single_thread (separate chat contexts) or global (one continuous cross-chat Agent).',
  default_model:'A model name from capabilities.models, or null to inherit platform_default_model.',
  model_fallbacks:'Ordered model names, excluding the primary model.',reasoning_effort:'A level declared by the chosen model, or null for its default.',
  approval_mode:'cc, codex, or null to follow the target computer.',
  skills:'Skill names from the target catalog.',skills_selection_mode:'explicit_allowlist, explicit_denylist, or default_discovery.',
  tool_allowlist:'Tool names from the target catalog. Enabled Features require their declared dependencies.',
  features:'Boolean settings by capabilities.features[].key. Include required Features, tools and Skills together.',
  group_reply_policy:'manual, mention_only or always.',
  workspace_root:'null uses the target computer default; custom paths are validated by that computer.',
  confirm_existing_workspace:'true only after the owner explicitly confirms using the specified existing directory; never overwrite its contents.',
};

/** Bind PA requests to configuration receipts; configuration remains the lifecycle owner. */
export class PersonalAgentCreation {
  constructor(private readonly pa: PersonalAgents, private readonly admitCreate: () => void) {}

  /** Query options, submit agreed configuration, or recover one existing request.
   *
   * Args:
   *   binding: Current server-authenticated main PA binding.
   *   args: Tool arguments with a separate target_node_id, never transport identity.
   * Returns:
   *   Current options or a truthful creation result associated with request_key.
   */
  async handle(binding: Row, args: Row): Promise<Row> {
    const ctx=this.pa.ctx;
    if(args.action==='options') {
      const id=args.target_node_id ?? binding.node_id;
      requireOwnedNode(ctx,id,binding.owner_id);
      const nodes=all(ctx.db,'SELECT node_id,node_name,alias,status FROM nodes WHERE owner_id=? ORDER BY node_id',binding.owner_id);
      const capabilities=await readNodeCreationCapabilities(ctx,id,binding.owner_id);
      // Recommend a valid dependency closure, using this computer's actual catalog.
      const features=featureClosure(Object.fromEntries(featureDependencies.map(feature=>{
        const available=capabilities.features.find((entry:Row)=>entry.key===feature.key);
        return [feature.key,!!available?.default_on && available.available!==false];
      })));
      const dependencies=featureDependencies.filter(feature=>features[feature.key]);
      const defaults={work_mode:'single_thread',group_reply_policy:'mention_only',default_model:null,
        model_fallbacks:[],reasoning_effort:null,approval_mode:null,workspace_root:null,features,
        skills_selection_mode:'explicit_allowlist',
        skills:[...new Set([...capabilities.skills.filter((s:Row)=>s.default_on).map((s:Row)=>s.name),...dependencies.flatMap(feature=>feature.requires.skills)])],
        tool_allowlist:[...new Set([...capabilities.tools.filter((t:Row)=>t.default_on).map((t:Row)=>t.name),...dependencies.flatMap(feature=>feature.requires.tools)])]};
      return {node_id:id,recommended_node_id:binding.node_id,nodes,capabilities,configuration_fields:fields,defaults};
    }
    if(!['create','status'].includes(args.action))fail(422,'invalid_creation_action');
    if(typeof args.request_key!=='string'||!args.request_key.trim())fail(422,'request_key is required');
    let record=one(ctx.db,'SELECT * FROM pa_agent_creations WHERE binding_id=? AND request_key=?',binding.binding_id,args.request_key);
    if(args.action==='status'&&!record)return {status:'not_started',request_key:args.request_key};
    if(args.action==='create') {
      this.pa.ownerMessage(binding,args.source_message_id);
      const node=args.target_node_id ?? binding.node_id;
      requireOwnedNode(ctx,node,binding.owner_id);
      const configuration=parseConfigurationInput(args.configuration,true);
      const frozen=sortedJsonUtf8(configuration);
      if(record) {
        if(record.node_id!==node||record.configuration_json!==frozen)fail(409,'creation_request_key_conflict');
      } else {
        requireSettingsNodeOnline(ctx,{owner_id:binding.owner_id,node_id:node});
        const operation=randomUUID().replaceAll('-','');
        ctx.db.prepare('INSERT INTO pa_agent_creations(binding_id,request_key,node_id,agent_id,operation_id,source_message_id,configuration_json,created_at) VALUES(?,?,?,?,?,?,?,?)')
          .run(binding.binding_id,args.request_key,node,configuration.agent_id,operation,args.source_message_id,frozen,now());
        record=one(ctx.db,'SELECT * FROM pa_agent_creations WHERE binding_id=? AND request_key=?',binding.binding_id,args.request_key)!;
      }
    }
    const saved=record!;
    requireOwnedNode(ctx,saved.node_id,binding.owner_id);
    const operation=readConfigOperation(ctx.db,saved.operation_id);
    if(args.action==='status'&&!operation)return {status:'not_started',request_key:args.request_key};
    if(operation?.status==='rejected')return {status:'rejected',request_key:args.request_key,
      error:{code:operation.error_code,message:operation.error_message}};
    try {
      const agent=await createAgent(ctx,binding.owner_id,saved.node_id,parseConfigurationInput(JSON.parse(saved.configuration_json),true),saved.operation_id,
        args.action==='create'?this.admitCreate:undefined);
      if(!agent)return {status:'pending',request_key:args.request_key};
      const chat=ctx.messaging.createConversation(ctx.identity.user(binding.owner_user_id)!,
        {type:'direct',title:agent.display_name,participants:[{type:'agent',id:agent.agent_id}]});
      const base=ctx.publicUrl.replace(/\/$/,'');
      return {status:'created',request_key:args.request_key,agent,
        urls:{settings:`${base}/settings/agents/${encodeURIComponent(agent.agent_id)}`,chat:`${base}/chat/${encodeURIComponent(chat.id)}`}};
    } catch(error) {
      const failure=error as {statusCode?:number;detail?:Row|string};
      const detail=failure.detail;
      if(typeof detail==='object'&&detail?.code==='config_apply_pending')return {status:'pending',request_key:args.request_key};
      const settled=readConfigOperation(ctx.db,saved.operation_id);
      if(settled?.status==='rejected')return {status:'rejected',request_key:args.request_key,
        error:{code:settled.error_code,message:settled.error_message}};
      throw error;
    }
  }
}
