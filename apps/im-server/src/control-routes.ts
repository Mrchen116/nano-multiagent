import {changeCapability, effectiveFeatures, featureDependencies} from '@nano/product-contracts/capabilities';
import type {FastifyInstance, FastifyRequest} from 'fastify';
import {all, one, fail, body, query, now, type ImContext, type Row} from './context.js';
import {bearer, canAccessSpace, ownerAccount, requireCompanyAdmin} from './identity.js';
import {registerAgentLifecycleRoutes} from './agent-lifecycle.js';
import {activeTaskCount, registerTaskGraphRoutes} from './task-graphs.js';
import {registerChannelRoutes} from './channels.js';
import {configurationDisplay, readSettingsSnapshot, writeSettingsSnapshot, settingsConnection, settingsReadCurrent,
  settingsSectionDisplay, requireSettingsNodeOnline, type SettingsSection, type SettingsRead} from './agent-settings.js';
import {ConfigOperations, profileResponse, fromProfile, gatewayKeys, optionalText, stringList, selection, copyConfigurationField} from './control.js';
import {configurationDependencies} from './configuration-assembly.js';
import {readAgentProfile, type AgentProfileRecord} from './configuration-records.js';
import {parseConfigurationInput, controlRouteId, configurationSource, parseSkillsMigration, type ConfigurationCandidate} from './configuration-input.js';
import {gatewayRequest} from './node-rpc-request.js';
import type {NodeCommand, NodeInput, NodeCapabilities} from './node-rpc-contracts.js';
import {isRecord} from './node-rpc-values.js';
function requireProfile(ctx: ImContext, agent: string, owner: string): AgentProfileRecord {
  const p = readAgentProfile(ctx.db, agent, owner);
  if (!p || !canAccessSpace(ownerAccount(ctx.db, owner), p.space_id)) fail(404, "agent_id not found");
  return p;
}
function requireNode(ctx: ImContext, node: string, owner: string) {
  const n = one(
    ctx.db,
    "SELECT * FROM nodes WHERE node_id=? AND owner_id=?",
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
function allowlistOptions(value: unknown): Row[] {
  return (Array.isArray(value) ? value : []).flatMap((item) => {
    const entry = typeof item === "string" ? { name: item } : item;
    if (!entry || !optionalText(entry.name)) return [];
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
        ...(optionalText(entry.display_name) ? {display_name: entry.display_name.trim()} : {}),
        ...(optionalText(entry.provider_display_name) ? {provider_display_name: entry.provider_display_name.trim()} : {}),
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
      requires: {features:stringList(x.requires?.features),tools:stringList(x.requires?.tools),skills:stringList(x.requires?.skills)},
    }));
}
function agentCapabilities(profile: Row, capabilities: NodeCapabilities | undefined): Row {
  if (!capabilities || !(['models','skills','tools'] as const).every(key => Array.isArray(capabilities[key])))
    fail(502, 'Agent capabilities are unavailable');
  return {agent_id:profile.agent_id,node_id:profile.node_id,workspace_root:profile.workspace_root,
    models:modelOptions(capabilities.models),skills:allowlistOptions(capabilities.skills),tools:allowlistOptions(capabilities.tools),
    inherited_approval_rules:capabilities.inherited_approval_rules ?? null,
    commands:capabilities.commands ?? [],features:featureOptions(capabilities.features),fixed_tools:stringList(capabilities.fixed_tools),platform_default_model:capabilities.platform_default_model ?? null};
}
function settingsError(code: string) {
  return {code,message:code === 'offline' ? 'The Agent computer is offline.' : code === 'timeout' ? 'The computer did not respond in time.' : 'Settings could not be confirmed. Refresh to try again.'};
}
function previewInput(b: Row): NodeInput<'node.prompt.preview.request'> {
  return {
    features: b.features ?? {},
    custom_prompt: b.custom_prompt ?? null,
    tool_ids: b.tool_ids ?? [],
    scenario: b.scenario ?? "direct",
    skill_ids: b.skill_ids ?? [],
    skills_selection_mode: b.skills_selection_mode ?? "explicit_allowlist",
  };
}
function previewResponse(r: {prompt?: string; section_count?: number} = {}): Row {
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
  registerAgentLifecycleRoutes(app,ctx);
  app.addHook('onRequest', async (req, reply) => {
    if (/^\/im\/v1\/agents\/[^/]+\/(settings|config|capabilities|plugins|heartbeat-md|cron\/jobs|skills\/usage|channels)(?:[/?]|$)/.test(req.url))
      reply.header('Cache-Control','private, no-store');
  });
  const ops = new ConfigOperations(configurationDependencies(ctx));
  const user = (req: FastifyRequest) => {
    const u = ctx.identity.authenticateRequest(req);
    const id = isRecord(req.params) && typeof req.params.agent_id === 'string' ? req.params.agent_id : undefined;
    if (id) {
      const profile = one(ctx.db, "SELECT space_id FROM agent_profiles WHERE agent_id=?", id);
      if (profile) ctx.identity.requireSpace(u, profile.space_id);
    }
    return u;
  };
  const rpc = async <K extends NodeCommand>(node: string, action: K, payload: NodeInput<NoInfer<K>>) => {
    const response = await gatewayRequest(ctx, node, action, payload);
    if (!response) fail(503, "target_node_id is not connected");
    return response;
  };
  app.get("/im/v1/nodes", async (req) =>
    all(
      ctx.db,
      "SELECT * FROM nodes WHERE owner_id=? ORDER BY node_id",
      (await user(req)).owner_id,
    ).map(node => ({...nodeResponse(node), ...(ctx.updates ? {update: ctx.updates.view(node)} : {})})),
  );
  app.patch("/im/v1/nodes/:node_id/config", async (req) => {
    const u = await user(req),
      p = {node_id:controlRouteId(req, 'node_id')},
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
  app.get("/im/v1/nodes/:node_id/approval", async (req) => {
    const u = await user(req), id = controlRouteId(req, 'node_id');
    requireNode(ctx, id, u.owner_id);
    const workspace = optionalText(query(req).workspace_root);
    if (!workspace) fail(422, "workspace_root is required");
    const result = await rpc(id, "node.approval.resolve", {workspace_root: workspace});
    return {inherited_approval_rules: result.inherited_approval_rules ?? null};
  });
  app.get("/im/v1/nodes/:node_id/capabilities", async (req) => {
    const u = await user(req),
      id = controlRouteId(req, 'node_id');
    requireNode(ctx, id, u.owner_id);
    const {capabilities} = await rpc(id, "node.capabilities.resolve", {});
    if (!capabilities) fail(502, 'Node capabilities are unavailable');
    const r = capabilities;
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
  });
  app.post("/im/v1/nodes/:node_id/prompt-preview", async (req) => {
    const u = await user(req),
      id = controlRouteId(req, 'node_id');
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
      id = controlRouteId(req, 'node_id'),
      b = parseConfigurationInput(req.body, true);
    requireNode(ctx, id, u.owner_id);
    const result = await ops.serialized(b.agent_id, async () => {
      const recovered = await ops.recover(b.agent_id, u.owner_id);
      if (recovered) return recovered;
      let skills = b.skills;
      if (skills === undefined) {
        const capabilities = await gatewayRequest(ctx, id, "node.capabilities.resolve", {});
        skills = capabilities
          ? (capabilities.skills ?? []).filter(isRecord).filter(s => s.default_on).map(s => s.name).filter((name): name is string => typeof name === 'string')
          : undefined;
      }
      const c: ConfigurationCandidate = {
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
        approval_mode: b.approval_mode ?? null,
        work_mode: b.work_mode ?? "single_thread",
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
      return ops.create(c, u.owner_id, id);
    });
    return reply.code(201).send(result);
  });
  app.get("/im/v1/agents", async (req) => {
    const u = await user(req);
    return all(
      ctx.db,
      "SELECT p.*,n.status AS node_status,u.id AS user_id FROM agent_profiles p LEFT JOIN nodes n ON n.node_id=p.node_id LEFT JOIN users u ON u.username='agent:'||p.agent_id WHERE p.is_stale=0 AND p.node_id IS NOT NULL AND p.owner_id=? AND n.owner_id=? ORDER BY p.created_at,p.rowid",
      u.owner_id,
      u.owner_id,
    ).filter(p => canAccessSpace(u, p.space_id)).map((p) => ({
      ...Object.fromEntries(
        [
          "agent_id",
          "owner_id",
          "space_id",
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
  const settingsProfile = (req: FastifyRequest) => {
    const identity = user(req);
    return requireProfile(ctx, controlRouteId(req, 'agent_id'), identity.owner_id);
  };
  const activeOperation = (profile: Row) => one(ctx.db,
    "SELECT operation_id,status FROM agent_config_operations WHERE agent_id=? AND owner_id=? AND status IN ('pending','gateway_applied') ORDER BY rowid DESC LIMIT 1",
    profile.agent_id, profile.owner_id) ?? null;
  app.get('/im/v1/agents/:agent_id/settings', async (req, reply) => {
    reply.header('Cache-Control', 'private, no-store');
    settingsProfile(req);
    return ops.serialized(controlRouteId(req, 'agent_id'), async () => {
      let profile = settingsProfile(req);
      let connection = settingsConnection(ctx, profile);
      let error: SettingsRead['error'] = connection ? null : settingsError('offline');
      if (connection && activeOperation(profile)) {
        try { await ops.recover(profile.agent_id, profile.owner_id); }
        catch (failure) {
          if ((failure as Row).detail?.code !== 'config_apply_pending') throw failure;
        }
        profile = settingsProfile(req);
        if (settingsConnection(ctx, profile) !== connection) { connection = undefined; error = settingsError('read_failed'); }
      }
      let live: Row | null = null;
      let display = readSettingsSnapshot(ctx, profile, 'configuration');
      const pendingOperation = activeOperation(profile);
      if (connection && !pendingOperation) {
        const before = profile;
        try {
          const response = await ctx.gateway.request(profile.node_id ?? '', 'agent.capabilities.resolve', {agent_id:profile.agent_id,workspace_root:requiredWorkspace(profile)});
          live = agentCapabilities(profile, response?.capabilities);
        } catch (failure) { error = settingsError((failure as Row).statusCode === 504 ? 'timeout' : 'read_failed'); }
        // Re-authenticate the HTTP identity after RPC; permission loss never falls back to a snapshot.
        profile = settingsProfile(req);
        if (!settingsReadCurrent(ctx, before, profile, connection)) { live = null; error = settingsError('read_failed'); }
        if (live) {
          const capturedAt = now(), data = configurationDisplay(profile, live);
          writeSettingsSnapshot(ctx, profile, 'configuration', data, capturedAt);
          display = {source:'current',captured_at:capturedAt,data,error:null};
        } else display = readSettingsSnapshot(ctx, profile, 'configuration');
      }
      if (error) display.error = error;
      return {config:profileResponse(profile,true),node:{node_id:profile.node_id,state:!profile.node_id?'unknown':settingsConnection(ctx,profile)?'online':'offline'},
        display,live_capabilities:live,pending_operation:activeOperation(profile),ready:!!live && !activeOperation(profile)};
    });
  });
  app.get('/im/v1/agents/:agent_id/settings/sections/:section', async (req, reply) => {
    reply.header('Cache-Control', 'private, no-store');
    let profile = settingsProfile(req);
    const section = controlRouteId(req, 'section') as Exclude<SettingsSection,'configuration'>;
    if (!['plugins','cron','usage'].includes(section)) fail(404, 'Settings section not found');
    const connection = settingsConnection(ctx, profile);
    if (!connection) return {...readSettingsSnapshot(ctx,profile,section),error:settingsError('offline')};
    const before = profile;
    let data: Row | Row[] | null = null, error: SettingsRead['error'] = null;
    try {
      const response = section === 'plugins'
        ? await ctx.gateway.request(profile.node_id ?? '', 'node.plugins.request', {agent_id:profile.agent_id,action:'list_bundles'})
        : await ctx.gateway.request(profile.node_id ?? '', section === 'cron' ? 'node.cron.jobs.request' : 'node.skills.usage.request', {agent_id:profile.agent_id,workspace_root:requiredWorkspace(profile)});
      if (response?.error) fail(502, 'Settings read failed');
      data = settingsSectionDisplay(section,profile,response);
    } catch (failure) { error = settingsError((failure as Row).statusCode === 504 ? 'timeout' : 'read_failed'); }
    profile = settingsProfile(req);
    if (!settingsReadCurrent(ctx,before,profile,connection)) { data = null; error = settingsError('read_failed'); }
    if (data !== null) {
      const capturedAt = now(); writeSettingsSnapshot(ctx,profile,section,data,capturedAt);
      return {source:'current',captured_at:capturedAt,data,error:null};
    }
    return {...readSettingsSnapshot(ctx,profile,section),error};
  });
  app.get("/im/v1/agents/:agent_id/config", async (req) => {
    const id = controlRouteId(req, 'agent_id'),
      source = configurationSource(req);
    const runtime = ctx.gateway.authenticate(bearer(req));
    if (runtime) {
      if (source !== "mirror") fail(401, "human identity required");
      const p = requireProfile(ctx, id, runtime.owner_id);
      if (p.node_id !== runtime.node_id) fail(404, "agent_id not found");
      return profileResponse(p, true);
    }
    const u = await user(req);
    if (source !== "live" && source !== "mirror") fail(422, "source must be live or mirror");
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
              copyConfigurationField(r, live, k);
      }
      return r;
    });
  });
  app.patch("/im/v1/agents/:agent_id/config", async (req) => {
    const u = await user(req),
      id = controlRouteId(req, 'agent_id'),
      b = parseConfigurationInput(req.body);
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
      requireSettingsNodeOnline(ctx, p);
      const previous = fromProfile(p);
      const c: ConfigurationCandidate = {
        ...previous,
        display_name: b.display_name,
        description: b.description ?? "",
        skills: b.skills ?? previous.skills,
        skills_selection_mode: b.skills_selection_mode ?? p.skills_selection_mode,
        tool_allowlist: b.tool_allowlist ?? previous.tool_allowlist,
        group_reply_policy: b.group_reply_policy,
        default_model: b.default_model ?? null,
        model_fallbacks: b.model_fallbacks ?? [],
        features: b.features ?? previous.features,
      };
      if ("approval_mode" in b) c.approval_mode = b.approval_mode;
      for (const k of ["reasoning_effort", "custom_prompt", "heartbeat_json"] as const)
        if (k in b && (k === "reasoning_effort" || b[k] !== null)) c[k] = b[k];
      if (b.heartbeat != null && !("heartbeat_json" in b))
        c.heartbeat_json = JSON.stringify(b.heartbeat);
      return ops.update(p, c, u.owner_id);
    });
  });
  app.post("/im/v1/agents/:agent_id/skills/migrate", async (req) => {
    const runtime = ctx.gateway.authenticate(bearer(req));
    if (!runtime) fail(401, "gateway identity required");
    const id = controlRouteId(req, 'agent_id'),
      b = parseSkillsMigration(req.body);
    return ops.serialized(id, async () => {
      let p = requireProfile(ctx, id, runtime.owner_id);
      if (p.node_id !== runtime.node_id) fail(404, "agent_id not found");
      const recovered = await ops.recover(id, runtime.owner_id);
      if (recovered) p = requireProfile(ctx, id, runtime.owner_id);
      if (p.skills_selection_mode === "explicit_denylist") return profileResponse(p);
      if (!recovered && p.profile_version !== b.profile_version) fail(409, "profile_version conflict");
      const c = fromProfile(p);
      const response = await ctx.gateway.request(runtime.node_id, "agent.capabilities.resolve", { agent_id: id, workspace_root: p.workspace_root });
      const catalog = response.capabilities?.skills ?? response.skills;
      if (!Array.isArray(catalog)) fail(503, "Skill catalog is unavailable");
      c.skills = selection(c.skills_selection_mode, c.skills) === "explicit_allowlist"
        ? catalog.filter(isRecord).map(skill => skill.name).filter((name): name is string => typeof name === 'string' && !(c.skills ?? []).includes(name))
        : [];
      c.skills_selection_mode = "explicit_denylist";
      return ops.update(p, c, runtime.owner_id);
    });
  });
  for (const method of ['GET', 'POST'] as const) app.route({method, url: '/im/v1/agents/:agent_id/plugins', handler: async req => {
    const u = await user(req), p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id);
    const b = method === 'GET' ? {action: 'list_bundles'} : body(req);
    if (method === 'POST' && (Object.keys(b).some(key => !['action', 'target', 'enabled'].includes(key))
      || !['set_bundle', 'remove_bundle'].includes(b.action) || typeof b.target !== 'string' || !b.target.trim()
      || b.action === 'set_bundle' && typeof b.enabled !== 'boolean'
      || b.action === 'remove_bundle' && b.enabled !== undefined)) fail(422, 'Invalid plugin command');
    if (method === 'POST') requireSettingsNodeOnline(ctx,p);
    const result = await rpc(p.node_id ?? '', 'node.plugins.request', {...b,agent_id: p.agent_id,action:b.action});
    if (result.error) fail(409, result.error);
    return result.plugins;
  }});
  app.get("/im/v1/agents/:agent_id/capabilities", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id);
    const {capabilities} = await rpc(p.node_id ?? '', "agent.capabilities.resolve", {
      agent_id: p.agent_id,
      workspace_root: requiredWorkspace(p),
    });
    if (!capabilities) fail(502, 'Node capabilities are unavailable');
    const r = capabilities;
    return {
      agent_id: p.agent_id,
      node_id: p.node_id,
      workspace_root: p.workspace_root,
      models: modelOptions(r.models),
      skills: allowlistOptions(r.skills),
      tools: allowlistOptions(r.tools),
      commands: r.commands ?? [],
      features: featureOptions(r.features),
      fixed_tools: stringList(r.fixed_tools),
      inherited_approval_rules: r.inherited_approval_rules ?? null,
      platform_default_model: r.platform_default_model ?? null,
    };
  });
  app.get('/im/v1/agents/:agent_id/capability-usage', async req => {
    const u = await user(req), p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id);
    let response: Row | null;
    try { response = await gatewayRequest(ctx,p.node_id ?? '','agent.capability-usage.request',{agent_id:p.agent_id}); }
    catch { response = null; }
    const usage = response?.usage;
    if (!usage || !Number.isInteger(usage.active_schedules) || !Array.isArray(usage.busy)) {
      fail(503,{code:'capability_usage_unavailable',message:'Cannot confirm capability usage right now'});
    }
    return {checked_at:usage.checked_at,active_schedules:usage.active_schedules,busy:usage.busy,active_tasks:activeTaskCount(ctx.db,p.agent_id)};
  });
  app.post("/im/v1/agents/:agent_id/prompt-preview", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id);
    const b = body(req),
      features = JSON.parse(p.features_json);
    const r = await rpc(p.node_id ?? '', "agent.prompt.preview.request", {
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
      p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id);
    if (!p.node_id) return { content: "", node_online: false };
    const r = await gatewayRequest(ctx, p.node_id, "node.heartbeat.md.request", {
      agent_id: p.agent_id,
      workspace_root: requiredWorkspace(p),
    });
    return { content: r?.content ?? "", node_online: !!r };
  });
  app.get("/im/v1/agents/:agent_id/cron/jobs", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id);
    if (!settingsConnection(ctx,p)) fail(503, {code:'agent_node_offline',message:'The Agent computer is offline.'});
    const r = await ctx.gateway.request(p.node_id ?? '', "node.cron.jobs.request", {
      agent_id: p.agent_id,
      workspace_root: requiredWorkspace(p),
    });
    if (!Array.isArray(r?.jobs)) fail(502, "Cron result is unavailable");
    return r.jobs;
  });
  app.delete("/im/v1/agents/:agent_id/cron/jobs/:job_id", async (req, reply) => {
    const u = await user(req),
      p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id);
    requireSettingsNodeOnline(ctx,p);
    const r = await ctx.gateway.request(p.node_id ?? '', "node.cron.delete.request", {
          agent_id: p.agent_id,
          workspace_root: requiredWorkspace(p),
          job_id: controlRouteId(req, 'job_id'),
        });
    if (!r || typeof r.deleted !== "boolean") fail(502, "Cron deletion result is unavailable");
    if (!r.deleted) fail(404, "job_id not found");
    return reply.code(204).send();
  });
  app.get("/im/v1/agents/:agent_id/skills/usage", async (req) => {
    const u = await user(req),
      p = requireProfile(ctx, controlRouteId(req, 'agent_id'), u.owner_id),
      { usage: r } = await rpc(p.node_id ?? '', "node.skills.usage.request", {
        agent_id: p.agent_id,
        workspace_root: requiredWorkspace(p),
      });
    return settingsSectionDisplay('usage', p, {usage:r});
  });
  app.get("/im/v1/policies", async (req) => {
    const u = await user(req);
    ctx.identity.requireSpace(u, "company:default");
    const { singleton_key: _key, ...result } = one(
      ctx.db,
      "SELECT * FROM settings_policies LIMIT 1",
    )!;
    return result;
  });
  app.patch("/im/v1/policies", async (req) => {
    const u = await user(req);
    requireCompanyAdmin(u);
    ctx.identity.requireSpace(u, "company:default");
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
