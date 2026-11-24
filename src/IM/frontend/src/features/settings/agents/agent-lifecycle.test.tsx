import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { AgentLifecycleAction, AgentLifecycleChatNotice, AgentLifecycleStatus, useAgentLifecycle, useDirectoryLifecycleRefresh } from './agent-lifecycle';
import { setLanguage } from '../../../i18n';
import { useAuthStore } from '../../auth/auth-store';

import type { UserStreamSubscriber } from '../../../realtime/user-stream';
const subscribers = vi.hoisted(() => new Set<UserStreamSubscriber>());
vi.mock('../../../realtime/user-stream', () => ({
  subscribeUserStream: (subscriber: UserStreamSubscriber) => {
    subscribers.add(subscriber);
    return () => subscribers.delete(subscriber);
  }
}));
const snapshot = (desired = 'enabled', observed = desired, revision = 1) => ({ agent_id: 'a', desired, observed, revision, applied_revision: observed === desired ? revision : 0, error_detail: observed === 'stop_unconfirmed' ? 'Cleanup timed out' : null });
function Surface({ owner = true, online = false }) {
  const lifecycle = useAgentLifecycle('a');
  return <><input aria-label="Draft" defaultValue="Unsaved name" /><AgentLifecycleAction lifecycle={lifecycle} canManage={owner} online={online} /><AgentLifecycleStatus lifecycle={lifecycle} online={online} /></>;
}
function mount(owner = true, online = false) {
  setLanguage('en');
  useAuthStore.setState({ user: { id: 'u' } as never });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Surface owner={owner} online={online} /></QueryClientProvider>);
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
  await userEvent.click(await screen.findByRole('button', { name: 'Disable Agent' }));
  await screen.findByText('The computer is offline. Disabling will continue when it reconnects.');
  expect(screen.getByRole('button', { name: 'Disabling…' })).toBeDisabled();
  expect(screen.queryByText('Disabled')).toBeNull();
  expect(screen.getByLabelText('Draft')).toHaveValue('Unsaved name');
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1);
});
it('retries only stopping and never enables an unconfirmed stop', async () => {
  const fetch = vi.fn(async (_url, init) => Response.json(snapshot('disabled', init?.method === 'POST' ? 'stopping' : 'stop_unconfirmed', 2)));
  vi.stubGlobal('fetch', fetch); mount(true, true);
  await screen.findByText('Disabling did not finish.');
  expect(screen.queryByText('Stop unconfirmed')).toBeNull();
  expect(screen.queryByText('Cleanup timed out')).toBeNull();
  await userEvent.click(await screen.findByRole('button', { name: 'Retry disabling' }));
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
  await userEvent.click(await screen.findByRole('button', { name: 'Disable Agent' }));
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
  mount(); await userEvent.click(await screen.findByRole('button', {name:'Enable Agent'}));
  await screen.findByRole('alert'); expect(writes).toBe(1);
  cleanup(); mount(false);
  await screen.findByText('Disabled'); expect(screen.queryByRole('button')).toBeNull();
});


it('updates the mounted directory through a burst of reports and reads it once on recovery', async () => {
  useAuthStore.setState({user:{id:'u'} as never});
  const client = new QueryClient();
  const list = [{agent_id:'a',lifecycle_disabled:false}];
  const read = vi.fn(async () => list);
  function Directory() {
    const query = useQuery({queryKey:['contacts','u','agents'],queryFn:read,initialData:list,staleTime:Infinity});
    useDirectoryLifecycleRefresh(query.refetch);
    return <output>{query.data[0].lifecycle_disabled ? 'Disabled' : 'Enabled'}</output>;
  }
  render(<QueryClientProvider client={client}><Directory /></QueryClientProvider>);
  act(() => {
    for (const subscriber of subscribers) {
      for (let i=0; i<50; i++) subscriber.onEvent({eventType:'agent.lifecycle.changed',payload:snapshot('disabled','disabled',2)});
    }
  });
  await screen.findByText('Disabled');
  expect(read).not.toHaveBeenCalled();
  await act(async () => {
    for (const subscriber of subscribers) await subscriber.onRecovery?.();
  });
  await screen.findByText('Enabled');
  expect(read).toHaveBeenCalledTimes(1);
});

it('updates the directory immediately after a successful enable without a socket event', async () => {
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => Response.json(init?.method === 'PUT' ? snapshot('enabled','enabling',3) : snapshot('disabled','disabled',2))));
  const client = mount();
  const key = ['contacts','u','agents'];
  client.setQueryData(key,[{agent_id:'a',display_name:'Assistant',lifecycle_disabled:true}]);
  await userEvent.click(await screen.findByRole('button',{name:'Enable Agent'}));
  await waitFor(() => expect(client.getQueryData(key)).toEqual([{agent_id:'a',display_name:'Assistant',lifecycle_disabled:false}]));
});
