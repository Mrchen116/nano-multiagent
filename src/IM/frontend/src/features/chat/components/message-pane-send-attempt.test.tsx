import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import type { Conversation, Message } from '../chat-types';
import { lookupMessageAttempt } from '../chat-api';
import { MessagePane } from './message-pane';
import { listSendAttempts, prepareSendAttempt, removeSendAttempt } from './send-attempt-store';
import type { ComposerSnapshot } from './composer-draft-store';

vi.mock('../chat-api',()=>({lookupMessageAttempt:vi.fn()}));
const conversation: Conversation = {id:'chat',title:'Assistant',participants:[],participant_ids:[],type:'direct',direct_kind:'agent',owner_id:'u1',creator_id:'u1',is_pinned:false,is_muted:false,unread_count:0,last_message_preview:null,last_message_at:null,created_at:'2026-01-01T00:00:00Z'};
function pane(extra: Partial<ComponentProps<typeof MessagePane>>) {
  return <MessagePane conversation={conversation} messages={[]} mentionCandidates={[]} selfUserId="u1" onSend={()=>{}} {...extra}/>;
}

beforeEach(()=>{ vi.mocked(lookupMessageAttempt).mockReset().mockResolvedValue(null); });

describe('ordinary composer send identity',()=>{
  it('persists before POST, reuses unchanged retries, and gives an edited explicit send a new identity',async()=>{
    const user = userEvent.setup();
    const snapshots: unknown[] = [];
    const onSend = vi.fn(async (...args: unknown[])=>{
      snapshots.push(await listSendAttempts('u1','chat'));
      throw new TypeError('connection lost');
    });
    render(pane({onSend}));
    await user.type(screen.getByRole('textbox'),'hello');
    await user.keyboard('{Enter}');
    await waitFor(()=>expect(onSend).toHaveBeenCalledTimes(1));
    await waitFor(()=>expect(screen.getByRole('textbox')).not.toBeDisabled());
    // A second tab can confirm this identity before the first tab retries it.
    await removeSendAttempt((await listSendAttempts('u1','chat'))[0]!);
    await user.keyboard('{Enter}');
    await waitFor(()=>expect(onSend).toHaveBeenCalledTimes(2));
    const firstKey = onSend.mock.calls[0]![3];
    expect(firstKey).toEqual(expect.any(String));
    expect(onSend.mock.calls[1]![3]).toBe(firstKey);
    expect(snapshots[0]).toEqual([expect.objectContaining({key:firstKey,text:'hello'})]);

    await waitFor(()=>expect(screen.getByRole('textbox')).not.toBeDisabled());
    await user.type(screen.getByRole('textbox'),' edited');
    await user.keyboard('{Enter}');
    await waitFor(()=>expect(onSend).toHaveBeenCalledTimes(3));
    expect(onSend.mock.calls[2]![3]).not.toBe(firstKey);
    expect(onSend.mock.calls[2]![0]).toBe('hello edited');
  });

  it('restores a submitted snapshot after remount and retries with its original key',async()=>{
    const user = userEvent.setup();
    const onSend = vi.fn().mockRejectedValue(new TypeError('response lost'));
    const submitted = {draft:'persist me',draftMentions:[],pending:[{url:'/upload/one',file_name:'one'}],slashDismissed:false,revision:'submitted'};
    const frozen = await prepareSendAttempt('u1','chat',submitted,{text:'persist me',attachments:submitted.pending,contexts:[{source_message_id:'card',state:{choice:'frozen'}}]});
    render(pane({onSend}));
    await waitFor(()=>expect(screen.getByRole('textbox')).toHaveValue('persist me'));
    expect(lookupMessageAttempt).toHaveBeenCalledWith('chat',frozen.key);
    expect(onSend).not.toHaveBeenCalled();
    await user.click(screen.getByRole('textbox'));
    await user.keyboard('{Enter}');
    await waitFor(()=>expect(onSend).toHaveBeenCalledWith(frozen.text,frozen.attachments,undefined,frozen.key,frozen.contexts));
  });

  it.each([
    ['old-version','old',''],
    ['new-version','new draft','new draft']
  ])('merges recovered success and clears only the submitted draft version (%s)',async(revision,draft,expected)=>{
    const submitted = {draft:'old',draftMentions:[],pending:[],slashDismissed:false,revision:'old-version'};
    await prepareSendAttempt('u1','chat',submitted,{text:'old',attachments:[],contexts:[]});
    let confirm: (message:Message)=>void = ()=>{};
    vi.mocked(lookupMessageAttempt).mockReturnValue(new Promise(resolve=>{confirm=resolve;}));
    const store = new Map<string,ComposerSnapshot>([['chat',{...submitted,draft,revision}]]);
    const onRecovered = vi.fn();
    render(pane({composerStore:store,onRecovered}));
    await waitFor(()=>expect(lookupMessageAttempt).toHaveBeenCalled());
    const message = {id:'original-message',conversation_id:'chat',content:'old'} as Message;
    await act(async()=>confirm(message));
    await waitFor(()=>expect(onRecovered).toHaveBeenCalledWith(message));
    await waitFor(()=>expect(screen.getByRole('textbox')).toHaveValue(expected));
    expect(await listSendAttempts('u1','chat')).toEqual([]);
  });

  it('gives two successfully submitted identical messages distinct keys',async()=>{
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(pane({onSend}));
    for (let index=0; index<2; index++) {
      await user.type(screen.getByRole('textbox'),'same');
      await user.keyboard('{Enter}');
      await waitFor(()=>expect(screen.getByRole('textbox')).toHaveValue(''));
    }
    expect(onSend.mock.calls[0]![3]).toEqual(expect.any(String));
    expect(onSend.mock.calls[1]![3]).not.toBe(onSend.mock.calls[0]![3]);
  });

  it('keeps the draft and existing error feedback when durable storage cannot accept the send',async()=>{
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onSendFailure = vi.fn();
    const storage = vi.spyOn(indexedDB,'open').mockImplementation(()=>{throw new DOMException('Storage unavailable','QuotaExceededError');});
    try {
      render(pane({onSend,onSendFailure}));
      await user.type(screen.getByRole('textbox'),'keep this draft');
      await user.keyboard('{Enter}');
      await waitFor(()=>expect(onSendFailure).toHaveBeenCalled());
      expect(onSend).not.toHaveBeenCalled();
      expect(screen.getByRole('textbox')).toHaveValue('keep this draft');
    } finally { storage.mockRestore(); }
  });
});
