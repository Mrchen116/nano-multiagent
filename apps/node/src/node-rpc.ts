import {decodeNodeInput,nodeCommands,type NodeCommand,type NodeParams,type NodeHandlers} from '@nano/product-contracts/node-rpc';

type Send = (type:string,payload:Record<string,unknown>)=>Promise<unknown>;

/** Await the reply's relay ACK inside the existing admission scope. Inspections may cancel without replying. */
export async function dispatchNodeCommand<K extends NodeCommand>(command:K,payload:Record<string,unknown>,handlers:NodeHandlers,nodeId:string,send:Send):Promise<void> {
  const requestId = payload.request_id;
  if (typeof requestId !== 'string' || !requestId) throw new Error(`Invalid ${command} field request_id`);
  const spec = nodeCommands[command];
  const reply = async (result:object) => { await send(spec.responseType,{...result,request_id:requestId,node_id:nodeId}); };
  let input:NodeParams<K>;
  try {
    if (payload.deadline_at !== undefined && (typeof payload.deadline_at !== 'number' || !Number.isFinite(payload.deadline_at)))
      throw new Error(`Invalid ${command} field deadline_at`);
    input = decodeNodeInput(command,payload);
  } catch (error) {
    if (!spec.invalid) throw error;
    await reply(spec.invalid);
    return;
  }
  const result = await handlers[command](input,{requestId,deadlineAt:typeof payload.deadline_at === 'number' ? payload.deadline_at : undefined},reply);
  if (result !== undefined) await reply(result);
}
