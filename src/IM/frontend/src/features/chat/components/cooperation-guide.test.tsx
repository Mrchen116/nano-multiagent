import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, cleanup, waitFor } from '@testing-library/react';
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
  return {onStart,...render(<QueryClientProvider client={client}><CooperationGuide agent={agent} canStart onStart={onStart} {...props}/></QueryClientProvider>)};
}
it('only seeds a draft and dismisses the whole guide when deferred', async()=>{
 const view=mount();await screen.findByText('Let Aster get to know you');
 expect(screen.getByText('Or get to know each other and discuss working together').closest('details')).not.toHaveAttribute('open');
 await userEvent.click(screen.getByText('Or get to know each other and discuss working together'));
 await userEvent.click(screen.getByRole('button',{name:'Introduce myself'}));
 expect(view.onStart).toHaveBeenCalledWith(expect.stringContaining('get to know me'));
 await userEvent.click(screen.getByRole('button',{name:'Start with a task, discuss this later'}));
 expect(screen.queryByRole('region',{name:'Working agreement'})).not.toBeInTheDocument();
});
it('does not display a saved role or its status in chat',async()=>{
 vi.mocked(getAgentRole).mockResolvedValue({content:'Track commitments. Draft replies for approval.',version:'v1'});
 const {container}=mount();
 await waitFor(()=>expect(client.getQueryState(['settings','agents','a','role'])?.status).toBe('success'));
 expect(container.querySelector('.assistant-agreement')).toBeNull();
 expect(screen.queryByRole('region',{name:'Working agreement'})).not.toBeInTheDocument();
 expect(screen.getByRole('button',{name:/Untangle an idea/})).toBeEnabled();
});
it('does not replace a failed role lookup with setup or a role status panel',async()=>{
 vi.mocked(getAgentRole).mockRejectedValue(new Error('unavailable'));
 const {container}=mount();
 await waitFor(()=>expect(client.getQueryState(['settings','agents','a','role'])?.status).toBe('error'));
 expect(container.querySelector('.assistant-agreement')).toBeNull();
 expect(screen.queryByRole('region',{name:'Working agreement'})).not.toBeInTheDocument();
 expect(screen.getByRole('button',{name:/Untangle an idea/})).toBeEnabled();
});
it('uses Global responsibilities and respects existing drafts',async()=>{
 const view=mount({agent:{...agent,personal:false},canStart:false});await screen.findByText('Agree on Aster’s responsibilities');
 expect(screen.getByRole('button',{name:'Discuss the context and goals'})).toBeDisabled();
 expect(view.onStart).not.toHaveBeenCalled();
});
