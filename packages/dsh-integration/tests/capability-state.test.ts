import {expect, it} from 'vitest';
import {CapabilityState} from '../src/capability-state.js';
import {featureDependencies} from '@nano/product-contracts/capabilities';
const features = Object.fromEntries(featureDependencies.map(feature => [feature.key, false]));
const config = {agentId: 'a', revision: '1', provider: 'p', model: 'm', features, toolAllowlist: ['read', 'memory', 'schedule_create']};
const catalog = {tools: ['read', 'memory', 'schedule_create'], skills: []};

it('rejects withdrawal of a live tool while allowing unrelated edits and reserves new admission until release', async () => {
  const state = new CapabilityState((value, names) => names.filter(name => value.toolAllowlist === undefined || value.toolAllowlist.includes(name)));
  expect(state.begin('call', 'a', {kind: 'tool', name: 'memory'})).toBe(true);
  const usage = async () => ({active_schedules: 0, busy: state.busy('a')});
  const candidate = {...config, toolAllowlist: ['read', 'schedule_create']};
  expect(await state.prepare({operationId: 'close', fingerprint: '2', config: candidate}, config, catalog, usage)).toMatchObject({ready: false, blocks: [{code: 'capability_busy', target: {kind: 'tool', name: 'memory'}}]});
  expect(await state.prepare({operationId: 'rename', fingerprint: '3', config: {...config, revision: '3'}}, config, catalog, usage)).toMatchObject({ready: true});
  state.release('a', 'rename'); state.end('call');
  expect(await state.prepare({operationId: 'close', fingerprint: '2', config: candidate}, config, catalog, usage)).toMatchObject({ready: true});
  expect(state.begin('later', 'a', {kind: 'tool', name: 'memory'})).toBe(false);
  expect(state.begin('other-agent', 'b', {kind: 'tool', name: 'memory'})).toBe(true);
  expect(state.begin('read', 'a', {kind: 'tool', name: 'read'})).toBe(true);
  state.release('a', 'wrong'); expect(state.held('a', {kind: 'tool', name: 'memory'})).toBe(true);
  state.release('a', 'close'); expect(state.begin('later', 'a', {kind: 'tool', name: 'memory'})).toBe(true);
});

it('holds Cron admission before checking schedules and retains the original selection on an active schedule', async () => {
  const state = new CapabilityState((value, names) => names.filter(name => value.toolAllowlist === undefined || value.toolAllowlist.includes(name)));
  const previous = {...config, features: {...features, cron_scheduling: true}};
  let checked = false;
  expect(await state.prepare({operationId: 'close', fingerprint: '2', config}, previous, catalog, async () => {
    checked = true;
    expect(state.begin('new-schedule', 'a', {kind: 'tool', name: 'schedule_create'})).toBe(false);
    return {active_schedules: 1, busy: []};
  })).toMatchObject({ready: false, blocks: [{code: 'active_schedules'}]});
  expect(checked).toBe(true);
  expect(state.begin('new-schedule', 'a', {kind: 'tool', name: 'schedule_create'})).toBe(true);
});
