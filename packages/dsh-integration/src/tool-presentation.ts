import type { Context } from '@deepseek-ai/cordis';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import type { ToolCallView, ToolResultView } from '@deepseek-ai/dsh-tools';
import {defineDomain, domainTable, type DomainSpec, type DomainTableSpec} from '@deepseek-ai/dsh-storage-domain';
import {z} from 'zod';

const keyOf = (session: string, call: string) => Buffer.from(JSON.stringify([session, call])).toString('base64url');

type ToolView = {callId: string; call?: ToolCallView; result?: ToolResultView; childSessionId?: string};
interface ToolViewDomain extends DomainSpec {tables: {calls: DomainTableSpec<string, ToolView>}}
const spec: ToolViewDomain = defineDomain({name:'nano_tool_views',version:1,layout:'per-record',tables:{calls:domainTable(z.object({callId:z.string(),call:z.any().optional(),result:z.any().optional(),childSessionId:z.string().optional()}))}});

/** Freeze public presenter output in a Nano domain; native logs accept no external event vocabulary. */
export function recordToolPresentations(ctx: Context): (sessionId: string, events: readonly SessionEvent[]) => Promise<SessionEvent[]> {
  const domain = ctx.storageDomain.open(spec);
  let writes = Promise.resolve();
  ctx.effect(() => async () => {await writes; await (await domain).close();});
  ctx.on('tools/result', (exec, result) => {
    if (!exec.agent?.session.header.agentPreset?.startsWith('nano:')) return;
    const definition = ctx.tools.get(exec.name, exec.agent);
    const value = !result.isError && result.value && typeof result.value === 'object' && !Array.isArray(result.value) ? result.value : {};
    const child = value.kind === 'continuable' ? value.subagentId : value.kind === 'foreground' ? value.runId : undefined;
    const view = {
      callId: exec.callId,
      call: definition?.presentCall?.(exec.arguments),
      result: definition?.presentResult?.(exec.arguments, result),
      ...(typeof child === 'string' ? {childSessionId: child} : {}),
    };
    if (view.call || view.result || view.childSessionId) {
      const key = keyOf(exec.agent.id, exec.callId);
      const snapshot = JSON.parse(JSON.stringify(view));
      writes = writes.then(async () => {await (await domain).table('calls').put(key, snapshot);});
      void writes.catch(() => {}); // Observation reports a failed durable presentation barrier.
    }
  });
  return async (sessionId: string, events: readonly SessionEvent[]) => {
    await writes;
    const table = (await domain).table('calls');
    return events.map(event => {
      if (event.type !== 'tool/result') return event;
      const view = table.get(keyOf(sessionId, event.data.message.toolCallId));
      return view ? {...event, data:{...event.data, nanoToolView:view}} : event;
    });
  };
}
