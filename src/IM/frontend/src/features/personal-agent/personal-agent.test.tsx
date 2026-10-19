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
const state:api.PersonalAgentState={binding:{binding_id:'pa1',agent_id:'a1',owner_id:'o1',owner_user_id:'u1',node_id:'n1',node_epoch:1,conversation_id:'pa-chat',display_name:'Aster',status:'active'},policy:{revision:4,observation_enabled:true,excluded_conversation_ids:[]}};
const clients:QueryClient[]=[];
function mount(element:React.ReactNode) {
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
 return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>);
}
beforeEach(async()=>{
 vi.resetAllMocks();await act(async()=>setLanguage('en'));
 vi.mocked(api.getPersonalIncidents).mockResolvedValue({items:[]});
 vi.mocked(api.getPersonalAssistance).mockResolvedValue({items:[]});
 vi.mocked(api.getPersonalDecisions).mockResolvedValue({items:[]});
 vi.mocked(api.getPersonalAgentCleanup).mockResolvedValue({items:[]});
});
afterEach(()=>{clients.splice(0).forEach(c=>c.clear());});
it('creates with the original goal exactly once and retries the same operation after an uncertain result',async()=>{
 const done=vi.fn();vi.mocked(api.createPersonalAgent).mockRejectedValueOnce(new Error('lost response')).mockResolvedValue(state);
 mount(<PersonalAgentDialog state={{binding:null,policy:null}} nodes={[{node_id:'n1',node_name:'Computer',status:'online'}]} conversations={[]} onClose={()=>{}} onCreated={done}/>);
 await userEvent.clear(screen.getByLabelText('Name'));await userEvent.type(screen.getByLabelText('Name'),'Aster');
 await userEvent.type(screen.getByLabelText('What would you like to work on? (optional)'),'Coordinate my launch');
 await userEvent.click(screen.getByRole('button',{name:'Create and start'}));await screen.findByRole('alert');
 const first=vi.mocked(api.createPersonalAgent).mock.calls[0][0];
 expect(first).toMatchObject({display_name:'Aster',node_id:'n1',initial_goal:'Coordinate my launch',observation_enabled:true});
 expect(first).not.toHaveProperty('history_days');
 expect(done).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole('button',{name:'Create and start'}));await waitFor(()=>expect(done).toHaveBeenCalledWith('pa-chat'));
 expect(vi.mocked(api.createPersonalAgent).mock.calls[1][0].request_key).toBe(first.request_key);
});
it('pauses observation without pausing goals, and excludes only the selected source with its current revision',async()=>{
 vi.mocked(api.updatePersonalAgentPolicy).mockResolvedValue({...state.policy!,revision:5});
 mount(<PersonalAgentDialog state={state} nodes={[]} conversations={[{id:'private',title:'Private group'} as Conversation]} onClose={()=>{}} onCreated={()=>{}}/>);
 await userEvent.click(screen.getByRole('checkbox',{name:'Observe new messages and follow up'}));
 await waitFor(()=>expect(api.updatePersonalAgentPolicy).toHaveBeenCalledWith({expected_revision:4,observation_enabled:false}));
 expect(api.setPersonalAssistancePaused).not.toHaveBeenCalled();
 await userEvent.click(screen.getByText('Chats excluded from assistant access'));
 await userEvent.click(screen.getByRole('checkbox',{name:'Private group'}));
 await waitFor(()=>expect(api.updatePersonalAgentPolicy).toHaveBeenLastCalledWith({expected_revision:4,excluded_conversation_ids:['private']}));
});
it('keeps a cleanup pending until the computer reports completion',async()=>{
 vi.mocked(api.cleanupPersonalAgent).mockResolvedValue({operation_id:'op1',status:'pending'});
 mount(<PersonalAgentDialog state={state} nodes={[]} conversations={[]} onClose={()=>{}} onCreated={()=>{}}/>);
 await userEvent.click(screen.getByText('Clear assistant source cache'));
 await userEvent.click(screen.getByRole('button',{name:'Clear source cache'}));
 expect(await screen.findByText('Requested; waiting for your computer to confirm completion.')).toBeInTheDocument();
 expect(screen.queryByText('Source cache cleared.')).not.toBeInTheDocument();
});
it('uses the real decision and goal revisions while keeping an edited draft private until the owner sends',async()=>{
 const draft:api.PersonalDecision={id:'draft',task_ref:null,kind:'draft',question:'Reply to Lin',options:[],recommended:null,target_conversation_id:'lin',source_message_id:'m-old',content:'Wednesday works.',status:'pending',revision:3,snooze_until:null};
 vi.mocked(api.getPersonalDecisions).mockResolvedValue({items:[draft,{id:'decision',task_ref:'g/n',kind:'choice',question:'Choose a venue',options:[{id:'small',label:'Small room',consequence:'Within your budget'}],recommended:'small',status:'pending',revision:7,snooze_until:null}]});
 vi.mocked(api.getPersonalAssistance).mockResolvedValue({items:[{task_ref:'g/n',task:{title:'Launch',status:'doing'},next_action:'Compare venues',next_check_at:null,waiting_on:'Lin',decision_id:'decision',paused:false,revision:9,status:'active'}]});
 vi.mocked(api.setPersonalAssistancePaused).mockResolvedValue({items:[]});
 vi.mocked(api.resolvePersonalDecision).mockResolvedValue({} as api.PersonalDecision);
 const onDraft=vi.fn();mount(<PersonalAgentCollaboration state={state} onDraft={onDraft}/>);
 await screen.findByText('Goals',{exact:false});
 await userEvent.click(screen.getByText('Goals',{exact:false}));
 await userEvent.clear(screen.getByLabelText('Reply draft'));await userEvent.type(screen.getByLabelText('Reply draft'),'Thursday works.');
 await userEvent.click(screen.getByRole('button',{name:'Use in original chat'}));
 expect(onDraft).toHaveBeenCalledWith(draft,'Thursday works.');expect(api.resolvePersonalDecision).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole('button',{name:/Small room/}));
 await waitFor(()=>expect(api.resolvePersonalDecision).toHaveBeenCalledWith('decision',expect.objectContaining({expected_revision:7,option:'small'})));
 await userEvent.click(screen.getByRole('button',{name:'Pause this goal'}));
 await waitFor(()=>expect(api.setPersonalAssistancePaused).toHaveBeenCalledWith('g/n',true,9));
});

it('restores a pending creation from the server instead of creating a second identity',async()=>{
 const pending={...state,binding:{...state.binding!,status:'pending'},creation:{request_key:'original-key',initial_goal:'Saved goal'}};
 vi.mocked(api.createPersonalAgent).mockResolvedValue(state);
 mount(<PersonalAgentDialog state={pending} nodes={[]} conversations={[]} onClose={()=>{}} onCreated={()=>{}}/>);
 await userEvent.click(screen.getByRole('button',{name:'Retry setup'}));
 await waitFor(()=>expect(api.createPersonalAgent).toHaveBeenCalledWith(expect.objectContaining({request_key:'original-key',initial_goal:'Saved goal',node_id:'n1'})));
});

it('treats an incident as information and records misunderstanding without approving disclosure',async()=>{
 vi.mocked(api.getPersonalIncidents).mockResolvedValue({items:[{id:'incident',actor_id:'lin',actor_name:'Lin',conversation_id:'lin-chat',source_message_id:'source',category:'private',reason:'Repeated request for private notes after refusal.',count:2,status:'open',owner_notice_message_id:'notice'}]});
 vi.mocked(api.respondToPersonalIncident).mockResolvedValue({} as api.PersonalIncident);
 mount(<PersonalAgentCollaboration state={state} onDraft={()=>{}}/>);
 await screen.findByText('Repeated request for private notes after refusal.');
 expect(screen.getByText('This is an information notice. No action is needed to keep the disclosure blocked.')).toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Misunderstanding; continue collaborating'}));
 await waitFor(()=>expect(api.respondToPersonalIncident).toHaveBeenCalledWith('incident','misunderstanding'));
 expect(api.resolvePersonalDecision).not.toHaveBeenCalled();
 expect(api.updatePersonalAgentPolicy).not.toHaveBeenCalled();
});
