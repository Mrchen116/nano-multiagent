import {cp,mkdir,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {load,dump} from 'js-yaml';
import {randomUUID} from 'node:crypto';
import {NodeConfiguration} from './configuration.js';
import {providerProfiles} from './providers.js';
import {prepareProfile,RuntimeClient} from '@nano/dsh-integration/client';

export interface ArchiveSession {sessionId:string;rootSessionId:string;agentId:string;stage:string;title:string;modelCalls?:number;toolErrors?:number}
/** Read a Memory evaluation's native records using the same public carrier as Agent Work. */
export class EvaluationArchive {
  private observers=new Set<string>();
  private constructor(private client:RuntimeClient,readonly sessions:ArchiveSession[]) {}
  /** Open a writable viewing copy; never initialize DSH against the original evidence.
   * Args:
   *   root: Existing experiment directory containing agent-work and analysis.
   *   scratch: New viewer-owned directory for a copy of the native runtime.
   */
  static async open(root:string,scratch:string) {
    const archive=join(root,'agent-work');
    await mkdir(scratch,{recursive:false});
    const raw=load(await readFile(join(archive,'gateway.yaml'),'utf8')) as {node:{workspace_base?:string};agents:Array<{agent_id:string;workspace_root?:string}>;gateway?:{environment?:Record<string,string>}};
    raw.node.workspace_base=join(scratch,'workspaces');
    for(const agent of raw.agents)agent.workspace_root=join(scratch,'workspaces',agent.agent_id);
    if(raw.gateway)raw.gateway.environment={...raw.gateway.environment,NANO_OWNER_CONFIG_ROOT:join(scratch,'owner')};
    await writeFile(join(scratch,'gateway.yaml'),dump(raw),{mode:0o600});
    const config=await NodeConfiguration.read(join(scratch,'gateway.yaml'));
    const metadata=JSON.parse(await readFile(join(archive,'metadata.json'),'utf8')) as Array<{stage:string;agentId:string;rootSessionId:string;sessions:Array<{id:string;createdAt:number}>}>;
    const metrics=JSON.parse(await readFile(join(root,'analysis/metrics.json'),'utf8'));
    await cp(join(archive,'runtime'),join(scratch,'runtime'),{recursive:true});
    const agents=config.value.agents.map(a=>({...config.runtime(a),workspace:join(scratch,'workspaces',a.agent_id),features:{...config.runtime(a).features,dreaming:false,memory_curation:false,skill_creation:false,cron_scheduling:false,heartbeat:false}}));
    for(const agent of agents)await mkdir(agent.workspace,{recursive:true});
    const bindings=metadata.map(m=>({sessionId:m.rootSessionId,agentId:m.agentId,ownerId:'evaluation-archive',revision:agents.find(a=>a.agentId===m.agentId)!.revision,cwd:join(scratch,'workspaces',m.agentId)}));
    const provider=providerProfiles(config.value.llm);
    await prepareProfile(join(scratch,'runtime'),[{id:'llm-pi-ai',config:{providers:provider.providers}}]);
    const client=new RuntimeClient({home:join(scratch,'runtime'),cwd:scratch,env:provider.env});
    client.rpc.handle('product.call',()=>{throw new Error('Read-only evaluation archive: execution unavailable')});
    try {await client.rpc.request('initialize',{protocol:1,observationOnly:true,agents,bindings,lifecycle:Object.fromEntries(agents.map(a=>[a.agentId,{revision:1,disabled:true,disabledThroughRevision:1}]))})}
    catch(error){await client.shutdown();throw error}
    const sessions=metadata.flatMap(m=>{
      let batch=0;
      return [...m.sessions].sort((a,b)=>a.id===m.rootSessionId?-1:b.id===m.rootSessionId?1:a.createdAt-b.createdAt).map(s=>{
        const main=s.id===m.rootSessionId;const stats=metrics[m.stage]?.sessionsDetail?.find((row:{sessionId:string})=>row.sessionId===s.id);
        return {sessionId:s.id,rootSessionId:m.rootSessionId,agentId:m.agentId,stage:m.stage,title:main?(m.stage==='answer'?'冷答题':'导入历史'):`${m.stage==='prepare'?'Dreaming':'执行'} 第 ${++batch} 批`,modelCalls:stats?.modelResponses,toolErrors:stats?.toolErrors};
      });
    });
    return new EvaluationArchive(client,sessions);
  }
  /** Forward only read/navigation operations for declared archived sessions. */
  async request(input:Record<string,unknown>):Promise<unknown> {
    if(input.type==='prepare') {
      const selected=this.sessions.find(s=>s.sessionId===input.sessionId);if(!selected)throw new Error('Unknown archived session');
      const observerId=randomUUID();const result=await this.client.rpc.request('trajectory.prepare',{observerId,rootAgentId:selected.agentId,rootSessionId:selected.rootSessionId,sessionId:selected.sessionId,ownerId:'evaluation-archive',nodeId:'archive',nodeEpoch:1}) as Record<string,unknown>;
      this.observers.add(observerId);return {...result,observerId};
    }
    if(typeof input.observerId!=='string'||!this.observers.has(input.observerId)||!['call','open','next','abort','close'].includes(String(input.type)))throw new Error('Read capability required');
    const result=await this.client.rpc.request('trajectory.'+input.type,{observerId:input.observerId,method:input.method,params:input.params,streamId:input.streamId});
    if(input.type==='close')this.observers.delete(input.observerId);return result;
  }
  async close(){try{for(const observerId of this.observers)await this.client.rpc.request('trajectory.close',{observerId})}finally{await this.client.shutdown()}}
}
