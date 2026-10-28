import type {NodeCommand, NodeInput, NodeOutput, NodeRequest, ConfigurationRequest, ConfigurationCommand} from './node-rpc-contracts.js';

/** Optional reads keep the existing offline/timeout fallback at their HTTP boundary. */
export async function gatewayRequest<K extends NodeCommand>(ctx: {gateway:{request:NodeRequest}}, node: string, action: K, payload: NodeInput<NoInfer<K>>): Promise<NodeOutput<K> | null> {
  try { return await ctx.gateway.request(node, action, payload); }
  catch (error) {
    if (error && typeof error === 'object' && 'statusCode' in error && (error.statusCode === 503 || error.statusCode === 504)) return null;
    throw error;
  }
}

/** A malformed receipt is unconfirmed, just like a lost ACK; keep the original durable intent. */
export async function requestConfiguration<K extends ConfigurationCommand>(request: ConfigurationRequest, node: string, action: K, payload: NodeInput<NoInfer<K>>): Promise<NodeOutput<K> | null> {
  try { return await request(node, action, payload); }
  catch (error) {
    if (error && typeof error === 'object' && 'statusCode' in error && [502,503,504].includes(Number(error.statusCode))) return null;
    throw error;
  }
}
