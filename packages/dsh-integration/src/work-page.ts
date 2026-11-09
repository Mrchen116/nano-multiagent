import type { SessionEvent } from '@deepseek-ai/dsh-session';
import type { ModelRunProjection, RuntimeEvent, RuntimeWorkPage } from '@nano/product-contracts';

export const workPageBytes = 1024 * 1024;
export const workPageItems = 256;

export const jsonBytes = (value: unknown): number => Buffer.byteLength(JSON.stringify(value)) + 1;

/** Retain the fields consumed by Work; the native log owns request reconstruction. */
export function workEvent(event: SessionEvent): RuntimeEvent {
  const base = event as RuntimeEvent;
  if (event.type === 'request/header') return {...base, data:{header:{config:{model:event.data.header.config?.model}}}};
  if (event.type === 'request/context') return {...base, data:{model:event.data.model, contextWindow:event.data.contextWindow}};
  return base;
}

/** Build one durable page without copying or serializing its unprocessed suffix. */
export async function workPage(input: {
  afterSeq: number; replayFrom?: number; firstOwn: number; head: number;
  eventAt(seq: number): SessionEvent | undefined;
  present(event: SessionEvent): Promise<SessionEvent>;
  model(turn: number): ModelRunProjection | undefined;
  modelVersion: string;
}): Promise<RuntimeWorkPage> {
  const {afterSeq, replayFrom, firstOwn, head, eventAt, present, model, modelVersion} = input;
  const events: RuntimeEvent[] = [];
  const modelRuns = new Map<string, ModelRunProjection>();
  let throughSeq = Math.max(afterSeq, Math.min(head, firstOwn - 1));
  let bytes = 256 + modelVersion.length;
  const prior = replayFrom !== undefined && replayFrom <= afterSeq ? eventAt(replayFrom) : undefined;
  const carried = prior?.type === 'turn/start' ? model(prior.data.turn) : undefined;
  if (carried) { modelRuns.set(carried.id, carried); bytes += jsonBytes(carried); }
  // Freeze the model sidecars at the native cut before asynchronous presenter reads.
  const candidates:{source:SessionEvent;run?:ModelRunProjection}[]=[];
  for (let seq=throughSeq+1; seq<=head && candidates.length<workPageItems; seq++) {
    const source=eventAt(seq);
    if (!source) throw new Error(`Missing native Work event at ${seq}`);
    const turn=(source as RuntimeEvent).data.turn;
    candidates.push({source,run:typeof turn==='number' ? model(turn) : undefined});
  }
  for (const {source,run} of candidates) {
    const event = workEvent(await present(source));
    const fresh = run && !modelRuns.has(run.id) ? run : undefined;
    const size = jsonBytes(event) + (fresh ? jsonBytes(fresh) : 0);
    // One unusually large record makes progress alone, preserving its complete content.
    if (events.length && bytes + size > workPageBytes) break;
    events.push(event);
    throughSeq = source.seq;
    bytes += size;
    if (fresh) modelRuns.set(fresh.id, fresh);
    if (bytes >= workPageBytes) break;
  }
  return {durable:true, events, modelRuns:[...modelRuns.values()], modelVersion, throughSeq, more: throughSeq < head};
}
