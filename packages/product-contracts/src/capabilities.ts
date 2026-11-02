/** Browser-safe declarations shared by configuration clients and owners. */
export interface FeatureDependency {
  key: string;
  default_on: boolean;
  requires: {features: string[]; tools: string[]; skills: string[]};
}
export type CapabilityTarget = {kind: 'feature' | 'tool' | 'skill'; name: string};
export type CapabilityAction = CapabilityTarget & {enabled: boolean};
export interface CapabilityBlock {
  code: 'required_by_feature' | 'fixed_capability' | 'active_tasks' | 'active_schedules' | 'capability_busy' | 'capability_unavailable';
  target: CapabilityTarget;
  required_by?: string[];
}
export interface CapabilityDraft {
  features?: Record<string, boolean>;
  tool_allowlist?: string[];
  skills?: string[] | null;
  skills_selection_mode?: string | null;
  work_mode?: string;
  personal_agent?: unknown;
}
export interface CapabilityCatalog {
  features?: FeatureDependency[];
  tools?: string[];
  skills?: string[];
  fixed_tools?: string[];
}
export const featureDependencies: FeatureDependency[] = [
  {key: 'intelligent_ui', default_on: true, requires: {features: [], tools: ['send_message', 'skill'], skills: ['nano-interactive-ui']}},
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

/** Fixed tools belong to the runtime role, never to a user's click history. */
export function fixedTools(mode: string = 'single_thread', role: 'root' | 'personal' | 'subagent' = 'root', contextEnabled = true): string[] {
  return [
    ...(mode === 'global' && role !== 'subagent' ? ['inbox', 'conversations', 'send_message', 'subagent', ...(role === 'personal' ? ['personal_sources', 'send_user_message'] : [])] : []),
    ...(contextEnabled ? ['notes', 'history', 'new_context', 'get_context_remaining'] : []),
  ];
}

const requiredKey = {feature: 'features', tool: 'tools', skill: 'skills'} as const;
function owners(features: Record<string, boolean>, target: CapabilityTarget, definitions: FeatureDependency[]): string[] {
  return definitions.filter(feature => features[feature.key] && feature.requires[requiredKey[target.kind]].includes(target.name)).map(feature => feature.key);
}
function skillMode(draft: CapabilityDraft): string {
  return draft.skills_selection_mode ?? (draft.skills?.length ? 'explicit_allowlist' : 'default_discovery');
}
function selected(draft: CapabilityDraft, target: CapabilityTarget, catalog: CapabilityCatalog): boolean {
  if (target.kind === 'feature') return !!effectiveFeatures(draft.features, catalog.features)[target.name];
  if (target.kind === 'tool') return draft.tool_allowlist === undefined || draft.tool_allowlist.includes(target.name)
    || (catalog.fixed_tools ?? fixedTools(draft.work_mode, draft.personal_agent ? 'personal' : 'root')).includes(target.name);
  const mode = skillMode(draft);
  return mode === 'default_discovery' || (mode === 'explicit_denylist' ? !draft.skills?.includes(target.name) : !!draft.skills?.includes(target.name));
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
  const features = effectiveFeatures(draft.features, definitions);
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
  const features = effectiveFeatures(draft.features, definitions);
  const fixed = catalog.fixed_tools ?? fixedTools(draft.work_mode, draft.personal_agent ? 'personal' : 'root');
  if (!action.enabled) {
    const required = owners(features, action, definitions);
    if (required.length) return {draft, blocks: [{code: 'required_by_feature', target: {kind: action.kind, name: action.name}, required_by: required}]};
    if (action.kind === 'tool' && fixed.includes(action.name)) return {draft, blocks: [{code: 'fixed_capability', target: {kind: 'tool', name: action.name}}]};
  }
  const next = {...draft, features, tool_allowlist: [...(draft.tool_allowlist ?? catalog.tools ?? definitions.flatMap(feature => feature.requires.tools))], skills: draft.skills ? [...draft.skills] : draft.skills} as T;
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
