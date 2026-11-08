import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import '../../../i18n';
import type { Conversation, Message } from '../chat-types';
import { MessagePane } from './message-pane';
const conversation={id:'reply-chat',title:'Assistant',type:'direct',participants:[],participant_ids:[],created_at:'2026-01-01T00:00:00Z',is_pinned:false,is_muted:false,unread_count:0} as unknown as Conversation;
const original:Message={id:'original',conversation_id:conversation.id,sender:{type:'agent',id:'a',display_name:'Assistant'},sender_type:'agent',sender_user_id:'agent-user',content:'第二点：先验证再交付',attachments:[],created_at:'2026-01-01T00:00:00Z',delivery_status:'completed',permission_requests:[]};

it('keeps quoted replies with the draft, preserves them on send failure, and clears them on success',async()=>{
  const onSend=vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined);
  render(<MemoryRouter><MessagePane conversation={conversation} messages={[original]} mentionCandidates={[]} onSend={onSend}/></MemoryRouter>);
  fireEvent.click(screen.getByTestId('message-reply-original'));
  expect(screen.getByTestId('composer-reply')).toHaveTextContent(original.content);
  const input=screen.getByRole('textbox');fireEvent.change(input,{target:{value:'展开这个'}});
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(onSend).toHaveBeenCalledTimes(1));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Send'})).not.toBeDisabled());
  expect(input).toHaveValue('展开这个');expect(screen.getByTestId('composer-reply')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(onSend).toHaveBeenCalledTimes(2));
  expect(onSend.mock.calls[0][5]).toBe('original');expect(onSend.mock.calls[1][3]).toBe(onSend.mock.calls[0][3]);
  await waitFor(()=>expect(screen.queryByTestId('composer-reply')).toBeNull());
});

it('offers attachment replies and cancellation, renders quotes, and excludes running and read-only messages',()=>{
  const attachment={...original,id:'file',content:'',attachments:[{url:'/file',file_name:'计划.pdf',content_type:'application/pdf'}]};
  const quote={message_id:original.id,sender:original.sender,content:original.content,attachments:[]};
  const {rerender}=render(<MemoryRouter><MessagePane conversation={conversation} messages={[attachment,{...original,id:'reply',reply_to:quote}]} mentionCandidates={[]} onSend={()=>{}}/></MemoryRouter>);
  fireEvent.click(screen.getByTestId('message-reply-file'));expect(screen.getByTestId('composer-reply')).toHaveTextContent('计划.pdf');
  fireEvent.click(screen.getByRole('button',{name:'Cancel reply'}));expect(screen.queryByTestId('composer-reply')).toBeNull();
  expect(screen.getByRole('link',{name:'View original message'})).toHaveAttribute('href',`/chat/${conversation.id}?message_id=original`);
  rerender(<MemoryRouter><MessagePane conversation={{...conversation,can_write:false}} messages={[original,{...original,id:'running',delivery_status:'running'}]} mentionCandidates={[]} onSend={()=>{}}/></MemoryRouter>);
  expect(screen.queryByTestId('message-reply-original')).toBeNull();expect(screen.queryByTestId('message-reply-running')).toBeNull();
});
