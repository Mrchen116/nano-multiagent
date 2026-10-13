import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { OnboardingPage } from './onboarding-page';
import { useAuthStore } from '../auth/auth-store';
import { TEST_AUTH_USER } from '../../test/render-router';
import { setLanguage } from '../../i18n';
import { getOnboarding, setupNode } from './onboarding-api';
import { createNodeAgent, getNodeCreateState } from '../settings/agents/im-agent-config-api';
import { createConversation, listConversations } from '../chat/chat-api';
vi.mock('./onboarding-api');
vi.mock('../settings/agents/im-agent-config-api');
vi.mock('../chat/chat-api');
const computer = { node_id: 'device', node_name: 'My computer', alias: null, status: 'online' };
const install = { available: true, origin: 'https://nano.example', command: 'install Nano', script_url: 'https://nano.example/install.sh' };
const modelStatus = { revision: 'r1', services: [], models: [], catalog: [{provider: 'deepseek', display_name: 'DeepSeek', models: [{id: 'deepseek-chat'}]}], default_model: '', workspace_base: '/my-workspaces' };
function mount(cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
 const router = createMemoryRouter([{ path: '/onboarding', element: <OnboardingPage /> }, { path: '/chat/:id', element: <p>Chat opened</p> }], { initialEntries: ['/onboarding'] });
 render(<QueryClientProvider client={cache}><RouterProvider router={router} /></QueryClientProvider>);
 return router;
}
beforeEach(() => {
 vi.resetAllMocks(); localStorage.clear(); setLanguage('en');
 useAuthStore.getState().setSession({ access_token: 'test', user: { ...TEST_AUTH_USER, personal_space_enabled: true, membership_status: 'none' } });
 vi.mocked(getOnboarding).mockResolvedValue({ nodes: [computer], agents: [], install });
 vi.mocked(setupNode).mockResolvedValue(modelStatus);
});
it('keeps failed model validation on the model step and never stores the entered key', async () => {
 mount();
 await screen.findByRole('heading', { name: 'Connect a model' });
 await screen.findByLabelText('API Key');
 await userEvent.type(screen.getByLabelText('API Key'), 'private-key-example');
 await userEvent.clear(screen.getByLabelText('Model ID'));
 await userEvent.type(screen.getByLabelText('Model ID'), 'model-one');
 vi.mocked(setupNode).mockResolvedValue({ ...modelStatus, operation: { id: 'op', state: 'failed' } });
 await userEvent.click(screen.getByRole('button', { name: 'Test and save' }));
 await screen.findByRole('alert');
 expect(screen.getByRole('button', { name: 'Continue →' })).toBeDisabled();
 expect(screen.getByLabelText('API Key')).toHaveValue('private-key-example');
 expect(Array.from({length: localStorage.length}, (_, i) => localStorage.getItem(localStorage.key(i)!)).join(' ')).not.toContain('private-key-example');
 expect(createNodeAgent).not.toHaveBeenCalled();
});
it('restores a verified model, creates one personal global assistant, and preserves its ID for retry', async () => {
 vi.mocked(setupNode).mockResolvedValue({ ...modelStatus, default_model: 'model-one', models: [{ provider: 'p', model: 'model-one' }] });
 vi.mocked(getNodeCreateState).mockResolvedValue({ capabilities: { tools: [{ name: 'read', default_on: true }, { name: 'disabled', default_on: false }], features: [] } } as never);
 vi.mocked(createNodeAgent).mockRejectedValue(new Error('offline'));
 mount();
 await screen.findByRole('heading', { name: 'What would you like help with?' });
 const button = screen.getByRole('button', { name: 'Create my assistant →' });
 await waitFor(() => expect(button).toBeEnabled());
 await userEvent.click(button);
 await screen.findByRole('alert');
 const first = vi.mocked(createNodeAgent).mock.calls[0][1];
 expect(first).toMatchObject({ owner_id: TEST_AUTH_USER.owner_id, work_mode: 'global', workspace_root: null, default_model: 'model-one', tool_allowlist: ['read'], features: { heartbeat: false, cron_scheduling: false } });
 await userEvent.click(screen.getByRole('button', { name: 'Check and retry' }));
 await waitFor(() => expect(createNodeAgent).toHaveBeenCalledTimes(2));
 expect(vi.mocked(createNodeAgent).mock.calls[1][1].agent_id).toBe(first.agent_id);
});
it('reopens an existing first chat without replacing its draft with another starter', async () => {
 vi.mocked(getOnboarding).mockResolvedValue({ nodes: [computer], agents: [{ agent_id: 'a', display_name: 'Assistant', node_id: 'device', default_model: 'm', workspace_root: '/a', work_mode: 'global' }], install });
 vi.mocked(listConversations).mockResolvedValue([{ id: 'existing', type: 'direct', participants: [{ type: 'agent', id: 'a' }] }] as never);
 const router = mount();
 await userEvent.click(await screen.findByRole('button', { name: 'Start your first task →' }));
 await screen.findByText('Chat opened');
 expect(router.state.location.pathname).toBe('/chat/existing');
 expect(router.state.location.state).toBeNull();
 expect(createConversation).not.toHaveBeenCalled();
});
it('shows saved models without developer proxy discovery or a duplicate setup test', async () => {
 vi.mocked(setupNode).mockResolvedValue({...modelStatus, default_model: 'model-one', models: [{provider: 'p', model: 'model-one'}], services: [{provider: 'p', display_name: 'Team service', source: 'custom', native: false, credential_stored: true, models: [{name: 'model-one', id: 'model-one'}]}]});
 vi.mocked(getNodeCreateState).mockResolvedValue({capabilities: {tools: [], features: []}} as never);
 mount();
 await screen.findByRole('heading', {name: 'What would you like help with?'});
 await userEvent.click(screen.getByRole('button', {name: '← Back'}));
 expect(await screen.findByRole('heading', {name: 'Team service'})).toBeInTheDocument();
 expect(screen.queryByText('Local model proxy')).not.toBeInTheDocument();
 expect(screen.getByRole('button', {name: 'Continue →'})).toBeEnabled();
});
it('returns to computer recovery when an already-created assistant is offline', async () => {
 vi.mocked(getOnboarding).mockResolvedValue({nodes: [{...computer, status: 'offline'}], agents: [{agent_id: 'a', display_name: 'Assistant', node_id: 'device', default_model: 'm', workspace_root: '/a', work_mode: 'global'}], install});
 mount();
 await screen.findByRole('heading', {name: 'Connect your computer'});
 expect(screen.queryByRole('heading', {name: 'Assistant is ready'})).not.toBeInTheDocument();
 expect(screen.getByText(/Run the command on that computer again/)).toBeInTheDocument();
});

it('switches from freshly created ready state to recovery when the same open page loses its computer', async () => {
 const cache = new QueryClient({defaultOptions: {queries: {retry: false}}});
 const ready = {nodes: [computer], agents: [{agent_id: 'a', display_name: 'Created assistant', node_id: 'device', default_model: 'm', workspace_root: '/a', work_mode: 'global'}], install};
 vi.mocked(setupNode).mockResolvedValue({...modelStatus, default_model: 'm', models: [{provider: 'p', model: 'm'}]});
 vi.mocked(getNodeCreateState).mockResolvedValue({capabilities: {tools: [], features: []}} as never);
 vi.mocked(createNodeAgent).mockImplementation(async () => {vi.mocked(getOnboarding).mockResolvedValue(ready); return {} as never;});
 mount(cache);
 const create = await screen.findByRole('button', {name: 'Create my assistant →'});
 await waitFor(() => expect(create).toBeEnabled());
 await userEvent.click(create);
 await screen.findByRole('heading', {name: 'Created assistant is ready'});
 vi.mocked(getOnboarding).mockResolvedValue({...ready, nodes: [{...computer, status: 'offline'}]});
 await cache.invalidateQueries({queryKey: ['onboarding', TEST_AUTH_USER.id]});
 await screen.findByRole('heading', {name: 'Connect your computer'});
 expect(screen.queryByRole('button', {name: 'Start your first task →'})).not.toBeInTheDocument();
});
