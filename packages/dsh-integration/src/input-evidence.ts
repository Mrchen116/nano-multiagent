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
