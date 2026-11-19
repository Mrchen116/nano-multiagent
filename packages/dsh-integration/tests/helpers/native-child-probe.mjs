import {appendFileSync} from 'node:fs';
import {join} from 'node:path';

export const name = 'native-child-probe';
export function apply(ctx) {
  const types = new Set(['turn/start', 'turn/end', 'tool/call', 'tool/result', 'llm/retry']);
  ctx.on('session/event', (session, event) => {
    if (!session.header.parentSession || !session.isOwnSeq(event.seq) || !types.has(event.type)) return;
    appendFileSync(join(process.env.DSH_HOME, 'native-child-events.jsonl'),
      JSON.stringify({id:session.id, parentId:session.header.parentSession, event}) + '\n');
  });
}
