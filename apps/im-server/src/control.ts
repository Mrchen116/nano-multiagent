import { sortedJsonUtf8 } from '@nano/product-contracts/serialization';
import {createHash, randomUUID} from 'node:crypto';
import type {DatabaseSync} from 'node:sqlite';
import {parseAgentConfigurationFields, type AgentConfigurationFields, type ConfigurationResult} from '@nano/product-contracts';
import {effectiveFeatures, featureDependencies, validateCapabilities} from '@nano/product-contracts/capabilities';
import {fail, now, transaction} from './context.js';
import {defaultSpace, accountEnabled, canAccessSpace, ownerAccount} from './identity.js';
import {activeTaskCount, withdrawsTask} from './task-graphs.js';
import type {ConfigurationRequest} from './node-rpc-contracts.js';
import {decodeNodeResult} from './node-rpc-values.js';
import {requestConfiguration} from './node-rpc-request.js';
import {readAgentProfile, activeConfigOperation, readConfigOperation, configurationPersonalBinding,
  type AgentProfileRecord, type ConfigOperationRecord} from './configuration-records.js';
import {storedConfigurationCandidate, type ConfigurationCandidate} from './configuration-input.js';

export interface ConfigurationDependencies {
  db: DatabaseSync;
  request: ConfigurationRequest;
  deliverLifecycle(agentId: string): void;
}
export const optionalText = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim() : null);
export const stringList = (v: unknown) =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && !!x.trim()).map((x) => x.trim()) : [];
// Candidate receipts historically escape DEL as well as non-ASCII characters.
const serializeCandidateJson = (v: unknown) =>
  sortedJsonUtf8(v).replace(
    /[\u007f-\uffff]/g,
    (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`,
  );
export const selection = (mode: string | null, skills: string[] | null) =>
  mode ?? (skills?.length ? "explicit_allowlist" : "default_discovery");
function heartbeat(v: unknown): string | null {
  if (typeof v !== "string" || !v.trim()) return null;
  try {
    return serializeCandidateJson(JSON.parse(v));
  } catch {
    return v.trim();
  }
}
export const gatewayKeys: (keyof AgentConfigurationFields)[] = [
  "agent_id",
  "display_name",
  "skills",
  "skills_selection_mode",
  "tool_allowlist",
  "group_reply_policy",
  "default_model",
  "model_fallbacks",
  "reasoning_effort",
  "approval_mode",
  "work_mode",
  "workspace_root",
  "features",
  "custom_prompt",
  "heartbeat_json",
];
/** Copy a present public field while retaining key/value correlation and omission. */
export function copyConfigurationField<K extends keyof AgentConfigurationFields>(target: AgentConfigurationFields, source: AgentConfigurationFields, key: K): void {
  if (key in source) target[key] = source[key];
}
export function gatewayCandidate(c: AgentConfigurationFields): AgentConfigurationFields & {agent_id: string} {
  const p: AgentConfigurationFields & {agent_id: string} = {
    agent_id: optionalText(c.agent_id) ?? "",
    display_name: optionalText(c.display_name) ?? c.agent_id,
    tool_allowlist: stringList(c.tool_allowlist),
    group_reply_policy: optionalText(c.group_reply_policy) ?? "manual",
    default_model: optionalText(c.default_model),
    model_fallbacks: stringList(c.model_fallbacks),
    reasoning_effort: optionalText(c.reasoning_effort),
    approval_mode: c.approval_mode ?? null,
    work_mode: c.work_mode || "single_thread",
    workspace_root: optionalText(c.workspace_root),
    features: Object.fromEntries(
      Object.entries(c.features ?? {}).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean" && !["memory_curation", "skill_creation"].includes(entry[0])),
    ),
    custom_prompt: optionalText(c.custom_prompt),
    heartbeat_json: heartbeat(c.heartbeat_json),
  };
  if (c.personal_agent) p.personal_agent = c.personal_agent;
  if ("skills" in c) p.skills = Array.isArray(c.skills) ? stringList(c.skills) : null;
  if ("skills" in c || "skills_selection_mode" in c)
    p.skills_selection_mode = Array.isArray(p.skills)
      ? selection(c.skills_selection_mode ?? null, p.skills)
      : (c.skills_selection_mode ?? null);
  if ("confirm_existing_workspace" in c)
    p.confirm_existing_workspace = c.confirm_existing_workspace === true;
  if (p.skills) p.skills = p.skills.filter(name => name !== 'skill-creator');
  return p;
}
export function candidateFingerprint(c: AgentConfigurationFields): string {
  const p = gatewayCandidate(c);
  if (p.heartbeat_json === "{}") p.heartbeat_json = null;
  // Null keeps pre-strategy operation receipts valid during upgrade/recovery.
  const keys = gatewayKeys.filter(k => k !== "approval_mode" || p.approval_mode !== null);
  if(p.personal_agent) keys.push("personal_agent");
  return createHash("sha256")
    .update(serializeCandidateJson(Object.fromEntries(keys.map((k) => [k, p[k] ?? null]))))
    .digest("hex");
}
export interface AgentProfileView extends ConfigurationCandidate {
  owner_id: string;
  space_id: string;
  node_id: string | null;
  display_name: string;
  description: string;
  group_reply_policy: string;
  default_model: string | null;
  reasoning_effort: string | null;
  approval_mode: 'cc' | 'codex' | null;
  work_mode: string;
  workspace_root: string | null;
  profile_version: number;
  updated_at: string;
  custom_prompt: string | null;
  heartbeat_json: string | null;
  skills: string[] | null;
  skills_selection_mode: string | null;
  tool_allowlist: string[];
  model_fallbacks: string[];
  features: Record<string, boolean>;
  workspace_is_default: boolean | null;
}
function storedStrings(json: string): string[] {
  const value: unknown = JSON.parse(json);
  if (!Array.isArray(value) || !value.every((item): item is string => typeof item === 'string')) throw new Error('Invalid stored configuration list');
  return value;
}
function storedFeatures(json: string): Record<string, boolean> {
  const fields = parseAgentConfigurationFields({features: JSON.parse(json)});
  return Object.fromEntries(Object.entries(fields.features!).filter(([key]) => !['memory_curation','skill_creation'].includes(key)));
}
/** Project public fields once; callers never expose the SQLite JSON columns. */
export function profileResponse(p: AgentProfileRecord, mirror = false): AgentProfileView {
  const rawSkills: unknown = JSON.parse(p.skills_json);
  const skills = rawSkills === null ? null : storedStrings(p.skills_json);
  const skillMode = p.skills_selection_mode ?? (skills?.includes('skill-creator') ? selection(null, skills) : null);
  return {
    agent_id:p.agent_id, owner_id:p.owner_id, space_id:p.space_id, node_id:p.node_id,
    display_name:p.display_name, description:p.description, group_reply_policy:p.group_reply_policy,
    default_model:p.default_model, reasoning_effort:p.reasoning_effort, approval_mode:p.approval_mode,
    work_mode:p.work_mode, workspace_root:p.workspace_root, profile_version:p.profile_version,
    updated_at:p.updated_at, custom_prompt:p.custom_prompt, heartbeat_json:p.heartbeat_json,
    skills:skills?.filter(name => name !== 'skill-creator') ?? null, skills_selection_mode:mirror ? skillMode : selection(skillMode, skills),
    tool_allowlist:storedStrings(p.tool_allowlist_json), model_fallbacks:storedStrings(p.model_fallbacks_json),
    features:storedFeatures(p.features_json),
    workspace_is_default:p.workspace_is_default == null ? null : !!p.workspace_is_default,
  };
}
/** Reconstruct the existing complete candidate without carrying display freshness into intent. */
export function fromProfile(p: AgentProfileRecord): Omit<AgentProfileView, 'node_id' | 'workspace_is_default' | 'profile_version' | 'updated_at'> {
  const {node_id,workspace_is_default,profile_version,updated_at,...candidate} = profileResponse(p, true);
  candidate.heartbeat_json = heartbeat(candidate.heartbeat_json);
  return candidate;
}
function pending(): never {
  fail(503, {
    code: "config_apply_pending",
    message: "Configuration application is still being confirmed.",
  });
}
const safeRejections = new Set([
  'capability_in_use', 'invalid_capability_dependencies', 'capability_unavailable', 'capability_usage_unavailable',
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
  constructor(private readonly dependencies: ConfigurationDependencies) {}
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
  private authorize(owner: string, node: string, agent: string): void {
    const user = ownerAccount(this.dependencies.db, owner);
    const device = this.dependencies.db.prepare("SELECT owner_id FROM nodes WHERE node_id=?").get(node);
    const profile = readAgentProfile(this.dependencies.db, agent);
    if (!accountEnabled(user) || device?.owner_id !== owner || (profile && (profile.owner_id !== owner || !canAccessSpace(user, profile.space_id)))) fail(404, "agent_id not found");
  }
  private active(agent: string, owner: string) {
    return activeConfigOperation(this.dependencies.db, agent, owner);
  }
  private insert(
    candidate: ConfigurationCandidate,
    owner: string,
    node: string,
    kind: ConfigOperationRecord['operation_kind'],
    previous: ConfigurationCandidate | null,
    expectedVersion: number | null,
    root: string | null = null,
    previousHash?: string,
  ): ConfigOperationRecord {
    this.authorize(owner, node, candidate.agent_id);
    const binding=configurationPersonalBinding(this.dependencies.db,candidate.agent_id,owner,node);
    if(binding) {
      candidate={...candidate,personal_agent:{bindingId:binding.binding_id,ownerId:binding.owner_id,conversationId:binding.conversation_id,epoch:binding.node_epoch}};
      if(previous)previous={...previous,personal_agent:candidate.personal_agent};
    } else {candidate={...candidate};delete candidate.personal_agent;}
    const unchangedDreaming = !!previous && previous.features?.dreaming !== false && candidate.features?.dreaming !== false
      && validateCapabilities(previous).some(block => block.required_by?.includes('dreaming'));
    const blocks = validateCapabilities(candidate, {features:featureDependencies.filter(feature => feature.key !== 'dreaming' || !unchangedDreaming)});
    if (blocks.length) fail(422, {code:'invalid_capability_dependencies', message:'Configuration is missing required capabilities', blocks});
    if (previous && withdrawsTask(previous, candidate) && activeTaskCount(this.dependencies.db, candidate.agent_id)) {
      const kind = effectiveFeatures(previous.features).task_graph && !effectiveFeatures(candidate.features).task_graph ? 'feature' : 'tool';
      fail(409, {code:'capability_in_use', message:'Pause or finish active tasks before withdrawing Task capability', blocks:[{code:'active_tasks',target:{kind,name:'task_graph'}}]});
    }
    const id = randomUUID().replaceAll("-", ""),
      hash = candidateFingerprint(candidate);
    if (
      this.dependencies.db.prepare("SELECT 1 FROM agent_config_operations WHERE agent_id=? AND status IN ('pending','gateway_applied')").get(candidate.agent_id)
    )
      pending();
    this.dependencies.db
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
    return readConfigOperation(this.dependencies.db, id)!;
  }
  private async request(op: ConfigOperationRecord) {
    this.authorize(op.owner_id, op.node_id, op.agent_id);
    const c = gatewayCandidate(storedConfigurationCandidate(op.candidate_json));
    const binding = configurationPersonalBinding(this.dependencies.db,op.agent_id,op.owner_id,op.node_id);
    if(binding) c.personal_agent={bindingId:binding.binding_id,ownerId:binding.owner_id,conversationId:binding.conversation_id,epoch:binding.node_epoch};
    else delete c.personal_agent;
    if (["create","restore"].includes(op.operation_kind)) c.create_operation_id = op.operation_id;
    return requestConfiguration(
      this.dependencies.request,
      op.node_id,
      ["create","restore"].includes(op.operation_kind) ? "agent.create" : "agent.config.apply",
      {
        operation_id: op.operation_id,
        candidate_fingerprint: op.candidate_fingerprint,
        expected_previous_fingerprint: op.expected_previous_fingerprint,
        agent: c,
      },
    );
  }
  private async resolve(op: ConfigOperationRecord, initial?: ConfigurationResult | null): Promise<ConfigurationResult> {
    let result = initial;
    if (op.status === "gateway_applied") result = decodeNodeResult('agent.config.operation.status', JSON.parse(op.gateway_result_json!));
    else if (!result || result.status === "pending") {
      result = await requestConfiguration(this.dependencies.request, op.node_id, "agent.config.operation.status", {
        operation_id: op.operation_id,
      });
      if (result?.status === "pending") result = await this.request(op);
    }
    this.authorize(op.owner_id, op.node_id, op.agent_id);
    if (!result || (result.status !== "applied" && result.status !== "rejected")) pending();
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
      const code = result.error_code && safeRejections.has(result.error_code)
        ? result.error_code
        : "invalid_agent_config";
      this.dependencies.db
        .prepare(
          "UPDATE agent_config_operations SET status='rejected',gateway_result_json=?,error_code=?,error_message=?,updated_at=? WHERE operation_id=?",
        )
        .run(JSON.stringify(result), code, result.message ?? null, now(), op.operation_id);
      fail(
        code === 'capability_usage_unavailable' ? 503 : ['invalid_capability_dependencies','capability_unavailable'].includes(code) ? 422 : code.startsWith("workspace_") &&
          !["workspace_already_assigned", "workspace_confirmation_required"].includes(code)
          ? 422
          : 409,
        { code, message: result.message ?? code, ...(Array.isArray(result.blocks) ? {blocks:result.blocks} : {}) },
      );
    }
    this.dependencies.db
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
  async create(candidate: ConfigurationCandidate, owner: string, node: string) {
    if (readAgentProfile(this.dependencies.db, candidate.agent_id))
      fail(409, "agent_id already exists");
    const op = transaction(this.dependencies.db, () => this.insert(candidate, owner, node, "create", null, null));
    return this.commit(op, await this.resolve(op, await this.request(op)));
  }
  async update(profile: AgentProfileRecord, candidate: ConfigurationCandidate, owner: string) {
    if (!profile.node_id) fail(404, "agent_id not found");
    const node = profile.node_id;
    const op = transaction(this.dependencies.db, () => this.insert(
      candidate,
      owner,
      node,
      "apply",
      fromProfile(profile),
      profile.profile_version,
    ));
    return this.commit(op, await this.resolve(op, await this.request(op)));
  }
  private async commit(op: ConfigOperationRecord, result: ConfigurationResult): Promise<AgentProfileView> {
    this.authorize(op.owner_id, op.node_id, op.agent_id);
    const db = this.dependencies.db;
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
    const candidate = storedConfigurationCandidate(op.candidate_json);
    const canonical = result.agent ?? {};
    const c: ConfigurationCandidate = {
      ...candidate,
      workspace_is_default:canonical.workspace_is_default ?? candidate.workspace_is_default ?? null,
    };
    for (const key of gatewayKeys) copyConfigurationField(c, canonical, key);
    c.description = candidate.description ?? "";
    c.owner_id = op.owner_id;
    c.node_id = op.node_id;
    const existing = readAgentProfile(db, op.agent_id);
    if (op.operation_kind === "apply" && existing) {
      c.workspace_root = existing.workspace_root;
      c.workspace_is_default =
        existing.workspace_is_default === null ? null : !!existing.workspace_is_default;
      c.work_mode = existing.work_mode;
    }
    if (["create","restore"].includes(op.operation_kind) && !optionalText(c.workspace_root)) pending();
    if (
      op.operation_kind === "apply" &&
      existing?.profile_version !== op.expected_profile_version
    ) {
      if (
        existing &&
        op.expected_profile_version !== null && existing.profile_version === op.expected_profile_version + 1 &&
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
      if(op.operation_kind==='restore') {
        db.prepare("UPDATE personal_agent_bindings SET status='active' WHERE agent_id=? AND node_id=?").run(op.agent_id,op.node_id);
        db.prepare('UPDATE agent_profiles SET is_stale=0,staled_at=NULL WHERE agent_id=?').run(op.agent_id);
        db.prepare("INSERT INTO pa_source_events(binding_id,kind,payload_json,policy_revision,created_at) SELECT b.binding_id,'runtime.restored','{}',p.revision,? FROM personal_agent_bindings b JOIN pa_policies p USING(binding_id) WHERE b.agent_id=?").run(now(),op.agent_id);
      }
      const vals = [
        c.display_name || op.agent_id,
        c.description ?? "",
        JSON.stringify(c.skills ?? []),
        c.skills_selection_mode ?? null,
        JSON.stringify(c.tool_allowlist ?? []),
        c.group_reply_policy ?? "manual",
        c.default_model ?? null,
        JSON.stringify(c.model_fallbacks ?? []),
        c.reasoning_effort ?? null,
        c.approval_mode ?? null,
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
            "UPDATE agent_profiles SET display_name=?,description=?,skills_json=?,skills_selection_mode=?,tool_allowlist_json=?,group_reply_policy=?,default_model=?,model_fallbacks_json=?,reasoning_effort=?,approval_mode=?,work_mode=?,workspace_root=?,workspace_is_default=?,features_json=?,custom_prompt=?,heartbeat_json=?,profile_version=profile_version+1,registration_seed=0,pending_create_operation_id=NULL,updated_at=? WHERE agent_id=? AND profile_version=?",
          )
          .run(...vals, now(), op.agent_id, existing.profile_version);
        if (!changed.changes) fail(409, "profile_version conflict");
      } else
        db.prepare(
          "INSERT INTO agent_profiles(display_name,description,skills_json,skills_selection_mode,tool_allowlist_json,group_reply_policy,default_model,model_fallbacks_json,reasoning_effort,approval_mode,work_mode,workspace_root,workspace_is_default,features_json,custom_prompt,heartbeat_json,agent_id,owner_id,node_id,profile_version,created_at,updated_at,space_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)",
        ).run(...vals, op.agent_id, op.owner_id, op.node_id, now(), now(), defaultSpace(ownerAccount(db, op.owner_id)!));
      db.prepare(
        "INSERT OR IGNORE INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?,?)",
      ).run(randomUUID(), `agent:${op.agent_id}`, c.display_name || op.agent_id, op.owner_id, now());
      db.prepare("UPDATE users SET display_name=? WHERE username=?").run(
        c.display_name || op.agent_id,
        `agent:${op.agent_id}`,
      );
      // All configuration entry points and delayed recovery commit the same PA identity.
      db.prepare("UPDATE personal_agent_bindings SET display_name=? WHERE agent_id=? AND owner_id=?").run(c.display_name || op.agent_id, op.agent_id, op.owner_id);
      db.prepare("UPDATE conversations SET title=? WHERE id IN (SELECT conversation_id FROM personal_agent_bindings WHERE agent_id=? AND owner_id=?)").run(c.display_name || op.agent_id, op.agent_id, op.owner_id);
      db.prepare(
        "UPDATE agent_config_operations SET status='committed',updated_at=? WHERE operation_id=?",
      ).run(now(), op.operation_id);
    });
    this.dependencies.deliverLifecycle(op.agent_id);
    return profileResponse(readAgentProfile(db, op.agent_id)!);
  }
}
