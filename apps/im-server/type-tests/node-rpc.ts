import type {NodeHandlers,NodeRequest} from '@nano/product-contracts/node-rpc';

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

import {ConfigOperations, type ConfigurationDependencies, type AgentProfileView} from '../src/control.js';
import type {AgentProfileRecord} from '../src/configuration-records.js';
import type {ConfigurationCandidate} from '../src/configuration-input.js';
function configurationContracts(dependencies: ConfigurationDependencies, record: AgentProfileRecord, view: AgentProfileView) {
  new ConfigOperations(dependencies);
  // @ts-expect-error Configuration business has no access to unrelated node setup.
  dependencies.request('node','node.setup.request',{action:'status'});
  // @ts-expect-error SQL JSON columns are not public configuration fields.
  view.skills_json;
  // @ts-expect-error SQLite flags cannot be sent as public boolean configuration.
  const candidate: ConfigurationCandidate = record;
  // @ts-expect-error A public view is not a persistent profile record for optimistic update.
  new ConfigOperations(dependencies).update(view, {agent_id:'agent'}, 'owner');
  return candidate;
}
void configurationContracts;

function setupContract(request:NodeRequest) {
  // @ts-expect-error Saving model setup requires both the revision and selected models.
  request('node','node.setup.request',{action:'save'});
}
void setupContract;

function handlerContracts(handlers:NodeHandlers) {
  const {['agent.work.permission']: removed, ...partial} = handlers;
  // @ts-expect-error Omitting a supported command leaves the dispatch table incomplete.
  const missing:NodeHandlers = partial;
  // @ts-expect-error A new Node cannot emit arbitrary execution states.
  const wrongState:NodeHandlers['task.execution.state'] = () => ({state:'made-up'});
  // @ts-expect-error An online jobs reply must distinguish an empty list from a failed read.
  const emptyJobs:NodeHandlers['node.cron.jobs.request'] = () => ({});
  // @ts-expect-error A configuration receipt must identify the durable operation.
  const emptyReceipt:NodeHandlers['agent.create'] = () => ({});
  const wrongInspection:NodeHandlers['node.prompt.preview.request'] = async (_input,_context,reply) => {
    // @ts-expect-error A preview reply must contain the preview or its failure.
    await reply({});
    // @ts-expect-error The bound preview callback cannot reply with a cron result.
    await reply({jobs:[]});
  };
  return {removed,missing,wrongState,emptyJobs,emptyReceipt,wrongInspection};
}
void handlerContracts;
