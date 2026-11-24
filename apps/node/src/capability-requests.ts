/** Transient capability reads do not wait behind execution or lifecycle recovery. */
import {inspectionTimeouts} from '@nano/product-contracts';
import type {NodeParams,NodeReply,NodeRequestContext} from '@nano/product-contracts/node-rpc';
import {mkdir} from 'node:fs/promises';
import {ConfigurationInspector, InspectionError} from '@nano/dsh-integration/client';
import {NodeConfiguration} from './configuration.js';
import {projectCapabilities} from './capabilities.js';
import {providerProfiles} from './providers.js';
import type {installedPackageManager} from './release.js';

interface Options {
  configuration:NodeConfiguration;
  inspector:ConfigurationInspector;
  packageManager:ReturnType<typeof installedPackageManager>;
}
type Preview = NodeParams<'node.prompt.preview.request'> & {agent_id?:string};
type Target = {agent_id?:string;workspace_root?:string|null;agent_id_hint?:string|null};
type Failure = {error_code:string;message:string};
type Reply<T> = (value:T)=>Promise<void>;
/** Own the finite lifetime of each IM waiter, not the underlying shared inspection. */
export class CapabilityRequests {
  private readonly requests = new Map<string,AbortController>();
  constructor(private readonly options: Options) {}
  cancel(id:unknown):void {
    if (typeof id === 'string') this.requests.get(id)?.abort(new InspectionError('catalog_cancelled','Capability request cancelled'));
  }
  cancelAll():void { for (const id of this.requests.keys()) this.cancel(id); }

  private target(payload:Target) {
    const configuration = this.options.configuration, config = configuration.value;
    const agent = config.agents.find(agent=>agent.agent_id===payload.agent_id);
    if (payload.agent_id && !agent) throw new Error('Unknown Agent');
    const workspace = agent?.workspace_root || payload.workspace_root || configuration.defaultWorkspace(payload.agent_id_hint ?? 'preview');
    return {config,agent,workspace};
  }

  catalog(input:Target,context:NodeRequestContext,reply:Reply<NodeReply<'node.capabilities.resolve'>>) {
    return this.run(context,reply,async (signal,deadlineAt)=>{
      const {config,agent,workspace} = this.target(input);
      const candidate = config.llm.default_model || agent ? this.options.configuration.runtime({...agent,agent_id:input.agent_id ?? 'preview',workspace_root:workspace}) : undefined;
      let catalog:Parameters<typeof projectCapabilities>[0] = {tools:[],skills:[]};
      if (candidate) {
        await mkdir(workspace,{recursive:true});
        signal.throwIfAborted();
        catalog = await this.options.inspector.inspect({method:'catalog',config:candidate,cwd:workspace,providers:providerProfiles(config.llm).providers,
          packageManager:this.options.packageManager,requestId:context.requestId,deadlineAt},signal) as typeof catalog;
      }
      return {...(agent?{agent_id:input.agent_id,workspace_root:workspace}:{}),capabilities:{
        ...projectCapabilities(catalog,config,agent?candidate:undefined),inherited_approval_rules:this.options.configuration.inheritedApproval(workspace).rules,
        ...(!agent?{default_workspace_template:this.options.configuration.defaultWorkspace('{agent_id}')}:{})}};
    });
  }

  preview(input:Preview,context:NodeRequestContext,reply:Reply<NodeReply<'node.prompt.preview.request'>>) {
    return this.run(context,reply,async (signal,deadlineAt)=>{
      const {config,agent,workspace} = this.target(input);
      if (!config.llm.default_model && !agent) return {error_code:'model_not_configured',message:'Connect a model before creating your assistant'};
      const candidate = this.options.configuration.runtime({...agent,agent_id:input.agent_id ?? 'preview',workspace_root:workspace,
        features:input.features,tool_allowlist:input.tool_ids,skills:input.skill_ids,skills_selection_mode:input.skills_selection_mode,work_mode:input.work_mode});
      await mkdir(workspace,{recursive:true});
      signal.throwIfAborted();
      const preview = await this.options.inspector.inspect({method:'preview',config:candidate,cwd:workspace,providers:providerProfiles(config.llm).providers,
        packageManager:this.options.packageManager,requestId:context.requestId,deadlineAt},signal) as {prompt:string;section_count:number};
      return {preview:{prompt:preview.prompt,section_count:preview.section_count}};
    });
  }

  private async run<T>(context:NodeRequestContext,reply:Reply<T | Failure>,inspect:(signal:AbortSignal,deadlineAt:number)=>Promise<T>) {
    const controller = new AbortController();
    this.requests.set(context.requestId,controller);
    const deadline = Math.min(context.deadlineAt ?? Infinity,Date.now()+inspectionTimeouts(process.platform === 'win32').nodeMs);
    const timer = setTimeout(()=>controller.abort(new InspectionError('catalog_timeout','Capability request deadline exceeded')),Math.max(0,deadline-Date.now()));
    try {
      let result:T | Failure;
      try {
        result = await inspect(controller.signal,deadline);
        controller.signal.throwIfAborted();
      } catch (error) {
        const failure = controller.signal.aborted ? controller.signal.reason : error;
        if (failure instanceof InspectionError && failure.code === 'catalog_cancelled') return;
        result = {error_code:failure instanceof InspectionError?failure.code:'catalog_failed',message:'Capability inspection could not be completed. Retry shortly.'};
      }
      await reply(result);
    } finally {
      clearTimeout(timer);
      if (this.requests.get(context.requestId)===controller) this.requests.delete(context.requestId);
    }
  }
}
