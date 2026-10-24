/** Retain bounded settings display data without making snapshots writable authority. */
import {fail, one, type ImContext, type Row} from './context.js';
import type {Connection} from './gateway.js';

export type SettingsSection = 'configuration' | 'plugins' | 'cron' | 'usage';
/** Describe freshness independently of an empty, successfully read value. */
export interface SettingsRead<T = Row | Row[]> {
  source: 'current' | 'last_known' | 'unavailable';
  captured_at: string | null;
  data: T | null;
  error: {code: string; message: string} | null;
}
const pick = (value: Row, keys: string[]): Row => Object.fromEntries(keys.filter(key => key in value).map(key => [key, value[key]]));

/** Return a live connection only when both persisted binding and open socket agree. */
export function settingsConnection(ctx: ImContext, profile: Row): Connection | undefined {
  const connection = ctx.gateway.nodes.get(profile.node_id);
  const node = one(ctx.db, 'SELECT owner_id FROM nodes WHERE node_id=?', profile.node_id);
  return connection && connection.owner_id === profile.owner_id && node?.owner_id === profile.owner_id
    && connection.socket.readyState === 1 && ctx.gateway.valid(connection) ? connection : undefined;
}

/** Reject a new settings mutation before it creates any durable intent.
 *
 * Raises:
 *   409: The current node is updating or has no valid open connection.
 * Notes:
 *   Recovery of already accepted operations must not call this gate.
 */
export function requireSettingsNodeOnline(ctx: ImContext, profile: Row): void {
  if (ctx.updates?.gate(profile.node_id)) fail(409, 'Computer is updating; try again when it reconnects');
  if (!settingsConnection(ctx, profile)) fail(409, {code:'agent_node_offline', message:'The Agent computer is offline. Reconnect it before making changes.'});
}

/** Fence an awaited read against reconnection, rebinding and committed profile changes. */
export function settingsReadCurrent(ctx: ImContext, before: Row, after: Row, connection: Connection): boolean {
  return before.owner_id === after.owner_id && before.node_id === after.node_id
    && before.workspace_root === after.workspace_root && before.profile_version === after.profile_version
    && settingsConnection(ctx, after) === connection;
}

/** Project configuration names and resolved selections, never the full optional catalog. */
export function configurationDisplay(profile: Row, capabilities: Row, derivedCurrent = true): Row {
  const configuredSkills: string[] = JSON.parse(profile.skills_json);
  const mode = profile.skills_selection_mode ?? (configuredSkills.length ? 'explicit_allowlist' : 'default_discovery');
  const skills: Row[] = capabilities.skills ?? [];
  const tools: Row[] = capabilities.tools ?? [];
  const models: Row[] = capabilities.models ?? [];
  const features: Row = JSON.parse(profile.features_json);
  const modelNames: string[] = [...new Set([profile.default_model ?? (derivedCurrent ? capabilities.platform_default_model : null), ...JSON.parse(profile.model_fallbacks_json)].filter(Boolean))] as string[];
  const mainModel = models.find(model => model.name === modelNames[0]);
  const level = profile.reasoning_effort ?? (derivedCurrent && mainModel?.reasoning?.kind === 'selectable' ? mainModel.reasoning.default : null);
  const selectedSkills = mode === 'explicit_allowlist' ? configuredSkills
    : [...new Set([...skills.filter(skill => mode === 'explicit_denylist' || skill.enabled !== false).map(skill => skill.name), ...configuredSkills])];
  return {
    profile_version: profile.profile_version,
    derived_current: derivedCurrent,
    models: modelNames.map(name => ({name, ...pick(models.find(model => model.name === name) ?? {}, ['display_name','provider','provider_display_name']), source: name === modelNames[0] && !profile.default_model ? 'inherited' : 'explicit'})),
    reasoning: level == null ? null : {value:level,source:profile.reasoning_effort == null ? 'inherited' : 'explicit'},
    features: [...new Set([...(capabilities.features ?? []).map((feature: Row) => feature.key), ...Object.keys(features)])].map(key => {
      const feature = (capabilities.features ?? []).find((item: Row) => item.key === key) ?? {};
      return {key,...pick(feature,['label_i18n','help_i18n']),enabled: key in features ? features[key] : derivedCurrent ? !!feature.default_on : null,source:key in features?'explicit':'default'};
    }),
    tools: (JSON.parse(profile.tool_allowlist_json) as string[]).map(name => ({name,description:tools.find(tool => tool.name === name)?.description ?? ''})),
    skills: selectedSkills.map(name => ({name,...pick(skills.find(skill => skill.name === name) ?? {}, ['description','source_group']),
      enabled:mode === 'explicit_allowlist' ? true : configuredSkills.includes(name) ? false : derivedCurrent ? true : null,
      source:configuredSkills.includes(name) ? 'explicit' : 'discovered'})),
    skills_selection_mode:mode,
    approval_mode:profile.approval_mode ?? null,
    inherited_approval_rules:derivedCurrent ? capabilities.inherited_approval_rules ?? null : null,
  };
}

/** Read a snapshot only for the current owner, workspace and binding generation. */
export function readSettingsSnapshot(ctx: ImContext, profile: Row, section: SettingsSection): SettingsRead {
  const binding = one(ctx.db, 'SELECT owner_id,node_epoch FROM node_binding_state WHERE node_id=?', profile.node_id);
  const snapshot = one(ctx.db, 'SELECT * FROM agent_settings_snapshots WHERE agent_id=? AND section=?', profile.agent_id, section);
  if (!snapshot || !binding || binding.owner_id !== profile.owner_id || snapshot.owner_id !== profile.owner_id
    || snapshot.node_id !== profile.node_id || snapshot.node_epoch !== binding.node_epoch || snapshot.workspace_root !== profile.workspace_root)
    return {source:'unavailable',captured_at:null,data:null,error:null};
  let data = JSON.parse(snapshot.data_json);
  if (section === 'configuration' && snapshot.profile_version !== profile.profile_version) {
    // Names remain useful; defaults/discovery from a different saved version are not current facts.
    data = configurationDisplay(profile, data, false);
  }
  return {source:'last_known',captured_at:snapshot.captured_at,data,error:null};
}

/** Persist one successful, already fenced projection for a settings section. */
export function writeSettingsSnapshot(ctx: ImContext, profile: Row, section: SettingsSection, data: Row | Row[], capturedAt: string): void {
  const binding = one(ctx.db, 'SELECT node_epoch FROM node_binding_state WHERE node_id=?', profile.node_id)!;
  ctx.db.prepare(`INSERT INTO agent_settings_snapshots(agent_id,section,owner_id,node_id,node_epoch,workspace_root,profile_version,captured_at,data_json)
    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(agent_id,section) DO UPDATE SET owner_id=excluded.owner_id,node_id=excluded.node_id,node_epoch=excluded.node_epoch,
    workspace_root=excluded.workspace_root,profile_version=excluded.profile_version,captured_at=excluded.captured_at,data_json=excluded.data_json`)
    .run(profile.agent_id,section,profile.owner_id,profile.node_id,binding.node_epoch,profile.workspace_root,profile.profile_version,capturedAt,JSON.stringify(data));
}

/** Remove arbitrary runtime diagnostics and retain only each section's public display fields. */
export function settingsSectionDisplay(section: Exclude<SettingsSection, 'configuration'>, profile: Row, response: Row): Row | Row[] {
  if (section === 'cron') {
    if (!Array.isArray(response.jobs)) fail(502, 'Cron result is unavailable');
    return response.jobs.map((job: Row) => pick(job, ['id','name','instruction','schedule','enabled','delete_after_run']));
  }
  if (section === 'plugins') {
    const plugins = response.plugins;
    if (!Array.isArray(plugins?.entries)) fail(502, 'Plugin result is unavailable');
    return {workspace:profile.workspace_root, entries:plugins.entries.map((entry: Row) => ({
      ...pick(entry,['name','display_name','version','description','enabled','state','removable']),
      rows:(entry.rows ?? []).map((row: Row) => pick(row,['id','name'])),diagnostics:[],
    })),diagnostics:[],...(plugins.pending ? {pending:pick(plugins.pending,['action','target','enabled','phase'])} : {})};
  }
  const usage = response.usage;
  if (!Array.isArray(usage?.skills)) fail(502, 'Skill usage result is unavailable');
  return {agent_id:profile.agent_id,node_id:profile.node_id,node_online:true,
    skills:usage.skills.map((skill: Row) => ({...pick(skill,['skill_id','name','source','state','use_count','uses_since_last_B','created_at','last_used_at','archived_at','trend_buckets']),
      session_refs:(skill.session_refs ?? []).map((ref: Row) => pick(ref,['session_id','tool_call_id','timestamp','location']))})),
    heatmap_data:usage.heatmap_data ?? [],health:pick(usage.health ?? {},['created_auto_total','active_auto_total','used_auto_total'])};
}
