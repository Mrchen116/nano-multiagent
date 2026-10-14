import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { setLanguage } from '../../../i18n';
const api=vi.hoisted(()=>({listAgentPlugins:vi.fn(),manageAgentPlugin:vi.fn()}));
vi.mock('./im-agent-config-api',()=>api);
import { AgentPluginsPanel } from './agent-plugins-panel';

const entry={name:'report-style',display_name:'Report style',description:'Format expense reports',version:'1.0.0',enabled:true,state:'enabled',rows:[],removable:true,diagnostics:[]};
const view={workspace:'/workspace',entries:[entry]};
function mount(){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><AgentPluginsPanel agentId="a"/></QueryClientProvider>);}
beforeEach(()=>{setLanguage('en');vi.resetAllMocks();api.listAgentPlugins.mockResolvedValue(view);});
it('lists zero-tool plugins and retains actual state while a switch waits', async()=>{
  api.manageAgentPlugin.mockResolvedValue({...view,pending:{action:'set_bundle',target:'report-style',enabled:false,phase:'waiting'}});
  mount();
  const toggle=await screen.findByRole('switch',{name:'Report style'});
  expect(toggle).toHaveAttribute('aria-checked','true');
  await userEvent.click(toggle);
  await waitFor(()=>expect(toggle).toBeDisabled());
  expect(toggle).toHaveAttribute('aria-checked','true');
  expect(screen.getByRole('status')).toHaveTextContent(/Waiting/i);
  expect(api.manageAgentPlugin).toHaveBeenCalledWith('a',{action:'set_bundle',target:'report-style',enabled:false});
});
it('requires inline confirmation for uninstall and keeps errors distinct from empty', async()=>{
  api.manageAgentPlugin.mockRejectedValue(new Error('Node disconnected'));
  mount(); await screen.findByText('Report style');
  await userEvent.click(screen.getByText('Details'));
  await userEvent.click(screen.getByRole('button',{name:'Uninstall'}));
  expect(api.manageAgentPlugin).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button',{name:'Confirm uninstall'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Node disconnected');
  expect(screen.getByText('Report style')).toBeVisible();
});
it('shows an unavailable read with refresh instead of an empty collection', async()=>{
  api.listAgentPlugins.mockRejectedValue(new Error('Offline'));
  mount(); expect(await screen.findByRole('alert')).toHaveTextContent(/unable|unavailable/i);
  expect(screen.getByRole('button',{name:'Refresh'})).toBeEnabled();
  expect(screen.queryByText('No plugins yet')).not.toBeInTheDocument();
});
