import {changeCapability, effectiveFeatures, featureDependencies} from '@nano/product-contracts/capabilities';
import {one, fail, type ImContext, type Row} from './context.js';
import {candidateFingerprint, profileResponse, optionalText, stringList} from './control.js';
import {configurationOperations} from './configuration-assembly.js';
import {readAgentProfile, readConfigOperation} from './configuration-records.js';
import {storedConfigurationCandidate, type ConfigurationCandidate, type CreateConfigurationInput} from './configuration-input.js';
import {settingsConnection, requireSettingsNodeOnline} from './agent-settings.js';
import {catalogReads, type CatalogScope} from './catalog-reads.js';
import type {NodeCapabilities} from '@nano/product-contracts/node-rpc';
import {isRecord} from './node-rpc-values.js';

/** Keep creation and catalog reads within the owning account's node directory. */
export function requireOwnedNode(ctx: ImContext, id: string, owner: string): Row {
  const node = one(ctx.db,'SELECT * FROM nodes WHERE node_id=? AND owner_id=?',id,owner);
  if (!node) fail(404,'node_id not found');
  return node;
}

function pluginTitle(value: unknown): string | Record<string, string> | null {
  const direct = optionalText(value);
  if (direct) return direct;
  if (!isRecord(value)) return null;
  const entries = Object.entries(value).flatMap(([key, item]) => {
    const text = optionalText(item);
    return text ? [[key, text] as const] : [];
  });
  return entries.length ? Object.fromEntries(entries) : null;
}

export function allowlistOptions(value: unknown): Row[] {
  return (Array.isArray(value) ? value : []).flatMap((item) => {
    const entry = typeof item === "string" ? { name: item } : item;
    if (!entry || !optionalText(entry.name)) return [];
    const bundle = optionalText(entry.plugin_bundle);
    const title = pluginTitle(entry.plugin_title);
    return [
      {
        name: entry.name.trim(),
        description: typeof entry.description === "string" ? entry.description.trim() : "",
        default_on: !!entry.default_on,
        ...(typeof entry.enabled === "boolean" ? {enabled: entry.enabled} : {}),
        location: optionalText(entry.location),
        source_group: ["workspace", "global", "compatibility"].includes(entry.source_group)
          ? entry.source_group
          : null,
        ...(bundle ? {plugin_bundle: bundle} : {}),
        ...(title ? {plugin_title: title} : {}),
      },
    ];
  });
}
export function modelOptions(value: unknown): Row[] {
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
        ...(optionalText(entry.display_name) ? {display_name: entry.display_name.trim()} : {}),
        ...(optionalText(entry.provider_display_name) ? {provider_display_name: entry.provider_display_name.trim()} : {}),
        reasoning,
      },
    ];
  });
}
export function featureOptions(value: unknown): Row[] {
  return (Array.isArray(value) ? value : [])
    .filter((x) => x && typeof x.key === "string" && x.key)
    .map((x) => ({
      key: x.key,
      label_i18n: typeof x.label_i18n === "string" ? x.label_i18n : "",
      help_i18n: typeof x.help_i18n === "string" ? x.help_i18n : "",
      default_on: !!x.default_on,
      available: x.available !== false,
      requires: {features:stringList(x.requires?.features),tools:stringList(x.requires?.tools),skills:stringList(x.requires?.skills)},
    }));
}

/** Read the shared online catalog through `CatalogReads` so creation flows reuse warm entries.
 *
 * Args:
 *   ctx: IM service dependencies.
 *   id: Target computer selected from the owner directory.
 *   owner: Authenticated account owner.
 *   options: When `allowUnboundRequestFallback` is true, permits direct `gateway.request`
 *     for unit tests that stub `gateway.request` without opening a live WebSocket.
 * Returns:
 *   Raw node capabilities payload from `CatalogReads` or direct request.
 */
export async function readNodeCapabilitiesRaw(
  ctx: ImContext,
  id: string,
  owner: string,
  options?: { allowUnboundRequestFallback?: boolean; allowLegacyMockResponse?: boolean },
): Promise<NodeCapabilities> {
  const unwrapMock = (response: unknown): NodeCapabilities | null => {
    if (!isRecord(response)) return null;
    if (isRecord(response.capabilities)) return response.capabilities as unknown as NodeCapabilities;
    if ('skills' in response || 'tools' in response || 'models' in response || 'features' in response) {
      return response as unknown as NodeCapabilities;
    }
    if (options?.allowLegacyMockResponse && !('error_code' in response)) {
      return {} as NodeCapabilities;
    }
    return null;
  };
  requireOwnedNode(ctx, id, owner);
  for (let attempt = 0; attempt < 2; attempt++) {
    const connection = settingsConnection(ctx, { owner_id: owner, node_id: id });
    if (!connection) {
      if (options?.allowUnboundRequestFallback) {
        const response = await ctx.gateway.request(id, 'node.capabilities.resolve', {});
        const unwrapped = unwrapMock(response);
        if (unwrapped) return unwrapped;
        fail(502, 'Node capabilities are unavailable');
      }
      fail(503, 'target_node_id is not connected');
    }
    const scope: CatalogScope = { owner_id: owner, node_id: id, node_epoch: connection.node_epoch, connection };
    let legacyFallback: NodeCapabilities | null = null;
    try {
      const result = await catalogReads(ctx).read(scope, async (signal, requestId) => {
        const response = await ctx.gateway.request(id, 'node.capabilities.resolve', { request_id: requestId }, signal);
        if (isRecord(response?.capabilities)) return response.capabilities;
        if (options?.allowLegacyMockResponse) {
          legacyFallback = unwrapMock(response);
          if (legacyFallback) fail(502, 'Legacy mock capabilities response');
        }
        fail(502, 'Node capabilities are unavailable');
      });
      requireOwnedNode(ctx, id, owner);
      if (!result.current() || settingsConnection(ctx, { owner_id: owner, node_id: id }) !== scope.connection) {
        fail(503, 'Catalog read superseded');
      }
      return result.capabilities;
    } catch (error) {
      if (legacyFallback) {
        catalogReads(ctx).invalidateNode(id);
        return legacyFallback;
      }
      const msg = String((error as { detail?: unknown; message?: string })?.detail ?? (error as { message?: string })?.message ?? '');
      const superseded = /Catalog (?:read superseded|request cancelled)/.test(msg);
      if (attempt === 0 && superseded && settingsConnection(ctx, { owner_id: owner, node_id: id })) {
        continue;
      }
      throw error;
    }
  }
  fail(503, 'Catalog read superseded');
}

/** Read the shared online catalog without losing its binding fence.
 *
 * Args:
 *   ctx: IM service dependencies.
 *   id: Target computer selected from the owner directory.
 *   owner: Authenticated account owner.
 * Returns:
 *   Confirmed public models, Skills, tools, Features and inherited defaults.
 */
export async function readNodeCreationCapabilities(ctx: ImContext, id: string, owner: string): Promise<Row> {
  const r = await readNodeCapabilitiesRaw(ctx, id, owner);
  return {
    node_id: id,
    models: modelOptions(r.models),
    skills: allowlistOptions(r.skills),
    tools: allowlistOptions(r.tools),
    features: featureOptions(r.features),
    fixed_tools: stringList(r.fixed_tools),
    inherited_approval_rules: r.inherited_approval_rules ?? null,
    platform_default_model: r.platform_default_model ?? null,
    default_workspace_template: r.default_workspace_template ?? null,
  };
}

/** Submit or recover one creation through the existing configuration owner.
 *
 * Args:
 *   ctx: IM service dependencies.
 *   owner: Authenticated account owner.
 *   id: Target computer, independently authorized.
 *   b: Parsed public creation configuration.
 *   operationId: Optional host-reserved identity for a PA business request.
 *   beforeCreate: Recheck the producer after queueing and candidate preparation.
 * Returns:
 *   Committed Agent profile; unconfirmed operations retain their original receipt.
 */
export async function createAgent(ctx: ImContext, owner: string, id: string, b: CreateConfigurationInput, operationId?: string, beforeCreate?: () => void) {
  requireOwnedNode(ctx,id,owner);
  const ops = configurationOperations(ctx);
  return ops.serialized(b.agent_id,async()=>{
    const own = operationId ? readConfigOperation(ctx.db,operationId) : undefined;
    if (own) {
      if (own.owner_id !== owner || own.node_id !== id || own.agent_id !== b.agent_id || own.operation_kind !== 'create') fail(409,'creation_operation_conflict');
      if (own.status === 'committed') {
        const profile = readAgentProfile(ctx.db,b.agent_id,owner);
        if (!profile || profile.node_id !== id) fail(409,'created_agent_unavailable');
        return profileResponse(profile);
      }
      if (own.status === 'rejected') fail(409,{code:own.error_code ?? 'creation_rejected',message:own.error_message ?? 'Creation rejected'});
      return ops.recover(b.agent_id,owner);
    }
    const pending = one(ctx.db, `SELECT owner_id,node_id,operation_kind,candidate_json,candidate_fingerprint,operation_id
      FROM agent_config_operations WHERE agent_id=? AND status IN ('pending','gateway_applied') ORDER BY rowid DESC LIMIT 1`, b.agent_id);
    if (pending && (operationId && pending.operation_id !== operationId || pending.operation_kind !== 'create' || pending.owner_id !== owner || pending.node_id !== id))
      fail(409, "agent_id already exists");
    const stored = pending && storedConfigurationCandidate(pending.candidate_json);
    // A retry with omitted skills must use the defaults chosen on its first submission.
    const defaults = stored && 'create_default_skills' in stored ? stored.create_default_skills : undefined;
    let skills = b.skills;
    if (skills === undefined && (defaults === null || Array.isArray(defaults) && defaults.every(name => typeof name === 'string'))) {
      skills = defaults ?? undefined;
    } else if (skills === undefined) {
      let capabilities: NodeCapabilities | null = null;
      try {
        capabilities = await readNodeCapabilitiesRaw(ctx, id, owner, {
          allowUnboundRequestFallback: true,
          allowLegacyMockResponse: true,
        });
      } catch (error) {
        const status = Number((error as { statusCode?: number })?.statusCode ?? 0);
        const msg = String((error as { detail?: unknown; message?: string })?.detail ?? (error as { message?: string })?.message ?? '');
        const isOfflineFallback =
          !settingsConnection(ctx, { owner_id: owner, node_id: id }) ||
          (error as { code?: string })?.code === 'node_offline' ||
          /offline|not connected/i.test(msg);
        if (!isOfflineFallback || ![503, 504].includes(status)) {
          throw error;
        }
      }
      skills = capabilities
        ? (capabilities.skills ?? []).filter(isRecord).filter(s => s.default_on).map(s => s.name).filter((name): name is string => typeof name === 'string')
        : undefined;
    }
    const c: ConfigurationCandidate = {
      agent_id: b.agent_id,
      owner_id: owner,
      display_name: b.display_name,
      ...(b.avatar_variant === undefined ? {} : {avatar_variant:b.avatar_variant}),
      description: b.description ?? "",
      features: b.features ?? {},
      ...(b.initial_role === undefined ? {} : {initial_role:b.initial_role}),
      tool_allowlist: b.tool_allowlist ?? [],
      collaboration_scope: b.collaboration_scope ?? 'team',
      default_model: b.default_model ?? null,
      model_fallbacks: b.model_fallbacks ?? [],
      reasoning_effort: b.reasoning_effort ?? null,
      approval_mode: b.approval_mode ?? null,
      work_mode: b.work_mode ?? "global",
      workspace_root: b.workspace_root ?? null,
      heartbeat_json: null,
      confirm_existing_workspace: b.confirm_existing_workspace === true,
    };
    if (skills !== undefined) {
      c.skills = skills;
      c.skills_selection_mode = b.skills_selection_mode ?? null;
    }
    if (b.features === undefined) {
      const desired = effectiveFeatures();
      c.features = Object.fromEntries(featureDependencies.map(feature => [feature.key,false]));
      for (const feature of featureDependencies) if (desired[feature.key]) Object.assign(c, changeCapability(c,{kind:'feature',name:feature.key,enabled:true},{}).draft);
    }
    if (pending && stored) {
      if (candidateFingerprint(c) !== pending.candidate_fingerprint || c.description !== (stored.description ?? "") ||
          c.confirm_existing_workspace !== (stored.confirm_existing_workspace === true) || c.initial_role !== stored.initial_role || c.avatar_variant !== stored.avatar_variant) fail(409, "agent_id already exists");
      const recovered = await ops.recover(b.agent_id, owner);
      if (!recovered) fail(409, "agent_id already exists");
      return recovered;
    }
    if (operationId) requireSettingsNodeOnline(ctx,{owner_id:owner,node_id:id});
    beforeCreate?.();
    const candidate = {...c, ...(b.skills === undefined ? {create_default_skills:skills ?? null} : {})};
    return ops.create(candidate, owner, id, operationId);
  });
}
