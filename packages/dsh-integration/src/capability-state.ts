import { effectiveFeatures, fixedTools, featureDependencies, validateCapabilities, type CapabilityBlock, type CapabilityCatalog, type CapabilityTarget } from '@nano/product-contracts/capabilities';
import type { AgentConfiguration } from './index.js';

/** Convert the runtime projection without inventing a second dependency graph. */
export function capabilityDraft(config: AgentConfiguration) {
  return { features: config.features, tool_allowlist: config.toolAllowlist, skills: config.skillSelection?.names,
    skills_selection_mode: config.skillSelection?.mode, work_mode: config.mode, personal_agent: config.personal };
}
/** Preserve an upgraded explicit tool selection while reporting Dreaming unavailable at runtime. */
export function configurationBlocks(config: AgentConfiguration, previous: AgentConfiguration | undefined, catalog: CapabilityCatalog) {
  const unchangedDreaming = previous && previous.features?.dreaming !== false && config.features?.dreaming !== false
    && validateCapabilities(capabilityDraft(previous), catalog).some(block => block.required_by?.includes('dreaming'));
  return validateCapabilities(capabilityDraft(config), { ...catalog,
    features: (catalog.features ?? featureDependencies).filter(feature => feature.key !== 'dreaming' || config.knowledge?.memoryMode !== 'legacy' && !unchangedDreaming) });
}
export function needsSchedules(config: AgentConfiguration): boolean {
  return config.features?.cron_scheduling === true || config.toolAllowlist === undefined || config.toolAllowlist.some(name => name.startsWith('schedule_'));
}
type Reservation = { operationId: string; fingerprint: string; candidate: string; targets: CapabilityTarget[] };
export interface Preparation { ready: boolean; error_code?: string; message?: string; blocks?: CapabilityBlock[] }

/** Holds only capabilities being withdrawn, from prepare through the existing apply. */
export class CapabilityState {
  constructor(private readonly selection: (config: AgentConfiguration, names: string[]) => string[]) {}
  private readonly reservations = new Map<string, Reservation>();
  private readonly calls = new Map<string, { agentId: string; target: CapabilityTarget }>();
  held(agentId: string, target: CapabilityTarget): boolean {
    return this.reservations.get(agentId)?.targets.some(item => item.kind === target.kind && item.name === target.name) ?? false;
  }
  begin(key: string, agentId: string, target: CapabilityTarget): boolean {
    if (this.held(agentId, target) || target.kind === 'tool' && ['schedule_create', 'schedule_update', 'schedule_run'].includes(target.name) && this.held(agentId, {kind: 'feature', name: 'cron_scheduling'})) return false;
    this.calls.set(key, {agentId, target}); return true;
  }
  end(key: string): void { this.calls.delete(key); }
  busy(agentId: string): CapabilityTarget[] {
    return [...new Map([...this.calls.values()].filter(call => call.agentId === agentId).map(call => [`${call.target.kind}:${call.target.name}`, call.target])).values()];
  }
  release(agentId: string, operationId: string): void {
    if (this.reservations.get(agentId)?.operationId === operationId) this.reservations.delete(agentId);
  }
  matches(agentId: string, operationId: string, fingerprint: string, config: AgentConfiguration): boolean {
    const reservation = this.reservations.get(agentId);
    return reservation?.operationId === operationId && reservation.fingerprint === fingerprint && reservation.candidate === JSON.stringify(config);
  }
  async prepare(input: { operationId: string; fingerprint: string; config: AgentConfiguration }, previous: AgentConfiguration | undefined,
    catalog: CapabilityCatalog, usage: () => Promise<{active_schedules: number; busy: CapabilityTarget[]}>): Promise<Preparation> {
    const {config, operationId, fingerprint} = input;
    const reject = (blocks: CapabilityBlock[], error_code = 'capability_in_use'): Preparation => ({ready: false, error_code, message: 'Capability configuration cannot be applied', blocks});
    const invalid = configurationBlocks(config, previous, catalog);
    if (invalid.length) return reject(invalid, invalid.some(block => block.code === 'capability_unavailable') ? 'capability_unavailable' : 'invalid_capability_dependencies');
    const existing = this.reservations.get(config.agentId);
    if (existing && (existing.operationId !== operationId || existing.fingerprint !== fingerprint || existing.candidate !== JSON.stringify(config))) return reject([{code: 'capability_busy', target: {kind: 'feature', name: 'configuration'}}]);
    if (existing) return {ready: true};
    const targets: CapabilityTarget[] = [];
    if (previous) {
      if (previous.knowledge?.memoryMode === 'legacy' && previous.knowledge.legacyMemory?.enabled !== false
        && (config.knowledge?.memoryMode !== 'legacy' || config.knowledge.legacyMemory?.enabled === false)) targets.push({kind:'feature',name:'memory_curation'});
      const before = effectiveFeatures(previous.features), after = effectiveFeatures(config.features);
      for (const name of Object.keys(before)) if (before[name] && !after[name]) targets.push({kind: 'feature', name});
      const fixed = fixedTools(config.mode, config.personal ? 'personal' : 'root');
      const beforeTools = new Set([...this.selection(previous, catalog.tools ?? []), ...fixed]);
      const afterTools = new Set([...this.selection(config, catalog.tools ?? []), ...fixed]);
      for (const name of beforeTools) if (!afterTools.has(name)) targets.push({kind: 'tool', name});
      const skill = (value: AgentConfiguration, name: string) => value.skillSelection?.mode === 'explicit_allowlist' ? value.skillSelection.names.includes(name) : value.skillSelection?.mode !== 'explicit_denylist' || !value.skillSelection.names.includes(name);
      for (const name of catalog.skills ?? []) if (skill(previous, name) && !skill(config, name)) targets.push({kind: 'skill', name});
    }
    this.reservations.set(config.agentId, {operationId, fingerprint, candidate: JSON.stringify(config), targets});
    if (!targets.length) return {ready: true};
    try {
      const current = await usage();
      const blocks: CapabilityBlock[] = targets.filter(target => current.busy.some(busy => busy.kind === target.kind && busy.name === target.name)).map(target => ({code: 'capability_busy', target}));
      if (targets.some(target => target.kind === 'feature' && target.name === 'cron_scheduling') && current.active_schedules > 0) blocks.unshift({code: 'active_schedules', target: {kind: 'feature', name: 'cron_scheduling'}});
      if (blocks.length) { this.release(config.agentId, operationId); return reject(blocks); }
      return {ready: true};
    } catch (error) { this.release(config.agentId, operationId); throw error; }
  }
}
