import { canAccessSpace, canActorAccess } from "./identity.js";
import { createHash, randomUUID } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import type { FastifyInstance } from "fastify";
import type { ImContext } from "./context.js";
import type { Messaging } from "./messaging.js";
import { conversationAccess, qualifiedUser } from "./conversation-access.js";
import { taskNotices } from "./task-notifications.js";

type Obj = Record<string, any>;
export interface TaskGraphActor {
  kind: "user" | "agent";
  id: string;
  node_id?: string;
  source_message_id?: string;
}
export class TaskGraphError extends Error {
  constructor(
    public code: string,
    message: string,
    public details: Obj = {},
  ) {
    super(message);
  }
  asDict() {
    return { code: this.code, message: this.message, ...this.details };
  }
}
export function canonicalJson(value: any): string {
  return JSON.stringify(value, (_key, item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? Object.fromEntries(
          Object.keys(item)
            .sort()
            .map((k) => [k, item[k]]),
        )
      : item,
  );
}
function fail(code: string, message: string): never {
  throw new TaskGraphError(code, message);
}
function text(value: any, field: string, limit = 128, empty = false): string {
  if (typeof value !== "string" || value.length > limit || (!empty && !value.trim()))
    fail(
      "invalid_arguments",
      `${field} must be a string of ${empty ? "at most" : "1–"}${limit} characters`,
    );
  return value;
}
function invalid(message: string): never {
  return fail("invalid_graph", message);
}
function forbidden(): never {
  return fail("not_found_or_forbidden", "Task graph or conversation is not accessible");
}
function newNode(
  id: string,
  container: string | null,
  title: string,
  actor: string,
  now: string,
  fields: Obj = {},
): Obj {
  return {
    id,
    container_id: container,
    title,
    description: "",
    mode: "none",
    status: "todo",
    result: "",
    derived_from_id: null,
    selected_candidate_id: null,
    selection_reason: "",
    links: [],
    order: 0,
    last_chat_id: null,
    ...fields,
    created_at: now,
    updated_at: now,
    updated_by: actor,
  };
}
function acyclic(ids: string[], edges: Obj[]) {
  const pending = new Map(ids.map((id) => [id, 0]));
  const outgoing = new Map(ids.map((id) => [id, [] as string[]]));
  for (const edge of edges) {
    pending.set(edge.to, pending.get(edge.to)! + 1);
    outgoing.get(edge.from)!.push(edge.to);
  }
  const ready = ids.filter((id) => !pending.get(id));
  let visited = 0;
  while (ready.length) {
    const id = ready.pop()!;
    visited++;
    for (const end of outgoing.get(id)!) {
      pending.set(end, pending.get(end)! - 1);
      if (!pending.get(end)) ready.push(end);
    }
  }
  if (visited !== ids.length) invalid("Relationships must not contain a cycle");
}
export function validateDocument(doc: Obj) {
  if (doc.schema_version !== 2) invalid("Unsupported task graph schema_version");
  if (
    !Array.isArray(doc.nodes) ||
    doc.nodes.length < 1 ||
    doc.nodes.length > 500 ||
    !Array.isArray(doc.dependencies) ||
    doc.dependencies.length > 1000
  )
    invalid("A graph allows at most 500 nodes and 1000 dependencies");
  const nodes: Obj[] = doc.nodes,
    by = new Map(nodes.map((n) => [n.id, n]));
  const root = by.get(doc.root_node_id);
  if (by.size !== nodes.length || !root) invalid("Node IDs must be unique and include the root");
  if (root.container_id !== null || !["dag", "explore"].includes(root.mode))
    invalid("The root must be a plan or exploration scope with no container");
  const derivations: Obj[] = [];
  for (const n of nodes) {
    text(n.title, "title", 240);
    actorRef(n.created_by);
    if (n.assignee !== null) actorRef(n.assignee);
    for (const key of ["description", "result"]) text(n[key], key, 32000, true);
    text(n.selection_reason, "selection_reason", 8000, true);
    if (
      !["none", "dag", "explore"].includes(n.mode) ||
      !["todo", "doing", "in_review", "done", "paused", "closed"].includes(n.status)
    )
      invalid("Unknown node mode or record status");
    if (!Number.isInteger(n.order)) invalid("order must be an integer");
    if (!Array.isArray(n.links) || n.links.length > 20)
      invalid("links must contain at most 20 URLs");
    for (const link of n.links) {
      text(link, "link", 2048);
      let allowed = /^\/im\/v1\/conversations\/.*\/(images|attachments)\//.test(link);
      try {
        const u = new URL(link);
        allowed = ["http:", "https:"].includes(u.protocol) && !!u.host;
      } catch {}
      if (!allowed) invalid("Links must be HTTP(S) URLs or protected IM attachment references");
    }
    if (n.id !== root.id) {
      let p = by.get(n.container_id);
      if (!p || p.mode === "none") invalid("Every non-root node must belong to a subdivided scope");
      const seen = new Set([n.id]);
      while (true) {
        if (seen.has(p.id) || seen.size >= 8)
          invalid("Containment must reach the root within eight levels without a cycle");
        seen.add(p.id);
        if (p.id === root.id) break;
        p = by.get(p.container_id);
        if (!p) invalid("Containment must reach the root");
      }
    }
    if (n.derived_from_id !== null) {
      const source = by.get(n.derived_from_id),
        parent = by.get(n.container_id);
      if (!source || !parent || parent.mode !== "explore" || source.container_id !== parent.id)
        invalid("A direction source must belong to the same exploration scope");
      derivations.push({ from: source.id, to: n.id });
    }
    if (n.selected_candidate_id !== null) {
      const selected = by.get(n.selected_candidate_id);
      if (
        n.mode !== "explore" ||
        !selected ||
        selected.container_id !== n.id ||
        selected.status === "closed"
      )
        invalid("The selected direction must be a non-closed direct exploration candidate");
    }
  }
  for (const edge of doc.dependencies) {
    const start = by.get(edge.from),
      end = by.get(edge.to),
      parent = by.get(start?.container_id);
    if (!start || !end || !parent || parent.mode !== "dag" || end.container_id !== parent.id)
      invalid("Dependencies must join direct children of the same plan scope");
  }
  if (
    new Set(doc.dependencies.map((e: Obj) => `${e.from}\0${e.to}`)).size !== doc.dependencies.length
  )
    invalid("Dependencies must be unique");
  acyclic([...by.keys()], doc.dependencies);
  acyclic([...by.keys()], derivations);
}
const editable = ["title", "description", "mode", "status", "result", "links", "order"];
export function applyOperations(
  document: Obj,
  operations: any,
  actor: string,
  now: string,
  note: string,
  identity: Obj,
) {
  if (!Array.isArray(operations) || operations.length < 1 || operations.length > 100)
    fail("invalid_arguments", "operations must contain 1–100 items");
  const doc = structuredClone(document),
    nodes = new Map<string, Obj>(doc.nodes.map((n: Obj) => [n.id, n])),
    refs: Obj = {},
    changed = new Set<string>();
  const allowed: Obj = {
    add_task: ["op", "client_ref", "container_id", "derived_from_id", "assignee", ...editable],
    update_task: ["op", "node_id", "patch"],
    set_assignee: ["op", "node_id", "assignee"],
    claim_task: ["op", "node_id"],
    add_dependency: ["op", "from", "to"],
    remove_dependency: ["op", "from", "to"],
    set_derivation: ["op", "node_id", "derived_from_id"],
    select_candidate: ["op", "scope_id", "node_id", "reason"],
  };
  function resolve(value: any, nullable = false): any {
    if (value == null && nullable) return null;
    const ref = text(value, "node reference"),
      id = ref.startsWith("@") ? refs[ref.slice(1)] : ref;
    if (!nodes.has(id)) invalid(`Unknown node or forward reference: ${ref}`);
    return id;
  }
  for (const [index, op] of operations.entries()) {
    try {
      if (!op || !allowed[op.op]) fail("invalid_arguments", "Unknown operation");
      if (Object.keys(op).some((k) => !allowed[op.op].includes(k)))
        fail("invalid_arguments", `Unknown fields for ${op.op}`);
      if (op.op === "add_task") {
        const ref = text(op.client_ref, "client_ref");
        if (refs[ref] || ref.startsWith("@"))
          invalid("client_ref must be unique within the batch and not start with @");
        const parent = resolve(op.container_id);
        const ordinal =
          doc.next_node_number ??
          Math.max(
            nodes.size,
            ...[...nodes.keys()].filter((k) => /^n\d+$/.test(k)).map((k) => Number(k.slice(1))),
          ) + 1;
        const id = `n${ordinal}`;
        doc.next_node_number = ordinal + 1;
        const fields = Object.fromEntries(editable.filter((k) => k in op).map((k) => [k, op[k]]));
        const n = newNode(id, parent, op.title, actor, now, {
          ...fields,
          created_by: identity,
          updated_by_actor: identity,
          assignee: op.assignee === undefined || op.assignee === null ? null : actorRef(op.assignee),
          derived_from_id: resolve(op.derived_from_id, true),
        });
        doc.nodes.push(n);
        nodes.set(id, n);
        refs[ref] = id;
        changed.add(id);
        changed.add(parent);
      } else if (op.op === "set_assignee" || op.op === "claim_task") {
        const id = resolve(op.node_id), n = nodes.get(id)!;
        if (op.op === "claim_task") {
          if (n.assignee && !sameActor(n.assignee, identity)) fail("already_assigned", "Task is already assigned; use explicit reassignment");
          if (n.status === "done" && !note.trim()) invalid("Reopening completed work requires a change_note");
          n.assignee = identity;
          n.status = "doing";
        } else n.assignee = op.assignee === null ? null : actorRef(op.assignee);
        changed.add(id);
      } else if (op.op === "update_task") {
        const id = resolve(op.node_id),
          n = nodes.get(id)!,
          p = op.patch;
        if (
          !p ||
          Array.isArray(p) ||
          typeof p !== "object" ||
          !Object.keys(p).length ||
          Object.keys(p).some((k) => !editable.includes(k))
        )
          fail("invalid_arguments", "patch must contain only editable node fields");
        if ("mode" in p && p.mode !== n.mode && doc.nodes.some((c: Obj) => c.container_id === id))
          invalid("A non-empty scope cannot change its internal mode");
        if (n.status === "done" && p.status === "doing" && !note.trim())
          invalid("Reopening completed work requires a change_note");
        Object.assign(n, p);
        changed.add(id);
      } else if (["add_dependency", "remove_dependency"].includes(op.op)) {
        const from = resolve(op.from),
          to = resolve(op.to);
        const i = doc.dependencies.findIndex((e: Obj) => e.from === from && e.to === to);
        if (op.op === "add_dependency" && i < 0) doc.dependencies.push({ from, to });
        else if (op.op === "remove_dependency") {
          if (i < 0) fail("relation_not_found", "That dependency does not exist");
          doc.dependencies.splice(i, 1);
        }
        changed.add(from);
        changed.add(to);
      } else if (op.op === "set_derivation") {
        const id = resolve(op.node_id),
          n = nodes.get(id)!;
        if (nodes.get(n.container_id)?.mode !== "explore")
          invalid("Derivation can only be changed inside an exploration scope");
        n.derived_from_id = resolve(op.derived_from_id, true);
        changed.add(id);
      } else {
        const id = resolve(op.scope_id),
          n = nodes.get(id)!;
        if (n.mode !== "explore") invalid("Selection can only be changed on an exploration scope");
        n.selected_candidate_id = resolve(op.node_id, true);
        n.selection_reason = text(op.reason ?? "", "reason", 8000, true);
        changed.add(id);
      }
    } catch (e) {
      if (e instanceof TaskGraphError) e.details.operation_index = index;
      throw e;
    }
  }
  validateDocument(doc);
  for (const id of changed)
    Object.assign(nodes.get(id)!, {
      updated_at: now,
      updated_by: actor,
      updated_by_actor: identity,
      change_note: note,
    });
  Object.assign(doc, {
    revision: document.revision + 1,
    updated_at: now,
    updated_by: actor,
  });
  return { document: doc, refs, changed: [...changed].sort() };
}
function actorRef(value: any): Obj {
  if (!value || !["user", "agent"].includes(value.type) || typeof value.id !== "string" || !value.id || Object.keys(value).some(k => !["type", "id"].includes(k)))
    fail("invalid_arguments", "Actor must contain type and id");
  return { type: value.type, id: value.id };
}
function sameActor(a: Obj | null, b: Obj | null): boolean {
  return a?.type === b?.type && a?.id === b?.id;
}
function directCounts(doc: Obj, id: string): Obj {
  const counts: Obj = {todo:0,doing:0,in_review:0,done:0,paused:0,closed:0,total:0};
  for (const n of doc.nodes) if (n.container_id === id) { counts[n.status]++; counts.total++; }
  return counts;
}
function summary(d: Obj): Obj {
  const root = d.nodes.find((n: Obj) => n.id === d.root_node_id);
  return {
    ...Object.fromEntries(
      ["graph_id", "root_node_id", "revision", "created_at", "updated_at", "updated_by"].map(
        (k) => [k, d[k]],
      ),
    ),
    title: root.title,
    mode: root.mode,
    status: root.status,
    created_by: root.created_by,
    assignee: root.assignee,
    direct_counts: directCounts(d, root.id),
    relative_url: `/tasks/${d.graph_id}`,
  };
}
const fields: Obj = {
  list: ["query", "cursor", "limit", "assignee_type", "assignee_id", "statuses"],
  activity: ["conversation_id"],
  get: ["graph_id", "scope_id", "view"],
  create: ["conversation_id", "title", "description", "mode", "request_key", "assignee", "status", "result"],
  apply: [
    "graph_id",
    "base_revision",
    "request_key",
    "operations",
    "change_note",
    "conversation_id",
  ],
  delete: ["graph_id", "node_id", "base_revision", "request_key", "conversation_id"],
};
/** Persist graph documents and replay receipts in the same synchronous transaction. */
export class TaskGraphService {
  constructor(private db: DatabaseSync, private messaging: Messaging,
    private personalRead?: {ownerUserId:string; sourceAllowed:(conversationId:string)=>boolean}) {}
  private row(sql: string, ...args: any[]): Obj | undefined {
    return this.db.prepare(sql).get(...args) as Obj | undefined;
  }
  private rows(sql: string, ...args: any[]): Obj[] {
    return this.db.prepare(sql).all(...args) as Obj[];
  }
  private chat(id: string | null | undefined, user: string) {
    return id && (!this.personalRead || this.personalRead.sourceAllowed(id)) ? conversationAccess(this.db, id, user) : undefined;
  }
  private writable(id: string, user: string) {
    const c = this.chat(id, user);
    if (!c?.is_member) forbidden();
    if (c.dissolved_at) fail("conversation_dissolved", "This conversation is read-only after dissolution");
    return c;
  }
  private identity(ref: Obj | null): Obj | null {
    if (!ref) return null;
    const u = this.row("SELECT id,display_name FROM users WHERE " + (ref.type === "agent" ? "username=?" : "id=?"), ref.type === "agent" ? `agent:${ref.id}` : ref.id);
    return {...ref, display_name:u?.display_name ?? ref.id, user_id:u?.id ?? null};
  }
  private assignee(ref: Obj | null, conversation: string) {
    if (!ref) return;
    const resolved = this.identity(ref)!;
    const user = resolved.user_id ? qualifiedUser(this.db, resolved.user_id) : undefined;
    if (user && (ref.type === "agent") !== user.username.startsWith("agent:"))
      fail("invalid_arguments", "Assignee actor type must match the resolved identity");
    if (!user || !conversationAccess(this.db, conversation, resolved.user_id)?.is_member)
      fail("assignee_not_member", "Assignee must be an active conversation member");
  }
  private canDelete(node: Obj, actor: Obj, user: string): boolean {
    return sameActor(node.created_by, actor) || (actor.type === "user" && !!this.row("SELECT is_company_admin FROM users WHERE id=?", user)?.is_company_admin);
  }
  private projection(doc: Obj, user: string, actor: Obj): Obj {
    const c = this.chat(doc.conversation_id, user);
    if (!c) forbidden();
    return {id:c.id,title:c.title,visibility:c.visibility,dissolved_at:c.dissolved_at,is_member:c.is_member,can_write:!this.personalRead && c.can_write};
  }

  private source(id: string, user: string) {
    return this.row(
      "SELECT m.*,c.external_source FROM messages m JOIN conversations c ON c.id=m.conversation_id JOIN conversation_participants p ON p.conversation_id=c.id AND p.user_id=? WHERE m.id=? AND m.sender_type='user'",
      user,
      id,
    );
  }
  execute(actor: TaskGraphActor, action: string, args: Obj): Obj {
    if (
      !fields[action] ||
      !args ||
      Array.isArray(args) ||
      Object.keys(args).some((k) => !fields[action].includes(k))
    )
      fail("invalid_arguments", "Unknown action or argument fields");
    if (Buffer.byteLength(JSON.stringify(args)) > 2 * 1024 * 1024)
      fail("invalid_arguments", "Request exceeds 2 MiB");
    const write = ["create", "apply", "delete"].includes(action);
    if (write && this.personalRead) forbidden();
    if (!["user", "agent"].includes(actor.kind)) forbidden();
    const notices: Obj[] = [];
    let result: Obj;
    this.db.exec(write ? "BEGIN IMMEDIATE" : "BEGIN");
    try {
      result = this.executeTransaction(actor, action, args, write, notices);
      this.db.exec("COMMIT");
    } catch (e) {
      this.db.exec("ROLLBACK");
      throw e;
    }
    // Delivery is after COMMIT: a disconnected node cannot turn a saved mutation into failure.
    try { this.messaging.publishMessages(notices); } catch { /* Durable events and relay are replayed. */ }
    return result!;
  }
  /** Read as the authenticated owner, filtering sources before projection and pagination.
   *
   * Args:
   *   actor: Gateway-authenticated current PA identity.
   *   ownerUserId: Owner resolved from the current personal binding.
   *   action: Read-only task action.
   *   args: Validated task query arguments.
   *   sourceAllowed: Current personal source policy, also applied to linked provenance.
   */
  readPersonal(actor:TaskGraphActor,ownerUserId:string,action:string,args:Obj,sourceAllowed:(id:string)=>boolean):Obj {
    if(!['get','list','activity'].includes(action)) forbidden();
    return new TaskGraphService(this.db,this.messaging,{ownerUserId,sourceAllowed}).execute(actor,action,args);
  }
  /** Apply a reviewed PA result in its caller's transaction with owner access and PA attribution.
   *
   * Args:
   *   actor: Server-resolved personal Agent identity.
   *   ownerUserId: Binding owner whose current write access is checked.
   *   args: Frozen update_task operations; reassignment and claiming are unsupported.
   *   notices: Messages to publish only after the caller commits.
   */
  executeDelegated(actor:TaskGraphActor,ownerUserId:string,args:Obj,notices:Obj[]):Obj {
    const binding=this.row("SELECT b.* FROM personal_agent_bindings b JOIN node_binding_state n ON n.node_id=b.node_id WHERE b.agent_id=? AND b.node_id=? AND b.owner_user_id=? AND b.status='active' AND n.node_epoch=b.node_epoch AND n.owner_id=b.owner_id",actor.id,actor.node_id??null,ownerUserId);
    if(!binding||actor.kind!=='agent'||Object.keys(args).some(k=>!fields.apply.includes(k))||!Array.isArray(args.operations)
      ||args.operations.some((op:Obj)=>op.op!=='update_task'||!op.patch||Object.keys(op.patch).some(k=>!['result','status'].includes(k))))forbidden();
    return this.executeTransaction(actor,'apply',args,true,notices,ownerUserId);
  }
  private executeTransaction(
    actor: TaskGraphActor,
    action: string,
    args: Obj,
    write: boolean,
    notices: Obj[],
    delegatedOwner?: string,
  ): Obj {
    const p =
      actor.kind === "user"
        ? this.row(
            "SELECT * FROM users WHERE id=? AND (personal_space_enabled=1 OR membership_status='active') AND username NOT LIKE 'agent:%'",
            actor.id,
          )
        : this.row(
            "SELECT u.id,p.owner_id,p.display_name,p.space_id,owner.membership_status,owner.personal_space_enabled FROM agent_profiles p JOIN users u ON u.username='agent:'||p.agent_id JOIN nodes n ON n.node_id=p.node_id AND n.owner_id=p.owner_id JOIN users owner ON owner.owner_id=p.owner_id AND owner.username NOT LIKE 'agent:%' WHERE p.agent_id=? AND p.node_id=? AND p.is_stale=0 AND (owner.personal_space_enabled=1 OR owner.membership_status='active') AND n.status='online' AND COALESCE(json_extract(p.features_json,'$.task_graph'),1)=1 AND EXISTS(SELECT 1 FROM json_each(p.tool_allowlist_json) WHERE value='task_graph')",
            actor.id,
            actor.node_id ?? null,
          );
    if (!p || (actor.kind === "agent" && !canAccessSpace(p, p.space_id))) forbidden();
    const user = this.personalRead?.ownerUserId ?? delegatedOwner ?? p.id,
      actorName = `${p.display_name} (${actor.id})`;
    const identity = {type:actor.kind,id:actor.id,...(delegatedOwner?{authorized_by:delegatedOwner}:{})};
    if (action === "list") return this.list(user, identity, args);
    if (action === "activity") {
      const chat = text(args.conversation_id, "conversation_id");
      if (!this.chat(chat, user)) forbidden();
      const items: Obj[] = [];
      for (const row of this.rows(
        "SELECT a.node_id,a.updated_at,g.document_json FROM task_node_chat_activity a JOIN task_graphs g ON g.graph_id=a.graph_id WHERE a.conversation_id=? ORDER BY a.updated_at DESC",
        chat,
      )) {
        const d = JSON.parse(row.document_json),
          n = d.nodes.find((n: Obj) => n.id === row.node_id);
        if (n && this.chat(d.conversation_id, user))
          items.push({
            graph_id: d.graph_id,
            node_id: n.id,
            scope_id: n.container_id,
            title: n.title,
            root_title: d.nodes.find((x: Obj) => x.id === d.root_node_id).title,
            status: n.status,
            updated_at: row.updated_at,
          });
      }
      return { items };
    }
    let key = "",
      hash = "";
    const actorKey = `${actor.kind}:${actor.id}`;
    if (write) {
      key = text(args.request_key, "request_key");
      hash = createHash("sha256")
        .update(
          canonicalJson({
            action,
            args: Object.fromEntries(Object.entries(args).filter(([k]) => action === "create" || k !== "conversation_id")),
          }),
        )
        .digest("hex");
      const cutoff = new Date(Date.now() - 7 * 86400000).toISOString();
      this.db
        .prepare(
          "DELETE FROM task_graph_mutation_receipts WHERE rowid IN (SELECT rowid FROM task_graph_mutation_receipts WHERE created_at<? AND json_type(result_json,'$.deleted_ids')='array' ORDER BY created_at LIMIT 100)",
        )
        .run(cutoff);
      const receipt = this.row(
        "SELECT * FROM task_graph_mutation_receipts WHERE actor_key=? AND request_key=? AND NOT(created_at<? AND json_type(result_json,'$.deleted_ids') IS 'array')",
        actorKey,
        key,
        cutoff,
      );
      if (receipt) {
        this.writable(receipt.conversation_id, user);
        if (receipt.operation_hash !== hash)
          fail("request_key_reused", "Use the original parameters with this request_key");
        return JSON.parse(receipt.result_json);
      }
    }
    let doc: Obj;
    if (action !== "create") {
      const row = this.row(
        "SELECT * FROM task_graphs WHERE graph_id=?",
        text(args.graph_id, "graph_id"),
      );
      if (!row) forbidden();
      doc = { ...JSON.parse(row.document_json), owner_id: row.owner_id };
      if (doc.schema_version !== 2) invalid("Unsupported task graph schema_version");
      if (!this.chat(doc.conversation_id, user)) forbidden();
      if (action === "get") return this.get(doc, args, user, identity);
      this.writable(doc.conversation_id, user);
    } else doc = {};
    const chat = args.conversation_id ?? null;
    if (chat !== null) this.writable(text(chat, "conversation_id"), user);
    if (action === "create" && !chat) fail("conversation_required", "Choose a writable conversation for the task");
    const before = action === "create" ? null : structuredClone(doc);
    const source = actor.source_message_id ? this.source(actor.source_message_id, user) : null;
    if (actor.source_message_id && !source) forbidden();
    const provenance = {
      agent_id: actor.kind === "agent" ? actor.id : null,
      source_message_id: actor.source_message_id ?? null,
      initiator_id: source ? source.sender_source_id || source.sender_user_id : null,
      channel: source?.external_source ?? null,
      source_chat_id: source?.conversation_id ?? null,
    };
    const now = new Date().toISOString();
    let changed: string[] = [],
      result: Obj;
    if (action === "create") {
      const title = text(args.title, "title", 240),
        description = text(args.description ?? "", "description", 32000, true);
      if (!["dag", "explore"].includes(args.mode))
        fail("invalid_arguments", "Root mode must be dag or explore");
      let graphId: string;
      do {
        graphId = `tg_${randomUUID().replaceAll("-", "").slice(0, 8)}`;
      } while (this.row("SELECT 1 FROM task_graphs WHERE graph_id=?", graphId));
      doc = {
        schema_version: 2,
        graph_id: graphId,
        owner_id: p.owner_id,
        conversation_id: chat,
        root_node_id: "n1",
        revision: 1,
        nodes: [
          newNode("n1", null, title, actorName, now, {
            description,
            status:args.status ?? "todo",result:args.result ?? "",
            mode: args.mode,
            created_by: identity,
            updated_by_actor: identity,
            assignee: args.assignee == null ? null : actorRef(args.assignee),
            last_chat_id: chat,
          }),
        ],
        dependencies: [],
        created_at: now,
        updated_at: now,
        updated_by: actorName,
      };
      validateDocument(doc);
      changed = ["n1"];
      result = summary(doc);
    } else {
      if (!Number.isInteger(args.base_revision) || args.base_revision < 1)
        fail("invalid_arguments", "base_revision must be a positive integer");
      if (args.base_revision !== doc.revision)
        throw new TaskGraphError(
          "version_conflict",
          "Read the current graph before adjusting this change",
          { current_revision: doc.revision },
        );
      if (action === "delete") {
        const id = args.node_id ?? doc.root_node_id,
          node = doc.nodes.find((n: Obj) => n.id === id);
        if (!node) fail("invalid_arguments", "node_id is not in this graph");
        if (!this.canDelete(node, identity, user)) forbidden();
        doc.next_node_number ??=
          Math.max(
            doc.nodes.length,
            ...doc.nodes.filter((n: Obj) => /^n\d+$/.test(n.id)).map((n: Obj) => +n.id.slice(1)),
          ) + 1;
        const removed = new Set([id]);
        let size;
        do {
          size = removed.size;
          for (const n of doc.nodes) if (removed.has(n.container_id)) removed.add(n.id);
        } while (removed.size !== size);
        doc.nodes = doc.nodes.filter((n: Obj) => !removed.has(n.id));
        doc.dependencies = doc.dependencies.filter(
          (e: Obj) => !removed.has(e.from) && !removed.has(e.to),
        );
        for (const n of doc.nodes) {
          if (removed.has(n.derived_from_id)) n.derived_from_id = null;
          if (removed.has(n.selected_candidate_id)) {
            n.selected_candidate_id = null;
            n.selection_reason = "";
          }
        }
        Object.assign(doc, {
          revision: doc.revision + 1,
          updated_at: now,
          updated_by: actorName,
        });
        if (doc.nodes.length) validateDocument(doc);
        result = {
          graph_id: doc.graph_id,
          revision: doc.revision,
          deleted_ids: [...removed].sort(),
          deleted: !doc.nodes.length,
          updated_by: actorName,
        };
        if (!doc.nodes.length)
          this.db.prepare("DELETE FROM task_graphs WHERE graph_id=?").run(doc.graph_id);
        else {
          this.save(doc);
          for (const removedId of removed)
            this.db
              .prepare("DELETE FROM task_node_chat_activity WHERE graph_id=? AND node_id=?")
              .run(doc.graph_id, removedId);
        }
        this.receipt(actorKey, key, hash, doc, result);
        return result;
      }
      const applied = applyOperations(
        doc,
        args.operations,
        actorName,
        now,
        text(args.change_note, "change_note", 8000, true),
        identity,
      );
      doc = applied.document;
      changed = applied.changed;
      for (const n of doc.nodes) if (changed.includes(n.id)) n.last_chat_id = chat;
      result = {
        ...summary(doc),
        client_refs: applied.refs,
        changed_ids: changed,
      };
    }
    if (Buffer.byteLength(JSON.stringify(doc)) > 2 * 1024 * 1024)
      invalid("Graph document exceeds 2 MiB");
    for (const n of doc.nodes) if (changed.includes(n.id)) n.provenance = provenance;
    for (const n of doc.nodes) {
      const old = before?.nodes.find((x:Obj) => x.id === n.id);
      if (!old || !sameActor(old.assignee,n.assignee)) this.assignee(n.assignee, doc.conversation_id);
    }
    this.save(doc);
    for (const notice of taskNotices(doc, before, actorName, ref => this.identity(ref), uid => !!this.row("SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?", doc.conversation_id, uid) && !!qualifiedUser(this.db, uid)))
      notices.push(this.messaging.persistTaskNotice(doc.conversation_id, p.id, notice.content, {...notice.metadata,...(delegatedOwner?{authorized_by:delegatedOwner}:{})}));
    this.receipt(actorKey, key, hash, doc, result);
    if (chat)
      for (const id of changed)
        this.db
          .prepare(
            "INSERT INTO task_node_chat_activity VALUES(?,?,?,?) ON CONFLICT(graph_id,node_id,conversation_id) DO UPDATE SET updated_at=excluded.updated_at",
          )
          .run(doc.graph_id, id, chat, now);
    return result;
  }
  private save(doc: Obj) {
    const { owner_id, ...body } = doc;
    const space = this.row("SELECT space_id FROM conversations WHERE id=?", doc.conversation_id)!.space_id;
    this.db
      .prepare(
        "INSERT INTO task_graphs(graph_id,owner_id,root_title,revision,document_json,created_at,updated_at,updated_by,conversation_id,space_id) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(graph_id) DO UPDATE SET root_title=excluded.root_title,revision=excluded.revision,document_json=excluded.document_json,updated_at=excluded.updated_at,updated_by=excluded.updated_by",
      )
      .run(
        doc.graph_id,
        owner_id,
        summary(doc).title,
        doc.revision,
        JSON.stringify(body),
        doc.created_at,
        doc.updated_at,
        doc.updated_by,
        doc.conversation_id,
        space,
      );
  }
  private receipt(actor: string, key: string, hash: string, doc: Obj, result: Obj) {
    this.db
      .prepare("INSERT INTO task_graph_mutation_receipts(actor_key,request_key,operation_hash,graph_id,result_json,created_at,conversation_id,space_id) VALUES(?,?,?,?,?,?,?,?)")
      .run(actor, key, hash, doc.graph_id, JSON.stringify(result), doc.updated_at, doc.conversation_id, this.row("SELECT space_id FROM conversations WHERE id=?", doc.conversation_id)!.space_id);
  }
  private list(user: string, actor: Obj, args: Obj) {
    const account = this.row("SELECT * FROM users WHERE id=?", user)!;
    const spaces = (actor.type === "agent" && !this.personalRead
      ? [this.row("SELECT space_id FROM agent_profiles WHERE agent_id=?", actor.id)!.space_id]
      : ["company:default", `personal:${account.owner_id}`]).filter(space=>canActorAccess(this.db,user,space));
    if (!spaces.length) return {items:[],total:0,next_cursor:null};
    const query = text(args.query ?? "", "query", 240, true).trim(), limit = args.limit ?? 20;
    if (!Number.isInteger(limit) || limit < 1 || limit > 50) fail("invalid_arguments", "limit must be an integer from 1 to 50");
    const filtered = args.assignee_type !== undefined || args.assignee_id !== undefined;
    const assignee = filtered ? actorRef({type:args.assignee_type,id:args.assignee_id}) : null;
    const statuses = args.statuses === undefined ? null : [...new Set(text(args.statuses,"statuses",128).split(",").map(value=>value.trim()))].sort();
    if (statuses?.some(status=>!["todo","doing","in_review","done","paused","closed"].includes(status))) fail("invalid_arguments","statuses must contain task status values separated by commas");
    const identity = {user,query,assignee,...(statuses ? {statuses} : {})};
    let after: Obj | undefined;
    if (args.cursor != null) {
      try {
        const saved = JSON.parse(Buffer.from(text(args.cursor,"cursor",2048),"base64url").toString());
        if (canonicalJson(saved.identity) !== canonicalJson(identity)) throw Error();
        after = saved.after;
        text(after!.updated_at,"cursor time"); text(after!.graph_id,"cursor graph"); text(after!.node_id,"cursor node");
      } catch { fail("invalid_arguments","Invalid cursor for this query"); }
    }
    // ACL is applied before json_each: summaries and counts never include inaccessible trees.
    const rows = this.rows(`SELECT g.document_json,n.value AS node_json FROM task_graphs g
      JOIN conversations c ON c.id=g.conversation_id JOIN json_each(g.document_json,'$.nodes') n
      WHERE c.space_id IN (${spaces.map(()=>"?").join(",")}) AND (EXISTS(SELECT 1 FROM conversation_participants p WHERE p.conversation_id=c.id AND p.user_id=?) OR (c.type='group' AND c.visibility='public'))
      AND ${filtered ? "json_extract(n.value,'$.assignee.type')=? AND json_extract(n.value,'$.assignee.id')=?" : "json_extract(n.value,'$.id')=json_extract(g.document_json,'$.root_node_id')"}
      AND ${statuses ? "json_extract(n.value,'$.status') IN ("+statuses.map(()=>"?").join(",")+")" : "1=1"}
      AND INSTR(LOWER(json_extract(n.value,'$.title')),LOWER(?))>0`, ...spaces, user, ...(assignee ? [assignee.type,assignee.id] : []), ...(statuses ?? []), query);
    const items = rows.filter(r=>!this.personalRead || !!this.chat(JSON.parse(r.document_json).conversation_id,user)).map((r): Obj => {
      const d = JSON.parse(r.document_json), n = JSON.parse(r.node_json);
      const path: Obj[] = [];
      for (let p = d.nodes.find((x:Obj)=>x.id===n.container_id); p; p=d.nodes.find((x:Obj)=>x.id===p.container_id)) path.unshift({id:p.id,title:p.title});
      const conversation = this.projection(d,user,actor);
      return {...summary(d), node_id:n.id,scope_id:n.container_id,title:n.title,mode:n.mode,status:n.status,
        updated_at:n.updated_at,created_by:this.identity(n.created_by),assignee:this.identity(n.assignee),
        direct_counts:directCounts(d,n.id),conversation,parent_path:path,
        can_edit:conversation.can_write,can_delete:conversation.can_write && this.canDelete(n,actor,user),
        can_claim:conversation.can_write && (!n.assignee || sameActor(n.assignee,actor)),
        relative_url:`/tasks/${d.graph_id}?scope=${n.container_id ?? d.root_node_id}&node=${n.id}`};
    }).sort((a,b)=> b.updated_at.localeCompare(a.updated_at) || b.graph_id.localeCompare(a.graph_id) || b.node_id.localeCompare(a.node_id));
    const eligible = after ? items.filter(n => n.updated_at < after!.updated_at || (n.updated_at===after!.updated_at && (n.graph_id<after!.graph_id || (n.graph_id===after!.graph_id && n.node_id<after!.node_id)))) : items;
    const page = eligible.slice(0,limit), last = page.at(-1);
    return {items:page,total:items.length,next_cursor:eligible.length>limit ? Buffer.from(JSON.stringify({identity,after:{updated_at:last!.updated_at,graph_id:last!.graph_id,node_id:last!.node_id}})).toString('base64url') : null};
  }
  private get(doc: Obj, args: Obj, user: string, actor: Obj) {
    const { owner_id: _owner, ...projected } = doc;
    projected.conversation = this.projection(doc,user,actor);
    projected.nodes = doc.nodes.map((n: Obj) => {
      const chat = this.chat(n.last_chat_id, user),
        provenance = n.provenance ?? {};
      return {
        ...n,
        created_by:this.identity(n.created_by),assignee:this.identity(n.assignee),
        updated_by_actor:this.identity(n.updated_by_actor ?? n.created_by),
        direct_counts:directCounts(doc,n.id),
        can_edit:projected.conversation.can_write,
        can_delete:projected.conversation.can_write && this.canDelete(n,actor,user),
        can_claim:projected.conversation.can_write && (!n.assignee || sameActor(n.assignee,actor)),
        provenance: this.chat(provenance.source_chat_id, user)
          ? provenance
          : {
              ...provenance,
              source_message_id: null,
              source_chat_id: null,
              initiator_id: null,
            },
        links: n.links.filter((link: string) => {
          const path = decodeURIComponent(new URL(link, "http://im.local").pathname),
            match = path.match(/^\/im\/v1\/conversations\/([^/]+)\/(images|attachments)\//);
          return !match || !!this.chat(match[1], user);
        }),
        last_chat_id: chat?.id ?? null,
        last_chat_title: chat?.title ?? null,
      };
    });
    if (!["scope", "all"].includes(args.view ?? "scope"))
      fail("invalid_arguments", "view must be scope or all");
    const nodes = new Map<string, Obj>(projected.nodes.map((n: Obj) => [n.id, n])),
      scope = nodes.get(text(args.scope_id ?? doc.root_node_id, "scope_id"));
    if (!scope) fail("invalid_arguments", "scope_id is not a node in this graph");
    if (args.view === "all") return { ...projected, relative_url: `/tasks/${doc.graph_id}` };
    const children = [...nodes.values()]
      .filter((n) => n.container_id === scope.id)
      .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
    const breadcrumbs = [];
    for (let n: Obj | undefined = scope; n; n = nodes.get(n.container_id)) breadcrumbs.unshift(n);
    return {
      ...summary(doc),
      schema_version: 2,
      conversation: projected.conversation,
      root: nodes.get(doc.root_node_id),
      scope,
      breadcrumbs,
      children: children.map((n) => ({
        ...n,
        child_count: [...nodes.values()].filter((c) => c.container_id === n.id).length,
      })),
      dependencies: doc.dependencies.filter((e: Obj) => children.some((n) => n.id === e.from)),
      derivations: children
        .filter((n) => n.derived_from_id)
        .map((n) => ({ from: n.derived_from_id, to: n.id })),
    };
  }
}
export function registerTaskGraphRoutes(app: FastifyInstance, ctx: ImContext) {
  const service = new TaskGraphService(ctx.db,ctx.messaging);
  for (const [method,path,action] of [
    ["GET","/im/v1/task-graphs","list"], ["GET","/im/v1/task-graphs/:graph_id","get"],
    ["GET","/im/v1/conversations/:conversation_id/task-activity","activity"],
    ["POST","/im/v1/task-graphs","create"], ["POST","/im/v1/task-graphs/:graph_id/apply","apply"],
    ["DELETE","/im/v1/task-graphs/:graph_id","delete"],
  ] as const)
    app.route({method,url:path,handler:async (req, reply) => {
      const principal = await ctx.identity.authenticateRequest(req);
      try {
        const args: Obj = { ...(req.query as Obj), ...(req.body as Obj), ...(req.params as Obj) };
        if (args.limit !== undefined) args.limit = Number(args.limit);
        return service.execute({ kind: "user", id: principal.id }, action!, args);
      } catch (e) {
        if (e instanceof TaskGraphError)
          return reply
            .code(e.code === "not_found_or_forbidden" ? 404 : e.code === "version_conflict" ? 409 : 400)
            .send({ detail: e.asDict() });
        if ((e as Obj)?.code?.startsWith?.("ERR_SQLITE"))
          return reply.code(503).send({
            detail: {
              code: "source_unavailable",
              message: "Task storage is temporarily unavailable",
            },
          });
        throw e;
      }
    }});
}
