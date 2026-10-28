import type { AgentPublication, ChatStreamFact } from '@nano/product-contracts';
import type { ExternalStore } from '../src/external-store.js';

declare const outbox: ExternalStore;
const completed: ChatStreamFact = {kind: 'message_completed', message_id: 'bubble', final_content: 'done', delivery_status: 'completed'};
outbox.frame('output', completed);
outbox.frame('output', {kind: 'tool_call_completed', message_id: 'bubble', tool_call: {id: 'call', input: ['any', null], output: false, detail: {vendor: [1, 2]}}});
outbox.frame('output', {kind: 'system_notice', system_notice: {vendor: 'opaque'}});
// @ts-expect-error Message updates need their persisted message identity.
outbox.frame('output', {kind: 'message_delta', delta_text: 'text'});
// @ts-expect-error A terminal message cannot receive the tool-update payload.
outbox.frame('output', {kind: 'message_completed', message_id: 'bubble', tool_call: {id: 'call'}});
// @ts-expect-error Tool call identities are required even when their contents are opaque.
outbox.frame('output', {kind: 'tool_call_upserted', message_id: 'bubble', tool_call: {input: {}}});
// @ts-expect-error A notice branch must not reopen arbitrary streaming kind names.
outbox.frame('output', {kind: 'future_stream_kind', message_id: 'bubble'});
// @ts-expect-error Known completion statuses cannot silently become arbitrary strings.
const badStatus: ChatStreamFact = {kind: 'message_completed', message_id: 'bubble', delivery_status: 'running'};
// @ts-expect-error Production publication requires a trusted source session.
const noSource: AgentPublication = {to: 'conversation:chat', text: 'reply'};
// @ts-expect-error Production publication requires a target.
const noTarget: AgentPublication = {from_session_id: 'agent|tool_call:call', text: 'reply'};
void badStatus; void noSource; void noTarget;
