import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import './interactive-card';
import { InteractionSubmissionError } from './submission-error';
import { MessagePane } from '../components/message-pane';
import { readInteractionDraft, saveInteractionDraft } from '../chat-api';
import type { Conversation, Message } from '../chat-types';
vi.mock('../chat-api', () => ({readInteractionDraft:vi.fn(),saveInteractionDraft:vi.fn()}));
const conversation={id:'chat',title:'Planner',type:'direct',direct_kind:'agent',participants:[{type:'agent',id:'a1',display_name:'Planner'}],participant_ids:['a1'],can_write:true} as Conversation;
const card={id:'card',conversation_id:'chat',sender:{type:'agent',id:'a1',display_name:'Planner'},sender_user_id:'a1',sender_type:'agent',content:'请确认草稿',attachments:[],created_at:'2026-10-19T08:00:00Z',delivery_status:'completed',permission_requests:[],interactive:{format:'openui',catalog_version:'nano-1',source:`root = Stack([form])
form = Form("draft", ContinueButton("send", "继续修改"), [FormControl("消息草稿", TextArea("body", "编辑草稿", 3, null, "周六见"))])`}} as Message;
beforeEach(()=>{
 vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:0,state:{},submission_message_id:null});
 vi.mocked(saveInteractionDraft).mockResolvedValue({draft_revision:1,state:{},submission_message_id:null});
});
describe('interactive choices and handwritten requests',()=>{
 it('keeps exact handwritten content beside edited fields and clears the attachment after successful send',async()=>{
  const send=vi.fn().mockResolvedValue(undefined);
  render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send}/>);
  fireEvent.change(await screen.findByPlaceholderText('编辑草稿', {}, {timeout:5000}),{target:{value:'林悦，周日10点断桥见'}});
  await screen.findByText(/将附带当前选择|Current choices will be attached/);
  const composer=screen.getByPlaceholderText(/Message Planner|发送消息给 Planner|给 Planner/);
  fireEvent.change(composer,{target:{value:'  先别发送，把语气改得随意一点  '}});
  fireEvent.submit(composer.closest('form')!);
  await waitFor(()=>expect(send).toHaveBeenCalledWith('  先别发送，把语气改得随意一点  ',[],expect.objectContaining({source_message_id:'card',state:expect.objectContaining({draft:expect.objectContaining({body:expect.objectContaining({value:'林悦，周日10点断桥见'})})})})));
  await waitFor(()=>expect(composer).toHaveValue(''));
  expect(screen.queryByText(/将附带当前选择|Current choices will be attached/)).not.toBeInTheDocument();
 });
 it('preserves handwritten text and detaches a definitively rejected choice so the user can continue',async()=>{
  const send=vi.fn().mockRejectedValueOnce(new InteractionSubmissionError('alreadySubmitted','original')).mockResolvedValue(undefined);
  render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send}/>);
  fireEvent.change(await screen.findByPlaceholderText('编辑草稿'),{target:{value:'本机新草稿'}});
  const composer=screen.getByPlaceholderText(/Message Planner|发送消息给 Planner|给 Planner/);
  fireEvent.change(composer,{target:{value:'先别发送，改成下午'} });
  fireEvent.submit(composer.closest('form')!);
  await waitFor(()=>expect(screen.queryByText(/将附带当前选择|Current choices will be attached/)).not.toBeInTheDocument());
  expect(composer).toHaveValue('先别发送，改成下午');
  fireEvent.submit(composer.closest('form')!);
  await waitFor(()=>expect(send).toHaveBeenLastCalledWith('先别发送，改成下午',[]));
 });
 it('leaves typed input untouched when the card button is used',async()=>{
  const send=vi.fn().mockResolvedValue(undefined);
  render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send}/>);
  const button=await screen.findByRole('button',{name:'继续修改'});
  const composer=screen.getByPlaceholderText(/Message Planner|发送消息给 Planner|给 Planner/);
  fireEvent.change(composer,{target:{value:'这是还没发出的补充'}});
  fireEvent.click(button);
  await waitFor(()=>expect(send).toHaveBeenCalledWith('',[],expect.objectContaining({action_id:'send'}),expect.any(String)));
  expect(composer).toHaveValue('这是还没发出的补充');
 });
});
