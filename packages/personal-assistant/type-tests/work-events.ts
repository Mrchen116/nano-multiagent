import type { RuntimeEvent, WorkFact, WorkJournalEvent } from '@nano/product-contracts';
import type { InboxStore } from '../src/inbox.js';
import { projectWorkEvent } from '../src/work-projection.js';

declare const inbox: InboxStore;
declare const runtimeEvent: RuntimeEvent;
const identity = {event_id: 'fact', root_agent_id: 'agent', session_id: 'main'};
const checkpoint = {rootSessionId: 'main', throughSeq: 1, replayFrom: 2};
const projected = projectWorkEvent('main', runtimeEvent, [runtimeEvent]);
if (projected) {
  const {turn, ...fact} = projected;
  inbox.append({...identity, ...fact, turn_id: turn === undefined ? undefined : String(turn)});
}
const journal: WorkJournalEvent[] = inbox.journal(0);
void journal;

// Production events must remain closed and keep their payload paired with their type.
// @ts-expect-error A model selection cannot carry a session-registration payload.
inbox.append({...identity, type: 'model_selected', payload: {scope: 'global_main'}});
// @ts-expect-error Current producers cannot use the wire decoder's unknown-event compatibility.
inbox.append({...identity, type: 'future_event', payload: {}});
// @ts-expect-error Event identity is mandatory at the durable production boundary.
inbox.append({event_id: 'missing-session', root_agent_id: 'agent', type: 'turn_end', payload: {}});
// @ts-expect-error Atomic checkpoint commits require the same complete identity.
inbox.commitWork('main', checkpoint, [{event_id: 'missing-root', session_id: 'main', type: 'turn_end', payload: {}}]);

// Knowledge producers participate in the same contract, including required link/review fields.
inbox.append({...identity, type: 'session_linked', payload: {parent_session_id: 'main', child_session_id: 'review'}});
inbox.append({...identity, type: 'self_evolution_review', payload: {review_id: 'review', updated_targets: ['memory']}});
// @ts-expect-error A session link needs both endpoints.
inbox.append({...identity, type: 'session_linked', payload: {parent_session_id: 'main'}});
// @ts-expect-error Knowledge target names are stable strings.
inbox.append({...identity, type: 'self_evolution_review', payload: {review_id: 'review', updated_targets: [1]}});

const modelPayload = {model: 'provider:model'};
// @ts-expect-error Fact values also retain the correlation before persistence.
const wrongPair: WorkFact = {type: 'session_registered', payload: modelPayload};
void wrongPair;
