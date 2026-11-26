/** Browser-safe declarations shared by configuration clients and owners. */
export interface FeatureDependency {
  key: string;
  default_on: boolean;
  requires: {features: string[]; tools: string[]; skills: string[]};
}
export type CapabilityTarget = {kind: 'feature' | 'tool' | 'skill'; name: string};
export type CapabilityAction = CapabilityTarget & {enabled: boolean};
export interface CapabilityBlock {
  code:
    | 'required_by_feature'
    | 'fixed_capability'
    | 'provided_by_plugin'
    | 'plugin_requires_manager'
    | 'active_tasks'
    | 'active_schedules'
    | 'capability_busy'
    | 'capability_unavailable';
  target: CapabilityTarget;
  required_by?: string[];
  plugin?: string;
}
export interface CapabilityDraft {
  features?: Record<string, boolean>;
  tool_allowlist?: string[];
  skills?: string[] | null;
  skills_selection_mode?: string | null;
  work_mode?: string;
  personal_agent?: unknown;
}
export interface PluginToolCatalogEntry {
  bundle?: string | null;
  title?: string | Record<string, string> | null;
  enabled?: boolean | null;
}
export interface CapabilityCatalog {
  features?: FeatureDependency[];
  tools?: string[];
  skills?: string[];
  fixed_tools?: string[];
  plugin_tools?: Record<string, PluginToolCatalogEntry>;
}
export const pluginInspectTools = ['cordis_inspect_list', 'cordis_inspect_query'] as const;
export const contextWindowTools = ['notes', 'history', 'new_context', 'get_context_remaining'] as const;
export const featureDependencies: FeatureDependency[] = [
  {key: 'intelligent_ui', default_on: true, requires: {features: [], tools: ['send_message', 'skill'], skills: ['nano-interactive-ui']}},
  {key: 'plugin_management', default_on: true, requires: {features: [], tools: ['plugin_manager', ...pluginInspectTools], skills: ['nano-plugin-development']}},
  {key: 'task_graph', default_on: true, requires: {features: ['cron_scheduling'], tools: ['task_graph'], skills: []}},
  {key: 'dreaming', default_on: true, requires: {features: [], tools: [], skills: []}},
  {key: 'cron_scheduling', default_on: false, requires: {features: [], tools: ['schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'], skills: []}},
  {key: 'heartbeat', default_on: false, requires: {features: [], tools: ['read'], skills: []}},
];

/** Resolve declared defaults without repairing the submitted dependency graph. */
export function effectiveFeatures(features: Record<string, boolean> = {}, definitions = featureDependencies): Record<string, boolean> {
  return {...Object.fromEntries(definitions.map(feature => [feature.key, feature.default_on])), ...Object.fromEntries(Object.entries(features).filter(([key]) => definitions.some(feature => feature.key === key) || !['memory_curation', 'skill_creation'].includes(key)))};
}

/** Expand only Feature dependencies for a newly generated default selection. */
export function featureClosure(features: Record<string, boolean> = {}, definitions = featureDependencies): Record<string, boolean> {
  const result = effectiveFeatures(features, definitions);
  const enable = (key: string) => {
    result[key] = true;
    for (const required of definitions.find(feature => feature.key === key)?.requires.features ?? []) if (!result[required]) enable(required);
  };
  for (const key of Object.keys(result)) if (result[key]) enable(key);
  return result;
}

/** Fixed tools belong to the runtime role, never to a user's click history.
 *
 * Args:
 *   mode: Agent work mode; an unknown or absent mode has no cross-chat fixed tools.
 */
export function fixedTools(mode: string | undefined, role: 'root' | 'personal' | 'subagent' = 'root', contextEnabled = true): string[] {
  return [
    ...(mode === 'global' && role !== 'subagent' ? ['inbox', 'conversations', 'read_messages', 'search_messages', 'threads', 'send_message', 'download_attachment', 'delegate_worker', ...(role === 'personal' ? ['personal_sources', 'send_user_message'] : [])] : []),
    ...(contextEnabled ? [...contextWindowTools] : []),
  ];
}

function skillMode(draft: CapabilityDraft): string {
  return draft.skills_selection_mode ?? (draft.skills?.length ? 'explicit_allowlist' : 'default_discovery');
}

/** Check whether a Skill is enabled in the draft's active selection mode. */
export function skillSelected(draft: CapabilityDraft, name: string): boolean {
  const mode = skillMode(draft);
  return mode === 'default_discovery' || (mode === 'explicit_denylist' ? !draft.skills?.includes(name) : !!draft.skills?.includes(name));
}

/** Resolve effective Feature flags, preserving pre-feat-791 plugin_manager restrictions without disk migration. */
export function effectiveCapabilityFeatures(
  draft: CapabilityDraft,
  definitions = featureDependencies,
  catalog: CapabilityCatalog = {},
): Record<string, boolean> {
  const result = effectiveFeatures(draft.features, definitions);
  const pluginFeature = definitions.find(feature => feature.key === 'plugin_management');
  if (pluginFeature && draft.features?.plugin_management === undefined) {
    const hasManager = draft.tool_allowlist === undefined || draft.tool_allowlist.includes('plugin_manager');
    const hasSkills = pluginFeature.requires.skills.every(name => skillSelected(draft, name));
    const toolsAvailable = pluginFeature.requires.tools.every(name => catalog.tools?.includes(name) ?? true);
    const skillsAvailable = pluginFeature.requires.skills.every(name => catalog.skills?.includes(name) ?? true);
    result.plugin_management = hasManager && hasSkills && toolsAvailable && skillsAvailable;
  }
  return result;
}

/** Expand implicit companion inspect tools only for pre-feat-791 configs that allowed plugin_manager. */
export function effectiveSelectedTools(draft: CapabilityDraft, catalog: CapabilityCatalog = {}): string[] {
  const definitions = catalog.features ?? featureDependencies;
  const base = draft.tool_allowlist ?? catalog.tools ?? definitions.flatMap(feature => feature.requires.tools);
  if (draft.features?.plugin_management === undefined && (draft.tool_allowlist === undefined || base.includes('plugin_manager'))) {
    const availableInspect = pluginInspectTools.filter(name => catalog.tools?.includes(name) ?? true);
    return [...new Set([...base, ...availableInspect])];
  }
  return [...new Set(base)];
}

/** Strip mode-fixed, context-plugin, and workspace-plugin tool names from persisted static allowlists. */
export function sanitizeStaticToolAllowlist(
  tools: readonly string[],
  workMode?: string,
  role: 'root' | 'personal' | 'subagent' = 'root',
  workspaceToolNames: Iterable<string> = [],
): string[] {
  const excluded = new Set<string>([
    ...fixedTools(workMode, role, false),
    ...contextWindowTools,
    ...workspaceToolNames,
  ]);
  return [...new Set(tools.map(name => name.trim()).filter(name => Boolean(name) && !excluded.has(name)))];
}

const requiredKey = {feature: 'features', tool: 'tools', skill: 'skills'} as const;
function owners(features: Record<string, boolean>, target: CapabilityTarget, definitions: FeatureDependency[]): string[] {
  return definitions.filter(feature => features[feature.key] && feature.requires[requiredKey[target.kind]].includes(target.name)).map(feature => feature.key);
}
function selected(draft: CapabilityDraft, target: CapabilityTarget, catalog: CapabilityCatalog): boolean {
  const definitions = catalog.features ?? featureDependencies;
  if (target.kind === 'feature') return !!effectiveCapabilityFeatures(draft, definitions, catalog)[target.name];
  if (target.kind === 'tool') return draft.tool_allowlist === undefined || effectiveSelectedTools(draft, catalog).includes(target.name)
    || (catalog.fixed_tools ?? fixedTools(draft.work_mode, draft.personal_agent ? 'personal' : 'root')).includes(target.name);
  return skillSelected(draft, target.name);
}
function setSkill(draft: CapabilityDraft, name: string, enabled: boolean): void {
  const mode = skillMode(draft);
  if (mode === 'default_discovery' && enabled) return;
  draft.skills_selection_mode = mode === 'default_discovery' ? 'explicit_denylist' : mode;
  const names = new Set(mode === 'default_discovery' ? [] : draft.skills ?? []);
  if (enabled === (draft.skills_selection_mode === 'explicit_allowlist')) names.add(name); else names.delete(name);
  draft.skills = [...names];
}

/** Validate a final snapshot; API validation never infers omitted click actions. */
export function validateCapabilities(draft: CapabilityDraft, catalog: CapabilityCatalog = {}): CapabilityBlock[] {
  const definitions = catalog.features ?? featureDependencies;
  const features = effectiveCapabilityFeatures(draft, definitions, catalog);
  const blocks: CapabilityBlock[] = [];
  const add = (code: CapabilityBlock['code'], target: CapabilityTarget, owner: string) => {
    const existing = blocks.find(block => block.code === code && block.target.kind === target.kind && block.target.name === target.name);
    if (existing) existing.required_by!.push(owner); else blocks.push({code, target, required_by: [owner]});
  };
  for (const feature of definitions) {
    if (!features[feature.key]) continue;
    for (const kind of ['feature', 'tool', 'skill'] as const) {
      for (const name of feature.requires[requiredKey[kind]]) {
        const target = {kind, name};
        const available = kind === 'feature' ? definitions.some(item => item.key === name)
          : catalog[requiredKey[kind]]?.includes(name) ?? true;
        if (!available) add('capability_unavailable', target, feature.key);
        else if (!selected(draft, target, catalog)) add('required_by_feature', target, feature.key);
      }
    }
  }
  return blocks;
}

/** Apply one UI action atomically, retaining fixed and shared dependencies. */
export function changeCapability<T extends CapabilityDraft>(draft: T, action: CapabilityAction, catalog: CapabilityCatalog): {draft: T; blocks: CapabilityBlock[]} {
  const definitions = catalog.features ?? featureDependencies;
  const features = effectiveCapabilityFeatures(draft, definitions, catalog);
  const fixed = catalog.fixed_tools ?? fixedTools(draft.work_mode, draft.personal_agent ? 'personal' : 'root');
  if (action.kind === 'tool' && catalog.plugin_tools && Object.hasOwn(catalog.plugin_tools, action.name)) {
    const pluginEntry = catalog.plugin_tools[action.name]!;
    const pluginName = typeof pluginEntry.title === 'string' && pluginEntry.title.trim() ? pluginEntry.title.trim() : pluginEntry.bundle ?? undefined;
    const code = !action.enabled || fixed.includes(action.name) || pluginEntry.enabled !== false
      ? 'provided_by_plugin'
      : 'plugin_requires_manager';
    return {draft, blocks: [{code, target: {kind: 'tool', name: action.name}, ...(pluginName ? {plugin: pluginName} : {})}]};
  }
  if (!action.enabled) {
    const required = owners(features, action, definitions);
    if (required.length) return {draft, blocks: [{code: 'required_by_feature', target: {kind: action.kind, name: action.name}, required_by: required}]};
    if (action.kind === 'tool' && fixed.includes(action.name)) return {draft, blocks: [{code: 'fixed_capability', target: {kind: 'tool', name: action.name}}]};
  }
  const next = {...draft, features, tool_allowlist: effectiveSelectedTools(draft, catalog), skills: draft.skills ? [...draft.skills] : draft.skills} as T;
  const tools = new Set(next.tool_allowlist);
  if (action.kind === 'feature') {
    const feature = definitions.find(item => item.key === action.name);
    if (!feature) return {draft, blocks: [{code: 'capability_unavailable', target: {kind: 'feature', name: action.name}}]};
    features[action.name] = action.enabled;
    if (action.enabled) {
      Object.assign(features, featureClosure(features, definitions));
      for (const dependency of definitions.filter(item => features[item.key])) {
        dependency.requires.tools.forEach(tool => tools.add(tool));
        dependency.requires.skills.forEach(skill => setSkill(next, skill, true));
      }
    } else {
      for (const tool of feature.requires.tools) if (!fixed.includes(tool) && !owners(features, {kind: 'tool', name: tool}, definitions).length) tools.delete(tool);
      for (const skill of feature.requires.skills) if (!owners(features, {kind: 'skill', name: skill}, definitions).length) setSkill(next, skill, false);
    }
  } else if (action.kind === 'tool') {
    if (action.enabled) tools.add(action.name); else tools.delete(action.name);
  } else setSkill(next, action.name, action.enabled);
  next.tool_allowlist = [...tools];
  const blocks = validateCapabilities(next, catalog);
  return {draft: blocks.length ? draft : next, blocks};
}
