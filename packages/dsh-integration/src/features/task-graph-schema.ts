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
    "statuses": { "type": "string", "description": "Optional list filter: comma-separated todo, doing, in_review, done, paused or closed. Applied before limit; cursor is bound to this set." },
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
      "type": "string",
      "maxLength": 8000
    },
    "operations": {
      "type": "array",
      "minItems": 1,
      "maxItems": 100,
      "description": "Atomic finite operations; IDs may use @client_ref defined by an earlier add_task in this batch. add_task: container_id,title,client_ref plus optional description/mode/status/result/links/order/derived_from_id/assignee. update_task: node_id,patch (title/description/mode/status/result/links/order only). add_dependency/remove_dependency: from,to (direct siblings in dag). set_derivation: node_id,derived_from_id (sibling in explore, or null). select_candidate: scope_id,node_id (direct child or null),reason. set_assignee: node_id,assignee ({type:user|agent,id} or null), without changing status. claim_task: node_id, claims for the actual caller and sets doing; cannot take another assignee. Creator is always the real caller, never supplied in arguments. Modes none/dag/explore; statuses todo/doing/in_review/done/paused/closed. Links are http(s) URLs or protected IM attachment paths. Example: [{\"op\":\"add_task\",\"client_ref\":\"A\",\"container_id\":\"n1\",\"title\":\"Choose a direction\",\"mode\":\"explore\"}].",
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
              "add_dependency",
              "remove_dependency",
              "set_derivation",
              "select_candidate"
            ]
          },
          "assignee": assignee,
          "client_ref": {
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
            "type": "string"
          },
          "to": {
            "type": "string"
          },
          "patch": {
            "type": "object",
            "description": "Only title/description/mode/status/result/links/order."
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
