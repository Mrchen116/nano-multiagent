import type { ToolDefinition } from '@deepseek-ai/dsh-tools';

const assignee = {
  type: ['object', 'null'],
  properties: { type: { type: 'string', enum: ['user', 'agent'] }, id: { type: 'string' } },
  required: ['type', 'id'], additionalProperties: false,
};

const proposalSchema = {
  type: ['object', 'null'],
  description: 'Required when status="proposed". State why this candidate matters (rationale) and what concrete action will be taken once approved (on_approve); optionally target proposed_for_user_id in shared chats.',
  properties: {
    rationale: { type: 'string', maxLength: 4000 },
    on_approve: { type: 'string', maxLength: 4000 },
    proposed_for_user_id: { type: ['string', 'null'] },
  },
  required: ['rationale', 'on_approve'],
  additionalProperties: false,
};

const allStatuses = ['proposed', 'todo', 'doing', 'waiting', 'in_review', 'done', 'paused', 'backlog', 'closed'] as const;

/** Progressive task-graph operations; IM remains their authority. */
export const taskGraphParameters: ToolDefinition['parameters'] = {
  type: 'object',
  properties: {
    action: {
      description: 'Choose one action; do not mix its fields with another action. create: requires title and request_key (mode defaults to "none" for a zero-friction single card, or pass "dag"/"explore" and optional initial operations to build a multi-step goal graph in one transaction; global mode requires target, while single_thread may omit target for its bound conversation). Optional create fields: mode, description, assignee, status, proposal, wait, result, and operations. apply: requires graph_id, base_revision, request_key, change_note, and operations; target is optional. delete: requires graph_id, base_revision, and request_key; node_id and target are optional. get: requires graph_id; scope_id and view are optional. list: all filters are optional; accepts query, cursor, limit, statuses, assignee_type, and assignee_id. Do not supply target for list/get.',
      type: 'string',
      enum: ['delete', 'create', 'list', 'get', 'apply'],
    },
    target: {
      type: 'string',
      description: 'For create, the existing conversation target fixes ownership; single_thread may omit it to use its bound conversation, global must supply it. For apply/delete, optional discussion source only; ownership never moves.',
    },
    assignee,
    proposal: proposalSchema,
    wait: {
      type: ['object', 'null'],
      description: 'Optional wait metadata when creating or updating a waiting Task: {reason, schedule_id?, question?, asked_user_id?}. Supply schedule_id when linking a native Schedule (up to 180 days out; requires an Agent assignee with assignee.type="agent"); omit schedule_id when silently waiting on a human reply or external event.',
    },
    status: {
      type: 'string',
      enum: [...allStatuses],
    },
    result: { type: 'string', maxLength: 32000 },
    statuses: {
      type: 'string',
      description: 'Optional list filter: comma-separated proposed, todo, doing, waiting, in_review, done, paused, backlog, or closed. Applied before limit; cursor is bound to this set.',
    },
    assignee_type: { type: 'string', enum: ['user', 'agent'], description: 'List filter; supply with assignee_id.' },
    assignee_id: { type: 'string', description: 'List filter; supply with assignee_type to find matching nodes across all levels.' },
    title: { type: 'string', maxLength: 240 },
    description: { type: 'string', maxLength: 32000 },
    mode: {
      type: 'string',
      description: 'Container mode: defaults to "none" (single standalone card); upgrade in place to "dag" (ordered dependencies) or "explore" (parallel alternatives) when children are needed.',
      enum: ['none', 'dag', 'explore'],
    },
    graph_id: { type: 'string' },
    node_id: {
      type: 'string',
      description: 'Optional subtree root for delete; omit to delete the graph.',
    },
    scope_id: { type: 'string' },
    view: { type: 'string', enum: ['scope', 'all'] },
    query: { type: 'string' },
    cursor: { type: 'string' },
    limit: { type: 'integer', minimum: 1, maximum: 50 },
    base_revision: { type: 'integer', minimum: 1 },
    request_key: {
      type: 'string',
      maxLength: 128,
      description: 'Required for create, apply, and delete. Choose a unique key for each new mutation; preserve the same key and arguments on uncertain retries.',
    },
    change_note: {
      description: 'Required for action=apply, including when the value is an empty string. Use a short explanation of the batch; an empty string is allowed for ordinary edits. Reopening done work as doing (including claim_task) requires a nonblank reason. Not accepted by create, delete, list, or get.',
      type: 'string',
      maxLength: 8000,
    },
    operations: {
      type: 'array',
      minItems: 1,
      maxItems: 100,
      description: 'For action=apply (or optional initial child setup on action=create when mode is dag/explore, where container_id="n1" references the newly created root). Execute 1-100 operations in order as one atomic mutation. Reference nodes added earlier in the same batch as @client_ref (for example @A). Ops: add_task (container_id,title,client_ref + optional description/mode/status/proposal/wait/result/links/order/derived_from_id/assignee), update_task (node_id,patch with title/description/mode/status/proposal/wait/result/links/order), approve_task (node_id — transitions a proposed node to doing when assigned to an Agent with all dag prerequisites done, otherwise to todo), add_dependency/remove_dependency (from,to in the same dag scope), set_derivation (node_id,derived_from_id), select_candidate (scope_id,node_id,reason), set_assignee (node_id,assignee), claim_task (node_id).',
      items: {
        type: 'object',
        properties: {
          op: {
            type: 'string',
            enum: [
              'add_task',
              'update_task',
              'approve_task',
              'set_assignee',
              'claim_task',
              'add_dependency',
              'remove_dependency',
              'set_derivation',
              'select_candidate',
            ],
          },
          assignee,
          proposal: proposalSchema,
          wait: { type: ['object', 'null'] },
          client_ref: {
            description: 'Required for add_task. Define a unique local name without @, for example A. Later operations in this batch must reference the new node as @A, not A.',
            type: 'string',
          },
          container_id: { type: 'string' },
          title: { type: 'string' },
          description: { type: 'string' },
          mode: { type: 'string', enum: ['none', 'dag', 'explore'] },
          status: { type: 'string', enum: [...allStatuses] },
          result: { type: 'string' },
          links: { type: 'array', items: { type: 'string' } },
          order: { type: 'number' },
          derived_from_id: { type: ['string', 'null'] },
          node_id: { type: ['string', 'null'] },
          scope_id: { type: 'string' },
          reason: { type: 'string' },
          from: {
            description: 'Required for add_dependency/remove_dependency. Prerequisite node ID (e.g. n2 or @A) in the same dag scope.',
            type: 'string',
          },
          to: {
            description: 'Required for add_dependency/remove_dependency. Successor node ID (e.g. n3 or @B) in the same dag scope.',
            type: 'string',
          },
          patch: {
            type: 'object',
            description: 'Only title/description/mode/status/proposal/wait/result/links/order. Upgrade a leaf card to a goal container in place via mode="dag"|"explore". For status="waiting", pass wait={reason,schedule_id?,question?,asked_user_id?}: include schedule_id when linking a native Schedule (up to 180 days out; requires an Agent assignee with assignee.type="agent"), or omit schedule_id when silently waiting on a human reply or external event.',
          },
        },
        required: ['op'],
        additionalProperties: false,
      },
    },
  },
  required: ['action'],
  additionalProperties: false,
};
