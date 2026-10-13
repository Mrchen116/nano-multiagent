import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { useAuthStore } from '../../auth/auth-store';
import { TEST_AUTH_USER } from '../../../test/render-router';
import { setLanguage } from '../../../i18n';
import { getOnboarding, setupNode, type SetupStatus } from '../../onboarding/onboarding-api';
import { ModelsPage } from './models-page';

vi.mock('../../onboarding/onboarding-api');
const computer = { node_id: 'computer', node_name: 'Studio computer', alias: null, status: 'online' };
const install = { available: true, origin: 'https://nano.test', command: '', script_url: '' };
const service = { provider: 'custom-team', display_name: 'Team service', native: false, source: 'custom', protocol: 'openai-completions' as const, base_url: 'https://models.test/v1', credential_stored: true, models: [{ name: 'custom-team/shared', id: 'shared', display_name: 'Shared model' }] };
const snapshot: SetupStatus = {
  revision: 'r1', services: [service], models: [{ provider: service.provider, model: 'custom-team/shared' }], default_model: 'custom-team/shared', workspace_base: '/workspaces',
  catalog: [{provider: 'deepseek', display_name: 'DeepSeek', models: [{id: 'deepseek-chat', contextWindow: 128000, maxTokens: 8192, inputModalities: ['text']}]}, {provider: 'openai-codex', display_name: 'Codex subscription', models: [{id: 'codex-model'}]}],
};
function mount(cache = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })) {
  const router = createMemoryRouter([{path: '/settings/models', element: <ModelsPage />}], { initialEntries: ['/settings/models'] });
  render(<QueryClientProvider client={cache}><RouterProvider router={router} /></QueryClientProvider>);
  return cache;
}
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); setLanguage('en');
  useAuthStore.getState().setSession({access_token: 'test', user: TEST_AUTH_USER});
  vi.mocked(getOnboarding).mockResolvedValue({ nodes: [computer], agents: [], install });
  vi.mocked(setupNode).mockResolvedValue(snapshot);
});
it('edits multiple model capabilities with a stable service ID and preserves a blank saved key', async () => {
  mount();
  await screen.findByRole('heading', {name: 'Team service'});
  await userEvent.click(screen.getByRole('button', {name: 'Edit Team service'}));
  expect(screen.getByLabelText('API Key')).toHaveValue('');
  expect(screen.getByPlaceholderText('Leave blank to keep the saved key')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', {name: '+ Add model'}));
  await userEvent.type(screen.getAllByLabelText('Model ID')[1], 'second');
  await userEvent.click(screen.getAllByText('Model capabilities')[1]);
  await userEvent.type(screen.getAllByLabelText('Context window')[1], '64000');
  await userEvent.click(screen.getAllByLabelText('Supports image input')[1]);
  vi.mocked(setupNode).mockResolvedValue({...snapshot, revision: 'r2', operation: {id: 'save-1', state: 'succeeded'}});
  await userEvent.click(screen.getByRole('button', {name: 'Test and save'}));
  await screen.findByText(/Connection verified and saved/);
  const input = vi.mocked(setupNode).mock.calls.find(([, input]) => input.action === 'save')![1];
  expect(input).toMatchObject({provider: 'custom-team', revision: 'r1', models: [{id: 'shared'}, {id: 'second', context_window: 64000, input: ['text', 'image']}]});
  expect(input).not.toHaveProperty('api_key');
});
it('takes built-in API choices from the catalog and keeps subscription login separate', async () => {
  mount();
  await userEvent.click(await screen.findByRole('button', {name: '+ Add service'}));
  const provider = screen.getByLabelText('Provider');
  expect(provider).toHaveValue('deepseek');
  expect(provider.querySelector('option[value="openai-codex"]')).toBeNull();
  expect(screen.getByLabelText('Model ID')).toHaveValue('deepseek-chat');
  await userEvent.click(screen.getByText('Model capabilities'));
  expect(screen.getByLabelText('Context window')).toHaveValue(128000);
  expect(screen.getByLabelText('Maximum output tokens')).toHaveValue(8192);
  expect(screen.getByText('Connect a ChatGPT / Codex subscription')).toBeInTheDocument();
});
it('compares conflicts explicitly before reapplying the untouched draft at the newer revision', async () => {
  mount();
  await userEvent.click(await screen.findByRole('button', {name: 'Edit Team service'}));
  await userEvent.clear(screen.getByLabelText('Service name'));
  await userEvent.type(screen.getByLabelText('Service name'), 'My draft');
  const latest = {...snapshot, revision: 'r2', services: [{...service, display_name: 'Remote name'}]};
  vi.mocked(setupNode).mockImplementation(async (_, input) => input.action === 'save' ? {...latest, error: {code: 'conflict', message: 'Configuration changed'}} : latest);
  await userEvent.click(screen.getByRole('button', {name: 'Test and save'}));
  expect(await screen.findByText('Review the latest configuration')).toBeInTheDocument();
  expect(screen.getByLabelText('Service name')).toHaveValue('My draft');
  expect(screen.getByRole('button', {name: 'Test and save'})).toBeDisabled();
  await userEvent.click(screen.getByRole('button', {name: 'Compare latest configuration'}));
  await screen.findByText(/Remote name/);
  await userEvent.click(screen.getByRole('button', {name: 'Reapply my changes after review'}));
  expect(vi.mocked(setupNode).mock.calls.filter(([, input]) => input.action === 'save')).toHaveLength(1);
  vi.mocked(setupNode).mockResolvedValue({...latest, revision: 'r3', operation: {id: 'saved', state: 'succeeded'}});
  await userEvent.click(screen.getByRole('button', {name: 'Test and save'}));
  await waitFor(() => expect(setupNode).toHaveBeenCalledWith('computer', expect.objectContaining({action: 'save', revision: 'r2', display_name: 'My draft'})));
});
it('keeps offline drafts and asks for a review after recovery instead of silently refreshing their revision', async () => {
  const cache = mount();
  await userEvent.click(await screen.findByRole('button', {name: 'Edit Team service'}));
  await userEvent.type(screen.getByLabelText('API Key'), 'write-only-secret');
  vi.mocked(getOnboarding).mockResolvedValue({ nodes: [{...computer, status: 'offline'}], agents: [], install });
  await act(() => cache.invalidateQueries({queryKey: ['onboarding']}));
  await screen.findByText('Computer unavailable');
  expect(screen.getByLabelText('API Key')).toHaveValue('write-only-secret');
  expect(screen.getByRole('button', {name: 'Test and save'})).toBeDisabled();
  expect(Array.from({length: localStorage.length}, (_, i) => localStorage.getItem(localStorage.key(i)!)).join(' ')).not.toContain('write-only-secret');
  vi.mocked(getOnboarding).mockResolvedValue({nodes: [computer], agents: [], install});
  await act(() => cache.invalidateQueries({queryKey: ['onboarding']}));
  await userEvent.click(await screen.findByRole('button', {name: 'Compare latest configuration'}));
  await userEvent.click(await screen.findByRole('button', {name: 'Use computer configuration'}));
  expect(screen.getByLabelText('API Key')).toHaveValue('');
  expect(screen.getByLabelText('Service name')).toHaveValue('Team service');
});
it('shows dependency names without removing a service and waits for confirmation', async () => {
  mount();
  await userEvent.click(await screen.findByRole('button', {name: 'Remove Team service'}));
  expect(vi.mocked(setupNode).mock.calls.every(([, input]) => input.action === 'status')).toBe(true);
  vi.mocked(setupNode).mockResolvedValue({...snapshot, error: {code: 'in_use', message: 'Models are in use', dependencies: [{agent_id: 'research', display_name: 'Research assistant'}]}});
  await userEvent.click(screen.getByRole('button', {name: 'Confirm removal'}));
  expect(await screen.findByRole('link', {name: 'Research assistant'})).toHaveAttribute('href', '/settings/agents/research');
  expect(screen.getByRole('heading', {name: 'Team service'})).toBeInTheDocument();
});
it('does not claim cancellation before the running operation reaches a terminal state', async () => {
  const cache = mount();
  await userEvent.click(await screen.findByRole('button', {name: 'Edit Team service'}));
  const pending = {...snapshot, operation: {id: 'operation', state: 'testing' as const}};
  vi.mocked(setupNode).mockResolvedValue(pending);
  await userEvent.click(screen.getByRole('button', {name: 'Test and save'}));
  await userEvent.click(await screen.findByRole('button', {name: 'Cancel verification'}));
  expect(screen.queryByText(/Verification cancelled without saving/)).not.toBeInTheDocument();
  vi.mocked(setupNode).mockResolvedValue({...pending, revision: 'r2', operation: {id: 'operation', state: 'succeeded'}});
  await act(() => cache.invalidateQueries({queryKey: ['node-setup']}));
  expect(await screen.findByText(/Connection verified and saved/)).toBeInTheDocument();
});
it('offers a connection guide for missing or offline computers without reporting an empty model configuration', async () => {
  vi.mocked(getOnboarding).mockResolvedValue({nodes: [], agents: [], install});
  mount();
  expect(await screen.findByRole('link', {name: 'Connect computer →'})).toHaveAttribute('href', '/onboarding');
  expect(screen.queryByText('No model services yet')).not.toBeInTheDocument();
});


it('updates the visible name and capabilities when another catalog model is selected', async () => {
  vi.mocked(setupNode).mockResolvedValue({...snapshot, catalog: [{provider: 'deepseek', display_name: 'DeepSeek', models: [...snapshot.catalog[0].models, {id: 'different-model', name: 'Different model', contextWindow: 256000, maxTokens: 16384, inputModalities: ['text', 'image']}]}]});
  mount();
  await userEvent.click(await screen.findByRole('button', {name: '+ Add service'}));
  await userEvent.clear(screen.getByLabelText('Model ID'));
  await userEvent.type(screen.getByLabelText('Model ID'), 'different-model');
  expect(screen.getByLabelText('Model display name')).toHaveValue('Different model');
  await userEvent.click(screen.getByText('Model capabilities'));
  expect(screen.getByLabelText('Context window')).toHaveValue(256000);
  expect(screen.getByLabelText('Maximum output tokens')).toHaveValue(16384);
  expect(screen.getByLabelText('Supports image input')).toBeChecked();
});
