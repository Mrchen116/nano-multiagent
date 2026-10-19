import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { InteractiveCard } from './interactive-card';
import { InteractionSubmissionError } from './submission-error';
import { listMessages, readInteractionDraft, saveInteractionDraft } from '../chat-api';
import type { Message } from '../chat-types';
vi.mock('../chat-api', () => ({listMessages:vi.fn(),readInteractionDraft: vi.fn(), saveInteractionDraft: vi.fn()}));
const message = {id:'card', conversation_id:'chat', content:'确认草稿', interactive:{format:'openui',catalog_version:'nano-1',source:`root = Stack([form])
form = Form("draft", ContinueButton("send", "发送给林悦"), [FormControl("消息草稿", TextArea("body", "编辑", 3, null, "周六见"))])`}} as Message;
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:2,state:{draft:{body:{value:'周日见'}}},submission_message_id:null});
  vi.mocked(saveInteractionDraft).mockResolvedValue({draft_revision:3,state:{},submission_message_id:null});
});
describe('private interactive reply', () => {
  it('restores the private draft, saves edits without sending, and submits current fields immediately', async () => {
    const send = vi.fn().mockResolvedValue({}); const select=vi.fn();
    render(<InteractiveCard message={message} onSend={send} onSelect={select} />);
    const field=await screen.findByRole('textbox');
    await waitFor(() => expect(field).toHaveValue('周日见'));
    fireEvent.change(field,{target:{value:'周日10点断桥见'}});
    await waitFor(()=>expect(select).toHaveBeenCalled());
    expect(send).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'发送给林悦'}));
    await waitFor(()=>expect(send).toHaveBeenCalledWith(expect.objectContaining({source_message_id:'card',action_id:'send',state:expect.objectContaining({draft:expect.objectContaining({body:expect.objectContaining({value:'周日10点断桥见'})})})}),expect.any(String)));
    expect(field).not.toBeDisabled();
  });
  it('retries an uncertain submission with the exact frozen request and identity', async () => {
    const send=vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({});
    render(<InteractiveCard message={message} onSend={send} onSelect={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button',{name:'发送给林悦'}));
    fireEvent.click(await screen.findByRole('button',{name:/重试|Retry/}));
    await waitFor(()=>expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[1]).toEqual(send.mock.calls[0]);
  });
  it.each(['alreadySubmitted', 'stale'] as const)('stops replaying a definite %s conflict while retaining local values', async reason => {
    const send=vi.fn().mockRejectedValue(new InteractionSubmissionError(reason, reason === 'alreadySubmitted' ? 'original' : undefined));
    render(<InteractiveCard message={message} onSend={send} onSelect={vi.fn()} />);
    const field=await screen.findByRole('textbox');
    fireEvent.change(field,{target:{value:'保留本机草稿'}});
    fireEvent.click(screen.getByRole('button',{name:'发送给林悦'}));
    expect(await screen.findByRole('alert')).toHaveTextContent(reason === 'stale' ? /已有更新|no longer accepts/i : /其他设备|another device/i);
    expect(screen.queryByRole('button',{name:/重试|Retry/})).not.toBeInTheDocument();
    expect(field).toHaveValue('保留本机草稿');
    expect(field).not.toBeDisabled();
    if(reason==='alreadySubmitted') expect(screen.getByRole('link',{name:/原提交|previous submission/i})).toHaveAttribute('href','/chat/chat?message_id=original');
  });
  it('does not overwrite another device after a draft conflict', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValue(new Error('409 conflict'));
    render(<InteractiveCard message={message} onSend={vi.fn()} onSelect={vi.fn()} />);
    fireEvent.change(await screen.findByRole('textbox'),{target:{value:'保留本机输入'}});
    expect(await screen.findByRole('alert')).toHaveTextContent(/另一设备|Another device/);
    expect(screen.getByRole('textbox')).toHaveValue('保留本机输入');
    expect(saveInteractionDraft).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button',{name:/载入最新|Load latest/}));
    await waitFor(()=>expect(screen.getByRole('textbox')).toHaveValue('周日见'));
  });
});


it.each(['native', 'mutation'])('captures complete state after Set and separates the visible label from generated %s content', async mode => {
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:0,state:{},submission_message_id:null});
  const send=vi.fn().mockResolvedValue({id:'request-1',delivery_status:'pending'});
  const action=mode==='native' ? '@ToAssistant("分析参数", {kind:"comparison"})' : '@Run(ask)';
  const source=`$scale = [2]
ask = Mutation("continue_conversation", {message:"分析参数",context:{kind:"comparison"}})
root = Stack([TextContent("比例：" + $scale[0]), form])
form = Form("draft", Buttons([Button("解释当前结果", Action([@Set($scale, [3]), ${action}]))]), [FormControl("草稿", TextArea("body", "", 3, null, "初稿"))])`;
  render(<InteractiveCard message={{...message,interactive:{...message.interactive!,source}}} onSend={send} onSelect={vi.fn()} />);
  fireEvent.change(await screen.findByRole('textbox'),{target:{value:'修改后的稿子'}});
  fireEvent.click(screen.getByRole('button',{name:'解释当前结果'}));
  await waitFor(()=>expect(send).toHaveBeenCalledTimes(1));
  expect(send.mock.calls[0][0]).toMatchObject({event:{type:'continue_conversation',label:'解释当前结果',message:'分析参数',context:{kind:'comparison'}},state:{'$scale':[3],draft:{body:{value:'修改后的稿子'}}}});
  await waitFor(()=>expect(screen.getByRole('button',{name:'解释当前结果'})).not.toBeDisabled());
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'再修改'}});
  fireEvent.click(screen.getByRole('button',{name:'解释当前结果'}));
  await waitFor(()=>expect(send).toHaveBeenCalledTimes(2));
  expect(send.mock.calls[1][1]).not.toBe(send.mock.calls[0][1]);
  expect(send.mock.calls[0][0].state.draft.body.value).toBe('修改后的稿子');
  expect(send.mock.calls[1][0].state.draft.body.value).toBe('再修改');
});

it('connects native Query to the existing current-conversation reader', async () => {
  vi.mocked(listMessages).mockResolvedValue({items:[],next_before_message_id:null});
  const source='data = Query("conversation_messages", {limit:5}, [])\nroot = TextContent("会话消息：" + @Count(data))';
  render(<InteractiveCard message={{...message,interactive:{...message.interactive!,source}}} onSend={vi.fn()} onSelect={vi.fn()} />);
  await waitFor(()=>expect(listMessages).toHaveBeenCalledWith('chat',{limit:5}));
  expect(await screen.findByText('会话消息：0')).toBeVisible();
});

it('refreshes draft revision after a composer submission while keeping the explorer editable', async () => {
  const props={message,onSend:vi.fn(),onSelect:vi.fn()};
  const view=render(<InteractiveCard {...props} />);
  await screen.findByRole('textbox');
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:7,state:{draft:{body:{value:'周日见'}}},submission_message_id:'new-request'});
  view.rerender(<InteractiveCard {...props} submittedMessageId="new-request" />);
  await waitFor(()=>expect(readInteractionDraft).toHaveBeenCalledTimes(2));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'继续探索'}});
  await waitFor(()=>expect(saveInteractionDraft).toHaveBeenCalledWith('chat','card',7,expect.any(Object)));
});

it.each(['ws-first', 'post-first'])('keeps the authoritative draft revision after a native submission with %s delivery', async order => {
  let complete!: (value: unknown) => void;
  const send = vi.fn(() => new Promise(resolve => { complete = resolve; }));
  const props = {message, onSend:send, onSelect:vi.fn()};
  const view = render(<InteractiveCard {...props} />);
  const field = await screen.findByRole('textbox');
  fireEvent.click(screen.getByRole('button', {name:'发送给林悦'}));
  await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:3,state:{draft:{body:{value:'周日见'}}},submission_message_id:'request-1'});
  const reflect = () => view.rerender(<InteractiveCard {...props} submittedMessageId="request-1" />);
  if (order === 'ws-first') {
    reflect();
    await waitFor(() => expect(readInteractionDraft).toHaveBeenCalledTimes(2));
  }
  complete({id:'request-1'});
  await waitFor(() => expect(field).not.toBeDisabled());
  if (order === 'post-first') reflect();
  fireEvent.change(field,{target:{value:'提交后继续修改'}});
  await waitFor(() => expect(saveInteractionDraft).toHaveBeenCalledWith('chat','card',3,expect.any(Object)));
  expect(field).toHaveValue('提交后继续修改');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});


it('preserves edits when saving a reply draft fails and adopts only after private persistence', async () => {
  const reply_draft={target_conversation_id:'original',source_message_id:'source',field_name:'$reply',possible_stale:true};
  const source='$reply = "Initial reply"\nroot = TextArea("body", "Reply draft", 3, null, $reply)';
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:2,state:{'$reply':'Saved reply'},submission_message_id:null});
  vi.mocked(saveInteractionDraft).mockRejectedValueOnce(new Error('offline')).mockResolvedValue({draft_revision:3,state:{'$reply':'Edited reply'},submission_message_id:null});
  const send=vi.fn(), adopt=vi.fn();
  render(<InteractiveCard message={{...message,reply_draft,interactive:{...message.interactive!,source}}} onSend={send} onSelect={vi.fn()} onUseReplyDraft={adopt}/>);
  const field=await screen.findByPlaceholderText('Reply draft');
  await waitFor(()=>expect(field).toHaveValue('Saved reply'));
  fireEvent.change(field,{target:{value:'Edited reply'}});
  fireEvent.click(screen.getByRole('button',{name:/在原聊天使用|Use in original chat/}));
  await screen.findByRole('alert');
  expect(field).toHaveValue('Edited reply');
  expect(adopt).not.toHaveBeenCalled();
  expect(send).not.toHaveBeenCalled();
  expect(screen.getByText(/可能已过时|may be out of date/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:/在原聊天使用|Use in original chat/}));
  await waitFor(()=>expect(adopt).toHaveBeenCalledWith(reply_draft,'Edited reply'));
  expect(saveInteractionDraft).toHaveBeenLastCalledWith('chat','card',2,expect.objectContaining({'$reply':'Edited reply'}));
  expect(send).not.toHaveBeenCalled();
});
