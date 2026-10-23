import type { SessionEvent } from '@deepseek-ai/dsh-session';
import type { UserMessage } from '@deepseek-ai/dsh-llm';

/** Durable input accounting also covers a claim interrupted before user/message. */
export function inputEvidence(events: readonly SessionEvent[], inputId: string) {
  const queues: Record<string, UserMessage[]> = { 'next-turn': [], 'next-step': [] };
  let acceptedSeq: number | undefined;
  let consumedSeq: number | undefined;
  let terminal: unknown;
  let inputTurn: number | undefined;
  let turn: number | undefined;
  for (const event of events) {
    if (event.type === 'turn/start') turn = event.data.turn;
    if (event.type === 'agent/inbox/spliced') {
      const { target, start, inserted, removedCount = 0, outcome } = event.data;
      const queue = queues[target]!;
      const removed = queue.splice(start, removedCount, ...inserted);
      if (inserted.some(message => message.id === inputId)) acceptedSeq ??= event.seq;
      if (removed.some(message => message.id === inputId)) {
        if (outcome === 'canceled') terminal = { kind: 'cancelled-before-consumption' };
        else inputTurn = turn;
      }
    }
    if (event.type === 'user/message' && event.data.id === inputId) {
      acceptedSeq ??= event.seq;
      consumedSeq = event.seq;
      inputTurn = turn;
    }
    if (event.type === 'turn/end') {
      if (inputTurn === event.data.turn) terminal = event.data.reason;
      turn = undefined;
    }
  }
  return {
    accepted: acceptedSeq !== undefined,
    acceptedSeq,
    consumedSeq,
    pending: Object.values(queues).some(queue => queue.some(message => message.id === inputId)),
    turn: inputTurn,
    terminal,
  };
}

/** Collects inbox inputs by final native turn ownership in one history replay.
 *
 * Args:
 *   events: Complete durable session history in event order.
 *   inputTurn: Native turn whose inputs are requested.
 *
 * Returns:
 *   Unique inbox input IDs in first-insertion order. Claims count even before
 *   user/message; cancellation preserves any prior ownership, as inputEvidence does.
 */
export function inputIdsForTurn(events: readonly SessionEvent[], inputTurn: number): string[] {
  const queues: Record<string, string[]> = { 'next-turn': [], 'next-step': [] };
  const insertedIds = new Set<string>();
  const turns = new Map<string, number | undefined>();
  let turn: number | undefined;
  for (const event of events) {
    if (event.type === 'turn/start') turn = event.data.turn;
    if (event.type === 'agent/inbox/spliced') {
      const { target, start, inserted, removedCount = 0, outcome } = event.data;
      const ids = inserted.map(message => message.id);
      const removed = queues[target]!.splice(start, removedCount, ...ids);
      for (const id of ids) insertedIds.add(id);
      if (outcome !== 'canceled')
        for (const id of removed) turns.set(id, turn);
    }
    if (event.type === 'user/message') turns.set(event.data.id, turn);
    if (event.type === 'turn/end') turn = undefined;
  }
  return [...insertedIds].filter(id => turns.get(id) === inputTurn);
}
