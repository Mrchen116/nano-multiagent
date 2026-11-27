import { expect, it } from 'vitest';
import {
  classifyChatDelivery,
  isCollaborationScope,
  isPersonalCollaborationScope,
  type ChatAddress,
} from '../src/collaboration.js';
import { chatAttachments } from '../src/chat-codec.js';
import { agentConfigurationFingerprint } from '../src/configuration.js';
import { parseAgentConfigurationFields } from '../src/configuration-rpc.js';

const baseFacts: ChatAddress = {
  ownerDirect: false,
  ownerInternal: false,
  ownerObserved: false,
  projectAllowed: false,
  directToAgent: false,
  addressedToAgent: false,
  addressedToOwner: false,
  contextOnly: false,
};

it('validates explicit collaboration scope values for ordinary/global Agents (3-tier) vs PA (2-tier)', () => {
  expect(isCollaborationScope('team')).toBe(true);
  expect(isCollaborationScope('project')).toBe(true);
  expect(isCollaborationScope('owner_only')).toBe(true);
  expect(isCollaborationScope('private')).toBe(false);
  expect(isCollaborationScope(undefined)).toBe(false);

  expect(isPersonalCollaborationScope('team')).toBe(true);
  expect(isPersonalCollaborationScope('owner_only')).toBe(true);
  expect(isPersonalCollaborationScope('project')).toBe(false);
  expect(isPersonalCollaborationScope(undefined)).toBe(false);
});

it('classifies owner_only chats across ownerDirect, ownerInternal, ownerObserved, and external skips', () => {
  // External colleagues and groups are skipped under owner_only even if projectAllowed were set.
  expect(classifyChatDelivery('owner_only', { ...baseFacts, projectAllowed: true, directToAgent: true, addressedToAgent: true })).toBe('skip');
  expect(classifyChatDelivery('owner_only', { ...baseFacts, addressedToOwner: true })).toBe('skip');

  // Human owner 1:1 direct chat stays high priority.
  expect(classifyChatDelivery('owner_only', { ...baseFacts, ownerDirect: true, directToAgent: true })).toBe('high');

  // Same-owner agent-to-agent 1:1 direct chat (ownerDirect=false, ownerInternal=true, directToAgent=true) is high priority.
  expect(classifyChatDelivery('owner_only', { ...baseFacts, ownerInternal: true, directToAgent: true })).toBe('high');

  // Same-owner internal private group preserves 10-minute background batching unless addressed.
  expect(classifyChatDelivery('owner_only', { ...baseFacts, ownerInternal: true })).toBe('background');
  expect(classifyChatDelivery('owner_only', { ...baseFacts, ownerInternal: true, addressedToAgent: true })).toBe('high');
  expect(classifyChatDelivery('owner_only', { ...baseFacts, ownerInternal: true, addressedToAgent: true, contextOnly: true })).toBe('background');

  // Private PA silent observer events pass through according to owner addressing.
  expect(classifyChatDelivery('owner_only', { ...baseFacts, ownerObserved: true })).toBe('background');
  expect(classifyChatDelivery('owner_only', { ...baseFacts, ownerObserved: true, addressedToOwner: true })).toBe('high');
});

it('classifies project chats across ownerDirect, ownerInternal, projectAllowed, and outsider skips', () => {
  // Outsider direct or public group without projectAllowed is skipped.
  expect(classifyChatDelivery('project', { ...baseFacts, directToAgent: true, addressedToAgent: true })).toBe('skip');
  expect(classifyChatDelivery('project', { ...baseFacts, addressedToAgent: true })).toBe('skip');

  // Owner 1:1 and owner-internal chats remain admitted without needing projectAllowed.
  expect(classifyChatDelivery('project', { ...baseFacts, ownerDirect: true, directToAgent: true })).toBe('high');
  expect(classifyChatDelivery('project', { ...baseFacts, ownerInternal: true })).toBe('background');

  // Shared private group and active project-member 1:1 DM pass when projectAllowed=true.
  expect(classifyChatDelivery('project', { ...baseFacts, projectAllowed: true })).toBe('background');
  expect(classifyChatDelivery('project', { ...baseFacts, projectAllowed: true, addressedToAgent: true })).toBe('high');
  expect(classifyChatDelivery('project', { ...baseFacts, projectAllowed: true, directToAgent: true })).toBe('high');
  expect(classifyChatDelivery('project', { ...baseFacts, projectAllowed: true, addressedToAgent: true, contextOnly: true })).toBe('background');
});

it('supports project scope, confirm_scope_widen field, and optional attachment local_path in contracts', () => {
  const parsed = parseAgentConfigurationFields({
    agent_id: 'family-bot',
    collaboration_scope: 'project',
    confirm_scope_widen: true,
  });
  expect(parsed.collaboration_scope).toBe('project');
  expect(parsed.confirm_scope_widen).toBe(true);
  expect(agentConfigurationFingerprint({ agent_id: 'family-bot', collaboration_scope: 'project' })).toHaveLength(64);

  const atts = chatAttachments([{
    url: '/im/v1/conversations/c_1/attachments/a_1',
    content_type: 'application/pdf',
    file_name: 'checkup.pdf',
    local_path: '/Users/alice/Documents/checkup.pdf',
  }]);
  expect(atts[0]?.local_path).toBe('/Users/alice/Documents/checkup.pdf');
});

it('defaults omitted collaboration scope to team behavior', () => {
  expect(classifyChatDelivery(undefined, { ...baseFacts, directToAgent: true })).toBe('high');
  expect(classifyChatDelivery('team', { ...baseFacts })).toBe('background');
  expect(classifyChatDelivery('team', { ...baseFacts, addressedToAgent: true })).toBe('high');
});
