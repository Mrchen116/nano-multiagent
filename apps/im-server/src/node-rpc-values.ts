import {decodeNodeResult as decode, type NodeCommand,type NodeOutput} from '@nano/product-contracts/node-rpc';

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

/** Adapt malformed live and persisted node receipts to the IM gateway failure. */
export function decodeNodeResult<K extends NodeCommand>(command:K,value:unknown):NodeOutput<K> {
  try {return decode(command,value);}
  catch (error) {throw Object.assign(new Error('invalid node response',{cause:error}),{statusCode:502});}
}
