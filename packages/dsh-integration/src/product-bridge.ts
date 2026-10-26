import { Service, type Context } from '@deepseek-ai/cordis';
import type { ToolRunContext } from '@deepseek-ai/dsh-tools';
import type {} from './policy/approval.js';
import type { RpcPeer } from './rpc.js';
import type { PersonalDeliveryEvidence } from './personal-delivery-evidence.js';
import type { NativeTaskExecutions } from './task-native-execution.js';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { SessionBinding } from './index.js';

declare module '@deepseek-ai/cordis' { interface Context { nanoProduct: ProductBridge } }

/** Adds only trusted execution identity to reverse product calls. */
export class ProductBridge extends Service {
  constructor(ctx: Context, private readonly options: { peer: RpcPeer; bindings: Map<string, SessionBinding>; memoryConsumer:(agent:Agent)=>Promise<boolean>; liveInputIds:(agent:Agent)=>Promise<string[]>; nativeTasks:NativeTaskExecutions; deliveryEvidence:PersonalDeliveryEvidence }) { super(ctx, 'nanoProduct'); }
  /** Original human inputs actually acquired by this native turn. */
  humanInputs(agent:Agent):Promise<string[]>{return this.options.liveInputIds(agent);}
  async call(method: string, args: unknown, exec: Pick<ToolRunContext, 'agent' | 'signal' | 'callId'>): Promise<unknown> {
    if (!exec.agent) throw new Error('Product tools require a bound Agent');
    let root = exec.agent;
    while (!this.options.bindings.has(root.id) && root.session.header.parentSession) {
      const parent = this.ctx.agents.get(root.session.header.parentSession);
      if (!parent) throw new Error('Missing product parent binding');
      root = parent;
    }
    const binding = this.options.bindings.get(root.id);
    if (!binding) throw new Error('Agent has no product identity');
    if (['send_user_message','publish_artifact','personal_context','personal_attention','personal_sources','pa.attention.snooze.complete'].includes(method)
      && (exec.agent.id !== root.id || exec.agent.session.header.origin === 'subagent')) throw new Error('Only the bound root PA can use private owner capabilities');
    if (method === 'pa.memory.sources' && !await this.options.memoryConsumer(exec.agent)) throw new Error('Private memory sources require the root or trusted memory maintenance');
    exec.signal.throwIfAborted();
    const operationId = `${exec.agent.id}:${exec.callId}`;
    const cancel = () => this.options.peer.notify('product.cancel', { operationId });
    exec.signal.addEventListener('abort', cancel, { once: true });
    try {
      if(method==='task_graph')args=await this.options.nativeTasks.prepare(exec.agent,args as Record<string,unknown>);
      const result=await this.options.peer.request('product.call', { method, args, operationId, callId: exec.callId,
        sessionId: exec.agent.id, rootSessionId: root.id, agentId: binding.agentId, ownerId: binding.ownerId,
        ...(method==='send_message'?{liveInputIds:await this.options.liveInputIds(exec.agent),scheduleTriggers:await this.options.deliveryEvidence.current(exec.agent),childReturns:await this.options.deliveryEvidence.childReturns(exec.agent)}:{}) });
      if(method==='task_graph')await this.options.nativeTasks.committed(exec.agent,args as Record<string,unknown>,result);
      return result;
    } finally { exec.signal.removeEventListener('abort', cancel); }
  }
}
