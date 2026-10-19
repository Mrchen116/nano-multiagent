import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { setLanguage } from '../../i18n';
import { PersonalAgentDialog } from './personal-agent-dialog';
import { PersonalAgentCollaboration } from './personal-agent-collaboration';
import * as api from './personal-agent-api';
import type { Conversation } from '../chat/chat-types';
vi.mock('./personal-agent-api');
const state:api.PersonalAgentState={binding:{binding_id:'pa1',agent_id:'a1',owner_id:'o1',owner_user_id:'u1',node_id:'n1',node_epoch:1,conversation_id:'pa-chat',display_name:'Aster',status:'active'},policy:{revision:4,excluded_conversation_ids:[]}};
const clients:QueryClient[]=[];
function mount(element:React.ReactNode) {
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
 return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>);
}
beforeEach(async()=>{
 vi.resetAllMocks();await act(async()=>setLanguage('en'));
 vi.mocked(api.getPersonalIncidents).mockResolvedValue({items:[]});
});
afterEach(()=>{clients.splice(0).forEach(c=>c.clear());});
it('creates without a task and retries the same operation after an uncertain result',async()=>{
 const done=vi.fn();vi.mocked(api.createPersonalAgent).mockRejectedValueOnce(new Error('lost response')).mockResolvedValue(state);
 mount(<PersonalAgentDialog state={{binding:null,policy:null}} nodes={[{node_id:'n1',node_name:'Computer',status:'online'}]} conversations={[]} onClose={()=>{}} onCreated={done}/>);
 await userEvent.clear(screen.getByLabelText('Name'));await userEvent.type(screen.getByLabelText('Name'),'Aster');
 expect(screen.queryByRole('textbox',{name:/work on/})).not.toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Create personal assistant'}));await screen.findByRole('alert');
 const first=vi.mocked(api.createPersonalAgent).mock.calls[0][0];
 expect(first).toMatchObject({display_name:'Aster',node_id:'n1'});
 expect(first).not.toHaveProperty('initial_goal');
 expect(first).not.toHaveProperty('history_days');
 expect(first).not.toHaveProperty('observation_enabled');
 expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
 expect(done).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole('button',{name:'Create personal assistant'}));await waitFor(()=>expect(done).toHaveBeenCalledWith('pa-chat'));
 expect(vi.mocked(api.createPersonalAgent).mock.calls[1][0].request_key).toBe(first.request_key);
});
it('offers source exclusions and ordinary configuration without retired observation or cleanup controls',async()=>{
 vi.mocked(api.updatePersonalAgentPolicy).mockResolvedValue({...state.policy!,revision:5});
 mount(<PersonalAgentDialog state={state} nodes={[]} conversations={[{id:'private',title:'Private group'} as Conversation]} onClose={()=>{}} onCreated={()=>{}}/>);
 expect(screen.getByRole('link',{name:'Model, instructions & capabilities'})).toHaveAttribute('href','/settings/agents/a1');
 expect(screen.queryByText('Clear assistant source cache')).not.toBeInTheDocument();
 expect(screen.queryByRole('checkbox',{name:/Observe/})).not.toBeInTheDocument();
 await userEvent.click(screen.getByText('Chats excluded from assistant access'));
 await userEvent.click(screen.getByRole('checkbox',{name:'Private group'}));
 await waitFor(()=>expect(api.updatePersonalAgentPolicy).toHaveBeenLastCalledWith({expected_revision:4,excluded_conversation_ids:['private']}));
});
it('restores a pending creation from the server instead of creating a second identity',async()=>{
 const pending={...state,binding:{...state.binding!,status:'pending'},creation:{request_key:'original-key'}};
 vi.mocked(api.createPersonalAgent).mockResolvedValue(state);
 mount(<PersonalAgentDialog state={pending} nodes={[]} conversations={[]} onClose={()=>{}} onCreated={()=>{}}/>);
 await userEvent.click(screen.getByRole('button',{name:'Retry setup'}));
 await waitFor(()=>expect(api.createPersonalAgent).toHaveBeenCalledWith(expect.objectContaining({request_key:'original-key',node_id:'n1'})));
});

it('treats an incident as information and records misunderstanding without approving disclosure',async()=>{
 vi.mocked(api.getPersonalIncidents).mockResolvedValue({items:[{id:'incident',actor_id:'lin',actor_name:'Lin',conversation_id:'lin-chat',source_message_id:'source',category:'private',reason:'Repeated request for private notes after refusal.',count:2,status:'open',owner_notice_message_id:'notice'}]});
 vi.mocked(api.respondToPersonalIncident).mockResolvedValue({} as api.PersonalIncident);
 mount(<PersonalAgentCollaboration state={state}/>);
 await userEvent.click(await screen.findByText('Privacy notices',{exact:false}));
 await screen.findByText('Repeated request for private notes after refusal.');
 expect(screen.getByText('This is an information notice. No action is needed to keep the disclosure blocked.')).toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Misunderstanding; continue collaborating'}));
 await waitFor(()=>expect(api.respondToPersonalIncident).toHaveBeenCalledWith('incident','misunderstanding'));
 expect(api.updatePersonalAgentPolicy).not.toHaveBeenCalled();
});

it('shows a saved owner request awaiting processing and removes it when processing completes',async()=>{
 const view=mount(<PersonalAgentCollaboration state={state} pendingOwnerInput/>);
 expect(screen.getByRole('status')).toHaveTextContent('Working on your request');
 view.unmount();
 mount(<PersonalAgentCollaboration state={state} pendingOwnerInput={false}/>);
 expect(screen.queryByText('Working on your request…')).not.toBeInTheDocument();
});
