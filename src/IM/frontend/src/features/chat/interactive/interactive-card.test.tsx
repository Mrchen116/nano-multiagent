import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { InteractiveCard } from './interactive-card';
import { InteractionSubmissionError } from './submission-error';
import { listMessages, readInteractionDraft, saveInteractionDraft } from '../chat-api';
import type { Message } from '../chat-types';
import { resetInteractionBackground } from '../interaction-background';
vi.mock('../chat-api', () => ({listMessages:vi.fn(),readInteractionDraft: vi.fn(), saveInteractionDraft: vi.fn()}));
const message = {id:'card', conversation_id:'chat', content:'确认草稿', interactive:{format:'openui',catalog_version:'nano-iui-1',source:`$body = "周六见"
root = Col([form])
form = Form([TextArea($body, "消息草稿", "编辑"), Button("发送给林悦", @SendToChat("发送给林悦"))])`}} as Message;
beforeEach(() => {
  resetInteractionBackground();
  vi.clearAllMocks();
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:2,state:{'$body':'周日见'},submission_message_id:null});
  vi.mocked(saveInteractionDraft).mockResolvedValue({draft_revision:3,state:{},submission_message_id:null});
});
describe('private interactive reply', () => {
  it('restores the private draft, saves edits without sending, and submits current fields immediately', async () => {
    const send = vi.fn().mockResolvedValue({});
    render(<InteractiveCard message={message} onSend={send} />);
    const field=await screen.findByRole('textbox');
    await waitFor(() => expect(field).toHaveValue('周日见'));
    // Rendering must not arm a background by itself: only a real input event may, and that
    // event only saves the private draft.
    expect(saveInteractionDraft).not.toHaveBeenCalled();
    fireEvent.change(field,{target:{value:'周日10点断桥见'}});
    await waitFor(()=>expect(saveInteractionDraft).toHaveBeenCalledWith('chat','card',2,expect.objectContaining({'$body':'周日10点断桥见'})));
    expect(send).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'发送给林悦'}));
    await waitFor(()=>expect(send).toHaveBeenCalledWith(expect.objectContaining({source_message_id:'card',event:expect.objectContaining({message:'发送给林悦'}),state:expect.objectContaining({'$body':'周日10点断桥见'})}),expect.any(String)));
    expect(field).not.toBeDisabled();
  });
  it('does not resave a pending card submission after the renderer is replaced', async () => {
    let complete!: (value: unknown) => void;
    const send = vi.fn(() => new Promise(resolve => { complete = resolve; }));
    const view = render(<InteractiveCard message={message} onSend={send} />);
    const field = await screen.findByRole('textbox');
    await waitFor(() => expect(field).toHaveValue('周日见'));
    fireEvent.change(field, {target:{value:'提交这次编辑'}});
    fireEvent.click(screen.getByRole('button',{name:'发送给林悦'}));
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    view.unmount();

    vi.mocked(readInteractionDraft).mockResolvedValue({
      draft_revision:3, state:{'$body':'提交这次编辑'}, submission_message_id:'accepted'
    });
    render(<InteractiveCard message={message} onSend={send} submittedMessageId="accepted" />);
    expect(await screen.findByRole('textbox')).toBeDisabled();
    complete({id:'accepted'});
    await waitFor(() => expect(screen.getByRole('textbox')).not.toBeDisabled());
    expect(saveInteractionDraft).not.toHaveBeenCalled();

    fireEvent.change(screen.getByRole('textbox'), {target:{value:'提交后的新编辑'}});
    await waitFor(() => expect(saveInteractionDraft).toHaveBeenCalledWith('chat','card',3,{'$body':'提交后的新编辑'}));
    expect(saveInteractionDraft).toHaveBeenCalledTimes(1);
  });

  it('retries an uncertain submission with the exact frozen request and identity', async () => {
    const send=vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({});
    render(<InteractiveCard message={message} onSend={send} />);
    fireEvent.click(await screen.findByRole('button',{name:'发送给林悦'}));
    fireEvent.click(await screen.findByRole('button',{name:/重试|Retry/}));
    await waitFor(()=>expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[1]).toEqual(send.mock.calls[0]);
  });
  it.each(['alreadySubmitted', 'stale'] as const)('stops replaying a definite %s conflict while retaining local values', async reason => {
    const send=vi.fn().mockRejectedValue(new InteractionSubmissionError(reason, reason === 'alreadySubmitted' ? 'original' : undefined));
    render(<InteractiveCard message={message} onSend={send} />);
    const field=await screen.findByRole('textbox');
    await waitFor(() => expect(field).toHaveValue('周日见'));
    fireEvent.change(field,{target:{value:'保留本机草稿'}});
    fireEvent.click(screen.getByRole('button',{name:'发送给林悦'}));
    expect(await screen.findByRole('alert')).toHaveTextContent(reason === 'stale' ? /已有更新|no longer accepts/i : /其他设备|another device/i);
    expect(screen.queryByRole('button',{name:/重试|Retry/})).not.toBeInTheDocument();
    expect(field).toHaveValue('保留本机草稿');
    expect(field).not.toBeDisabled();
    if(reason==='alreadySubmitted') expect(screen.getByRole('link',{name:/原提交|previous submission/i})).toHaveAttribute('href','/chat/chat?message_id=original');
  });

});


it.each(['chat', 'legacy', 'mutation'])('captures complete state after Set and separates the visible label from generated %s content', async mode => {
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:0,state:{},submission_message_id:null});
  const send=vi.fn().mockResolvedValue({id:'request-1',delivery_status:'pending'});
  const action=mode==='chat' ? '@SendToChat("分析参数", {kind:"comparison"})' : mode==='legacy' ? '@ToAssistant("分析参数", {kind:"comparison"})' : '@Run(ask)';
  const source=`$scale = [2]
ask = Mutation("continue_conversation", {message:"分析参数",context:{kind:"comparison"}})
$body = "初稿"
root = Col([Text("比例：" + $scale[0]), form])
form = Form([Button("解释当前结果", Action([@Set($scale, [3]), ${action}])), TextArea($body, "草稿")])`;
  render(<InteractiveCard message={{...message,interactive:{...message.interactive!,source}}} onSend={send} />);
  fireEvent.change(await screen.findByRole('textbox'),{target:{value:'修改后的稿子'}});
  fireEvent.click(screen.getByRole('button',{name:'解释当前结果'}));
  await waitFor(()=>expect(send).toHaveBeenCalledTimes(1));
  expect(send.mock.calls[0][0]).toMatchObject({event:{type:'continue_conversation',label:'解释当前结果',message:'分析参数',context:{kind:'comparison'}},state:{'$scale':[3],'$body':'修改后的稿子'}});
  await waitFor(()=>expect(screen.getByRole('button',{name:'解释当前结果'})).not.toBeDisabled());
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'再修改'}});
  fireEvent.click(screen.getByRole('button',{name:'解释当前结果'}));
  await waitFor(()=>expect(send).toHaveBeenCalledTimes(2));
  expect(send.mock.calls[1][1]).not.toBe(send.mock.calls[0][1]);
  expect(send.mock.calls[0][0].state['$body']).toBe('修改后的稿子');
  expect(send.mock.calls[1][0].state['$body']).toBe('再修改');
});

it('connects native Query to the existing current-conversation reader', async () => {
  vi.mocked(listMessages).mockResolvedValue({items:[],next_before_message_id:null});
  const source='data = Query("conversation_messages", {limit:5}, [])\nroot = Text("会话消息：" + @Count(data))';
  render(<InteractiveCard message={{...message,interactive:{...message.interactive!,source}}} onSend={vi.fn()} />);
  await waitFor(()=>expect(listMessages).toHaveBeenCalledWith('chat',{limit:5}));
  expect(await screen.findByText('会话消息：0')).toBeVisible();
});

it('refreshes draft revision after a composer submission while keeping the explorer editable', async () => {
  const props={message,onSend:vi.fn()};
  const view=render(<InteractiveCard {...props} />);
  await screen.findByRole('textbox');
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:7,state:{'$body':'周日见'},submission_message_id:'new-request'});
  view.rerender(<InteractiveCard {...props} submittedMessageId="new-request" />);
  await waitFor(()=>expect(readInteractionDraft).toHaveBeenCalledTimes(2));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'继续探索'}});
  await waitFor(()=>expect(saveInteractionDraft).toHaveBeenCalledWith('chat','card',7,expect.any(Object)));
});

it.each(['ws-first', 'post-first'])('keeps the authoritative draft revision after a native submission with %s delivery', async order => {
  let complete!: (value: unknown) => void;
  const send = vi.fn(() => new Promise(resolve => { complete = resolve; }));
  const props = {message, onSend:send};
  const view = render(<InteractiveCard {...props} />);
  const field = await screen.findByRole('textbox');
  fireEvent.click(screen.getByRole('button', {name:'发送给林悦'}));
  await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:3,state:{'$body':'周日见'},submission_message_id:'request-1'});
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


it('adopts evaluated edits only after private save and fresh source access, without submitting', async () => {
  const source='$reply = "Initial reply"\nroot = Col([TextArea($reply, null, "Reply draft"), Button("Adopt", @ComposeMessage("c_target", "Reply: " + $reply))])';
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:2,state:{'$reply':'Saved reply'},submission_message_id:null,can_interact:true});
  vi.mocked(saveInteractionDraft).mockRejectedValueOnce(new Error('offline')).mockResolvedValue({draft_revision:3,state:{'$reply':'Edited reply'},submission_message_id:null});
  const send=vi.fn(), adopt=vi.fn();
  render(<InteractiveCard message={{...message,interactive:{...message.interactive!,source}}} onSend={send} onComposeMessage={adopt}/>);
  const field=await screen.findByPlaceholderText('Reply draft');
  await waitFor(()=>expect(field).toHaveValue('Saved reply'));
  fireEvent.change(field,{target:{value:'Edited reply'}});
  fireEvent.click(screen.getByRole('button',{name:'Adopt'}));
  await screen.findByRole('alert');
  expect(field).toHaveValue('Edited reply');
  expect(adopt).not.toHaveBeenCalled();
  expect(send).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Adopt'}));
  await waitFor(()=>expect(adopt).toHaveBeenCalledWith('c_target','Reply: Edited reply'));
  expect(saveInteractionDraft).toHaveBeenLastCalledWith('chat','card',2,expect.objectContaining({'$reply':'Edited reply'}));
  expect(send).not.toHaveBeenCalled();
  vi.mocked(readInteractionDraft).mockResolvedValue({draft_revision:3,state:{},submission_message_id:null,can_interact:false,superseded_by:'new'});
  fireEvent.click(screen.getByRole('button',{name:'Adopt'}));
  await screen.findByRole('alert');
  expect(adopt).toHaveBeenCalledTimes(1);
  expect(field).toHaveValue('Edited reply');
});


it('keeps a Pressable drawing unchanged inside a read-only historical card', async () => {
  const source='$n = 1\nroot = Col([Text("数量 " + $n), Pressable([Text("增加")], @Set($n, $n + 1))])';
  const send=vi.fn();
  render(<InteractiveCard message={{...message, interactive:{...message.interactive!,source}}} readOnly onSend={send} />);
  fireEvent.click(await screen.findByRole('button',{name:'增加'}));
  expect(await screen.findByText('数量 1')).toBeVisible();
  expect(send).not.toHaveBeenCalled();
  expect(saveInteractionDraft).not.toHaveBeenCalled();
});
