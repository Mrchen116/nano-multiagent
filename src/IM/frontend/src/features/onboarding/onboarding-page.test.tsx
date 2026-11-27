import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { OnboardingPage } from './onboarding-page';
import { useAuthStore } from '../auth/auth-store';
import { TEST_AUTH_USER } from '../../test/render-router';
import { setLanguage } from '../../i18n';
import { getOnboarding, setupNode } from './onboarding-api';
import { bindingTargetKey } from './binding-target';
import { createPersonalAgent, getPersonalAgent } from '../personal-agent/personal-agent-api';
import { createConversation, listConversations } from '../chat/chat-api';
vi.mock('./onboarding-api');
vi.mock('../personal-agent/personal-agent-api');
vi.mock('../chat/chat-api');
const pa={binding:{binding_id:'b',agent_id:'a',owner_id:'o',owner_user_id:'u',node_id:'device',node_epoch:1,conversation_id:'existing',display_name:'Assistant',status:'active'},policy:{revision:1,excluded_conversation_ids:[]}};
const computer = { node_id: 'device', node_name: 'My computer', alias: null, status: 'online' };
const install = { available: true, origin: 'https://nano.example', command: 'install Nano', script_url: 'https://nano.example/install.sh' };
const modelStatus = { revision: 'r1', services: [], models: [], catalog: [{provider: 'deepseek', display_name: 'DeepSeek', models: [{id: 'deepseek-chat'}]}], default_model: '', workspace_base: '/my-workspaces' };
function mount(cache = new QueryClient({ defaultOptions: { queries: { retry: false } } }), path = '/onboarding') {
 const router = createMemoryRouter([{ path: '/onboarding', element: <OnboardingPage /> }, { path: '/chat/:id', element: <p>Chat opened</p> }], { initialEntries: [path] });
 render(<QueryClientProvider client={cache}><RouterProvider router={router} /></QueryClientProvider>);
 return router;
}
beforeEach(() => {
 vi.resetAllMocks(); localStorage.clear(); setLanguage('en');
 Object.defineProperty(window,'innerWidth',{configurable:true,writable:true,value:1280});
 useAuthStore.getState().setSession({ access_token: 'test', user: { ...TEST_AUTH_USER, personal_space_enabled: true, membership_status: 'none' } });
 vi.mocked(getPersonalAgent).mockResolvedValue({binding:null,policy:null});
 vi.mocked(getOnboarding).mockResolvedValue({ nodes: [computer], agents: [], install });
 vi.mocked(setupNode).mockResolvedValue(modelStatus);
});
it('keeps failed model validation on the model step and never stores the entered key', async () => {
 mount();
 await screen.findByRole('heading', { name: 'Connect a model' });
 await screen.findByLabelText('API Key');
 await userEvent.type(screen.getByLabelText('API Key'), 'private-key-example');
 expect(screen.getByLabelText('Model')).toHaveValue('deepseek-chat');
 vi.mocked(setupNode).mockResolvedValue({ ...modelStatus, operation: { id: 'op', state: 'failed' } });
 await userEvent.click(screen.getByRole('button', { name: 'Verify and continue' }));
 await screen.findByRole('alert');
 expect(screen.queryByRole('button', { name: 'Continue' })).not.toBeInTheDocument();
 expect(screen.getByRole('button', { name: 'Verify and continue' })).toBeEnabled();
 expect(screen.getByLabelText('API Key')).toHaveValue('private-key-example');
 expect(Array.from({length: localStorage.length}, (_, i) => localStorage.getItem(localStorage.key(i)!)).join(' ')).not.toContain('private-key-example');
 expect(createPersonalAgent).not.toHaveBeenCalled();
});
it('creates one personal assistant and preserves the name and operation key for retry', async () => {
 vi.mocked(setupNode).mockResolvedValue({ ...modelStatus, default_model: 'model-one', models: [{ provider: 'p', model: 'model-one' }] });
 vi.mocked(createPersonalAgent).mockRejectedValue(new Error('offline'));
 mount();
 await screen.findByRole('heading', { name: 'Name your personal assistant' });
 const button = screen.getByRole('button', { name: 'Create personal assistant' });
 await waitFor(() => expect(button).toBeEnabled());
 await userEvent.click(button);
 await screen.findByRole('alert');
 const first = vi.mocked(createPersonalAgent).mock.calls[0][0];
 expect(first).toMatchObject({node_id:'device'});
 expect(first).not.toHaveProperty('observation_enabled');
 expect(first).not.toHaveProperty('history_days');
 await userEvent.click(screen.getByRole('button', { name: 'Check and retry' }));
 await waitFor(() => expect(createPersonalAgent).toHaveBeenCalledTimes(2));
 expect(vi.mocked(createPersonalAgent).mock.calls[1][0].request_key).toBe(first.request_key);
});
it('reopens the canonical PA chat without replacing the owner draft or converting an ordinary agent', async () => {
 vi.mocked(getPersonalAgent).mockResolvedValue(pa);
 vi.mocked(getOnboarding).mockResolvedValue({ nodes: [computer], agents: [{ agent_id: 'a', display_name: 'Assistant', node_id: 'device', default_model: 'm', workspace_root: '/a', work_mode: 'global' }], install });
 vi.mocked(listConversations).mockResolvedValue([{ id: 'existing', type: 'direct', participants: [{ type: 'agent', id: 'a' }] }] as never);
 const router = mount();
 await userEvent.click(await screen.findByRole('button', { name: 'Open personal assistant →' }));
 await screen.findByText('Chat opened');
 expect(router.state.location.pathname).toBe('/chat/existing');
 expect(router.state.location.state).toBeNull();
 expect(createConversation).not.toHaveBeenCalled();
});
it('shows saved models without developer proxy discovery or a duplicate setup test', async () => {
 vi.mocked(setupNode).mockResolvedValue({...modelStatus, default_model: 'model-one', models: [{provider: 'p', model: 'model-one'}], services: [{provider: 'p', display_name: 'Team service', source: 'custom', native: false, credential_stored: true, models: [{name: 'model-one', id: 'model-one'}]}]});
 mount();
 await screen.findByRole('heading', {name: 'Name your personal assistant'});
 await userEvent.click(screen.getByRole('button', {name: '← Back'}));
 expect(await screen.findByRole('heading', {name: 'Team service'})).toBeInTheDocument();
 expect(screen.queryByText('Local model proxy')).not.toBeInTheDocument();
 expect(screen.getByRole('button', {name: 'Continue'})).toBeEnabled();
});
it('returns to computer recovery when an already-created assistant is offline', async () => {
 vi.mocked(getOnboarding).mockResolvedValue({nodes: [{...computer, status: 'offline'}], agents: [{agent_id: 'a', display_name: 'Assistant', node_id: 'device', default_model: 'm', workspace_root: '/a', work_mode: 'global'}], install});
 mount();
 await screen.findByRole('heading', {name: 'Connect your computer'});
 expect(screen.queryByRole('heading', {name: 'Assistant is ready'})).not.toBeInTheDocument();
 expect(screen.getByText(/Run the command on that computer again/)).toBeInTheDocument();
});

it('creates an empty personal chat without sending an old setup goal', async () => {
 vi.mocked(setupNode).mockResolvedValue({...modelStatus, default_model:'m',models:[{provider:'p',model:'m'}]});
 vi.mocked(createPersonalAgent).mockResolvedValue(pa);
 localStorage.setItem(`nano-onboarding:${TEST_AUTH_USER.id}`,JSON.stringify({goal:'Old setup draft'}));
 const router=mount();
 await screen.findByRole('heading',{name:'Name your personal assistant'});
 expect(screen.queryByRole('textbox',{name:/work on/})).not.toBeInTheDocument();
 expect(screen.queryByText('Start your first task')).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Jellybean'}));
 await userEvent.click(screen.getByRole('button',{name:'Mint'}));
 await userEvent.click(screen.getByRole('button',{name:'Create personal assistant'}));
 await screen.findByText('Chat opened');
 expect(createPersonalAgent).toHaveBeenCalledTimes(1);
 expect(vi.mocked(createPersonalAgent).mock.calls[0][0]).not.toHaveProperty('initial_goal');
 expect(vi.mocked(createPersonalAgent).mock.calls[0][0]).toHaveProperty('avatar_variant',7);
 expect(router.state.location.pathname).toBe('/chat/existing');
 expect(router.state.location.state).toBeNull();
 expect(createConversation).not.toHaveBeenCalled();
});

it('explains assistant-status failure and retries without losing the name or creating early', async () => {
 vi.mocked(setupNode).mockResolvedValue({...modelStatus,default_model:'m',models:[{provider:'p',model:'m'}]});
 vi.mocked(getPersonalAgent).mockRejectedValue(new Error('unavailable'));
 mount();
 await screen.findByRole('button',{name:'Retry assistant status'});
 await userEvent.clear(await screen.findByLabelText('Name your assistant'));
 await userEvent.type(screen.getByLabelText('Name your assistant'),'Poppy');
 expect(screen.getByRole('button',{name:'Create personal assistant'})).toBeDisabled();
 expect(screen.getByRole('alert')).toHaveTextContent('We couldn’t check your personal assistant');
 vi.mocked(getPersonalAgent).mockResolvedValue({binding:null,policy:null});
 await userEvent.click(screen.getByRole('button',{name:'Retry assistant status'}));
 await waitFor(()=>expect(screen.getByRole('button',{name:'Create personal assistant'})).toBeEnabled());
 expect(screen.getByLabelText('Name your assistant')).toHaveValue('Poppy');
 expect(createPersonalAgent).not.toHaveBeenCalled();
});

it('continues to naming only after the first model connection has succeeded', async () => {
 vi.mocked(setupNode).mockImplementation(async (_node,input)=> input.action==='save' ? {
   ...modelStatus,revision:'r2',default_model:'deepseek-chat',models:[{provider:'deepseek',model:'deepseek-chat'}],
   services:[{provider:'deepseek',display_name:'DeepSeek',source:'deepseek',native:true,credential_stored:true,models:[{name:'deepseek-chat',id:'deepseek-chat'}]}],
   operation:{id:'verified',state:'succeeded'},
 } : modelStatus);
 mount();
 await screen.findByLabelText('API Key');
 expect(screen.queryByLabelText('Service name')).not.toBeInTheDocument();
 expect(screen.queryByLabelText('Model display name')).not.toBeInTheDocument();
 await userEvent.type(screen.getByLabelText('API Key'),'private-test-key');
 await userEvent.click(screen.getByRole('button',{name:'Verify and continue'}));
 await screen.findByRole('heading',{name:'Name your personal assistant'});
 expect(setupNode).toHaveBeenCalledWith('device',expect.objectContaining({action:'save',source:'deepseek',api_key:'private-test-key',models:[expect.objectContaining({id:'deepseek-chat'})]}));
 expect(createPersonalAgent).not.toHaveBeenCalled();
});

it('keeps an API draft when switching to subscription authorization and back', async () => {
 vi.mocked(setupNode).mockResolvedValue({...modelStatus,catalog:[...modelStatus.catalog,{provider:'openai-codex',display_name:'Codex',models:[{id:'subscription-model'}]}]});
 mount();
 await screen.findByLabelText('API Key');
 await userEvent.type(screen.getByLabelText('API Key'),'draft-key');
 await userEvent.click(screen.getByRole('button',{name:'Use a ChatGPT / Codex subscription'}));
 expect(screen.getByRole('button',{name:'Connect Codex account'})).toBeEnabled();
 expect(screen.queryByLabelText('API Key')).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Use an API service'}));
 expect(screen.getByLabelText('API Key')).toHaveValue('draft-key');
 expect(vi.mocked(setupNode).mock.calls.every(([,input])=>input.action==='status')).toBe(true);
});

it('restores a pending subscription authorization after returning to setup', async () => {
 vi.mocked(setupNode).mockResolvedValue({...modelStatus,
   catalog:[...modelStatus.catalog,{provider:'openai-codex',display_name:'Codex',models:[{id:'subscription-model'}]}],
   operation:{id:'pending-login',state:'waiting',url:'https://example.test/authorize',code:'ABCD'},
 });
 mount();
 expect(await screen.findByRole('link',{name:'Open authorization page ↗'})).toHaveAttribute('href','https://example.test/authorize');
 expect(screen.getByRole('button',{name:'Cancel verification'})).toBeEnabled();
 expect(screen.getByRole('button',{name:'Use a ChatGPT / Codex subscription'})).toHaveAttribute('aria-pressed','true');
 expect(createPersonalAgent).not.toHaveBeenCalled();
});

it('explains the PA and prerequisites before first-time installation, then remembers starting', async () => {
 vi.mocked(getOnboarding).mockResolvedValue({nodes:[],agents:[],install});
 mount();
 await screen.findByRole('button',{name:'Set up my assistant'});
 expect(screen.getByRole('heading',{name:'Two things to have ready'})).toBeInTheDocument();
 expect(screen.getByRole('link',{name:'Explore my space first'})).toHaveAttribute('href','/chat');
 expect(screen.queryByRole('heading',{name:'Connect your computer'})).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Set up my assistant'}));
 await screen.findByRole('heading',{name:'Connect your computer'});
 expect(JSON.parse(localStorage.getItem(`nano-onboarding:${TEST_AUTH_USER.id}`)!)).toMatchObject({started:true});
 expect(createPersonalAgent).not.toHaveBeenCalled();
 expect(setupNode).not.toHaveBeenCalled();
});

it('resumes installation on a phone with handoff first and opt-in computer instructions', async () => {
 Object.defineProperty(window,'innerWidth',{configurable:true,writable:true,value:390});
 localStorage.setItem(`nano-onboarding:${TEST_AUTH_USER.id}`,JSON.stringify({started:true}));
 vi.mocked(getOnboarding).mockResolvedValue({nodes:[],agents:[],install});
 mount();
 await screen.findByRole('heading',{name:'Connect your computer'});
 expect(screen.getByRole('button',{name:'Copy link'})).toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Copy install command'})).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:/View computer installation steps/}));
 expect(screen.getByRole('button',{name:'Copy install command'})).toBeInTheDocument();
});

it('offers a Windows download or handoff and waits for the specifically bound computer to come online', async () => {
 const ua = vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Windows NT 10.0; Win64; x64');
 try {
   Object.defineProperty(window,'innerWidth',{configurable:true,writable:true,value:390});
   localStorage.setItem(`nano-onboarding:${TEST_AUTH_USER.id}`, JSON.stringify({started:true}));
   const materials = {...install, available:false, windows_x64:{
     download_url:'https://example.test/Crewden-Setup-x64.exe', connect_url:'crewden://connect?origin=https%3A%2F%2Fnano.example',
   }};
   const state = {nodes:[],agents:[],install:materials};
   vi.mocked(getOnboarding).mockResolvedValue(state);
   const cache = new QueryClient({defaultOptions:{queries:{retry:false}}});
   mount(cache);
   const download = await screen.findByRole('link', {name:'Download Windows installer'});
   expect(download).toHaveAttribute('href',materials.windows_x64.download_url);
   download.addEventListener('click', event => event.preventDefault(), {once:true});
   await userEvent.click(download);
   const open = screen.getByRole('link', {name:'Open Crewden to connect'});
   expect(open).toHaveAttribute('href',materials.windows_x64.connect_url);
   open.addEventListener('click', event => event.preventDefault(), {once:true});
   await userEvent.click(open);
   expect(screen.getByRole('link', {name:'Reopen Crewden'})).toBeInTheDocument();
   const queryKey = ['onboarding', TEST_AUTH_USER.id];
   await act(async () => { cache.setQueryData(queryKey, {...state, nodes:[computer]}); });
   expect(screen.queryByRole('button',{name:'Continue'})).toBeNull();
   expect(setupNode).not.toHaveBeenCalled();
   const key = bindingTargetKey(TEST_AUTH_USER.id);
   await act(async () => {
     localStorage.setItem(key, 'windows-computer');
     window.dispatchEvent(new StorageEvent('storage',{key,newValue:'windows-computer'}));
   });
   const selected = {...computer,node_id:'windows-computer',node_name:'My Windows PC'};
   await act(async () => { cache.setQueryData(queryKey,{...state,nodes:[computer,{...selected,status:'offline'}]}); });
   expect(await screen.findByText('My Windows PC · Offline')).toBeInTheDocument();
   expect(screen.queryByRole('button',{name:'Continue'})).toBeNull();
   await act(async () => { cache.setQueryData(queryKey,{...state,nodes:[computer,selected]}); });
   expect(await screen.findByText('My Windows PC · Connected')).toBeInTheDocument();
   await userEvent.click(screen.getByRole('button',{name:'Continue'}));
   await screen.findByRole('heading',{name:'Connect a model'});
   expect(setupNode).toHaveBeenCalledWith('windows-computer',{action:'status'});
 } finally { ua.mockRestore(); }
});

it('lets the original browser choose its confirmed computer when the default browser holds the binding receipt', async () => {
 const targetKey = bindingTargetKey(TEST_AUTH_USER.id);
 localStorage.setItem(targetKey, '');
 localStorage.setItem(`nano-onboarding:${TEST_AUTH_USER.id}`, JSON.stringify({started:true}));
 vi.mocked(getOnboarding).mockResolvedValue({nodes:[computer],agents:[],install});
 mount();
 const choose = await screen.findByRole('combobox', {name:'Choose the computer you just confirmed'});
 expect(choose).toHaveValue('');
 expect(screen.queryByText('My computer · Connected')).toBeNull();
 await userEvent.selectOptions(choose, computer.node_id);
 expect(await screen.findByRole('heading', {name:'Connect a model'})).toBeInTheDocument();
 expect(setupNode).toHaveBeenCalledWith(computer.node_id, {action:'status'});
 expect(localStorage.getItem(targetKey)).toBe(computer.node_id);
});

it('selects the authenticated reconnect target before resuming setup', async () => {
 const key = bindingTargetKey(TEST_AUTH_USER.id);
 const selected = {...computer,node_id:'windows-computer',node_name:'My Windows PC',status:'offline'};
 vi.mocked(getOnboarding).mockResolvedValue({nodes:[computer,selected],agents:[],install});
 mount(undefined, '/onboarding?node=windows-computer');
 await screen.findByText('My Windows PC · Offline');
 expect(localStorage.getItem(key)).toBe('windows-computer');
 expect(setupNode).not.toHaveBeenCalled();
});

it.each([true,false])('resumes a pending assistant after refresh without mixing another draft (%s)', async (sameDraft) => {
 localStorage.setItem(`nano-onboarding:${TEST_AUTH_USER.id}`,JSON.stringify({requestKey:sameDraft?'original-key':'other-key',nodeId:'other-device',name:'',avatar:7}));
 const pending={...pa,binding:{...pa.binding,status:'pending'},creation:{request_key:'original-key'}};
 vi.mocked(getPersonalAgent).mockResolvedValue(pending);
 vi.mocked(getOnboarding).mockResolvedValue({nodes:[{...computer,node_id:'other-device'},computer],agents:[],install});
 vi.mocked(createPersonalAgent).mockRejectedValueOnce(new Error('not ready')).mockResolvedValueOnce(pa);
 const router=mount();
 await userEvent.click(await screen.findByRole('button',{name:'Retry setup'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Your computer has not confirmed creation');
 expect(router.state.location.pathname).toBe('/onboarding');
 expect(screen.queryByRole('button',{name:'Open personal assistant →'})).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Retry setup'}));
 await screen.findByText('Chat opened');
 expect(createPersonalAgent).toHaveBeenNthCalledWith(2,{request_key:'original-key',node_id:'device',display_name:'Assistant',...(sameDraft?{avatar_variant:7}:{})});
 expect(router.state.location.pathname).toBe('/chat/existing');
});

it('opens an already-created assistant chat while its runtime is unavailable', async () => {
 vi.mocked(getPersonalAgent).mockResolvedValue({...pa,binding:{...pa.binding,status:'unavailable'},creation:null});
 const router=mount();
 await userEvent.click(await screen.findByRole('button',{name:'Open personal assistant →'}));
 expect(router.state.location.pathname).toBe('/chat/existing');
 expect(createPersonalAgent).not.toHaveBeenCalled();
});

it('lifts Verify and continue into the pinned onboarding footer alongside Back during first-run API setup', async () => {
 mount();
 await screen.findByLabelText('API Key');
 const verifyBtn = screen.getByRole('button', { name: 'Verify and continue' });
 const backBtn = screen.getByRole('button', { name: '← Back' });
 expect(verifyBtn.closest('.onboarding-footer')).toBe(backBtn.closest('.onboarding-footer'));
 expect(verifyBtn).toHaveAttribute('form', 'onboarding-model-form');
});

it('maps pre-persistence node_offline and node_capabilities_timeout errors to distinct copy while preserving draft and request_key', async () => {
 vi.mocked(setupNode).mockResolvedValue({ ...modelStatus, default_model: 'model-one', models: [{ provider: 'p', model: 'model-one' }] });
 vi.mocked(createPersonalAgent)
   .mockRejectedValueOnce(Object.assign(new Error('offline'), { status: 503, code: 'node_offline' }))
   .mockRejectedValueOnce(Object.assign(new Error('timeout'), { status: 504, code: 'node_capabilities_timeout' }));
 mount();
 await screen.findByRole('heading', { name: 'Name your personal assistant' });
 await userEvent.clear(screen.getByLabelText('Name your assistant'));
 await userEvent.type(screen.getByLabelText('Name your assistant'), 'Atlas');

 await userEvent.click(screen.getByRole('button', { name: 'Create personal assistant' }));
 expect(await screen.findByRole('alert')).toHaveTextContent('Your selected computer is offline, so creation has not started yet');
 expect(screen.getByLabelText('Name your assistant')).toHaveValue('Atlas');

 await userEvent.click(screen.getByRole('button', { name: 'Check and retry' }));
 await waitFor(() => expect(createPersonalAgent).toHaveBeenCalledTimes(2));
 expect(await screen.findByRole('alert')).toHaveTextContent('Reading your computer runtime capabilities timed out');
 expect(vi.mocked(createPersonalAgent).mock.calls[1]![0].request_key).toBe(
   vi.mocked(createPersonalAgent).mock.calls[0]![0].request_key,
 );
});
