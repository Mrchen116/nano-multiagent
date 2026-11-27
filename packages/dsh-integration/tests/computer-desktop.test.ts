import { beforeEach, expect, it, vi } from 'vitest';
import { checkDesktopRole } from '../src/computer/desktop-status.js';
import { DesktopBackend } from '../src/computer/desktop.js';
import { openMcp } from '../src/computer/mcp.js';

vi.mock('../src/computer/desktop-status.js', async (original) => ({
  ...(await original<typeof import('../src/computer/desktop-status.js')>()),
  cuaDriver: '/fixture/cua-driver',
  desktopStatus: async () => ({ available: true, accessibility: true, screen_recording: true }),
  verifyDesktopApp: async (bundle: string) => checkDesktopRole({ CFBundleIdentifier: bundle }),
}));
vi.mock('../src/computer/mcp.js', () => ({ openMcp: vi.fn() }));
const signal = new AbortController().signal;
const app = 'com.example.NanoFixture';
const id = { app, pid: 12, window_id: 34 };
let bundle = app;
const token = 's00000001:2';
let active = 99;
let title = 'Test document';
const call = vi.fn(async () => [{ type: 'text' as const, text: 'test result' }]);
const structured = vi.fn(async (name: string, _args: Record<string, unknown>, _signal: AbortSignal) => {
  if (name === 'clipboard_read') return { text: 'fixture only', types: ['text/plain'] };
  if (name === 'check_permissions') return { accessibility: true, screen_recording: true };
  if (name === 'list_apps')
    return {
      apps: [
        { bundle_id: bundle, pid: 12, running: true, active: active === 12 },
        { bundle_id: 'com.example.Other', pid: active, active: true, running: true },
      ],
    };
  if (name === 'list_windows')
    return {
      windows: [
        {
          pid: 12,
          window_id: 34,
          title,
          layer: 0,
          is_on_screen: true,
          bounds: { width: 500, height: 340 },
          z_index: 3,
        },
      ],
    };
  if (name === 'get_window_state')
    return {
      elements: [{ role: 'AXTextField', label: 'Name', element_token: token }],
      snapshot_id: 's00000001',
    };
  throw new Error(name);
});
const close = vi.fn(async () => {});
let backend: DesktopBackend;
beforeEach(() => {
  vi.clearAllMocks();
  bundle = app;
  active = 99;
  title = 'Test document';
  vi.mocked(openMcp).mockResolvedValue({ call, callStructured: structured, close } as Awaited<
    ReturnType<typeof openMcp>
  >);
  backend = new DesktopBackend();
});
async function run(action: string, input: Record<string, unknown> = {}) {
  return (await backend.prepare(action, input, signal)).run(signal);
}

it('preparing binding exposes only target evidence and takes no window snapshot', async () => {
  const list = await run('list_windows', { app });
  expect(JSON.stringify(list)).not.toContain(title);
  const binding = await backend.prepare('bind', id, signal);
  expect(binding.access).toBe('review');
  expect(binding.evidence).toContain(title);
  expect(structured.mock.calls.some(([name]) => name === 'get_window_state')).toBe(false);
  await expect(backend.prepare('snapshot', {}, signal)).rejects.toThrow(/bind/i);
  await binding.run(signal);
  await run('snapshot');
  const click = await backend.prepare('click', { element_token: token }, signal);
  expect(click.access).toBe('review');
  expect(click.evidence).toContain('Name');
  await click.run(signal);
  expect(call).toHaveBeenCalledWith(
    'click',
    expect.objectContaining({
      target: { kind: 'window', pid: 12, window_id: 34 },
      element_token: token,
      delivery_mode: 'background',
    }),
    signal,
  );
});

it('checks target and focus again after review; no click is dispatched on focus change', async () => {
  await run('bind', id);
  await run('snapshot');
  const click = await backend.prepare('click', { element_token: token }, signal);
  active = 97;
  await expect(click.run(signal)).rejects.toThrow(/focus|frontmost/i);
  expect(call).not.toHaveBeenCalled();
  await expect(backend.prepare('snapshot', {}, signal)).rejects.toThrow(/bind/i);
});

it('rejects scope overrides and only reuses the exact recently reviewed navigation key', async () => {
  await run('bind', id);
  await expect(backend.prepare('scroll', { direction: 'down', scope: 'desktop' }, signal)).rejects.toThrow();
  await expect(backend.prepare('key', { key: 'cmd+v' }, signal)).rejects.toThrow();
  const first = await backend.prepare('key', { key: 'pagedown' }, signal);
  expect(first.access).toBe('review');
  await first.run(signal);
  expect((await backend.prepare('key', { key: 'pagedown' }, signal)).access).toBe('observe');
  expect((await backend.prepare('key', { key: 'pageup' }, signal)).access).toBe('review');
  await backend.close();
  expect(close).toHaveBeenCalledOnce();
});

it('defers a protected clipboard read until the host executes the prepared action', async () => {
  const read = await backend.prepare('read_clipboard', {}, signal);
  expect(read.access).toBe('system_clipboard');
  expect(openMcp).not.toHaveBeenCalled();
  expect(await read.run(signal)).toEqual([{ type: 'text', text: 'fixture only' }]);
  expect(structured).toHaveBeenCalledWith('clipboard_read', { include_text: true }, signal);
  await backend.close();
  await expect(read.run(signal)).rejects.toThrow();
});

it.each(['com.apple.Terminal', 'com.apple.ScriptEditor2', 'com.google.Chrome'])(
  'routes %s away before exposing its windows',
  async (id) => {
    bundle = id;
    await expect(run('list_windows', { app: id })).rejects.toThrow(/browser|shell/i);
    expect(structured.mock.calls.some(([name]) => name === 'list_windows')).toBe(false);
  },
);
it('detects web and shell URL handlers and developer apps by bundle metadata', () => {
  const info = { CFBundleIdentifier: 'com.example.unknown' };
  for (const scheme of ['https', 'ssh'])
    expect(() => checkDesktopRole({ ...info, CFBundleURLTypes: [{ CFBundleURLSchemes: [scheme] }] })).toThrow();
  expect(() =>
    checkDesktopRole({ ...info, LSApplicationCategoryType: 'public.app-category.developer-tools' }),
  ).toThrow();
  expect(() =>
    checkDesktopRole({ ...info, LSApplicationCategoryType: 'public.app-category.productivity' }),
  ).not.toThrow();
});
