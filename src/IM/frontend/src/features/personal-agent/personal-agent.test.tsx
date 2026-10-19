import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { setLanguage } from '../../i18n';
import { PersonalAgentSettings } from './personal-agent-settings';
import { listConversations } from '../chat/chat-api';
import { listNodes } from '../settings/agents/im-agent-config-api';
import { PersonalAgentDialog } from './personal-agent-dialog';
import { PersonalAgentCollaboration } from './personal-agent-collaboration';
import * as api from './personal-agent-api';
import type { Conversation } from '../chat/chat-types';
vi.mock('./personal-agent-api');
vi.mock('../chat/chat-api');
vi.mock('../settings/agents/im-agent-config-api');
const state:api.PersonalAgentState={binding:{binding_id:'pa1',agent_id:'a1',owner_id:'o1',owner_user_id:'u1',node_id:'n1',node_epoch:1,conversation_id:'pa-chat',display_name:'Aster',status:'active'},policy:{revision:4,excluded_conversation_ids:[]}};
const clients:QueryClient[]=[];
function mount(element:React.ReactNode) {
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
 return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>);
}
beforeEach(async()=>{
 vi.resetAllMocks();await act(async()=>setLanguage('en'));
 vi.mocked(api.getPersonalIncidents).mockResolvedValue({items:[]});
 vi.mocked(api.getPersonalAgent).mockResolvedValue(state);
 vi.mocked(listConversations).mockResolvedValue([{id:'private',title:'Private group'} as Conversation]);
 vi.mocked(listNodes).mockResolvedValue([]);
});
afterEach(()=>{clients.splice(0).forEach(c=>c.clear());});
it('creates without a task and retries the same operation after an uncertain result',async()=>{
 const done=vi.fn();vi.mocked(api.createPersonalAgent).mockRejectedValueOnce(new Error('lost response')).mockResolvedValue(state);
 mount(<PersonalAgentDialog state={{binding:null,policy:null}} nodes={[{node_id:'n1',node_name:'Computer',status:'online'}]} onClose={()=>{}} onCreated={done}/>);
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
 mount(<PersonalAgentSettings agentId="a1"/>);
 await screen.findByRole('heading',{name:'Chat access'});
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
 expect(screen.queryByRole('textbox',{name:'Name'})).not.toBeInTheDocument();
 expect(screen.queryByText('Clear assistant source cache')).not.toBeInTheDocument();
 expect(screen.queryByRole('checkbox',{name:/Observe/})).not.toBeInTheDocument();
 await userEvent.click(screen.getByText('Excluded chats · 0'));
 await userEvent.click(screen.getByRole('checkbox',{name:'Private group'}));
 await waitFor(()=>expect(api.updatePersonalAgentPolicy).toHaveBeenLastCalledWith({expected_revision:4,excluded_conversation_ids:['private']}));
});
it('restores a pending creation from the server instead of creating a second identity',async()=>{
 const pending={...state,binding:{...state.binding!,status:'pending'},creation:{request_key:'original-key'}};
 vi.mocked(api.createPersonalAgent).mockResolvedValue(state);
 mount(<PersonalAgentDialog state={pending} nodes={[]} onClose={()=>{}} onCreated={()=>{}}/>);
 await userEvent.click(screen.getByRole('button',{name:'Retry setup'}));
 await waitFor(()=>expect(api.createPersonalAgent).toHaveBeenCalledWith(expect.objectContaining({request_key:'original-key',node_id:'n1'})));
});

it('preserves unsaved shared configuration before changing the PA computer',async()=>{
 vi.mocked(listNodes).mockResolvedValue([{node_id:'n2',node_name:'Other computer',status:'online'} as Awaited<ReturnType<typeof listNodes>>[number]]);
 mount(<PersonalAgentSettings agentId="a1" hasUnsavedChanges/>);
 await userEvent.click(await screen.findByText('Change working computer'));
 await userEvent.selectOptions(screen.getByRole('combobox',{name:'Computer'}),'n2');
 expect(screen.getByRole('button',{name:'Continue on this computer'})).toBeDisabled();
 expect(screen.getByText('Save or discard your configuration changes before changing computers.')).toBeInTheDocument();
 expect(api.restorePersonalAgent).not.toHaveBeenCalled();
});

it('groups repeated privacy notices and acknowledges without changing policy',async()=>{
 const incident={id:'incident',actor_id:'lin',actor_name:'Lin',conversation_id:'lin-chat',source_message_id:'source',category:'private',reason:'Repeated request for private notes after refusal.',count:2,status:'open',owner_notice_message_id:'notice'};
 vi.mocked(api.getPersonalIncidents).mockResolvedValue({items:[incident,{...incident,id:'second',source_message_id:'source-2',count:1}]});
 vi.mocked(api.respondToPersonalIncident).mockResolvedValue({} as api.PersonalIncident);
 mount(<PersonalAgentCollaboration state={state}/>);
 await userEvent.click(await screen.findByRole('button',{name:/Privacy protection/}));
 expect(screen.getAllByRole('heading',{name:'Lin'})).toHaveLength(1);
 expect(screen.getByText('Nothing to do. Your assistant declined these requests.')).toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Got it'}));
 await waitFor(()=>expect(api.respondToPersonalIncident).toHaveBeenCalledTimes(2));
 expect(api.respondToPersonalIncident).toHaveBeenCalledWith('incident','dismiss');
 expect(api.respondToPersonalIncident).toHaveBeenCalledWith('second','dismiss');
 expect(api.updatePersonalAgentPolicy).not.toHaveBeenCalled();
});

it('keeps privacy records available when acknowledging fails',async()=>{
 vi.mocked(api.getPersonalIncidents).mockResolvedValue({items:[{id:'incident',actor_id:'lin',actor_name:'Lin',conversation_id:'lin-chat',source_message_id:'source',category:'private',reason:'Private notes requested.',count:1,status:'open',owner_notice_message_id:'notice'}]});
 vi.mocked(api.respondToPersonalIncident).mockRejectedValue(new Error('offline'));
 mount(<PersonalAgentCollaboration state={state}/>);
 await userEvent.click(await screen.findByRole('button',{name:/Privacy protection/}));
 await userEvent.click(screen.getByRole('button',{name:'Got it'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Could not save');
 expect(screen.getByRole('button',{name:'Got it'})).toBeEnabled();
 expect(screen.getByRole('heading',{name:'Lin'})).toBeInTheDocument();
});

it('shows a saved owner request awaiting processing and removes it when processing completes',async()=>{
 const view=mount(<PersonalAgentCollaboration state={state} pendingOwnerInput/>);
 expect(screen.getByRole('status')).toHaveTextContent('Working on your request');
 view.unmount();
 mount(<PersonalAgentCollaboration state={state} pendingOwnerInput={false}/>);
 expect(screen.queryByText('Working on your request…')).not.toBeInTheDocument();
});
