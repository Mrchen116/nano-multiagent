import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { afterEach, expect, it, vi } from 'vitest';
import { DriverClient, MAX_OUTPUT_BYTES } from '../src/browser/driver.js';

interface Outcome { stdout?: string; stderr?: string; code?: number; hang?: boolean; spawnError?: Error }

function fakeSpawn(script: Outcome[] | ((args: readonly string[]) => Outcome)) {
  const calls: { command: string; args: readonly string[]; options: Record<string, unknown> }[] = [];
  const kill = vi.fn();
  const spawn = (command: string, args: readonly string[], options: Record<string, unknown>) => {
    calls.push({ command, args, options });
    const outcome = typeof script === 'function' ? script(args) : script[Math.min(calls.length - 1, script.length - 1)]!;
    if (outcome.spawnError) throw outcome.spawnError;
    const child = new EventEmitter() as EventEmitter & { stdout: PassThrough; stderr: PassThrough; kill: typeof kill };
    child.stdout = new PassThrough();
    child.stderr = new PassThrough();
    child.kill = kill;
    if (outcome.hang) return child;
    process.nextTick(() => {
      if (outcome.stdout) child.stdout.write(outcome.stdout);
      if (outcome.stderr) child.stderr.write(outcome.stderr);
      process.nextTick(() => child.emit('close', outcome.code ?? 0));
    });
    return child;
  };
  return { spawn: spawn as never, calls, kill };
}

afterEach(() => { vi.useRealTimers(); });

it('probes version, daemon and permissions once without a shell', async () => {
  const fake = fakeSpawn(args => args[0] === '--version' ? { stdout: 'cua-driver 0.38.0\n' }
    : args[0] === 'status' ? { stdout: 'daemon is running\npermission mode: standard\n' }
      : { stdout: '{"accessibility":true,"screen_recording":{"granted":true}}' });
  const client = new DriverClient({ spawn: fake.spawn, command: '/opt/cua-driver', env: {} });
  await expect(client.probe()).resolves.toEqual({ version: '0.38.0' });
  await client.probe();
  expect(fake.calls.map(call => call.args)).toEqual([
    ['--version'],
    ['status'],
    ['permissions', 'status', '--json'],
  ]);
  for (const call of fake.calls) {
    expect(call.command).toBe('/opt/cua-driver');
    expect(call.options.shell).toBe(false);
    expect(call.options.stdio).toEqual(['ignore', 'pipe', 'pipe']);
  }
});

it('rejects unsupported versions, a stopped daemon, and missing permissions with raw evidence', async () => {
  await expect(new DriverClient({ spawn: fakeSpawn([{ stdout: 'cua-driver 0.37.9\n' }]).spawn }).probe())
    .rejects.toMatchObject({ code: 'browser_driver_version_unsupported' });
  await expect(new DriverClient({ spawn: fakeSpawn([
    { stdout: 'cua-driver 0.38.0\n' },
    { stdout: 'daemon is stopped' },
  ]).spawn }).probe()).rejects.toMatchObject({ code: 'browser_driver_not_running', message: expect.stringContaining('daemon is stopped') });
  await expect(new DriverClient({ spawn: fakeSpawn([
    { stdout: 'cua-driver 0.38.0\n' },
    { stdout: 'daemon is running\npermission mode: standard\n' },
    { stdout: '{"accessibility":true,"screen_recording":false}' },
  ]).spawn }).probe()).rejects.toMatchObject({ code: 'browser_permission_missing', details: { missing: ['screen_recording'] } });
});

it('maps non-zero exit, empty stdout, non-JSON, and missing fields to malformed', async () => {
  const cases: { outcome: Outcome; requireFields?: string[] }[] = [
    { outcome: { code: 2, stderr: 'refused badly' } },
    { outcome: { stdout: '   ' } },
    { outcome: { stdout: 'not json' } },
    { outcome: { stdout: '{"ok":true}' }, requireFields: ['pid'] },
  ];
  for (const scenario of cases) {
    const client = new DriverClient({ spawn: fakeSpawn([scenario.outcome]).spawn });
    await expect(client.call('browser_click', { ref: 'r' }, { requireFields: scenario.requireFields }))
      .rejects.toMatchObject({ code: 'browser_driver_malformed' });
  }
});

it('keeps structured refusals distinct and preserves code and hint', async () => {
  const client = new DriverClient({ spawn: fakeSpawn([{
    stdout: JSON.stringify({ status: 'refused', refusal: { code: 'browser_action_unavailable', message: 'no pointer action' }, hint: 'use another ref' }),
  }]).spawn });
  await expect(client.call('browser_click', { ref: 'p1:0' })).rejects.toMatchObject({
    code: 'browser_driver_refused',
    details: { refusalCode: 'browser_action_unavailable', hint: 'use another ref' },
  });
});

it('kills a hung child on timeout and reports an unknown page state', async () => {
  vi.useFakeTimers();
  const fake = fakeSpawn([{ hang: true }]);
  const client = new DriverClient({ spawn: fake.spawn });
  const pending = client.call('browser_click', { ref: 'r' }, { timeoutMs: 100 }).catch(error => error);
  await vi.advanceTimersByTimeAsync(101);
  const error = await pending;
  expect(error).toMatchObject({ code: 'browser_driver_timeout' });
  expect(error.message).toContain('页面状态未知');
  expect(fake.kill).toHaveBeenCalledWith('SIGKILL');
});

it('stops a child whose output exceeds the configured cap', async () => {
  const fake = fakeSpawn([{ stdout: '123456789' }]);
  const client = new DriverClient({ spawn: fake.spawn, maxOutputBytes: 8 });
  await expect(client.call('browser_click', {})).rejects.toMatchObject({ code: 'browser_driver_malformed' });
  expect(fake.kill).toHaveBeenCalledWith('SIGKILL');
  expect(MAX_OUTPUT_BYTES).toBe(32 * 1024 * 1024);
});

it('reports a missing executable and refuses tools outside the call whitelist', async () => {
  const missing = Object.assign(new Error('spawn cua-driver ENOENT'), { code: 'ENOENT' });
  await expect(new DriverClient({ spawn: fakeSpawn([{ spawnError: missing }]).spawn }).call('browser_click', {}))
    .rejects.toMatchObject({ code: 'browser_driver_unavailable' });
  const fake = fakeSpawn([{ stdout: '{}' }]);
  const client = new DriverClient({ spawn: fake.spawn });
  await expect(client.call('run_script' as never, {})).rejects.toMatchObject({ code: 'browser_arguments_invalid' });
  expect(fake.calls).toHaveLength(0);
});
