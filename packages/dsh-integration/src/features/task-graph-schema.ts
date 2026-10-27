import type { ToolDefinition } from '@deepseek-ai/dsh-tools';

const assignee = {
  type: ['object', 'null'],
  properties: { type: { type: 'string', enum: ['user', 'agent'] }, id: { type: 'string' } },
  required: ['type', 'id'], additionalProperties: false,
};

/** Existing product operations; IM remains their authority. */
export const taskGraphParameters: ToolDefinition['parameters'] = {
  "type": "object",
  "properties": {
    "action": {
      "description": "Choose one action; do not mix its fields with another action. create: requires title, mode and request_key; global mode also requires target, while single_thread may omit target for its bound conversation. Optional create fields: description, assignee, status and result. create does not accept operations. apply: requires graph_id, base_revision, request_key, change_note and operations; target is optional. delete: requires graph_id, base_revision and request_key; node_id and target are optional. get: requires graph_id; scope_id and view are optional. list: all filters are optional; accepts only query, cursor, limit, statuses, assignee_type and assignee_id. Do not supply target for list/get.",
      "type": "string",
      "enum": [
        "delete",
        "create",
        "list",
        "get",
        "apply"
      ]
    },
    "target": {
      "type": "string",
      "description": "For create, the existing conversation target fixes ownership; single_thread may omit it to use its bound conversation, global must supply it. For apply/delete, optional discussion source only; ownership never moves."
    },
    "assignee": assignee,
    "status": { "type": "string", "enum": ["todo", "doing", "in_review", "done", "paused", "closed"] },
    "result": { "type": "string", "maxLength": 32000 },
    "statuses": { "type": "string", "description": "Optional list filter: comma-separated todo, doing, waiting, in_review, done, paused or closed. Applied before limit; cursor is bound to this set." },
    "assignee_type": { "type": "string", "enum": ["user", "agent"], "description": "List filter; supply with assignee_id." },
    "assignee_id": { "type": "string", "description": "List filter; supply with assignee_type to find matching nodes across all levels." },
    "title": {
      "type": "string",
      "maxLength": 240
    },
    "description": {
      "type": "string",
      "maxLength": 32000
    },
    "mode": {
      "type": "string",
      "enum": [
        "dag",
        "explore"
      ]
    },
    "graph_id": {
      "type": "string"
    },
    "node_id": {
      "type": "string",
      "description": "Optional subtree root for delete; omit to delete the graph."
    },
    "scope_id": {
      "type": "string"
    },
    "view": {
      "type": "string",
      "enum": [
        "scope",
        "all"
      ]
    },
    "query": {
      "type": "string"
    },
    "cursor": {
      "type": "string"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50
    },
    "base_revision": {
      "type": "integer",
      "minimum": 1
    },
    "request_key": {
      "type": "string",
      "maxLength": 128,
      "description": "Required for create, apply, and delete. Choose a unique key for each new mutation; preserve the same key and arguments on uncertain retries."
    },
    "change_note": {
      "description": "Required for action=apply, including when the value is an empty string. Use a short explanation of the batch; an empty string is allowed for ordinary edits. Reopening done work as doing (including claim_task) requires a nonblank reason. Not accepted by create, delete, list or get.",
      "type": "string",
      "maxLength": 8000
    },
    "operations": {
      "type": "array",
      "minItems": 1,
      "maxItems": 100,
      "description": "Only for action=apply. Execute 1-100 operations in order as one atomic mutation. Use stable node IDs (for example n1) for existing nodes. To reference a node added earlier in this batch, use @client_ref (for example @A); bare A is not a batch reference and forward references are not allowed. add_task: container_id,title,client_ref plus optional description/mode/status/result/links/order/derived_from_id/assignee. update_task: node_id,patch (title/description/mode/status/wait/result/links/order only). add_dependency/remove_dependency: from,to (prerequisite -> successor; direct siblings in the same dag scope). set_derivation: node_id,derived_from_id (sibling in explore, or null). select_candidate: scope_id,node_id (direct child or null),reason. set_assignee: node_id,assignee ({type:user|agent,id} or null), without changing status. claim_task: node_id, claims for the actual caller and sets doing; cannot take another assignee. bind_execution: node_id,child_id,request_revision (current graph revision), optional correction_source_ref,input_receipt (actual native send_message messageId),delivery_receipt (actual sent message ID in the Task conversation). Only bind your own doing Task to your direct continuable child. After a correction forward it to the existing child, then rebind with the current revision and receipt. clear_execution: node_id. Creator is always the real caller, never supplied in arguments. Modes none/dag/explore; statuses todo/doing/waiting/in_review/done/paused/closed. Links are http(s) URLs or protected IM attachment paths. For an existing dag root n1, example: [{\"op\":\"add_task\",\"client_ref\":\"A\",\"container_id\":\"n1\",\"title\":\"Choose a plan\"},{\"op\":\"add_task\",\"client_ref\":\"B\",\"container_id\":\"n1\",\"title\":\"Confirm attendees\"},{\"op\":\"add_dependency\",\"from\":\"@A\",\"to\":\"@B\"}].",
      "items": {
        "type": "object",
        "properties": {
          "op": {
            "type": "string",
            "enum": [
              "add_task",
              "update_task",
              "set_assignee",
              "claim_task",
              "bind_execution",
              "clear_execution",
              "add_dependency",
              "remove_dependency",
              "set_derivation",
              "select_candidate"
            ]
          },
          "child_id": {"type":"string"},
          "request_revision": {"type":"integer"},
          "correction_source_ref": {"type":"string"},
          "input_receipt": {"type":"string"},
          "delivery_receipt": {"type":"string"},
          "assignee": assignee,
          "client_ref": {
            "description": "Required for add_task. Define a unique local name without @, for example A. Later operations in this batch must reference the new node as @A, not A. The returned client_refs maps this name to the stable node ID for future calls.",
            "type": "string"
          },
          "container_id": {
            "type": "string"
          },
          "title": {
            "type": "string"
          },
          "description": {
            "type": "string"
          },
          "mode": {
            "type": "string",
            "enum": [
              "none",
              "dag",
              "explore"
            ]
          },
          "status": {
            "type": "string",
            "enum": [
              "todo",
              "doing",
              "in_review",
              "done",
              "paused",
              "closed"
            ]
          },
          "result": {
            "type": "string"
          },
          "links": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "order": {
            "type": "number"
          },
          "derived_from_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "node_id": {
            "type": [
              "string",
              "null"
            ]
          },
          "scope_id": {
            "type": "string"
          },
          "reason": {
            "type": "string"
          },
          "from": {
            "description": "Required for add_dependency/remove_dependency. The prerequisite node that to depends on. Use an existing stable node ID such as n2, or @A for a client_ref defined by an earlier add_task in this batch. Both nodes must be direct children of the same dag scope.",
            "type": "string"
          },
          "to": {
            "description": "Required for add_dependency/remove_dependency. The successor that depends on from. Use an existing stable node ID such as n3, or @B for a client_ref defined by an earlier add_task in this batch. Both nodes must be direct children of the same dag scope.",
            "type": "string"
          },
          "patch": {
            "type": "object",
            "description": "Only title/description/mode/status/wait/result/links/order. Enter waiting with status=waiting and wait={reason,schedule_id}; first create a real future Schedule for the current owner session. Leaving waiting clears the reference. Server supplies verification fields; do not include them."
          }
        },
        "required": [
          "op"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "action"
  ],
  "additionalProperties": false
};
