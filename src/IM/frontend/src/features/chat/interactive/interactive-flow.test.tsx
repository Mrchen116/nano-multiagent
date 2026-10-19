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
 it('shows readable choices and an explicit queued status until delivery resumes',()=>{
  const reply={...card,id:'reply',interactive:undefined,sender:{type:'user',id:'u1'},sender_user_id:'u1',sender_type:'user',content:'',delivery_status:'pending',interaction_reply:{source_message_id:'card',source_summary:'行程',agent_id:'a1',state:{},fields:[{name:'mode',label:'方式',value:'bike',display_value:'骑行'}]}} as Message;
  const view=render(<MessagePane conversation={conversation} messages={[reply]} selfUserId="u1" mentionCandidates={[]} onSend={vi.fn()}/>);
  expect(screen.getByText('骑行')).toBeInTheDocument();
  expect(screen.queryByText('bike')).not.toBeInTheDocument();
  expect(screen.getByText(/已保存，等待 Agent 处理|Saved, waiting for Agent/)).toBeInTheDocument();
  view.rerender(<MessagePane conversation={conversation} messages={[{...reply,delivery_status:'running'}]} selfUserId="u1" mentionCandidates={[]} onSend={vi.fn()}/>);
  expect(screen.queryByText(/已保存，等待 Agent 处理|Saved, waiting for Agent/)).not.toBeInTheDocument();
 });
 it('keeps direct-chat background silent and retains it across natural questions',async()=>{
  const send=vi.fn().mockResolvedValue(undefined);
  render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send}/>);
  fireEvent.change(await screen.findByPlaceholderText('编辑草稿', {}, {timeout:5000}),{target:{value:'私聊新草稿'}});
  const composer=screen.getByPlaceholderText(/Message Planner|发送消息给 Planner|给 Planner/);
  fireEvent.change(composer,{target:{value:'先别发送，帮我解释'}});fireEvent.submit(composer.closest('form')!);
  await waitFor(()=>expect(send).toHaveBeenCalledWith('先别发送，帮我解释',[],undefined,expect.any(String),[expect.objectContaining({source_message_id:'card',state:expect.objectContaining({draft:expect.objectContaining({body:expect.objectContaining({value:'私聊新草稿'})})})})]));
  expect(screen.queryByText(/将附带当前选择|Current choices will be attached|草稿已保存|Draft saved/)).not.toBeInTheDocument();
  await waitFor(()=>expect(composer).toHaveValue(''));
  fireEvent.change(composer,{target:{value:'你好，换个话题'}});fireEvent.submit(composer.closest('form')!);
  await waitFor(()=>expect(send).toHaveBeenCalledTimes(2));
  expect(send.mock.calls[1][4]).toEqual(send.mock.calls[0][4]);
 });
 it('does not attach group state to ordinary text but shares explicit card actions',async()=>{
  const send=vi.fn().mockResolvedValue(undefined);
  render(<MessagePane conversation={{...conversation,type:'group'}} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send}/>);
  fireEvent.change(await screen.findByPlaceholderText('编辑草稿'),{target:{value:'群内私人草稿'}});
  const composer=screen.getByPlaceholderText(/type @ to mention|输入 @ 召唤/);
  fireEvent.change(composer,{target:{value:'解释一下'}});fireEvent.submit(composer.closest('form')!);
  await waitFor(()=>expect(send).toHaveBeenCalledWith('解释一下',[]));
  fireEvent.click(screen.getByRole('button',{name:'继续修改'}));
  await waitFor(()=>expect(send).toHaveBeenLastCalledWith('',[],expect.objectContaining({action_id:'send',state:expect.objectContaining({draft:expect.objectContaining({body:expect.objectContaining({value:'群内私人草稿'})})})}),expect.any(String)));
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

it('retries an uncertain handwritten interaction with the same frozen message, state and key',async()=>{
 const send=vi.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValue(undefined);
 render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send}/>);
 const field=await screen.findByPlaceholderText('编辑草稿');
 fireEvent.change(field,{target:{value:'第一版草稿'}});
 const composer=screen.getByPlaceholderText(/Message Planner|发送消息给 Planner|给 Planner/);
 fireEvent.change(composer,{target:{value:'解释现在的选择'}});
 fireEvent.submit(composer.closest('form')!);
 await screen.findByText(/是否送达尚未确认|Delivery is unconfirmed/);
 expect(composer).toBeDisabled();
 fireEvent.change(field,{target:{value:'继续在本地探索'}});
 const retry = screen.getByRole('button',{name:'Send'});
 expect(retry).not.toBeDisabled();
 expect(retry.closest('[aria-disabled="true"]')).toBeNull();
 fireEvent.click(retry);
 await waitFor(()=>expect(send).toHaveBeenCalledTimes(2));
 expect(send.mock.calls[1]).toEqual(send.mock.calls[0]);
 expect(send.mock.calls[0][3]).toEqual(expect.any(String));
 await waitFor(()=>expect(composer).not.toBeDisabled());
 expect(field).toHaveValue('继续在本地探索');
});

it('keeps both private-chat card states and prioritizes the one most recently used',async()=>{
 const send=vi.fn().mockResolvedValue(undefined);
 const second={...card,id:'other-card',content:'另一个草稿',interactive:{...card.interactive!,source:card.interactive!.source.replace('编辑草稿','另一份草稿')}};
 render(<MessagePane conversation={conversation} messages={[card,second]} selfUserId="u1" mentionCandidates={[]} onSend={send}/>);
 const first=await screen.findByPlaceholderText('编辑草稿');const other=await screen.findByPlaceholderText('另一份草稿');
 const clock=vi.spyOn(Date,'now').mockReturnValue(200);
 try {
  fireEvent.change(other,{target:{value:'第二张的修改'}});
  clock.mockReturnValue(201);fireEvent.change(first,{target:{value:'第一张的修改'}});
 } finally {clock.mockRestore();}
 const composer=screen.getByPlaceholderText(/Message Planner|发送消息给 Planner|给 Planner/);
 fireEvent.change(composer,{target:{value:'对比这两份草稿'}});fireEvent.submit(composer.closest('form')!);
 await waitFor(()=>expect(send).toHaveBeenCalled());
 const contexts=send.mock.calls[0][4];
 expect(contexts.map((context:any)=>context.source_message_id)).toEqual(['card','other-card']);
 expect(contexts.map((context:any)=>context.state.draft.body.value)).toEqual(['第一张的修改','第二张的修改']);
 fireEvent.change(first,{target:{value:'发送后的修改'}});
 expect(contexts[0].state.draft.body.value).toBe('第一张的修改');
});
