import type {NodeRequest} from '../src/node-rpc-contracts.js';

// These calls compile only; the errors protect the public command association,
// not an implementation detail of the socket or its pending map.
async function commandContracts(request: NodeRequest) {
  const result = await request('node', 'agent.config.get', {agent_id:'agent'});
  const name: string | null | undefined = result.agent?.display_name;
  // @ts-expect-error A response from config.get is not a cron deletion result.
  result.deleted;
  // @ts-expect-error Unknown command names cannot escape through a string overload.
  request('node', 'agent.config.gett', {agent_id:'agent'});
  // @ts-expect-error Config get requires an Agent identity.
  request('node', 'agent.config.get', {operation_id:'operation'});
  // @ts-expect-error Status needs an operation, not a configuration candidate.
  request('node', 'agent.config.operation.status', {agent_id:'agent'});
  // @ts-expect-error Plugin mutation action names are a finite contract.
  request('node', 'node.plugins.request', {agent_id:'agent',action:'delete_everything'});
  // @ts-expect-error Fork input cannot be used as configuration input.
  request('node', 'agent.config.apply', {source_conversation_id:'chat'});
  return name;
}
void commandContracts;
