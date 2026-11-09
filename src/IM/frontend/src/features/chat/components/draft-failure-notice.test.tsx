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
  // `fields` is what the centre uses to label the three-column comparison.
  vi.mocked(readInteractionDraft).mockReset().mockResolvedValue({
    draft_revision: 2, state: { '$body': '周日见' }, submission_message_id: null,
    fields: [{ name: '$body', label: '消息草稿', value: '周日见' }]
  });
  vi.mocked(saveInteractionDraft).mockReset().mockResolvedValue({ draft_revision: 3, state: {}, submission_message_id: null, updated_at: '2026-05-01T00:00:01.000Z' });
});

describe('composer block for an unsaved card edit', () => {
  it('refuses to send on a 409, compares the three columns read-only, and only sends after the local edit is abandoned', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValue(new Error('409 conflict'));
    const send = vi.fn().mockResolvedValue(undefined);
    render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send} />);
    const field = await openCard();
    await waitFor(() => expect(field).toHaveValue('周日见'));
    fireEvent.change(field, { target: { value: '本机改动' } });

    fireEvent.change(composerBox(), { target: { value: '  发送这条  ' } });
    fireEvent.click(sendButton());

    // The message must not leave: the centre would derive the other device's draft, not this
    // edit, so the user's change would silently be missing.
    const alert = await within(composerForm()).findByRole('alert');
    expect(alert).toHaveTextContent('另一台设备更新了这张卡片，这个会话暂时不能发送');
    expect(send).not.toHaveBeenCalled();
    expect(sendButton()).toBeDisabled();
    // A 409 cannot be fixed by retrying the same stale revision, so that action is absent.
    expect(within(alert).queryByRole('button', { name: '重试保存' })).not.toBeInTheDocument();
    // Nothing is thrown away while the user has not decided.
    expect(field).toHaveValue('本机改动');
    expect(composerBox()).toHaveValue('  发送这条  ');

    fireEvent.click(within(alert).getByRole('button', { name: '查看最新改动' }));
    const table = await within(alert).findByRole('table');
    expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['字段', '另一台设备', '我这台']);
    expect(within(table).getByRole('row', { name: /消息草稿/ })).toHaveTextContent('周日见');
    expect(within(table).getByRole('row', { name: /消息草稿/ })).toHaveTextContent('本机改动');
    // Comparing is read-only: still nothing sent, still nothing applied, no extra save.
    expect(send).not.toHaveBeenCalled();
    expect(field).toHaveValue('本机改动');
    expect(saveInteractionDraft).toHaveBeenCalledTimes(1);

    vi.mocked(saveInteractionDraft).mockResolvedValue({ draft_revision: 6, state: {}, submission_message_id: null, updated_at: '2026-05-01T00:00:02.000Z' });
    fireEvent.click(screen.getByRole('button', { name: '改用最新草稿（会放弃本机这次改动）' }));

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    // Adopting remounts the explorer (new generation), so the field is a new element.
    await waitFor(() => expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('周日见'));
    // The composer keeps the text the user typed; only the card edit was abandoned.
    expect(composerBox()).toHaveValue('  发送这条  ');

    fireEvent.click(sendButton());
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    // Trimmed content and no client-chosen background: the centre derives it.
    expect(send).toHaveBeenCalledWith('发送这条', [], undefined, expect.any(String));
    expect(send.mock.calls[0]).toHaveLength(4);
  // Mounting the lazy explorer costs seconds under a full-suite run; the assertions above
  // are timing-independent, so only the budget needs room.
  }, 20000);

  it('keeps the conflict and local edit when fetching the draft to adopt fails', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValue(new Error('409 conflict'));
    const send = vi.fn();
    render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send} />);
    const field = await openCard();
    await waitFor(() => expect(field).toHaveValue('周日见'));
    fireEvent.change(field, { target: { value: '不能丢的本机改动' } });
    fireEvent.change(composerBox(), { target: { value: '正文也保留' } });
    fireEvent.click(sendButton());
    const alert = await within(composerForm()).findByRole('alert');
    fireEvent.click(within(alert).getByRole('button', { name: '查看最新改动' }));
    await within(alert).findByRole('table');
    vi.mocked(readInteractionDraft).mockRejectedValueOnce(new Error('offline while adopting'));
    fireEvent.click(within(alert).getByRole('button', { name: '改用最新草稿（会放弃本机这次改动）' }));
    await waitFor(() => expect(within(composerForm()).getByRole('alert')).toHaveTextContent('另一台设备更新了这张卡片'));
    expect(sendButton()).toBeDisabled();
    expect(field).toHaveValue('不能丢的本机改动');
    expect(composerBox()).toHaveValue('正文也保留');
    expect(send).not.toHaveBeenCalled();
  });

  it('keeps a conflicted local edit across an internal pane remount until explicit adoption', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValue(new Error('409 conflict'));
    const send = vi.fn();
    // Production uses the account store; test-mode panes otherwise get disposable stores.
    const composerStore = new Map<string, ComposerSnapshot>();
    const props = { conversation, messages: [card], selfUserId: 'u1', mentionCandidates: [], onSend: send, composerStore };
    const view = render(<MessagePane {...props} />);
    const field = await openCard();
    await waitFor(() => expect(field).toHaveValue('周日见'));
    fireEvent.change(field, { target: { value: '内部恢复不能丢的改动' } });
    fireEvent.change(composerBox(), { target: { value: '保留正文直到我决定' } });
    fireEvent.click(sendButton());
    const alert = await within(composerForm()).findByRole('alert');
    fireEvent.click(within(alert).getByRole('button', { name: '查看最新改动' }));
    await within(alert).findByRole('table');

    // Membership recovery temporarily conceals the pane without a user leave or logout.
    view.rerender(<></>);
    view.rerender(<MessagePane {...props} />);
    await openCard();
    await waitFor(() => expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('内部恢复不能丢的改动'));
    expect(sendButton()).toBeDisabled();
    expect(composerBox()).toHaveValue('保留正文直到我决定');
    expect(readInteractionDraft).toHaveBeenCalledTimes(2); // initial read + comparison, not adoption on remount
    const recovered = within(composerForm()).getByRole('alert');
    fireEvent.click(within(recovered).getByRole('button', { name: '查看最新改动' }));
    const comparison = await within(recovered).findByRole('table');
    expect(comparison).toHaveTextContent('内部恢复不能丢的改动');
    expect(comparison).toHaveTextContent('周日见');
    expect(send).not.toHaveBeenCalled();
    fireEvent.click(within(recovered).getByRole('button', { name: '改用最新草稿（会放弃本机这次改动）' }));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('周日见'));
    expect(sendButton()).not.toBeDisabled();
  });

  it('retains a transient edit across a pane remount and retries the same local state', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValueOnce(new Error('offline'));
    const props = {conversation, messages:[card], selfUserId:'u1', mentionCandidates:[], onSend:vi.fn(),
      composerStore:new Map<string, ComposerSnapshot>()};
    const view = render(<MessagePane {...props} />);
    const field = await openCard();
    fireEvent.change(field, {target:{value:'断网时编辑'}});
    fireEvent.change(composerBox(), {target:{value:'正文不丢'}});
    fireEvent.click(sendButton());
    await within(composerForm()).findByRole('alert');
    view.rerender(<></>);
    view.rerender(<MessagePane {...props} />);
    await waitFor(() => expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('断网时编辑'));
    expect(sendButton()).toBeDisabled();
    expect(composerBox()).toHaveValue('正文不丢');
    expect(readInteractionDraft).toHaveBeenCalledTimes(1);
    fireEvent.click(within(composerForm()).getByRole('button', {name:'重试保存'}));
    await waitFor(() => expect(within(composerForm()).queryByRole('alert')).not.toBeInTheDocument());
    expect(saveInteractionDraft).toHaveBeenLastCalledWith('chat','card',2,{'$body':'断网时编辑'});
    expect(screen.getByPlaceholderText('编辑草稿')).toHaveValue('断网时编辑');
    expect(sendButton()).not.toBeDisabled();
    expect(props.onSend).not.toHaveBeenCalled();
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

  it('offers a retry on a transient save failure and releases the send once the edit is saved', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValueOnce(new Error('offline'));
    const send = vi.fn().mockResolvedValue(undefined);
    render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={send} />);
    const field = await openCard();
    await waitFor(() => expect(field).toHaveValue('周日见'));
    fireEvent.change(field, { target: { value: '本机改动' } });
    fireEvent.change(composerBox(), { target: { value: '先保存再发' } });
    fireEvent.click(sendButton());

    const alert = await within(composerForm()).findByRole('alert');
    expect(alert).toHaveTextContent('卡片改动尚未保存，这个会话暂时不能发送');
    // The block is conversation-wide, not just this message.
    expect(alert).toHaveTextContent('同一会话的其他消息也要等它保存好');
    expect(send).not.toHaveBeenCalled();
    expect(field).toHaveValue('本机改动');
    expect(composerBox()).toHaveValue('先保存再发');

    // The retry saves; the bar disappears without a reload and the message can go.
    fireEvent.click(within(alert).getByRole('button', { name: '重试保存' }));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    expect(sendButton()).not.toBeDisabled();
    fireEvent.click(sendButton());
    await waitFor(() => expect(send).toHaveBeenCalledWith('先保存再发', [], undefined, expect.any(String)));
  });

  it('says the network is unavailable in the transient branch when the browser is offline', async () => {
    vi.mocked(saveInteractionDraft).mockRejectedValue(new Error('offline'));
    const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    try {
      render(<MessagePane conversation={conversation} messages={[card]} selfUserId="u1" mentionCandidates={[]} onSend={vi.fn()} />);
      const field = await openCard();
      await waitFor(() => expect(field).toHaveValue('周日见'));
      fireEvent.change(field, { target: { value: '本机改动' } });
      fireEvent.change(composerBox(), { target: { value: '离线时仍要拦' } });
      fireEvent.click(sendButton());

      const alert = await within(composerForm()).findByRole('alert');
      expect(alert).toHaveTextContent('当前网络不可用，恢复后会自动放行');
      // Retry stays available: the copy promises a way out instead of an endless block.
      expect(within(alert).getByRole('button', { name: '重试保存' })).toBeEnabled();
    } finally { online.mockRestore(); }
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
