import { createHash, randomUUID } from "node:crypto";
import type { FastifyInstance, FastifyRequest } from "fastify";
import {
  all,
  one,
  transaction,
  fail,
  now,
  body,
  params,
  query,
  type ImContext,
  type Row,
} from "./context.js";
import { bearer } from "./identity.js";
import { canonicalJson } from "./task-graphs.js";
import { registerTaskGraphRoutes } from "./task-graphs.js";
import { registerChannelRoutes } from "./channels.js";
async function gatewayRequest(
  ctx: ImContext,
  node: string,
  action: string,
  payload: Row,
): Promise<Row | null> {
  try {
    return await ctx.gateway.request(node, action, payload);
  } catch (e) {
    if ([503, 504].includes((e as Row).statusCode)) return null;
    throw e;
  }
}
const optionalText = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim() : null);
const stringList = (v: unknown) =>
  Array.isArray(v) ? v.filter((x) => typeof x === "string" && x.trim()).map((x) => x.trim()) : [];
const asciiJson = (v: unknown) =>
  canonicalJson(v).replace(
    /[\u007f-\uffff]/g,
    (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`,
  );
const selection = (mode: string | null, skills: string[]) =>
  mode ?? (skills.length ? "explicit_allowlist" : "default_discovery");
function heartbeat(v: unknown): string | null {
  if (typeof v !== "string" || !v.trim()) return null;
  try {
    return asciiJson(JSON.parse(v));
  } catch {
    return v.trim();
  }
}
const gatewayKeys = [
  "agent_id",
  "display_name",
  "skills",
  "skills_selection_mode",
  "tool_allowlist",
  "group_reply_policy",
  "default_model",
  "model_fallbacks",
  "reasoning_effort",
  "work_mode",
  "workspace_root",
  "features",
  "custom_prompt",
  "heartbeat_json",
];
export function gatewayCandidate(c: Row): Row {
  const p: Row = {
    agent_id: optionalText(c.agent_id) ?? "",
    display_name: optionalText(c.display_name) ?? c.agent_id,
    tool_allowlist: stringList(c.tool_allowlist),
    group_reply_policy: optionalText(c.group_reply_policy) ?? "manual",
    default_model: optionalText(c.default_model),
    model_fallbacks: stringList(c.model_fallbacks),
    reasoning_effort: optionalText(c.reasoning_effort),
    work_mode: c.work_mode || "single_thread",
    workspace_root: optionalText(c.workspace_root),
    features: Object.fromEntries(
      Object.entries(c.features ?? {}).filter(([, v]) => typeof v === "boolean"),
    ),
    custom_prompt: optionalText(c.custom_prompt),
    heartbeat_json: heartbeat(c.heartbeat_json),
  };
  if ("skills" in c) p.skills = Array.isArray(c.skills) ? stringList(c.skills) : null;
  if ("skills" in c || "skills_selection_mode" in c)
    p.skills_selection_mode = Array.isArray(p.skills)
      ? selection(c.skills_selection_mode, p.skills)
      : (c.skills_selection_mode ?? null);
  if ("confirm_existing_workspace" in c)
    p.confirm_existing_workspace = c.confirm_existing_workspace === true;
  return p;
}
export function candidateFingerprint(c: Row): string {
  const p = gatewayCandidate(c);
  if (p.heartbeat_json === "{}") p.heartbeat_json = null;
  return createHash("sha256")
    .update(asciiJson(Object.fromEntries(gatewayKeys.map((k) => [k, p[k] ?? null]))))
    .digest("hex");
}
export function profileResponse(p: Row, mirror = false): Row {
  return {
    ...Object.fromEntries(
      [
        "agent_id",
        "owner_id",
        "node_id",
        "display_name",
        "description",
        "group_reply_policy",
        "default_model",
        "reasoning_effort",
        "work_mode",
        "workspace_root",
        "profile_version",
        "updated_at",
        "custom_prompt",
        "heartbeat_json",
      ].map((k) => [k, p[k] ?? null]),
    ),
    skills: JSON.parse(p.skills_json),
    skills_selection_mode: mirror
      ? p.skills_selection_mode
      : selection(p.skills_selection_mode, JSON.parse(p.skills_json)),
    tool_allowlist: JSON.parse(p.tool_allowlist_json),
    model_fallbacks: JSON.parse(p.model_fallbacks_json),
    features: JSON.parse(p.features_json),
    workspace_is_default: p.workspace_is_default == null ? null : !!p.workspace_is_default,
  };
}
function fromProfile(p: Row) {
  const c = profileResponse(p, true);
  for (const k of ["node_id", "workspace_is_default", "profile_version", "updated_at"]) delete c[k];
  c.heartbeat_json = heartbeat(c.heartbeat_json);
  return c;
}
function pending(): never {
  fail(503, {
    code: "config_apply_pending",
    message: "Configuration application is still being confirmed.",
  });
}
const safeRejections = new Set([
  "agent_id_already_exists",
  "invalid_agent_config",
  "operation_conflict",
  "operation_id_reused",
  "workspace_already_assigned",
  "workspace_confirmation_required",
  "workspace_initialization_failed",
  "workspace_parent_missing",
  "workspace_parent_unusable",
  "workspace_target_not_directory",
]);
/** Recover durable Gateway apply receipts before exposing a committed profile. */
export class ConfigOperations {
  private locks = new Map<string, Promise<unknown>>();
  constructor(private ctx: ImContext) {}
  async serialized<T>(id: string, fn: () => Promise<T>): Promise<T> {
    const previous = this.locks.get(id) ?? Promise.resolve();
    const next = previous.catch(() => undefined).then(fn);
    this.locks.set(id, next);
    try {
      return await next;
    } finally {
      if (this.locks.get(id) === next) this.locks.delete(id);
    }
  }
  private active(agent: string, owner: string) {
    return one(
      this.ctx.db,
      "SELECT * FROM agent_config_operations WHERE agent_id=? AND owner_id=? AND status IN ('pending','gateway_applied') ORDER BY rowid DESC LIMIT 1",
      agent,
      owner,
    );
  }
  private insert(
    candidate: Row,
    owner: string,
    node: string,
    kind: string,
    previous: Row | null,
    expectedVersion: number | null,
    root: string | null = null,
    previousHash?: string,
  ): Row {
    const id = randomUUID().replaceAll("-", ""),
      hash = candidateFingerprint(candidate);
    if (
      one(
        this.ctx.db,
        "SELECT 1 FROM agent_config_operations WHERE agent_id=? AND status IN ('pending','gateway_applied')",
        candidate.agent_id,
      )
    )
      pending();
    this.ctx.db
      .prepare(
        "INSERT INTO agent_config_operations(operation_id,root_operation_id,agent_id,owner_id,node_id,operation_kind,status,candidate_json,candidate_fingerprint,previous_candidate_json,expected_previous_fingerprint,expected_profile_version,created_at,updated_at) VALUES(?,?,?,?,?,?,'pending',?,?,?,?,?,?,?)",
      )
      .run(
        id,
        root,
        candidate.agent_id,
        owner,
        node,
        kind,
        JSON.stringify(candidate),
        hash,
        previous ? JSON.stringify(previous) : null,
        previousHash ?? (previous ? candidateFingerprint(previous) : null),
        expectedVersion,
        now(),
        now(),
      );
    return one(this.ctx.db, "SELECT * FROM agent_config_operations WHERE operation_id=?", id)!;
  }
  private async request(op: Row) {
    const c = gatewayCandidate(JSON.parse(op.candidate_json));
    if (op.operation_kind === "create") c.create_operation_id = op.operation_id;
    return gatewayRequest(
      this.ctx,
      op.node_id,
      op.operation_kind === "create" ? "agent.create" : "agent.config.apply",
      {
        operation_id: op.operation_id,
        candidate_fingerprint: op.candidate_fingerprint,
        expected_previous_fingerprint: op.expected_previous_fingerprint,
        agent: c,
      },
    );
  }
  private async resolve(op: Row, initial?: Row | null): Promise<Row> {
    let result = initial;
    if (op.status === "gateway_applied") result = JSON.parse(op.gateway_result_json);
    else if (!result || result.status === "pending") {
      result = await gatewayRequest(this.ctx, op.node_id, "agent.config.operation.status", {
        operation_id: op.operation_id,
      });
      if (result?.status === "pending") result = await this.request(op);
    }
    if (!result || !["applied", "rejected"].includes(result.status)) pending();
    if (
      result.operation_id !== op.operation_id ||
      result.candidate_fingerprint !== op.candidate_fingerprint
    )
      pending();
    if (
      result.status === "applied" &&
      (!result.agent || typeof result.agent !== "object" || Array.isArray(result.agent))
    )
      pending();
    if (result.status === "rejected") {
      if (op.operation_kind === "compensation") pending();
      const code = safeRejections.has(result.error_code)
        ? result.error_code
        : "invalid_agent_config";
      this.ctx.db
        .prepare(
          "UPDATE agent_config_operations SET status='rejected',gateway_result_json=?,error_code=?,error_message=?,updated_at=? WHERE operation_id=?",
        )
        .run(JSON.stringify(result), code, result.message ?? null, now(), op.operation_id);
      fail(
        code.startsWith("workspace_") &&
          !["workspace_already_assigned", "workspace_confirmation_required"].includes(code)
          ? 422
          : 409,
        { code, message: result.message ?? code },
      );
    }
    this.ctx.db
      .prepare(
        "UPDATE agent_config_operations SET status='gateway_applied',gateway_result_json=?,updated_at=? WHERE operation_id=?",
      )
      .run(JSON.stringify(result), now(), op.operation_id);
    return result;
  }
  async recover(agent: string, owner: string) {
    const op = this.active(agent, owner);
    if (!op) return null;
    return this.commit(op, await this.resolve(op));
  }
  async create(candidate: Row, owner: string, node: string) {
    if (one(this.ctx.db, "SELECT 1 FROM agent_profiles WHERE agent_id=?", candidate.agent_id))
      fail(409, "agent_id already exists");
    const op = this.insert(candidate, owner, node, "create", null, null);
    return this.commit(op, await this.resolve(op, await this.request(op)));
  }
  async update(profile: Row, candidate: Row, owner: string) {
    const op = this.insert(
      candidate,
      owner,
      profile.node_id,
      "apply",
      fromProfile(profile),
      profile.profile_version,
    );
    return this.commit(op, await this.resolve(op, await this.request(op)));
  }
  private async commit(op: Row, result: Row): Promise<Row> {
    const db = this.ctx.db;
    if (op.operation_kind === "compensation") {
      transaction(db, () => {
        db.prepare(
          "UPDATE agent_config_operations SET status='committed',updated_at=? WHERE operation_id=?",
        ).run(now(), op.operation_id);
        db.prepare(
          "UPDATE agent_config_operations SET status='rejected',error_code='profile_version_conflict',updated_at=? WHERE operation_id=?",
        ).run(now(), op.root_operation_id);
      });
      fail(409, "profile_version conflict");
    }
    const candidate = JSON.parse(op.candidate_json),
      canonical = result.agent ?? {},
      c = {
        ...candidate,
        ...Object.fromEntries(
          gatewayKeys.filter((k) => k in canonical).map((k) => [k, canonical[k]]),
        ),
        workspace_is_default:
          canonical.workspace_is_default ?? candidate.workspace_is_default ?? null,
      };
    c.description = candidate.description ?? "";
    c.owner_id = op.owner_id;
    c.node_id = op.node_id;
    const existing = one(db, "SELECT * FROM agent_profiles WHERE agent_id=?", op.agent_id);
    if (op.operation_kind === "apply" && existing) {
      c.workspace_root = existing.workspace_root;
      c.workspace_is_default =
        existing.workspace_is_default === null ? null : !!existing.workspace_is_default;
      c.work_mode = existing.work_mode;
    }
    if (op.operation_kind === "create" && !optionalText(c.workspace_root)) pending();
    if (
      op.operation_kind === "apply" &&
      existing?.profile_version !== op.expected_profile_version
    ) {
      if (
        existing &&
        existing.profile_version === op.expected_profile_version + 1 &&
        candidateFingerprint(fromProfile(existing)) === candidateFingerprint(c) &&
        existing.description === c.description
      ) {
        db.prepare(
          "UPDATE agent_config_operations SET status='committed',updated_at=? WHERE operation_id=?",
        ).run(now(), op.operation_id);
        return profileResponse(existing);
      }
      if (!existing) pending();
      const compensation = transaction(db, () => {
        db.prepare(
          "UPDATE agent_config_operations SET status='compensating',error_code='profile_version_conflict',updated_at=? WHERE operation_id=?",
        ).run(now(), op.operation_id);
        return this.insert(
          fromProfile(existing),
          op.owner_id,
          op.node_id,
          "compensation",
          null,
          null,
          op.operation_id,
          op.candidate_fingerprint,
        );
      });
      const restored = await this.resolve(compensation, await this.request(compensation));
      return this.commit(compensation, restored);
    }
    if (op.operation_kind === "create" && existing) {
      const matches =
        existing.owner_id === op.owner_id &&
        existing.node_id === op.node_id &&
        existing.workspace_root === c.workspace_root &&
        existing.display_name === c.display_name;
      const seed =
        existing.registration_seed && existing.pending_create_operation_id === op.operation_id;
      if (
        !matches ||
        (existing.registration_seed && !seed) ||
        (seed && existing.workspace_is_default !== Number(c.workspace_is_default))
      )
        pending();
      if (!seed) {
        db.prepare(
          "UPDATE agent_config_operations SET status='committed',updated_at=? WHERE operation_id=?",
        ).run(now(), op.operation_id);
        return profileResponse(existing);
      }
    }
    transaction(db, () => {
      const vals = [
        c.display_name || op.agent_id,
        c.description,
        JSON.stringify(c.skills ?? []),
        c.skills_selection_mode ?? null,
        JSON.stringify(c.tool_allowlist ?? []),
        c.group_reply_policy ?? "manual",
        c.default_model ?? null,
        JSON.stringify(c.model_fallbacks ?? []),
        c.reasoning_effort ?? null,
        c.work_mode ?? "single_thread",
        c.workspace_root ?? null,
        c.workspace_is_default == null ? null : +c.workspace_is_default,
        JSON.stringify(c.features ?? {}),
        c.custom_prompt ?? null,
        c.heartbeat_json ?? null,
      ];
      if (existing) {
        const changed = db
          .prepare(
            "UPDATE agent_profiles SET display_name=?,description=?,skills_json=?,skills_selection_mode=?,tool_allowlist_json=?,group_reply_policy=?,default_model=?,model_fallbacks_json=?,reasoning_effort=?,work_mode=?,workspace_root=?,workspace_is_default=?,features_json=?,custom_prompt=?,heartbeat_json=?,profile_version=profile_version+1,registration_seed=0,pending_create_operation_id=NULL,updated_at=? WHERE agent_id=? AND profile_version=?",
          )
          .run(...vals, now(), op.agent_id, existing.profile_version);
        if (!changed.changes) fail(409, "profile_version conflict");
      } else
        db.prepare(
          "INSERT INTO agent_profiles(display_name,description,skills_json,skills_selection_mode,tool_allowlist_json,group_reply_policy,default_model,model_fallbacks_json,reasoning_effort,work_mode,workspace_root,workspace_is_default,features_json,custom_prompt,heartbeat_json,agent_id,owner_id,node_id,profile_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
        ).run(...vals, op.agent_id, op.owner_id, op.node_id, now(), now());
      db.prepare(
        "INSERT OR IGNORE INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?,?)",
      ).run(randomUUID(), `agent:${op.agent_id}`, c.display_name || op.agent_id, "", now());
      db.prepare("UPDATE users SET display_name=? WHERE username=?").run(
        c.display_name || op.agent_id,
        `agent:${op.agent_id}`,
      );
      db.prepare(
        "UPDATE agent_config_operations SET status='committed',updated_at=? WHERE operation_id=?",
      ).run(now(), op.operation_id);
    });
    return profileResponse(one(db, "SELECT * FROM agent_profiles WHERE agent_id=?", op.agent_id)!);
  }
}
function requireProfile(ctx: ImContext, agent: string, owner: string): Row {
  const p = one(
    ctx.db,
    "SELECT * FROM agent_profiles WHERE agent_id=? AND owner_id=? AND is_stale=0",
    agent,
    owner,
  );
  if (!p) fail(404, "agent_id not found");
  return p;
}
function requireNode(ctx: ImContext, node: string, owner: string) {
  const n = one(
    ctx.db,
    "SELECT * FROM nodes WHERE node_id=? AND (owner_id=? OR COALESCE(owner_id,'')='')",
    node,
    owner,
  );
  if (!n) fail(404, "node_id not found");
  return n;
}
function nodeResponse(n: Row) {
  return {
    ...n,
    owner_id: n.owner_id ?? "",
    relay_enabled: !!n.relay_enabled,
    reporting_enabled: !!n.reporting_enabled,
  };
}
function validateCandidate(input: Row, create = false) {
  for (const key of create
    ? ["agent_id", "display_name", "group_reply_policy"]
    : ["display_name", "group_reply_policy"])
    if (!optionalText(input[key])) fail(422, `${key} is required`);
  for (const key of ["skills", "tool_allowlist", "model_fallbacks"])
    if (
      key in input &&
      (!Array.isArray(input[key]) || input[key].some((s: unknown) => typeof s !== "string"))
    )
      fail(422, `${key} must be a string list`);
  if (input.work_mode != null && !["single_thread", "global"].includes(input.work_mode))
    fail(422, "invalid work_mode");
  if (
    input.skills_selection_mode != null &&
    !["default_discovery", "explicit_allowlist"].includes(input.skills_selection_mode)
  )
    fail(422, "invalid skills_selection_mode");
  if (!create && (!Number.isInteger(input.profile_version) || input.profile_version < 1))
    fail(422, "invalid profile_version");
}
function allowlistOptions(value: unknown): Row[] {
  return (Array.isArray(value) ? value : []).flatMap((item) => {
    const entry = typeof item === "string" ? { name: item } : item;
    if (!entry || !optionalText(entry.name)) return [];
    return [
      {
        name: entry.name.trim(),
        description: typeof entry.description === "string" ? entry.description.trim() : "",
        default_on: !!entry.default_on,
        location: optionalText(entry.location),
        source_group: ["workspace", "global", "compatibility"].includes(entry.source_group)
          ? entry.source_group
          : null,
      },
    ];
  });
}
function modelOptions(value: unknown): Row[] {
  return (Array.isArray(value) ? value : []).flatMap((item) => {
    const entry = typeof item === "string" ? { name: item } : item;
    if (!entry || !optionalText(entry.name)) return [];
    const r = entry.reasoning;
    let reasoning: Row | null = null;
    if (r?.kind === "fixed") reasoning = { kind: "fixed" };
    else if (r?.kind === "selectable") {
      const levels = [...new Set(stringList(r.levels))];
      if (levels.length && levels.includes(r.default))
        reasoning = { kind: "selectable", levels, default: r.default };
    }
    return [
      {
        name: entry.name.trim(),
        provider: typeof entry.provider === "string" ? entry.provider : "",
        reasoning,
      },
    ];
  });
}
function featureOptions(value: unknown): Row[] {
  return (Array.isArray(value) ? value : [])
    .filter((x) => x && typeof x.key === "string" && x.key)
    .map((x) => ({
      key: x.key,
      label_i18n: typeof x.label_i18n === "string" ? x.label_i18n : "",
      help_i18n: typeof x.help_i18n === "string" ? x.help_i18n : "",
      default_on: !!x.default_on,
      available: x.available !== false,
      requires_tool: typeof x.requires_tool === "string" ? x.requires_tool : null,
    }));
}
function previewInput(b: Row): Row {
  return {
    features: b.features ?? {},
    custom_prompt: b.custom_prompt ?? null,
    tool_ids: b.tool_ids ?? [],
    scenario: b.scenario ?? "direct",
    skill_ids: b.skill_ids ?? [],
  };
}
function previewResponse(r: Row): Row {
  return {
    prompt: typeof r.prompt === "string" ? r.prompt : "",
    section_count: Number.isInteger(r.section_count) ? r.section_count : 0,
  };
}
function requiredWorkspace(p: Row) {
  if (!p.workspace_root) fail(409, "workspace_root is pending gateway registration");
  return p.workspace_root;
}
export function registerControlRoutes(app: FastifyInstance, ctx: ImContext) {
  const ops = new ConfigOperations(ctx);
  const user = (req: FastifyRequest) => ctx.identity.authenticateRequest(req);
  const rpc = async (node: string, action: string, payload: Row) => {
    const response = await gatewayRequest(ctx, node, action, payload);
    if (!response) fail(503, "target_node_id is not connected");
    return response;
  };
  app.get("/im/v1/nodes", async (req) =>
    all(
      ctx.db,
      "SELECT * FROM nodes WHERE owner_id=? OR COALESCE(owner_id,'')='' ORDER BY node_id",
      (await user(req)).owner_id,
    ).map(nodeResponse),
  );
  app.patch("/im/v1/nodes/:node_id/config", async (req) => {
    const u = await user(req),
      p = params(req),
      b = body(req);
    const n = requireNode(ctx, p.node_id, u.owner_id);
    ctx.db
      .prepare("UPDATE nodes SET alias=?,relay_enabled=?,reporting_enabled=? WHERE node_id=?")
      .run(
        b.alias ?? n.alias,
        b.relay_enabled == null ? n.relay_enabled : +b.relay_enabled,
        b.reporting_enabled == null ? n.reporting_enabled : +b.reporting_enabled,
        p.node_id,
      );
    const updated = nodeResponse(requireNode(ctx, p.node_id, u.owner_id));
    ctx.gateway.send(p.node_id, {
      type: "config.sync",
      payload: { node: updated },
    });
    return updated;
  });
  app.get("/im/v1/nodes/:node_id/capabilities", async (req) => {
    const u = await user(req),
      id = params(req).node_id;
    requireNode(ctx, id, u.owner_id);
    const {capabilities: r} = await rpc(id, "node.capabilities.resolve", {});
    return {
      node_id: id,
      models: modelOptions(r.models),
      skills: allowlistOptions(r.skills),
      tools: allowlistOptions(r.tools),
      features: featureOptions(r.features),
      platform_default_model: r.platform_default_model ?? null,
      default_workspace_template: r.default_workspace_template ?? null,
    };
  });
  app.post("/im/v1/nodes/:node_id/prompt-preview", async (req) => {
    const u = await user(req),
      id = params(req).node_id;
    requireNode(ctx, id, u.owner_id);
    const b = body(req);
    const r = await rpc(id, "node.prompt.preview.request", {
      ...previewInput(b),
      work_mode: b.work_mode ?? "single_thread",
      workspace_mode: b.workspace_mode ?? "default",
      agent_id_hint: b.agent_id_hint ?? null,
      workspace_root: b.workspace_root ?? null,
    });
    if (r.error) {
      const code = r.error.code;
      fail(
        [
          "workspace_confirmation_required",
          "workspace_already_assigned",
          "agent_id_already_exists",
        ].includes(code)
          ? 409
          : 422,
        { code, message: r.error.detail },
      );
    }
    return previewResponse(r.preview);
  });
  app.post("/im/v1/nodes/:node_id/agents", async (req, reply) => {
    const u = await user(req),
      id = params(req).node_id,
      b = body(req);
    requireNode(ctx, id, u.owner_id);
    validateCandidate(b, true);
    const result = await ops.serialized(b.agent_id, async () => {
      const recovered = await ops.recover(b.agent_id, u.owner_id);
      if (recovered) return recovered;
      let skills = b.skills;
      if (skills === undefined) {
        const capabilities = await gatewayRequest(ctx, id, "node.capabilities.resolve", {});
        skills = capabilities
          ? (capabilities.skills ?? []).filter((s: Row) => s.default_on).map((s: Row) => s.name)
          : undefined;
      }
      const c: Row = {
        agent_id: b.agent_id,
        owner_id: u.owner_id,
        display_name: b.display_name,
        description: b.description ?? "",
        features: b.features ?? {},
        custom_prompt: b.custom_prompt ?? null,
        tool_allowlist: b.tool_allowlist ?? [],
        group_reply_policy: b.group_reply_policy,
        default_model: b.default_model ?? null,
        model_fallbacks: b.model_fallbacks ?? [],
        reasoning_effort: b.reasoning_effort ?? null,
        work_mode: b.work_mode ?? "single_thread",
        workspace_root: b.workspace_root ?? null,
        heartbeat_json: null,
        confirm_existing_workspace: b.confirm_existing_workspace === true,
      };
      if (skills !== undefined) {
        c.skills = skills;
        c.skills_selection_mode = b.skills_selection_mode ?? null;
      }
      return ops.create(c, u.owner_id, id);
    });
    return reply.code(201).send(result);
  });
  app.get("/im/v1/agents", async (req) => {
    const u = await user(req);
    return all(
      ctx.db,
      "SELECT p.*,n.status AS node_status,u.id AS user_id FROM agent_profiles p LEFT JOIN nodes n ON n.node_id=p.node_id LEFT JOIN users u ON u.username='agent:'||p.agent_id WHERE p.is_stale=0 AND p.node_id IS NOT NULL AND ((p.owner_id=? AND COALESCE(n.owner_id,'') IN ('',?)) OR (p.owner_id='' AND COALESCE(n.owner_id,'')='')) ORDER BY p.created_at,p.rowid",
      u.owner_id,
      u.owner_id,
    ).map((p) => ({
      ...Object.fromEntries(
        [
          "agent_id",
          "owner_id",
          "node_id",
          "display_name",
          "description",
          "profile_version",
          "default_model",
          "workspace_root",
          "updated_at",
          "user_id",
          "node_status",
        ].map((k) => [k, p[k] ?? null]),
      ),
      workspace_is_default: p.workspace_is_default == null ? null : !!p.workspace_is_default,
    }));
  });
  app.get("/im/v1/agents/:agent_id/config", async (req) => {
    const id = params(req).agent_id,
      source = query(req).source ?? "live";
    const runtime = ctx.gateway.authenticate(bearer(req));
    if (runtime) {
      if (source !== "mirror") fail(401, "human identity required");
      const p = requireProfile(ctx, id, runtime.owner_id);
      if (p.node_id !== runtime.node_id) fail(404, "agent_id not found");
      return profileResponse(p, true);
    }
    const u = await user(req);
    if (!["live", "mirror"].includes(source)) fail(422, "source must be live or mirror");
    return ops.serialized(id, async () => {
      await ops.recover(id, u.owner_id);
      const p = requireProfile(ctx, id, u.owner_id),
        r = profileResponse(p, source === "mirror");
      if (source === "live" && p.node_id) {
        const response = await gatewayRequest(ctx, p.node_id, "agent.config.get", { agent_id: id });
        const live = response?.agent ?? response;
        if (live && (!live.agent_id || live.agent_id === id))
          for (const k of gatewayKeys)
            if (
              k in live &&
              ![
                "agent_id",
                "workspace_root",
                "features",
                "custom_prompt",
                "heartbeat_json",
                "work_mode",
              ].includes(k)
            )
              r[k] = live[k];
      }
      return r;
    });
  });
  app.patch("/im/v1/agents/:agent_id/config", async (req) => {
    const u = await user(req),
      id = params(req).agent_id,
      b = body(req);
    validateCandidate(b);
    return ops.serialized(id, async () => {
      const recovered = await ops.recover(id, u.owner_id);
      if (recovered) return recovered;
      const p = requireProfile(ctx, id, u.owner_id);
      if (!p.node_id)
        fail(422, {
          code: "agent_not_bound",
          message: "The Agent is not bound to a Gateway node.",
        });
      if (b.work_mode != null && b.work_mode !== p.work_mode) fail(409, "work_mode is immutable");
      if (b.profile_version !== p.profile_version) fail(409, "profile_version conflict");
      const c: Row = {
        ...fromProfile(p),
        display_name: b.display_name,
        description: b.description ?? "",
        skills: b.skills ?? [],
        skills_selection_mode: b.skills_selection_mode ?? p.skills_selection_mode,
        tool_allowlist: b.tool_allowlist ?? [],
        group_reply_policy: b.group_reply_policy,
        default_model: b.default_model ?? null,
        model_fallbacks: b.model_fallbacks ?? [],
        features: b.features ?? {},
      };
      for (const k of ["reasoning_effort", "custom_prompt", "heartbeat_json"])
        if (k in b && (k === "reasoning_effort" || b[k] !== null)) c[k] = b[k];
      if (b.heartbeat != null && !("heartbeat_json" in b))
        c.heartbeat_json = JSON.stringify(b.heartbeat);
      return ops.update(p, c, u.owner_id);
    });
  });
  app.post("/im/v1/agents/:agent_id/skills/enable", async (req) => {
    const runtime = ctx.gateway.authenticate(bearer(req));
    if (!runtime) fail(401, "gateway identity required");
    const id = params(req).agent_id,
      b = body(req);
    if (
      Object.keys(b).some((k) => !["profile_version", "skills"].includes(k)) ||
      !Array.isArray(b.skills) ||
      b.skills.some((s: unknown) => typeof s !== "string" || !s.trim())
    )
      fail(422, "Invalid skills");
    return ops.serialized(id, async () => {
      const p = requireProfile(ctx, id, runtime.owner_id);
      if (p.node_id !== runtime.node_id) fail(404, "agent_id not found");
      if (p.profile_version !== b.profile_version) fail(409, "profile_version conflict");
      const c = fromProfile(p);
      c.skills = [...new Set([...c.skills, ...b.skills])];
      return ops.update(p, c, runtime.owner_id);
    });
  });
  app.get("/im/v1/agents/:agent_id/capabilities", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, params(req).agent_id, u.owner_id);
    const {capabilities: r} = await rpc(p.node_id, "agent.capabilities.resolve", {
      agent_id: p.agent_id,
      workspace_root: requiredWorkspace(p),
    });
    return {
      agent_id: p.agent_id,
      node_id: p.node_id,
      workspace_root: p.workspace_root,
      models: modelOptions(r.models),
      skills: allowlistOptions(r.skills),
      tools: allowlistOptions(r.tools),
      commands: r.commands ?? [],
      features: featureOptions(r.features),
      platform_default_model: r.platform_default_model ?? null,
    };
  });
  app.post("/im/v1/agents/:agent_id/prompt-preview", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, params(req).agent_id, u.owner_id);
    const b = body(req),
      features = JSON.parse(p.features_json);
    const r = await rpc(p.node_id, "agent.prompt.preview.request", {
      ...previewInput(b),
      agent_id: p.agent_id,
      workspace_root: requiredWorkspace(p),
      work_mode: p.work_mode,
      heartbeat_enabled: b.heartbeat_enabled ?? !!features.heartbeat,
      cron_enabled: b.cron_enabled ?? !!features.cron_scheduling,
    });
    return previewResponse(r.preview);
  });
  app.get("/im/v1/agents/:agent_id/heartbeat-md", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, params(req).agent_id, u.owner_id);
    if (!p.node_id) return { content: "", node_online: false };
    const r = await gatewayRequest(ctx, p.node_id, "node.heartbeat.md.request", {
      agent_id: p.agent_id,
      workspace_root: requiredWorkspace(p),
    });
    return { content: r?.content ?? "", node_online: !!r };
  });
  app.get("/im/v1/agents/:agent_id/cron/jobs", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, params(req).agent_id, u.owner_id);
    if (!p.node_id) return [];
    const r = await gatewayRequest(ctx, p.node_id, "node.cron.jobs.request", {
      agent_id: p.agent_id,
      workspace_root: requiredWorkspace(p),
    });
    return r?.jobs ?? [];
  });
  app.delete("/im/v1/agents/:agent_id/cron/jobs/:job_id", async (req, reply) => {
    const u = await user(req),
      p = requireProfile(ctx, params(req).agent_id, u.owner_id);
    const r = p.node_id
      ? await gatewayRequest(ctx, p.node_id, "node.cron.delete.request", {
          agent_id: p.agent_id,
          workspace_root: requiredWorkspace(p),
          job_id: params(req).job_id,
        })
      : null;
    if (!r?.deleted) fail(404, "job_id not found");
    return reply.code(204).send();
  });
  app.get("/im/v1/agents/:agent_id/skills/usage", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, params(req).agent_id, u.owner_id),
      { usage: r } = await rpc(p.node_id, "node.skills.usage.request", {
        agent_id: p.agent_id,
        workspace_root: requiredWorkspace(p),
      });
    return {
      agent_id: p.agent_id,
      node_id: p.node_id,
      node_online: true,
      skills: r.skills ?? [],
      heatmap_data: r.heatmap_data ?? Array(30).fill(0),
      health: r.health ?? {
        created_auto_total: 0,
        active_auto_total: 0,
        used_auto_total: 0,
      },
    };
  });
  app.get("/im/v1/policies", async (req) => {
    await user(req);
    const { singleton_key: _key, ...result } = one(
      ctx.db,
      "SELECT * FROM settings_policies LIMIT 1",
    )!;
    return result;
  });
  app.patch("/im/v1/policies", async (req) => {
    const u = await user(req);
    if (!u.is_company_admin) fail(403, "Company administrator required");
    const b = body(req),
      fields = [
        "default_model",
        "max_turn_per_run",
        "max_attachment_size_mb",
        "retention_days",
        "audit_level",
        "rate_limit_per_min",
      ];
    if (
      !optionalText(b.default_model) ||
      !["off", "basic", "strict"].includes(b.audit_level) ||
      fields
        .filter((k) => !["default_model", "audit_level"].includes(k))
        .some((k) => !Number.isInteger(b[k]) || b[k] < 1)
    )
      fail(422, "Invalid settings policy");
    ctx.db
      .prepare(`UPDATE settings_policies SET ${fields.map((k) => `${k}=?`).join(",")}`)
      .run(...fields.map((k) => b[k]));
    return Object.fromEntries(fields.map((k) => [k, b[k]]));
  });
  registerTaskGraphRoutes(app, ctx);
  registerChannelRoutes(app, ctx);
}
