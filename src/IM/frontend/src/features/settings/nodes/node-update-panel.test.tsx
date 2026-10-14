import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { setLanguage } from '../../../i18n';
import { NodeUpdatePanel } from './node-update-panel';
import { NodeChip } from '../../chat/components/node-chip';
import { startNodeUpdate, cancelNodeUpdate, type NodeUpdateView } from '../im-settings-api';
vi.mock('../im-settings-api',()=>({startNodeUpdate:vi.fn(),cancelNodeUpdate:vi.fn()}));
const value:NodeUpdateView={installation:'managed',current:{version:'1.2.2'},target:{version:'1.2.3',sha256:'hash',release_notes:'Improved reconnects'},available:true,reason:'available',operation:null,install_command:'curl https://im.test/install.sh'};
function show(update=value){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{mutations:{retry:false}}})}><NodeUpdatePanel nodeId="my-computer" update={update}/></QueryClientProvider>);}
beforeEach(()=>{vi.resetAllMocks();setLanguage('en');});
it('starts from one click with the displayed version and a stable authorization id',async()=>{
  vi.mocked(startNodeUpdate).mockResolvedValue({});show();
  expect(startNodeUpdate).not.toHaveBeenCalled();
  expect(screen.getByText('Improved reconnects')).toBeVisible();
  await userEvent.click(screen.getByRole('button',{name:'Update'}));
  await waitFor(()=>expect(startNodeUpdate).toHaveBeenCalledTimes(1));
  expect(startNodeUpdate).toHaveBeenCalledWith('my-computer',{request_id:expect.any(String),version:'1.2.3',sha256:'hash'});
});
it('allows cancellation while waiting, but removes it once switching starts',async()=>{
  const operation={id:'op',state:'waiting',cancel_requested:false,relay_gated:true,request_id:'request'};
  vi.mocked(cancelNodeUpdate).mockResolvedValue({});const view=show({...value,reason:'active',available:false,operation});
  await userEvent.click(screen.getByRole('button',{name:'Cancel update'}));
  expect(cancelNodeUpdate).toHaveBeenCalledWith('my-computer','op');
  view.unmount();show({...value,reason:'active',available:false,operation:{...operation,state:'switching'}});
  expect(screen.queryByRole('button',{name:'Cancel update'})).not.toBeInTheDocument();
  expect(screen.getByText('Updating')).toBeVisible();
});
it('shows the next published release after a previous update succeeded',()=>{
  show({...value,operation:{id:'previous',state:'succeeded',cancel_requested:false,relay_gated:false,request_id:'previous-click'}});
  expect(screen.getByRole('heading',{name:/Nano 1.2.3 is ready/})).toBeVisible();
  expect(screen.getByText('Improved reconnects')).toBeVisible();
});
it('clears an obsolete failure after a manual installation reaches the published version',()=>{
  show({...value,current:{version:'1.2.3'},available:false,reason:'current',operation:{id:'old-failure',state:'failed',cancel_requested:false,relay_gated:false,request_id:'old-click'}});
  expect(screen.queryByTestId('node-update-my-computer')).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Retry'})).not.toBeInTheDocument();
});
it('disables offline updates and gives a precise recovery link after a failed switch',()=>{
  const offline=show({...value,reason:'offline',available:false});expect(screen.queryByRole('button',{name:'Update'})).not.toBeInTheDocument();offline.unmount();
  render(<MemoryRouter><NodeChip nodeName="My computer" nodeId="my-computer" status="offline" update={{...value,reason:'recovery_required',available:false,operation:{id:'op',state:'recovery_required',relay_gated:true,cancel_requested:false,request_id:'request'}}}/></MemoryRouter>);
  expect(screen.getByRole('link',{name:/Recovery needed/})).toHaveAttribute('href','/settings/nodes#node-my-computer');
  expect(screen.queryByText('Update available')).not.toBeInTheDocument();
});
