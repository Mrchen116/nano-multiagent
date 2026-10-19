import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { InteractiveCard } from './interactive-card';
import { InteractionSubmissionError } from './submission-error';
import { readInteractionDraft, saveInteractionDraft } from '../chat-api';
import type { Message } from '../chat-types';
vi.mock('../chat-api', () => ({readInteractionDraft: vi.fn(), saveInteractionDraft: vi.fn()}));
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
    expect(field).toHaveValue('周日见');
    fireEvent.change(field,{target:{value:'周日10点断桥见'}});
    await waitFor(()=>expect(select).toHaveBeenCalled());
    expect(send).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'发送给林悦'}));
    await waitFor(()=>expect(send).toHaveBeenCalledWith(expect.objectContaining({source_message_id:'card',action_id:'send',state:expect.objectContaining({draft:expect.objectContaining({body:expect.objectContaining({value:'周日10点断桥见'})})})}),expect.any(String)));
    expect(field).toBeDisabled();
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
    expect(field).toBeDisabled();
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
