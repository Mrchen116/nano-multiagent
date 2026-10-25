import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { AgentLifecycleAction, AgentLifecycleChatNotice, AgentLifecycleStatus, useAgentLifecycle } from './agent-lifecycle';
import { setLanguage } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';

vi.mock('../../../realtime/user-stream', () => ({ subscribeUserStream: () => () => {} }));
const snapshot = (desired = 'enabled', observed = desired, revision = 1) => ({ agent_id: 'a', desired, observed, revision, applied_revision: observed === desired ? revision : 0, error_detail: observed === 'stop_unconfirmed' ? 'Cleanup timed out' : null });
function Surface({ owner = true, online = false }) {
  const lifecycle = useAgentLifecycle('a');
  return <><input aria-label="Draft" defaultValue="Unsaved name" /><AgentLifecycleAction lifecycle={lifecycle} canManage={owner} /><AgentLifecycleStatus lifecycle={lifecycle} online={online} /></>;
}
function mount(owner = true) {
  setLanguage('en');
  useAuthStore.setState({ user: { id: 'u' } as never });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Surface owner={owner} /></QueryClientProvider>);
  return client;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('explains that chat retains messages without processing them while stopping',async()=>{
  setLanguage('en');vi.stubGlobal('fetch',vi.fn(async()=>Response.json(snapshot('disabled','stopping',2))));
  render(<QueryClientProvider client={new QueryClient()}><AgentLifecycleChatNotice agentId="a" name="Assistant" /></QueryClientProvider>);
  await screen.findByText('Messages are kept, but this Agent will not process them.');
  expect(screen.queryByRole('button')).toBeNull();
});
it('stops while offline without saving a draft and cannot enable until cleanup is confirmed', async () => {
  let state = snapshot();
  const fetch = vi.fn(async (_url, init) => {
    if (init?.method === 'PUT') state = snapshot('disabled', 'stopping', 2);
    return Response.json(state);
  });
  vi.stubGlobal('fetch', fetch); mount();
  await userEvent.click(await screen.findByRole('button', { name: 'Disable' }));
  await screen.findByText('Disable requested; waiting for the node to confirm.');
  expect(screen.getByRole('button', { name: 'Stopping…' })).toBeDisabled();
  expect(screen.getByLabelText('Draft')).toHaveValue('Unsaved name');
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1);
});
it('retries only stopping and never enables an unconfirmed stop', async () => {
  const fetch = vi.fn(async (_url, init) => Response.json(snapshot('disabled', init?.method === 'POST' ? 'stopping' : 'stop_unconfirmed', 2)));
  vi.stubGlobal('fetch', fetch); mount();
  await userEvent.click(await screen.findByRole('button', { name: 'Retry stop' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => String(url).endsWith('/lifecycle/retry') && init?.method === 'POST')).toBe(true));
  expect(fetch.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false);
});
it('rereads a disable conflict and resubmits the same intent at the latest revision', async () => {
  let reads = 0, writes = 0;
  const fetch = vi.fn(async (_url, init) => {
    if (init?.method === 'PUT') { writes++; return writes === 1 ? Response.json({detail:'revision_conflict'}, {status:409}) : Response.json(snapshot('disabled', 'stopping', 4)); }
    return Response.json(snapshot('enabled', 'enabled', ++reads === 1 ? 1 : 3));
  });
  vi.stubGlobal('fetch', fetch); mount();
  await userEvent.click(await screen.findByRole('button', { name: 'Disable' }));
  await waitFor(() => expect(writes).toBe(2));
  const bodies = fetch.mock.calls.filter(([,init]) => init?.method === 'PUT').map(([,init]) => JSON.parse(init.body));
  expect(bodies.map(b => [b.enabled, b.expected_revision])).toEqual([[false,1],[false,3]]);
  expect(bodies[0].request_id).toBe(bodies[1].request_id);
});
it('refreshes an enable conflict without resubmitting and shows nonowners only status', async () => {
  let writes = 0;
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => {
    if (init?.method === 'PUT') { writes++; return Response.json({detail:'revision_conflict'}, {status:409}); }
    return Response.json(snapshot('disabled', 'disabled', 2));
  }));
  mount(); await userEvent.click(await screen.findByRole('button', {name:'Enable again'}));
  await screen.findByRole('alert'); expect(writes).toBe(1);
  cleanup(); mount(false);
  await screen.findByText('Disabled'); expect(screen.queryByRole('button')).toBeNull();
});
