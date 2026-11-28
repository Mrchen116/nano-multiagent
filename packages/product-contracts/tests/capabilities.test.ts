import { describe, expect, it } from 'vitest';
import {
  changeCapability,
  definitionsForRole,
  effectiveCapabilityFeatures,
  effectiveFeatures,
  effectiveSelectedTools,
  featureClosure,
  featureDependencies,
  fixedTools,
  sanitizeStaticToolAllowlist,
  validateCapabilities,
} from '../src/capabilities.js';
import { agentConfigurationFingerprint } from '../src/configuration.js';

const off = Object.fromEntries(['intelligent_ui', 'plugin_management', 'task_graph', 'dreaming', 'cron_scheduling', 'heartbeat'].map(key => [key, false]));
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
  it('preserves Heartbeat read and independently selected maintenance tools', () => {
    let state = {...draft(),tool_allowlist:['memory_maintenance']};
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
  it('keeps Dreaming independent of foreground tools during unrelated edits', () => {
    const initial = {...draft(), features:{...off,dreaming:true},tool_allowlist:['read']};
    const changed = changeCapability(initial,{kind:'feature',name:'heartbeat',enabled:true},{});
    expect(changed.blocks).toEqual([]);
    expect(changed.draft.tool_allowlist).toEqual(['read']);
    expect(changed.draft.features.dreaming).toBe(true);
  });
  it('enables automatic Dreaming without granting foreground tools', () => {
    const opened = changeCapability(draft(), {kind:'feature', name:'dreaming', enabled:true}, {tools:[]});
    expect(opened.blocks).toEqual([]);
    expect(opened.draft.tool_allowlist).toEqual([]);
    expect(validateCapabilities(opened.draft, {tools:[]})).toEqual([]);
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
    expect(changeCapability(initial, {kind: 'feature', name: 'heartbeat', enabled: true}, {tools: []}).draft).toBe(initial);
    expect(changeCapability(initial, {kind: 'feature', name: 'heartbeat', enabled: true}, {tools: ['read']}).blocks).toEqual([]);
    expect(validateCapabilities({...initial, features: {...off, task_graph: true}, tool_allowlist: ['task_graph']})).toContainEqual({code: 'required_by_feature', target: {kind: 'feature', name: 'cron_scheduling'}, required_by: ['task_graph']});
  });
  it('keeps root fixed tools scoped to mode and role and protects context tools', () => {
    expect(fixedTools('global', 'personal')).toEqual(expect.arrayContaining(['personal_sources','send_user_message']));
    expect(fixedTools('global', 'root')).not.toContain('send_user_message');
    expect(fixedTools('global', 'subagent')).not.toContain('send_user_message');
    expect(changeCapability({...draft(),work_mode:'global',personal_agent:{}}, {kind:'tool',name:'send_user_message',enabled:false}, {}).blocks[0].code).toBe('fixed_capability');
    expect(fixedTools('global', 'subagent')).not.toContain('send_message');
    expect(fixedTools('single_thread', 'root', false)).toEqual([]);
    // An absent mode describes an unknown or legacy Agent, not a new global one.
    expect(fixedTools(undefined, 'root', false)).toEqual([]);
    expect(changeCapability(draft(), {kind: 'tool', name: 'notes', enabled: false}, {fixed_tools: ['notes']}).blocks[0].code).toBe('fixed_capability');
    expect(featureClosure(effectiveFeatures()).cron_scheduling).toBe(true);
  });
  it('lets the PA creation tool close and reopen independently of its Skill', () => {
    const initial = {...draft(),work_mode:'global',personal_agent:{},tool_allowlist:['agent_creation'],skills:['nano-agent-creation']};
    const closed = changeCapability(initial,{kind:'tool',name:'agent_creation',enabled:false},{});
    expect(closed.blocks).toEqual([]);
    expect(closed.draft.tool_allowlist).not.toContain('agent_creation');
    expect(closed.draft.skills).toEqual(initial.skills);
    const reopened = changeCapability(closed.draft,{kind:'tool',name:'agent_creation',enabled:true},{});
    expect(reopened.blocks).toEqual([]);
    expect(reopened.draft.tool_allowlist).toContain('agent_creation');
  });
  it('manages plugin_management dependencies and allows standalone inspect tools when closed', () => {
    const opened = changeCapability(draft(), {kind: 'feature', name: 'plugin_management', enabled: true}, {});
    expect(opened.blocks).toEqual([]);
    expect(opened.draft.features.plugin_management).toBe(true);
    expect(opened.draft.tool_allowlist).toEqual(expect.arrayContaining(['plugin_manager', 'cordis_inspect_list', 'cordis_inspect_query']));
    expect(opened.draft.skills).toContain('nano-plugin-development');
    expect(changeCapability(opened.draft, {kind: 'tool', name: 'cordis_inspect_list', enabled: false}, {}).blocks[0]).toMatchObject({
      code: 'required_by_feature',
      required_by: ['plugin_management'],
    });
    expect(changeCapability(opened.draft, {kind: 'skill', name: 'nano-plugin-development', enabled: false}, {}).blocks[0]).toMatchObject({
      code: 'required_by_feature',
      required_by: ['plugin_management'],
    });
    const closed = changeCapability(opened.draft, {kind: 'feature', name: 'plugin_management', enabled: false}, {}).draft;
    expect(closed.features.plugin_management).toBe(false);
    expect(closed.tool_allowlist).toEqual([]);
    expect(closed.skills).not.toContain('nano-plugin-development');
    const singleInspect = changeCapability(closed, {kind: 'tool', name: 'cordis_inspect_list', enabled: true}, {}).draft;
    expect(singleInspect.features.plugin_management).toBe(false);
    expect(singleInspect.tool_allowlist).toEqual(['cordis_inspect_list']);
    expect(validateCapabilities(singleInspect)).toEqual([]);
  });
  it('preserves pre-feat-791 default and restricted configs without disk migration', () => {
    const pre791Off = {intelligent_ui: false, task_graph: false, dreaming: false, cron_scheduling: false, heartbeat: false};
    const legacyAllowed = {features: {...pre791Off}, tool_allowlist: ['plugin_manager', 'read'], skills: [], skills_selection_mode: 'default_discovery'};
    expect(effectiveCapabilityFeatures(legacyAllowed).plugin_management).toBe(true);
    expect(effectiveSelectedTools(legacyAllowed)).toEqual(['plugin_manager', 'read', 'cordis_inspect_list', 'cordis_inspect_query']);
    expect(validateCapabilities(legacyAllowed)).toEqual([]);
    const edited = changeCapability(legacyAllowed, {kind: 'feature', name: 'heartbeat', enabled: true}, {
      tools: ['plugin_manager', 'read', 'cordis_inspect_list', 'cordis_inspect_query'],
      skills: ['nano-plugin-development'],
    });
    expect(edited.blocks).toEqual([]);
    expect(edited.draft.features.plugin_management).toBe(true);
    expect(edited.draft.tool_allowlist).toEqual(expect.arrayContaining(['cordis_inspect_list', 'cordis_inspect_query']));

    const legacyRestricted = {features: {intelligent_ui: false, task_graph: false, dreaming: false}, tool_allowlist: ['read'], skills: [], skills_selection_mode: 'explicit_allowlist'};
    expect(effectiveCapabilityFeatures(legacyRestricted).plugin_management).toBe(false);
    expect(effectiveSelectedTools(legacyRestricted)).toEqual(['read']);
    expect(validateCapabilities(legacyRestricted)).toEqual([]);

    const legacyExplicitSkillsMissing = {features: {intelligent_ui: false, task_graph: false, dreaming: false}, tool_allowlist: ['plugin_manager'], skills: ['other-skill'], skills_selection_mode: 'explicit_allowlist'};
    expect(effectiveCapabilityFeatures(legacyExplicitSkillsMissing).plugin_management).toBe(false);
    expect(validateCapabilities(legacyExplicitSkillsMissing)).toEqual([]);

    const workspacelessCatalog = {tools: ['read'], skills: []};
    expect(effectiveCapabilityFeatures(legacyAllowed, featureDependencies, workspacelessCatalog).plugin_management).toBe(false);
    expect(validateCapabilities({features: {intelligent_ui: false, task_graph: false, dreaming: false}, tool_allowlist: ['read']}, workspacelessCatalog)).toEqual([]);
  });
  it('reports plugin-attributed blocks and sanitizes static allowlists by mode and role', () => {
    const catalog = {
      fixed_tools: ['notes'],
      plugin_tools: {
        notes: {bundle: 'dsh-agent-context', title: '上下文整理', enabled: true},
        roll_dice: {bundle: 'dice-plugin', title: 'Dice Plugin', enabled: false},
      },
    };
    expect(changeCapability(draft(), {kind: 'tool', name: 'notes', enabled: false}, catalog).blocks).toEqual([
      {code: 'provided_by_plugin', target: {kind: 'tool', name: 'notes'}, plugin: '上下文整理'},
    ]);
    expect(changeCapability(draft(), {kind: 'tool', name: 'roll_dice', enabled: true}, catalog).blocks).toEqual([
      {code: 'plugin_requires_manager', target: {kind: 'tool', name: 'roll_dice'}, plugin: 'Dice Plugin'},
    ]);
    expect(sanitizeStaticToolAllowlist(['read', 'send_message', 'inbox', 'notes', 'roll_dice', 'memory'], 'single_thread', 'root', ['roll_dice']))
      .toEqual(['read', 'send_message', 'inbox', 'memory']);
    expect(sanitizeStaticToolAllowlist(['read', 'send_message', 'inbox', 'notes', 'personal_sources'], 'global', 'root'))
      .toEqual(['read', 'personal_sources']);
    expect(sanitizeStaticToolAllowlist(['read', 'send_message', 'inbox', 'notes', 'personal_sources', 'send_user_message'], 'global', 'personal'))
      .toEqual(['read']);
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

  it('scopes proactive_planning to global-mode Agents (PA and ordinary Global) while keeping single_thread clean and preserving legacy fingerprints', () => {
    expect(definitionsForRole(false, undefined, 'single_thread').map(item => item.key)).not.toContain('proactive_planning');
    expect(definitionsForRole(false, undefined, 'global').map(item => item.key)).toContain('proactive_planning');
    expect(definitionsForRole(true).map(item => item.key)).toContain('proactive_planning');
    expect(effectiveFeatures({}, definitionsForRole(false, undefined, 'single_thread'))).not.toHaveProperty('proactive_planning');
    expect(effectiveFeatures({}, definitionsForRole(false, undefined, 'global')).proactive_planning).toBe(true);
    expect(effectiveFeatures({}, definitionsForRole(true)).proactive_planning).toBe(true);

    // Single-thread explicitly enabling proactive_planning is rejected with capability_unavailable.
    expect(validateCapabilities({ work_mode: 'single_thread', features: { task_graph: true, cron_scheduling: true, proactive_planning: true } })).toContainEqual({
      code: 'capability_unavailable',
      target: { kind: 'feature', name: 'proactive_planning' },
    });

    // Single-thread can disable task_graph without proactive_planning blocking it.
    const singleThreadWithTask = { ...draft(), work_mode: 'single_thread', features: { ...off, task_graph: true, cron_scheduling: true }, tool_allowlist: ['task_graph', 'schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'] };
    const singleThreadTaskClosed = changeCapability(singleThreadWithTask, { kind: 'feature', name: 'task_graph', enabled: false }, {});
    expect(singleThreadTaskClosed.blocks).toEqual([]);
    expect(singleThreadTaskClosed.draft.features.task_graph).toBe(false);

    // Legacy PA and legacy Global Agent that explicitly disabled task_graph degrade cleanly.
    const legacyTaskOff = { work_mode: 'global', personal_agent: { bindingId: 'b1', ownerId: 'u1', conversationId: 'c1', epoch: 1 }, features: { task_graph: false }, tool_allowlist: ['send_message', 'skill'] };
    expect(effectiveFeatures(legacyTaskOff.features, definitionsForRole(true), legacyTaskOff).proactive_planning).toBe(false);
    expect(validateCapabilities(legacyTaskOff)).toEqual([]);
    const legacyGlobalTaskOff = { work_mode: 'global', features: { task_graph: false }, tool_allowlist: ['skill'] };
    expect(effectiveFeatures(legacyGlobalTaskOff.features, definitionsForRole(false, undefined, 'global'), legacyGlobalTaskOff).proactive_planning).toBe(false);
    expect(validateCapabilities(legacyGlobalTaskOff)).toEqual([]);

    // Active Global Agent and PA require turning off proactive_planning before disabling task_graph.
    for (const activeGlobal of [
      { ...draft(), work_mode: 'global', personal_agent: legacyTaskOff.personal_agent, features: { ...off, task_graph: true, cron_scheduling: true, proactive_planning: true }, tool_allowlist: ['task_graph', 'schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'] },
      { ...draft(), work_mode: 'global', features: { ...off, task_graph: true, cron_scheduling: true, proactive_planning: true }, tool_allowlist: ['task_graph', 'schedule_create', 'schedule_list', 'schedule_update', 'schedule_delete', 'schedule_run', 'schedule_history'] },
    ]) {
      expect(changeCapability(activeGlobal, { kind: 'feature', name: 'task_graph', enabled: false }, {}).blocks[0]).toMatchObject({ code: 'required_by_feature', required_by: ['proactive_planning'] });
      const afterProactiveOff = changeCapability(activeGlobal, { kind: 'feature', name: 'proactive_planning', enabled: false }, {}).draft;
      expect(afterProactiveOff.features.proactive_planning).toBe(false);
      expect(afterProactiveOff.tool_allowlist).toContain('task_graph');
      expect(changeCapability(afterProactiveOff, { kind: 'feature', name: 'task_graph', enabled: false }, {}).blocks).toEqual([]);
    }

    // Stored fingerprint without proactive_planning key stays bit-identical.
    const basePayload = { agent_id: 'pa_1', work_mode: 'global', personal_agent: legacyTaskOff.personal_agent, features: { task_graph: true, cron_scheduling: true } };
    expect(agentConfigurationFingerprint(basePayload)).toBe('2e9a8fd6fc535195d0a1c038992840e8118b3d83d6a107c7c6647ae85bd817aa');
  });
});
