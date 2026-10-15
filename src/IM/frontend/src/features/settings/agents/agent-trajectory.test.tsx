import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { AgentTrajectory } from './agent-trajectory';
import { useAuthStore } from '../../auth/auth-store';

vi.mock('../../auth/auth-fetch', () => ({ authFetch: async () => new Response(JSON.stringify({ ticket: 'readonly-ticket' })) }));
class Socket {
  static OPEN = 1;
  static instances: Socket[] = [];
  readyState = 1;
  onmessage?: (event: { data: string }) => void;
  onclose?: (event: { code: number; reason: string }) => void;
  send = vi.fn();
  close = vi.fn();
  constructor(readonly url: string) { Socket.instances.push(this); }
}
const channels: { port1: ReturnType<typeof port>; port2: ReturnType<typeof port> }[] = [];
const port = () => ({ close: vi.fn(), start: vi.fn(), postMessage: vi.fn(), onmessage: null });
function message(frame: HTMLIFrameElement, data: unknown) {
  act(() => window.dispatchEvent(new MessageEvent('message', { source: frame.contentWindow, data })));
}
async function connect(frame: HTMLIFrameElement, index: number) {
  await waitFor(() => expect(Socket.instances.length).toBeGreaterThan(index));
  vi.spyOn(frame.contentWindow!, 'postMessage').mockImplementation(() => {});
  act(() => Socket.instances[index].onmessage?.({ data: JSON.stringify({ type: 'ready', version: '0.2.1-alpha.1' }) }));
  message(frame, { type: 'nano-trajectory-ready' });
}
beforeEach(() => {
  Socket.instances = [];
  channels.length = 0;
  vi.stubGlobal('WebSocket', Socket);
  vi.stubGlobal('MessageChannel', class { port1 = port(); port2 = port(); constructor() { channels.push(this); } });
  useAuthStore.setState({ user: { id: 'reader' } as never, revision: 1 });
});

it('keeps each parent frame when entering nested runs and releases popped and revoked observations', async () => {
  const active = vi.fn();
  const { container } = render(<AgentTrajectory agentId="agent" sessionId="main" positions={{}} onActiveSessionChange={active} onBack={() => {}} />);
  const parent = container.querySelector('iframe')!;
  await connect(parent, 0);
  message(parent, { type: 'viewer-navigate', run: { runId: 'run-one', parentSessionId: 'main', sessionId: 'child', label: '计算' } });
  await waitFor(() => expect(container.querySelectorAll('iframe')).toHaveLength(2));
  expect(parent).not.toBeVisible();
  expect(active).toHaveBeenLastCalledWith('child', '计算');
  const child = container.querySelectorAll('iframe')[1];
  await connect(child, 1);
  message(child, { type: 'viewer-navigate', run: { runId: 'run-two', parentSessionId: 'child', sessionId: 'nested', label: '核对' } });
  await waitFor(() => expect(container.querySelectorAll('iframe')).toHaveLength(3));
  await connect(container.querySelectorAll('iframe')[2], 2);
  fireEvent.click(screen.getByRole('button', { name: '返回发起点' }));
  expect(container.querySelectorAll('iframe')[1]).toBe(child);
  expect(child).toBeVisible();
  expect(active).toHaveBeenLastCalledWith('child', '计算');
  expect(Socket.instances[2].close).toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '返回发起点' }));
  expect(container.querySelector('iframe')).toBe(parent);
  expect(parent).toBeVisible();
  expect(active).toHaveBeenLastCalledWith('main', '当前执行');
  expect(Socket.instances[0].close).not.toHaveBeenCalled();
  message(parent, { type: 'viewer-navigate', run: { runId: 'run-one', parentSessionId: 'main', sessionId: 'child', label: '计算' } });
  await waitFor(() => expect(container.querySelectorAll('iframe')).toHaveLength(2));
  await connect(container.querySelectorAll('iframe')[1], 3);
  act(() => Socket.instances[3].onclose?.({ code: 1008, reason: '资格失效' }));
  expect(container.querySelector('iframe')).toBeNull();
  expect(Socket.instances[0].close).toHaveBeenCalled();
});

it('ignores foreign sources and mismatched parent targets and clears the stack on identity changes', async () => {
  const { container } = render(<AgentTrajectory agentId="agent" sessionId="main" positions={{}} onBack={() => {}} />);
  const parent = container.querySelector('iframe')!;
  await connect(parent, 0);
  const data = { type: 'viewer-navigate', run: { runId: 'run', parentSessionId: 'main', sessionId: 'child' } };
  act(() => window.dispatchEvent(new MessageEvent('message', { source: window, data })));
  message(parent, { ...data, run: { ...data.run, parentSessionId: 'unrelated' } });
  expect(container.querySelectorAll('iframe')).toHaveLength(1);
  message(parent, data);
  await waitFor(() => expect(container.querySelectorAll('iframe')).toHaveLength(2));
  act(() => useAuthStore.getState().clear());
  expect(container.querySelector('iframe')).toBeNull();
  expect(Socket.instances[0].close).toHaveBeenCalled();
});

it.each([false, true])('keeps fragmented reads pending until the final fragment (final=%s)', async final => {
  const { container } = render(<AgentTrajectory agentId="agent" sessionId="main" positions={{}} onBack={() => {}} />);
  await connect(container.querySelector('iframe')!, 0);
  const channel = channels[0];
  act(() => (channel.port1.onmessage as unknown as (event: { data: unknown }) => void)({ data: { type: 'call', requestId: 'page', method: 'session/page' } }));
  const part = { type: 'trajectory-fragment', requestId: 'page', transferId: 'transfer', index: 0, final, data: 'partial' };
  act(() => Socket.instances[0].onmessage?.({ data: JSON.stringify(part) }));
  expect(channel.port1.postMessage).toHaveBeenCalledWith(part);
  channel.port1.postMessage.mockClear();
  act(() => Socket.instances[0].onclose?.({ code: 1011, reason: '断开' }));
  if (final) expect(channel.port1.postMessage).not.toHaveBeenCalled();
  else expect(channel.port1.postMessage).toHaveBeenCalledWith({ type: 'error', requestId: 'page', code: 'trajectory_disconnected', message: '断开' });
});
