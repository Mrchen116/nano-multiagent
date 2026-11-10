import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { StrictMode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { setLanguage } from '../../../i18n';
import type { Conversation, Message } from '../chat-types';
import { readInteractionDraft, saveInteractionDraft } from '../chat-api';
import { draftWatermark, flushInteractionDrafts, resetInteractionBackground } from '../interaction-background';
import type { InteractionDraft } from '../interactive/types';
import { MessagePane } from './message-pane';
import type { ComposerSnapshot } from './composer-draft-store';
// Preload the lazy explorer module so the first test does not race its dynamic import.
import '../interactive/interactive-card';

vi.mock('../chat-api', () => ({
  readInteractionDraft: vi.fn(),
  saveInteractionDraft: vi.fn(),
  lookupMessageAttempt: vi.fn()
}));

const conversation = {
  id: 'chat', title: 'Planner', type: 'direct', direct_kind: 'agent',
  participants: [{ type: 'agent', id: 'a1', display_name: 'Planner' }],
  participant_ids: ['a1'], can_write: true
} as Conversation;

const card = {
  id: 'card', conversation_id: 'chat',
  sender: { type: 'agent', id: 'a1', display_name: 'Planner' }, sender_user_id: 'a1', sender_type: 'agent',
  content: '请确认草稿', attachments: [], created_at: '2026-10-19T08:00:00Z',
  delivery_status: 'completed', permission_requests: [],
  interactive: {
    format: 'openui', catalog_version: 'nano-iui-1',
    source: `$body = "周六见"
root = Col([form])
form = Form([TextArea($body, "消息草稿", "编辑草稿"), Button("继续修改", @SendToChat("继续修改"))])`
  }
} as Message;

const composerBox = () => screen.getByPlaceholderText(/给 Planner 发消息|Message Planner/) as HTMLTextAreaElement;
const sendButton = () => screen.getByRole('button', { name: 'Send' });
const composerForm = () => composerBox().closest('form') as HTMLElement;
// The card is lazy-loaded, so the first mount in this file pays the renderer's import cost.
const openCard = () => screen.findByPlaceholderText('编辑草稿', {}, { timeout: 5000 }) as Promise<HTMLTextAreaElement>;

beforeEach(() => {
  setLanguage('zh');
  // Draft handles, failures and watermarks are module state shared by every card/composer.
  resetInteractionBackground();
  vi.mocked(readInteractionDraft).mockReset().mockResolvedValue({
    draft_revision: 2, state: { '$body': '周日见' }, submission_message_id: null,
    fields: [{ name: '$body', label: '消息草稿', value: '周日见' }]
  });
  vi.mocked(saveInteractionDraft).mockReset().mockResolvedValue({ draft_revision: 3, state: {}, submission_message_id: null, updated_at: '2026-05-01T00:00:01.000Z' });
});

describe('private card drafts in the ordinary send flow', () => {
  it('synchronizes a stale card before the original composer click sends once', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValueOnce(Object.assign(new Error('conflict'), {status:409}));
    const send = vi.fn().mockResolvedValue(undefined);
    render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send} />);
    const local = await openCard();
    fireEvent.change(local, {target:{value:'本机改动'}});
    let finishRead!: (draft: InteractionDraft) => void;
    vi.mocked(readInteractionDraft).mockReturnValueOnce(new Promise(resolve => { finishRead = resolve; }));
    fireEvent.change(composerBox(), {target:{value:'  发送这条  '}});
    fireEvent.click(sendButton());
    await waitFor(() => expect(local).toBeDisabled());
    expect(send).not.toHaveBeenCalled();
    await act(async () => { finishRead({draft_revision:5,state:{'$body':'另一端最新'},submission_message_id:null}); });
    await waitFor(() => expect(send).toHaveBeenCalledOnce());
    expect(send).toHaveBeenCalledWith('发送这条', [], undefined, expect.any(String));
    expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('另一端最新');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(within(composerForm()).queryByRole('alert')).not.toBeInTheDocument();
    expect(saveInteractionDraft).toHaveBeenCalledOnce();
    expect(draftWatermark('chat')).toBeUndefined();
  }, 20000);

  it.each(['save', 'refresh'] as const)('uses the ordinary send failure when the card %s fails and retries with Send', async stage => {
    vi.mocked(saveInteractionDraft).mockRejectedValueOnce(stage === 'save'
      ? new Error('offline') : Object.assign(new Error('conflict'), {status:409}));
    const send = vi.fn(), failure = vi.fn();
    const props = {conversation,messages:[card],selfUserId:'u1',mentionCandidates:[],onSend:send,onSendFailure:failure,
      composerStore:new Map<string, ComposerSnapshot>()};
    const view = render(<MessagePane {...props} />);
    const field = await openCard();
    if (stage === 'refresh') vi.mocked(readInteractionDraft).mockRejectedValueOnce(new Error('offline'));
    fireEvent.change(field, {target:{value:'本机改动'}});
    fireEvent.change(composerBox(), {target:{value:'正文也保留'}});
    fireEvent.click(sendButton());
    await waitFor(() => expect(failure).toHaveBeenCalledOnce());
    expect(send).not.toHaveBeenCalled();
    expect(field).toHaveValue('本机改动');
    expect(composerBox()).toHaveValue('正文也保留');
    view.rerender(<></>);
    view.rerender(<MessagePane {...props} />);
    expect(await openCard()).toHaveValue('本机改动');
    expect(sendButton()).toBeEnabled();
    fireEvent.click(sendButton());
    await waitFor(() => expect(send).toHaveBeenCalledOnce());
    expect(send).toHaveBeenCalledWith('正文也保留', [], undefined, expect.any(String));
    expect(saveInteractionDraft).toHaveBeenCalledTimes(stage === 'save' ? 2 : 1);
    if (stage === 'refresh') expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('周日见');
  });

  it('retries an unconfirmed ordinary message even if a later card save fails', async () => {
    const send = vi.fn().mockRejectedValueOnce(new Error('receipt lost')).mockResolvedValue(undefined);
    render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send} />);
    const field = await openCard();
    fireEvent.change(composerBox(), {target:{value:'同一条消息'}});
    fireEvent.click(sendButton());
    await screen.findByText('是否送达尚未确认。再次发送将重试原消息。');
    vi.mocked(saveInteractionDraft).mockRejectedValue(new Error('offline while saving a later edit'));
    fireEvent.change(field, {target:{value:'后来改的卡片'}});
    await act(async () => { await flushInteractionDrafts('chat'); });
    fireEvent.click(sendButton());
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[1]).toEqual(send.mock.calls[0]);
  });

  it('reattaches to a pending PUT and saves newer input with its acknowledgement without reseeding the renderer', async () => {
    let complete!: (value: InteractionDraft) => void;
    vi.mocked(saveInteractionDraft).mockReturnValueOnce(new Promise(resolve => { complete = resolve; }))
      .mockResolvedValueOnce({draft_revision:4,state:{},submission_message_id:null,updated_at:'2026-05-01T00:00:02.000Z'});
    const props = {conversation,messages:[card],selfUserId:'u1',mentionCandidates:[],onSend:vi.fn()};
    const view = render(<MessagePane {...props} />);
    fireEvent.change(await openCard(), {target:{value:'第一次编辑'}});
    let saving!: ReturnType<typeof flushInteractionDrafts>;
    act(() => { saving = flushInteractionDrafts('chat'); });
    expect(saveInteractionDraft).toHaveBeenCalledTimes(1);
    view.rerender(<></>);
    view.rerender(<MessagePane {...props} />);
    const replacement = await openCard();
    await waitFor(() => expect(replacement).toHaveValue('第一次编辑'));
    fireEvent.change(replacement, {target:{value:'新页面继续编辑'}});
    await act(async () => {
      complete({draft_revision:3,state:{'$body':'旧回执不替换输入'},submission_message_id:null,updated_at:'2026-05-01T00:00:01.000Z'});
      await saving;
    });
    expect(saveInteractionDraft).toHaveBeenNthCalledWith(2,'chat','card',3,{'$body':'新页面继续编辑'});
    expect(screen.getByPlaceholderText('编辑草稿')).toBe(replacement);
    expect(replacement).toHaveValue('新页面继续编辑');
    expect(readInteractionDraft).toHaveBeenCalledTimes(1);
    expect(draftWatermark('chat')).toBe('2026-05-01T00:00:02.000Z');
    expect(within(composerForm()).queryByRole('alert')).not.toBeInTheDocument();
    expect(props.onSend).not.toHaveBeenCalled();
  });

  it('resumes a debounce interrupted by concealment and tolerates StrictMode view leases', async () => {
    const props = {conversation,messages:[card],selfUserId:'u1',mentionCandidates:[],onSend:vi.fn()};
    const view = render(<StrictMode><MessagePane {...props} /></StrictMode>);
    fireEvent.change(await openCard(), {target:{value:'防抖中尚未保存'}});
    expect(saveInteractionDraft).not.toHaveBeenCalled();
    view.rerender(<></>);
    view.rerender(<StrictMode><MessagePane {...props} /></StrictMode>);
    await waitFor(() => expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('防抖中尚未保存'));
    await waitFor(() => expect(saveInteractionDraft).toHaveBeenCalledWith('chat','card',2,{'$body':'防抖中尚未保存'}));
    expect(saveInteractionDraft).toHaveBeenCalledTimes(1);
    expect(readInteractionDraft).toHaveBeenCalledTimes(1);
  });

  it('sends with no background at all when every card is clean', async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send} />);
    await waitFor(() => expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('周日见'), { timeout: 5000 });
    fireEvent.change(composerBox(), { target: { value: ' 没有改动也要发 ' } });
    fireEvent.click(sendButton());

    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send).toHaveBeenCalledWith('没有改动也要发', [], undefined, expect.any(String));
    expect(JSON.stringify(send.mock.calls[0])).not.toContain('contexts');
  });
});
