import type { Agent } from '@deepseek-ai/dsh-agent';
import type { UserMessage } from '@deepseek-ai/dsh-llm';
import type {} from '@deepseek-ai/dsh-session';

/** Only the event fields approval routing and the browser gate need. */
export interface TurnEvent {
  seq: number;
  time: number;
  type: string;
  data: { turn?: number; source?: UserMessage['source']; [key: string]: unknown };
}

/** A live session view; the browser gate deliberately does not require a full Agent. */
export interface TurnSession {
  id: string;
  header: { origin?: 'subagent'; parentSession?: string };
  snapshotEvents(): readonly TurnEvent[];
}

/** Adapt a live Agent to the session view used by the turn gate.
 *
 * A live Agent exposes its durable session under `agent.session`; lineage and
 * turn decisions only need this stable subset.
 */
export function liveTurnSession(agent: Agent): TurnSession {
  const session = agent.session;
  return {
    id: agent.id,
    header: session.header,
    snapshotEvents: () => session.snapshotEvents() as unknown as readonly TurnEvent[],
  };
}

export interface CurrentTurn {
  startSeq: number;
  /** Messages claimed for the open turn, in append order. */
  inputs: UserMessage[];
}

export interface OpenTurn {
  open: boolean;
  turn?: number;
  startSeq?: number;
  /** Human messages in the open turn, in append order. */
  human: { message: UserMessage; time: number }[];
}

export type TurnGateDenial =
  | 'no_open_turn'
  | 'no_human_message'
  | 'outside_presence_window'
  | 'lineage_broken'
  | 'lineage_cycle';

export type TurnGateDecision =
  | { allowed: true; sessionId: string; deltaMs: number; turnStartSeq: number }
  | { allowed: false; reason: TurnGateDenial };

/** Presence window chosen to match the driver's 300s idle expiry. */
export const PRESENCE_WINDOW_MS = 300_000;

/** Return the messages claimed after the latest `turn/start`.
 *
 * Args:
 *   agent: Live Agent whose session log is authoritative.
 *
 * Returns:
 *   The latest turn start sequence and its user-role messages.
 */
export function currentTurnInputs(agent: Agent): CurrentTurn {
  const events = agent.session.snapshotEvents();
  const startSeq = events.findLast(event => event.type === 'turn/start')?.seq ?? -1;
  return {
    startSeq,
    inputs: events
      .filter(event => event.seq > startSeq && event.type === 'user/message')
      .map(event => event.data as UserMessage),
  };
}

/** Locate the last turn from the tail and report whether it is still open.
 *
 * Scanning from the tail keeps long sessions cheap and makes an earlier open
 * turn irrelevant once a newer turn has ended.
 */
export function openTurn(session: TurnSession): OpenTurn {
  const events = session.snapshotEvents();
  const startIndex = events.findLastIndex(event => event.type === 'turn/start');
  if (startIndex < 0) return { open: false, human: [] };
  const start = events[startIndex]!;
  const turn = start.data.turn;
  const closed = events.slice(startIndex + 1).some(event => event.type === 'turn/end' && event.data.turn === turn);
  if (closed) return { open: false, turn, startSeq: start.seq, human: [] };
  const human = events
    .slice(startIndex + 1)
    .filter(event => event.type === 'user/message' && isHumanEvent(event))
    .map(event => ({ message: event.data as unknown as UserMessage, time: event.time }));
  return { open: true, turn, startSeq: start.seq, human };
}

function isHumanEvent(event: TurnEvent): boolean {
  const source = event.data.source as { kind?: string; actorId?: unknown; channel?: unknown; messageId?: unknown } | undefined;
  if (!source) return false;
  return source.kind === 'nano-human'
    || source.kind === 'user' && 'actorId' in source && 'channel' in source && 'messageId' in source;
}

/** Resolve the non-subagent session whose user turn authorizes a launch.
 *
 * `agents` is a live registry rather than durable lineage, so a missing parent
 * is a real chain break. The `seen` set makes self/mutual cycles terminate.
 */
export function judgmentSession(
  start: TurnSession,
  agents: (id: string) => TurnSession | undefined,
): { session: TurnSession } | { reason: 'lineage_broken' | 'lineage_cycle' } {
  let current = start;
  const seen = new Set<string>();
  while (current.header.origin === 'subagent') {
    if (seen.has(current.id)) return { reason: 'lineage_cycle' };
    seen.add(current.id);
    const parentId = current.header.parentSession;
    if (!parentId) return { reason: 'lineage_broken' };
    if (seen.has(parentId)) return { reason: 'lineage_cycle' };
    const parent = agents(parentId);
    if (!parent) return { reason: 'lineage_broken' };
    current = parent;
  }
  return { session: current };
}

/** Decide whether a new browser instance may be launched for this request.
 *
 * The three conditions are: the judgment session's last turn is still open,
 * that turn contains a host-attested human message, and the latest such message
 * is within {@link PRESENCE_WINDOW_MS}. `event.time` is assigned by this local
 * DSH process when the event is appended and the gate runs in the same
 * process, so both sides of the delta share one clock. A negative delta means
 * the clock moved backwards and is rejected rather than treated as fresh.
 *
 * Schedule, heartbeat, task-execution and task-change turns are not special
 * cased: those turns simply have no human message, which is the equivalent
 * refusal. If a human message and a `nano-system` task input share one turn,
 * the human message wins.
 */
export function evaluateTurnGate(
  start: TurnSession,
  agents: (id: string) => TurnSession | undefined,
  now: number,
): TurnGateDecision {
  const resolved = judgmentSession(start, agents);
  if ('reason' in resolved) return { allowed: false, reason: resolved.reason };
  const turn = openTurn(resolved.session);
  if (!turn.open) return { allowed: false, reason: 'no_open_turn' };
  if (!turn.human.length) return { allowed: false, reason: 'no_human_message' };
  const latest = turn.human.at(-1)!;
  const deltaMs = now - latest.time;
  if (deltaMs < 0 || deltaMs > PRESENCE_WINDOW_MS) return { allowed: false, reason: 'outside_presence_window' };
  return { allowed: true, sessionId: resolved.session.id, deltaMs, turnStartSeq: turn.startSeq! };
}
