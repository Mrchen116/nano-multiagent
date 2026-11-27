import { expect, it } from 'vitest';
import { classifyChatDelivery, isCollaborationScope, type ChatAddress } from '../src/collaboration.js';

const baseFacts: ChatAddress = {
  ownerDirect: false,
  ownerInternal: false,
  ownerObserved: false,
  directToAgent: false,
  addressedToAgent: false,
  addressedToOwner: false,
  contextOnly: false,
};

it('validates explicit collaboration scope values without coercing unknown strings', () => {
  expect(isCollaborationScope('team')).toBe(true);
  expect(isCollaborationScope('owner_only')).toBe(true);
  expect(isCollaborationScope('private')).toBe(false);
  expect(isCollaborationScope(undefined)).toBe(false);
});

it('classifies owner_only chats across ownerDirect, ownerInternal, ownerObserved, and external skips', () => {
  // External colleagues and groups are skipped under owner_only.
  expect(classifyChatDelivery('owner_only', { ...baseFacts, directToAgent: true, addressedToAgent: true })).toBe('skip');
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

it('defaults omitted collaboration scope to team behavior', () => {
  expect(classifyChatDelivery(undefined, { ...baseFacts, directToAgent: true })).toBe('high');
  expect(classifyChatDelivery('team', { ...baseFacts })).toBe('background');
  expect(classifyChatDelivery('team', { ...baseFacts, addressedToAgent: true })).toBe('high');
});
