import { SessionLogOffset, type Session, type SessionEvent } from '@deepseek-ai/dsh-session';
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

type InputState = {
  acceptedSeq: number;
  consumedSeq?: number;
  pending: number;
  insertion?: number;
  turn?: number;
  terminal?: unknown;
};

/** Identity-only index for the append-only log of a single native Session. */
export class InputEvidenceIndex {
  private readonly queues = { 'next-turn': [] as string[], 'next-step': [] as string[] };
  private readonly inputs = new Map<string, InputState>();
  private readonly turns = new Map<number, Set<string>>();
  private turn?: number;
  private insertion = 0;
  private cursor = SessionLogOffset(0);

  /** Bring the index to the current native cut without reading the prefix again. */
  update(session: Pick<Session, 'seq' | 'snapshotEvents'>): this {
    if (session.seq === this.cursor) return this;
    for (const event of session.snapshotEvents(this.cursor)) this.append(event);
    this.cursor = session.seq;
    return this;
  }

  private state(id: string, seq: number): InputState {
    let state = this.inputs.get(id);
    if (!state) {
      state = { acceptedSeq: seq, pending: 0 };
      this.inputs.set(id, state);
    }
    return state;
  }

  private claim(id: string, state: InputState): void {
    if (state.turn === this.turn) return;
    if (state.turn !== undefined) this.turns.get(state.turn)?.delete(id);
    state.turn = this.turn;
    if (this.turn === undefined) return;
    let members = this.turns.get(this.turn);
    if (!members) this.turns.set(this.turn, members = new Set());
    members.add(id);
  }

  private append(event: SessionEvent): void {
    switch (event.type) {
      case 'turn/start':
        this.turn = event.data.turn;
        break;
      case 'agent/inbox/spliced': {
        const { target, start, inserted, removedCount = 0, outcome } = event.data;
        const ids = inserted.map(message => {
          const state = this.state(message.id, event.seq);
          state.pending++;
          state.insertion ??= this.insertion++;
          return message.id;
        });
        for (const id of this.queues[target].splice(start, removedCount, ...ids)) {
          const state = this.inputs.get(id)!;
          state.pending--;
          if (outcome === 'canceled') state.terminal = { kind: 'cancelled-before-consumption' };
          else this.claim(id, state);
        }
        break;
      }
      case 'user/message': {
        const state = this.state(event.data.id, event.seq);
        state.consumedSeq = event.seq;
        this.claim(event.data.id, state);
        break;
      }
      case 'turn/end':
        for (const id of this.turns.get(event.data.turn) ?? []) this.inputs.get(id)!.terminal = event.data.reason;
        this.turn = undefined;
        break;
    }
  }

  evidence(id: string): ReturnType<typeof inputEvidence> {
    const state = this.inputs.get(id);
    return {
      accepted: state !== undefined,
      acceptedSeq: state?.acceptedSeq,
      consumedSeq: state?.consumedSeq,
      pending: !!state?.pending,
      turn: state?.turn,
      terminal: state?.terminal,
    };
  }

  idsForTurn(turn: number): string[] {
    return [...(this.turns.get(turn) ?? [])]
      .filter(id => this.inputs.get(id)!.insertion !== undefined)
      .sort((left, right) => this.inputs.get(left)!.insertion! - this.inputs.get(right)!.insertion!);
  }
}

const indexes = new WeakMap<Session, InputEvidenceIndex>();

export function indexedInputs(session: Session): InputEvidenceIndex {
  let index = indexes.get(session);
  if (!index) indexes.set(session, index = new InputEvidenceIndex());
  return index.update(session);
}
