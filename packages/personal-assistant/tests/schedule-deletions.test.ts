import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import type { AgentConfiguration, RuntimePort } from '@nano/product-contracts';
import { ScheduleDeletions, type ScheduleDeletionIntent } from '../src/schedule-deletions.js';
import { NodeStore } from '../src/store.js';

type Identity = Parameters<ScheduleDeletions['delete']>[0];
type NativeSchedule = { agentId: string; id: string; sessionId: string; name: string };
type NativeCommand = { agentId: string; action: string; sessionId?: string; args?: { id: string } };
const agents: AgentConfiguration[] = ['a', 'b'].map(agentId => ({
  agentId, mode: 'global', revision: '1', workspace: '/tmp', provider: 'unused', model: 'unused',
}));
const identity: Identity = { operationId: 'delete-1', agentId: 'a', scheduleId: 'schedule-1', actor: { kind: 'user', id: 'owner' } };
const schedule: NativeSchedule = { agentId: 'a', id: 'schedule-1', sessionId: 'native-session', name: 'Native reminder title' };

function nativeRuntime(initial: NativeSchedule[] = [schedule]) {
  const state = {
    schedules: structuredClone(initial), commands: [] as NativeCommand[], catalogError: undefined as Error | undefined,
    deleteError: undefined as Error | undefined, deleteResult: 'deleted' as 'deleted' | 'retained' | 'missing',
    beforeDelete: undefined as (() => void) | undefined,
  };
  const runtime: RuntimePort = {
    onNotification: () => () => {},
    async request(method, value) {
      if (method !== 'schedule.command') throw new Error(`Unexpected runtime request: ${method}`);
      const command = value as NativeCommand;
      state.commands.push(structuredClone(command));
      if (command.action === 'jobs') {
        if (state.catalogError) throw state.catalogError;
        return state.schedules.filter(item => item.agentId === command.agentId).map(({ agentId: _agentId, ...item }) => item);
      }
      if (command.action !== 'delete') throw new Error(`Unexpected Schedule action: ${command.action}`);
      state.beforeDelete?.();
      if (state.deleteError) throw state.deleteError;
      const index = state.schedules.findIndex(item => item.agentId === command.agentId
        && item.sessionId === command.sessionId && item.id === command.args?.id);
      if (index < 0 || state.deleteResult === 'retained') return { deleted: false };
      state.schedules.splice(index, 1);
      return { deleted: state.deleteResult === 'deleted' };
    },
  };
  return { state, runtime };
}

function harness(store: NodeStore, native = nativeRuntime()) {
  const changes: ScheduleDeletionIntent[] = [], repairs: ScheduleDeletionIntent[] = [];
  const durableAtChange: ScheduleDeletionIntent[][] = [], durableAtRepair: ScheduleDeletionIntent[][] = [];
  const errors: unknown[] = [];
  const failures = { change: undefined as Error | undefined, repair: undefined as Error | undefined };
  const service = new ScheduleDeletions({
    ownerId: 'owner', agents, store, runtime: native.runtime,
    async notify(intent) {
      changes.push(structuredClone(intent)); durableAtChange.push(store.scheduleDeletions());
      if (failures.change) throw failures.change;
    },
    async repair(intent) {
      repairs.push(structuredClone(intent)); durableAtRepair.push(store.scheduleDeletions());
      if (failures.repair) throw failures.repair;
    },
    onError: error => { errors.push(error); },
  });
  return { service, native, changes, repairs, durableAtChange, durableAtRepair, failures, errors };
}

afterEach(() => { vi.restoreAllMocks(); });

it('uses the native Agent catalog and Session, persisting intent and confirmed phase before either independent notification', async () => {
  const store = new NodeStore(':memory:', 'owner');
  // A current product binding is not authority for the Schedule's original Session.
  store.bind({ agentId: 'a', sessionId: 'current-session', conversationId: 'chat', ownerId: 'owner', cwd: '/tmp', revision: '1' });
  const current = harness(store, nativeRuntime([{ ...schedule, agentId: 'b', sessionId: 'foreign-session' }, schedule]));
  current.native.state.beforeDelete = () => {
    expect(store.scheduleDeletions()).toEqual([expect.objectContaining({
      ...identity, sessionId: schedule.sessionId, title: schedule.name, phase: 'pending',
      changeNotified: false, repairNotified: false,
    })]);
  };
  try {
    await expect(current.service.delete(identity)).resolves.toEqual({ id: schedule.id, deleted: true });
    expect(current.native.state.commands.filter(command => command.action === 'delete')).toEqual([{
      agentId: 'a', sessionId: schedule.sessionId, action: 'delete', args: { id: schedule.id },
    }]);
    expect(current.native.state.schedules).toEqual([{ ...schedule, agentId: 'b', sessionId: 'foreign-session' }]);
    expect(current.changes).toHaveLength(1); expect(current.repairs).toHaveLength(1);
    const intent = store.scheduleDeletions()[0]!;
    expect(intent).toMatchObject({ phase: 'deleted', actor: identity.actor, title: schedule.name, changeNotified: true, repairNotified: true });
    expect(Number.isNaN(Date.parse(intent.deletedAt!))).toBe(false);
    expect(intent.changeInputId).not.toBe(intent.repairInputId);
    expect(current.durableAtChange[0]).toEqual([expect.objectContaining({ phase: 'deleted', deletedAt: intent.deletedAt, changeNotified: false, repairNotified: false })]);
    expect(current.durableAtRepair[0]).toEqual([expect.objectContaining({ phase: 'deleted', changeNotified: true, repairNotified: false })]);
    expect(current.errors).toEqual([]);

    const commands = structuredClone(current.native.state.commands);
    await expect(current.service.delete({ ...identity, sessionId: schedule.sessionId })).resolves.toEqual({ id: schedule.id, deleted: true });
    await current.service.recover(['a']);
    expect(current.native.state.commands).toEqual(commands);
    expect(current.changes).toHaveLength(1); expect(current.repairs).toHaveLength(1);
    // A different operation cannot turn an already absent ID into another deleted fact.
    await expect(current.service.delete({ ...identity, operationId: 'delete-2' })).resolves.toEqual({ id: schedule.id, deleted: false, code: 'schedule_not_found' });
    expect(store.scheduleDeletions()).toEqual([intent]);
  } finally { store.close(); }
});

it('requires waiting repair for a self-Agent deletion without sending a human deletion notification', async () => {
  const store = new NodeStore(':memory:', 'owner'); const current = harness(store);
  try {
    await current.service.delete({ ...identity, sessionId: schedule.sessionId, actor: { kind: 'agent', id: 'a' } });
    expect(current.changes).toEqual([]);
    expect(current.repairs).toEqual([expect.objectContaining({ actor: { kind: 'agent', id: 'a' }, phase: 'deleted' })]);
    expect(store.scheduleDeletions()).toEqual([expect.objectContaining({ phase: 'deleted', changeNotified: true, repairNotified: true })]);
    await current.service.recover(['a']);
    expect(current.repairs).toHaveLength(1);
  } finally { store.close(); }
});

it.each([
  { name: 'wrong owner', patch: { actor: { kind: 'user', id: 'other-owner' } } },
  { name: 'non-self Agent', patch: { actor: { kind: 'agent', id: 'b' } } },
  { name: 'unknown Agent', patch: { agentId: 'unknown' } },
  { name: 'empty operation identity', patch: { operationId: '' } },
] satisfies { name: string; patch: Partial<Identity> }[])('rejects $name before reading or changing native state', async ({ patch }) => {
  const store = new NodeStore(':memory:', 'owner'); const current = harness(store);
  try {
    await expect(current.service.delete({ ...identity, ...patch })).rejects.toThrow('authority');
    expect(current.native.state.commands).toEqual([]);
    expect(current.native.state.schedules).toEqual([schedule]);
    expect(store.scheduleDeletions()).toEqual([]);
    expect(current.changes).toEqual([]); expect(current.repairs).toEqual([]);
  } finally { store.close(); }
});

it.each([
  { name: 'wrong Session', input: { ...identity, sessionId: 'other-session' }, catalog: [schedule] },
  { name: 'another Agent catalog', input: identity, catalog: [{ ...schedule, agentId: 'b' }] },
  { name: 'nonexistent ID', input: { ...identity, scheduleId: 'absent' }, catalog: [schedule] },
])('does not create a deleted fact for $name', async ({ input, catalog }) => {
  const store = new NodeStore(':memory:', 'owner'); const current = harness(store, nativeRuntime(catalog));
  try {
    await expect(current.service.delete(input)).resolves.toEqual({ id: input.scheduleId, deleted: false, code: 'schedule_not_found' });
    expect(store.scheduleDeletions()).toEqual([]);
    expect(current.native.state.commands.every(command => command.action === 'jobs' && command.agentId === 'a')).toBe(true);
    expect(current.native.state.schedules).toEqual(catalog);
    expect(current.changes).toEqual([]); expect(current.repairs).toEqual([]);
  } finally { store.close(); }
});

it.each([
  { name: 'Agent', patch: { agentId: 'b' } },
  { name: 'Schedule', patch: { scheduleId: 'other-schedule' } },
  { name: 'actor', patch: { actor: { kind: 'agent', id: 'a' } } },
  { name: 'Session', patch: { sessionId: 'other-session' } },
] satisfies { name: string; patch: Partial<Identity> }[])('rejects reuse of an operation identity with a different $name', async ({ patch }) => {
  const store = new NodeStore(':memory:', 'owner'); const current = harness(store);
  try {
    await current.service.delete(identity);
    const intents = store.scheduleDeletions(), commands = structuredClone(current.native.state.commands);
    await expect(current.service.delete({ ...identity, ...patch })).rejects.toThrow('identity conflict');
    expect(store.scheduleDeletions()).toEqual(intents);
    expect(current.native.state.commands).toEqual(commands);
    expect(current.changes).toHaveLength(1); expect(current.repairs).toHaveLength(1);
  } finally { store.close(); }
});

it('does not invoke native deletion if the authorized pending intent cannot be persisted', async () => {
  const store = new NodeStore(':memory:', 'owner'); const current = harness(store);
  const save = vi.spyOn(store, 'saveScheduleDeletion').mockImplementation(() => { throw new Error('intent storage unavailable'); });
  try {
    await expect(current.service.delete(identity)).rejects.toThrow('intent storage unavailable');
    expect(current.native.state.commands.some(command => command.action === 'delete')).toBe(false);
    expect(current.native.state.schedules).toEqual([schedule]);
    expect(store.scheduleDeletions()).toEqual([]);
    expect(current.changes).toEqual([]); expect(current.repairs).toEqual([]);
  } finally { save.mockRestore(); store.close(); }
});

it('does not mistake an unavailable native lookup for missing, initially or during pending recovery', async () => {
  const store = new NodeStore(':memory:', 'owner'); const current = harness(store);
  try {
    current.native.state.catalogError = new Error('native catalog unavailable');
    await expect(current.service.delete(identity)).rejects.toThrow('native catalog unavailable');
    expect(store.scheduleDeletions()).toEqual([]);

    current.native.state.catalogError = undefined; current.native.state.deleteError = new Error('native delete unavailable');
    await expect(current.service.delete(identity)).rejects.toThrow('native delete unavailable');
    const pending = store.scheduleDeletions();
    expect(pending).toEqual([expect.objectContaining({ phase: 'pending', changeNotified: false, repairNotified: false })]);
    expect(pending[0]!.deletedAt).toBeUndefined();
    current.native.state.catalogError = new Error('native lookup unknown');
    await expect(current.service.recover(['a'])).rejects.toThrow('native lookup unknown');
    expect(store.scheduleDeletions()).toEqual(pending);
    expect(current.changes).toEqual([]); expect(current.repairs).toEqual([]);

    current.native.state.catalogError = undefined; current.native.state.deleteError = undefined;
    await current.service.recover(['b']);
    expect(store.scheduleDeletions()).toEqual(pending);
    await current.service.recover(['a']);
    expect(store.scheduleDeletions()).toEqual([expect.objectContaining({ phase: 'deleted', changeNotified: true, repairNotified: true })]);
    expect(current.changes).toHaveLength(1); expect(current.repairs).toHaveLength(1);
  } finally { store.close(); }
});

it('requires authoritative disappearance when native delete returns an unconfirmed result', async () => {
  const store = new NodeStore(':memory:', 'owner'); const current = harness(store);
  try {
    current.native.state.deleteResult = 'retained';
    await expect(current.service.delete(identity)).rejects.toThrow('unconfirmed');
    expect(store.scheduleDeletions()).toEqual([expect.objectContaining({ phase: 'pending', changeNotified: false, repairNotified: false })]);
    expect(current.changes).toEqual([]); expect(current.repairs).toEqual([]);
    // A false delete result is not itself proof, but a successful native read can confirm absence.
    current.native.state.deleteResult = 'missing';
    await current.service.recover(['a']);
    expect(current.native.state.schedules).toEqual([]);
    expect(store.scheduleDeletions()).toEqual([expect.objectContaining({ phase: 'deleted', changeNotified: true, repairNotified: true })]);
    expect(current.changes).toHaveLength(1); expect(current.repairs).toHaveLength(1);
  } finally { store.close(); }
});

it('recovers a crash after native success but before phase persistence from the durable pending intent after NodeStore restart', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-schedule-deletion-'));
  const path = join(directory, 'node.sqlite3');
  let store = new NodeStore(path, 'owner'); const native = nativeRuntime();
  const current = harness(store, native), save = store.saveScheduleDeletion.bind(store);
  const interrupted = vi.spyOn(store, 'saveScheduleDeletion').mockImplementation(intent => {
    if (intent.phase === 'deleted') throw new Error('crash before confirmed phase save');
    save(intent);
  });
  try {
    await expect(current.service.delete(identity)).rejects.toThrow('crash before confirmed phase save');
    const pending = store.scheduleDeletions()[0]!;
    expect(pending.phase).toBe('pending'); expect(pending.deletedAt).toBeUndefined();
    expect(native.state.schedules).toEqual([]);
    expect(current.changes).toEqual([]); expect(current.repairs).toEqual([]);
    interrupted.mockRestore(); store.close(); store = new NodeStore(path, 'owner');
    expect(store.scheduleDeletions()).toEqual([pending]);
    native.state.commands.length = 0;
    const restarted = harness(store, native);
    await restarted.service.recover(['a']);
    expect(native.state.commands).toEqual([{ agentId: 'a', action: 'jobs' }]);
    expect(restarted.changes).toEqual([expect.objectContaining({ phase: 'deleted', changeInputId: pending.changeInputId, repairInputId: pending.repairInputId })]);
    expect(restarted.repairs).toHaveLength(1);
    expect(store.scheduleDeletions()).toEqual([expect.objectContaining({ phase: 'deleted', changeNotified: true, repairNotified: true })]);
    await restarted.service.recover(['a']);
    expect(restarted.changes).toHaveLength(1); expect(restarted.repairs).toHaveLength(1);
    expect(native.state.commands).toHaveLength(1);
  } finally { interrupted.mockRestore(); store.close(); await rm(directory, { recursive: true, force: true }); }
});

it.each(['change', 'repair'] as const)('durably preserves the other receipt when %s fails and retries only the debt after NodeStore restart', async failed => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-schedule-receipts-'));
  const path = join(directory, 'node.sqlite3');
  let store = new NodeStore(path, 'owner'); const native = nativeRuntime();
  const current = harness(store, native), failure = new Error(`${failed} notification unavailable`);
  current.failures[failed] = failure;
  try {
    await expect(current.service.delete(identity)).resolves.toEqual({ id: schedule.id, deleted: true });
    expect(current.changes).toHaveLength(1); expect(current.repairs).toHaveLength(1);
    expect(current.errors).toEqual([failure]);
    const receipt = store.scheduleDeletions()[0]!;
    expect(receipt).toMatchObject({ phase: 'deleted', changeNotified: failed !== 'change', repairNotified: failed !== 'repair' });
    store.close(); store = new NodeStore(path, 'owner');
    expect(store.scheduleDeletions()).toEqual([receipt]);
    native.state.commands.length = 0;
    const restarted = harness(store, native);
    await restarted.service.recover(['b']);
    expect(restarted.changes).toEqual([]); expect(restarted.repairs).toEqual([]);
    await restarted.service.recover(['a']);
    expect(restarted.changes).toHaveLength(failed === 'change' ? 1 : 0);
    expect(restarted.repairs).toHaveLength(failed === 'repair' ? 1 : 0);
    const retried = (failed === 'change' ? restarted.changes : restarted.repairs)[0]!;
    expect(retried.changeInputId).toBe(receipt.changeInputId); expect(retried.repairInputId).toBe(receipt.repairInputId);
    expect(retried.deletedAt).toBe(receipt.deletedAt);
    expect(store.scheduleDeletions()).toEqual([{ ...receipt, changeNotified: true, repairNotified: true }]);
    await restarted.service.recover(['a']);
    await expect(restarted.service.delete(identity)).resolves.toEqual({ id: schedule.id, deleted: true });
    expect(restarted.changes).toHaveLength(failed === 'change' ? 1 : 0);
    expect(restarted.repairs).toHaveLength(failed === 'repair' ? 1 : 0);
    expect(native.state.commands).toEqual([]);
    expect(restarted.errors).toEqual([]);
  } finally { store.close(); await rm(directory, { recursive: true, force: true }); }
});
