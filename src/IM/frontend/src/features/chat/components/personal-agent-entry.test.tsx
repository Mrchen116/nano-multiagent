import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { setLanguage } from '../../../i18n';
import type { Conversation } from '../chat-types';
import { PersonalAgentEntry } from './personal-agent-entry';

const conversation: Conversation = {
  id: 'pa-chat', title: 'Milo', participants: [], participant_ids: [], type: 'direct', direct_kind: 'agent',
  owner_id: 'owner', creator_id: 'owner', is_pinned: false, is_muted: false, unread_count: 1,
  last_message_preview: 'The meeting notes are ready.', last_message_at: new Date().toISOString(), created_at: '',
};
beforeEach(() => setLanguage('en'));

it('updates the pinned assistant summary and unread count with the conversation', async () => {
  const select = vi.fn();
  const view = render(<PersonalAgentEntry name="Milo" conversation={conversation} active={false} onSelect={select} />);
  expect(screen.getByText('The meeting notes are ready.')).toBeVisible();
  expect(screen.getByLabelText('1 unread')).toBeVisible();
  const date = new Date(conversation.last_message_at!);
  expect(screen.getByText(`${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`)).toBeVisible();
  await userEvent.click(screen.getByRole('button'));
  expect(select).toHaveBeenCalledOnce();
  view.rerender(<PersonalAgentEntry name="Milo" conversation={{...conversation, last_message_preview: 'I also checked the new date.', unread_count: 0}} active onSelect={select} />);
  expect(screen.queryByText('The meeting notes are ready.')).not.toBeInTheDocument();
  expect(screen.getByText('I also checked the new date.')).toBeVisible();
  expect(screen.queryByLabelText(/unread/)).not.toBeInTheDocument();
  expect(screen.getByRole('button')).toHaveAttribute('aria-current', 'true');
});

it('keeps an unconfigured assistant usable without inventing a message or timestamp', async () => {
  const select = vi.fn();
  render(<PersonalAgentEntry active={false} onSelect={select} />);
  await userEvent.click(screen.getByRole('button'));
  expect(select).toHaveBeenCalledOnce();
  expect(screen.queryByLabelText(/unread/)).not.toBeInTheDocument();
});
