import { describe, expect, it } from 'vitest';
import { changeCapability, effectiveFeatures, featureClosure, featureDependencies, fixedTools, validateCapabilities } from '../src/capabilities.js';

const off = Object.fromEntries(['intelligent_ui', 'task_graph', 'dreaming', 'cron_scheduling', 'heartbeat'].map(key => [key, false]));
const draft = () => ({features: {...off}, tool_allowlist: [] as string[], skills: [] as string[], skills_selection_mode: 'explicit_allowlist'});
describe('capability selections', () => {
  it('expands Task into the full Cron capability and keeps Cron when Task closes', () => {
    const opened = changeCapability(draft(), {kind: 'feature', name: 'task_graph', enabled: true}, {});
    expect(opened.blocks).toEqual([]);
    expect(opened.draft.features).toMatchObject({task_graph: true, cron_scheduling: true});
    expect(opened.draft.tool_allowlist).toEqual(expect.arrayContaining(['task_graph', 'schedule_create', 'schedule_history']));
    const blocked = changeCapability(opened.draft, {kind: 'feature', name: 'cron_scheduling', enabled: false}, {});
    expect(blocked.blocks[0]).toMatchObject({code: 'required_by_feature', required_by: ['task_graph']});
    expect(blocked.draft).toBe(opened.draft);
    const closed = changeCapability(opened.draft, {kind: 'feature', name: 'task_graph', enabled: false}, {});
    expect(closed.draft.features.cron_scheduling).toBe(true);
    expect(closed.draft.tool_allowlist).not.toContain('task_graph');
  });
  it('preserves shared read and skill dependencies, then allows a tool alone', () => {
    let state = draft();
    for (const name of ['dreaming', 'heartbeat']) state = changeCapability(state, {kind: 'feature', name, enabled: true}, {}).draft;
    state = changeCapability(state, {kind: 'feature', name: 'dreaming', enabled: false}, {}).draft;
    expect(state.tool_allowlist).toContain('read');
    expect(state.tool_allowlist).toContain('memory_maintenance');
    state = changeCapability(state, {kind: 'tool', name: 'memory', enabled: true}, {}).draft;
    expect(state.features.dreaming).toBe(false);
    expect(validateCapabilities(state)).toEqual([]);
  });
  it('turns off automatic Dreaming without withdrawing immediate memory tools', () => {
    const opened = changeCapability(draft(), {kind:'feature',name:'dreaming',enabled:true}, {}).draft;
    const closed = changeCapability(opened, {kind:'feature',name:'dreaming',enabled:false}, {}).draft;
    expect(closed.features.dreaming).toBe(false);
    expect(closed.tool_allowlist).toEqual(opened.tool_allowlist);
  });
  it('keeps an upgraded unavailable Dreaming selection from granting tools during unrelated edits', () => {
    const initial = {...draft(), features:{...off,dreaming:true},tool_allowlist:['read']};
    const changed = changeCapability(initial,{kind:'feature',name:'heartbeat',enabled:true},{});
    expect(changed.blocks).toEqual([]);
    expect(changed.draft.tool_allowlist).toEqual(['read']);
    expect(changed.draft.features.dreaming).toBe(true);
  });
  it('protects required Skills and converts discovery to a denylist only when withdrawing', () => {
    const initial = {...draft(), skills_selection_mode: 'default_discovery'};
    const opened = changeCapability(initial, {kind: 'feature', name: 'intelligent_ui', enabled: true}, {}).draft;
    expect(changeCapability(opened, {kind: 'skill', name: 'nano-interactive-ui', enabled: false}, {}).blocks[0].code).toBe('required_by_feature');
    const closed = changeCapability(opened, {kind: 'feature', name: 'intelligent_ui', enabled: false}, {}).draft;
    expect(closed.skills_selection_mode).toBe('explicit_denylist');
    expect(closed.skills).toContain('nano-interactive-ui');
  });
  it('rejects an unavailable dependency atomically, without treating deselection as unavailability', () => {
    const initial = draft();
    expect(changeCapability(initial, {kind: 'feature', name: 'dreaming', enabled: true}, {tools: ['memory_maintenance']}).draft).toBe(initial);
    expect(changeCapability(initial, {kind: 'feature', name: 'dreaming', enabled: true}, {tools: ['memory_maintenance', 'read', 'write', 'edit']}).blocks).toEqual([]);
    expect(validateCapabilities({...initial, features: {...off, task_graph: true}, tool_allowlist: ['task_graph']})).toContainEqual({code: 'required_by_feature', target: {kind: 'feature', name: 'cron_scheduling'}, required_by: ['task_graph']});
  });
  it('keeps root fixed tools scoped to mode and role and protects context tools', () => {
    expect(fixedTools('global', 'personal')).toEqual(expect.arrayContaining(['personal_sources','send_user_message']));
    expect(fixedTools('global', 'root')).not.toContain('send_user_message');
    expect(fixedTools('global', 'subagent')).not.toContain('send_user_message');
    expect(changeCapability({...draft(),work_mode:'global',personal_agent:{}}, {kind:'tool',name:'send_user_message',enabled:false}, {}).blocks[0].code).toBe('fixed_capability');
    expect(fixedTools('global', 'subagent')).not.toContain('send_message');
    expect(fixedTools('single_thread', 'root', false)).toEqual([]);
    expect(changeCapability(draft(), {kind: 'tool', name: 'notes', enabled: false}, {fixed_tools: ['notes']}).blocks[0].code).toBe('fixed_capability');
    expect(featureClosure(effectiveFeatures()).cron_scheduling).toBe(true);
  });
  it('has only known, acyclic Feature dependencies', () => {
    const visit = (key: string, path: string[]) => {
      expect(path).not.toContain(key);
      const feature = featureDependencies.find(item => item.key === key);
      expect(feature).toBeDefined();
      feature!.requires.features.forEach(next => visit(next, [...path, key]));
    };
    featureDependencies.forEach(feature => visit(feature.key, []));
  });
});
