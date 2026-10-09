import { Service, type Context } from '@deepseek-ai/cordis';
import type { ToolRunContext } from '@deepseek-ai/dsh-tools';
import type { RpcPeer } from './rpc.js';
import type { SessionBinding } from './index.js';

declare module '@deepseek-ai/cordis' { interface Context { nanoProduct: ProductBridge } }

/** Adds only trusted execution identity to reverse product calls. */
export class ProductBridge extends Service {
  constructor(ctx: Context, private readonly options: { peer: RpcPeer; bindings: Map<string, SessionBinding> }) { super(ctx, 'nanoProduct'); }
  async call(method: string, args: unknown, exec: ToolRunContext): Promise<unknown> {
    if (!exec.agent) throw new Error('Product tools require a bound Agent');
    let root = exec.agent;
    while (!this.options.bindings.has(root.id) && root.session.header.parentSession) {
      const parent = this.ctx.agents.get(root.session.header.parentSession);
      if (!parent) throw new Error('Missing product parent binding');
      root = parent;
    }
    const binding = this.options.bindings.get(root.id);
    if (!binding) throw new Error('Agent has no product identity');
    exec.signal.throwIfAborted();
    const operationId = `${exec.agent.id}:${exec.callId}`;
    const cancel = () => this.options.peer.notify('product.cancel', { operationId });
    exec.signal.addEventListener('abort', cancel, { once: true });
    try {
      return await this.options.peer.request('product.call', { method, args, operationId, callId: exec.callId,
        sessionId: exec.agent.id, rootSessionId: root.id, agentId: binding.agentId, ownerId: binding.ownerId });
    } finally { exec.signal.removeEventListener('abort', cancel); }
  }
}
