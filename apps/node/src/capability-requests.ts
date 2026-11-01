/** Transient capability reads do not wait behind execution or lifecycle recovery. */
import {mkdir} from 'node:fs/promises';
import {ConfigurationInspector, InspectionError} from '@nano/dsh-integration/client';
import {NodeConfiguration} from './configuration.js';
import {projectCapabilities} from './capabilities.js';
import {providerProfiles} from './providers.js';
import type {installedPackageManager} from './release.js';

const commands = new Set(['agent.capabilities.resolve','node.capabilities.resolve','agent.prompt.preview.request','node.prompt.preview.request']);
interface Options {
  configuration: NodeConfiguration;
  inspector: ConfigurationInspector;
  packageManager: ReturnType<typeof installedPackageManager>;
  reply(type: string, payload: Record<string,unknown>): Promise<unknown>;
}
/** Own the finite lifetime of each IM waiter, not the underlying shared inspection. */
export class CapabilityRequests {
  private readonly requests = new Map<string,AbortController>();
  constructor(private readonly options: Options) {}
  accepts(type: string): boolean {return commands.has(type) || type === 'node.request.cancel';}

  /** End only network waiters when their authenticated relay connection is lost. */
  cancelAll(): void {
    for (const controller of this.requests.values()) controller.abort(new InspectionError('catalog_cancelled','Capability request cancelled'));
  }

  /** Resolve an already authenticated transient request with bounded work and cleanup. */
  async handle(frame: {type:string;payload:Record<string,unknown>}): Promise<void> {
    const {type,payload} = frame;
    if (type === 'node.request.cancel') {
      this.requests.get(String(payload.target_request_id))?.abort(new InspectionError('catalog_cancelled','Capability request cancelled'));
      return;
    }
    const requestId = String(payload.request_id);
    const controller = new AbortController();
    this.requests.set(requestId,controller);
    const deadline = Math.min(typeof payload.deadline_at === 'number' ? payload.deadline_at : Infinity,Date.now()+8000);
    const timer = setTimeout(()=>controller.abort(new InspectionError('catalog_timeout','Capability request deadline exceeded')),Math.max(0,deadline-Date.now()));
    const {configuration,inspector} = this.options, config = configuration.value;
    const preview = type.endsWith('preview.request');
    const responseType = preview ? type.replace('.request','') : type.startsWith('agent.') ? 'agent.capabilities' : 'node.capabilities';
    const reply = (value:Record<string,unknown>) => this.options.reply(responseType,{request_id:payload.request_id,node_id:config.node.node_id,...value});
    try {
      const agentId = typeof payload.agent_id === 'string' ? payload.agent_id : undefined;
      const current = config.agents.find(agent=>agent.agent_id===agentId);
      if (agentId && !current) throw new Error('Unknown Agent');
      const workspace = current?.workspace_root ?? (typeof payload.workspace_root === 'string' && payload.workspace_root
        ? payload.workspace_root : configuration.defaultWorkspace(String(payload.agent_id_hint ?? 'preview')));
      if (!config.llm.default_model && !current) {
        await reply(preview ? {error_code:'model_not_configured',message:'Connect a model before creating your assistant'} : {
          capabilities:{...projectCapabilities({tools:[],skills:[]},config),inherited_approval_rules:configuration.inheritedApproval(workspace).rules,
            default_workspace_template:configuration.defaultWorkspace('{agent_id}')},
        });
        return;
      }
      const candidate = configuration.runtime({...current,agent_id:agentId ?? 'preview',workspace_root:workspace,
        ...(preview ? {features:payload.features as Record<string,boolean>,custom_prompt:payload.custom_prompt as string,
          tool_allowlist:payload.tool_ids as string[] ?? [],skills:payload.skill_ids as string[] ?? [],
          skills_selection_mode:payload.skills_selection_mode as 'explicit_denylist' | 'explicit_allowlist' ?? 'explicit_denylist',work_mode:payload.work_mode as 'single_thread' | 'global'} : {}),
      });
      // New-Agent previews have no committed workspace yet; existing workspaces
      // are initialized by Node configuration, not by catalog Session storage.
      await mkdir(workspace,{recursive:true});
      controller.signal.throwIfAborted();
      const result = await inspector.inspect({method:preview?'preview':'catalog',config:candidate,cwd:workspace,
        providers:providerProfiles(config.llm).providers,packageManager:this.options.packageManager,requestId,deadlineAt:deadline},controller.signal);
      controller.signal.throwIfAborted();
      if (preview) {
        const value = result as {prompt:string;section_count:number};
        await reply({preview:{prompt:value.prompt,section_count:value.section_count}});
      } else {
        await reply({...(current?{agent_id:agentId,workspace_root:workspace}:{}),capabilities:{
          ...projectCapabilities(result as Parameters<typeof projectCapabilities>[0],config,current?candidate:undefined),
          inherited_approval_rules:configuration.inheritedApproval(workspace).rules,
          ...(!current?{default_workspace_template:configuration.defaultWorkspace('{agent_id}')}:{}),
        }});
      }
    } catch (error) {
      const failure = controller.signal.aborted ? controller.signal.reason : error;
      if (failure instanceof InspectionError && failure.code === 'catalog_cancelled') return;
      await reply({error_code:failure instanceof InspectionError?failure.code:'catalog_failed',message:'Capability inspection could not be completed. Retry shortly.'});
    } finally {
      clearTimeout(timer);
      if (this.requests.get(requestId)===controller) this.requests.delete(requestId);
    }
  }
}
