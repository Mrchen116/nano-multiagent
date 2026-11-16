import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { setLanguage } from '../../../i18n';
import { CooperationGuide } from './cooperation-guide';
import { getAgentRole } from '../../settings/agents/im-agent-config-api';
vi.mock('../../settings/agents/im-agent-config-api', () => ({getAgentRole:vi.fn()}));
let client: QueryClient;
const agent = {id:'a', name:'Aster', personal:true, online:true};
beforeEach(async () => { vi.resetAllMocks(); await act(async()=>setLanguage('en')); client=new QueryClient({defaultOptions:{queries:{retry:false}}}); vi.mocked(getAgentRole).mockResolvedValue({content:'',version:null}); });
afterEach(()=>{cleanup();client.clear();});
function mount(props:Partial<React.ComponentProps<typeof CooperationGuide>>={}) {
  const onStart=vi.fn();
  const element=(next={})=><QueryClientProvider client={client}><CooperationGuide agent={agent} messageCount={0} canStart onStart={onStart} {...props} {...next}/></QueryClientProvider>;
  const view=render(element());return {...view,onStart,update:(next:object)=>view.rerender(element(next))};
}
it('starts with owner context, only seeds a draft, and permits deferral and resumption', async()=>{
 const view=mount();await screen.findByText('Let Aster get to know you');
 await userEvent.click(screen.getByRole('button',{name:'Introduce myself'}));
 expect(view.onStart).toHaveBeenCalledWith(expect.stringContaining('get to know me'));
 expect(screen.queryByText('Working agreement saved')).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Start with a task, discuss this later'}));
 await userEvent.click(screen.getByRole('button',{name:'Continue setup'}));
 expect(view.onStart).toHaveBeenLastCalledWith(expect.stringContaining('earlier conversation'));
 view.update({messageCount:1});expect(screen.getByText('Discussing the agreement · not saved yet')).toBeInTheDocument();
});
it('shows actual saved content after a new message, then withdraws success when offline',async()=>{
 const view=mount();await screen.findByText('Let Aster get to know you');
 vi.mocked(getAgentRole).mockResolvedValue({content:'Track commitments. Draft replies for approval.',version:'v1'});
 view.update({messageCount:2});await screen.findByText(/Working agreement saved/);
 expect(screen.queryByRole('button',{name:'Introduce myself'})).not.toBeInTheDocument();
 await userEvent.click(screen.getByText(/Working agreement saved/));expect(screen.getByText('Track commitments. Draft replies for approval.')).toBeVisible();
 view.update({agent:{...agent,online:false},messageCount:2});expect(screen.queryByText(/Working agreement saved/)).not.toBeInTheDocument();expect(screen.getByRole('status')).toHaveTextContent('offline');
});
it('distinguishes failed reads from unset and retries',async()=>{
 vi.mocked(getAgentRole).mockRejectedValue(new Error('unavailable'));mount();await screen.findByText('The agreement could not be verified. Your conversation is still here.');
 expect(screen.queryByText('Let Aster get to know you')).not.toBeInTheDocument();
 vi.mocked(getAgentRole).mockResolvedValue({content:'',version:null});await userEvent.click(screen.getByRole('button',{name:'Read again'}));await screen.findByText('Let Aster get to know you');
});
it('uses Global responsibilities, respects existing drafts and skips setup for an existing agreement',async()=>{
 const view=mount({agent:{...agent,personal:false},canStart:false});await screen.findByText('Agree on Aster’s responsibilities');
 expect(screen.getByRole('button',{name:'Discuss the context and goals'})).toBeDisabled();
 vi.mocked(getAgentRole).mockResolvedValue({content:'Own delivery quality.',version:'v2'});
 await act(async()=>{await client.invalidateQueries();});await waitFor(()=>expect(screen.getByText(/Working agreement saved/)).toBeInTheDocument());
 expect(screen.queryByText('Agree on Aster’s responsibilities')).not.toBeInTheDocument();expect(view.onStart).not.toHaveBeenCalled();
});
