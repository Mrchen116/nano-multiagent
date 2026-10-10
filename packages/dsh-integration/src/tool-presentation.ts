import type { Context } from '@deepseek-ai/cordis';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import type { ToolCallView, ToolResultView } from '@deepseek-ai/dsh-tools';
import {defineDomain, domainTable, type DomainSpec, type DomainTableSpec} from '@deepseek-ai/dsh-storage-domain';
import {z} from 'zod';

const keyOf = (session: string, call: string) => Buffer.from(JSON.stringify([session, call])).toString('base64url');

type ToolView = {callId: string; call?: ToolCallView; result?: ToolResultView; childSessionId?: string; delegationKind?: string};
interface ToolViewDomain extends DomainSpec {tables: {calls: DomainTableSpec<string, ToolView>}}
const spec: ToolViewDomain = defineDomain({name:'nano_tool_views',version:1,layout:'per-record',tables:{calls:domainTable(z.object({callId:z.string(),call:z.any().optional(),result:z.any().optional(),childSessionId:z.string().optional(),delegationKind:z.string().optional()}))}});

/** Freeze public presenter output in a Nano domain; native logs accept no external event vocabulary. */
export function recordToolPresentations(ctx: Context): (sessionId: string, events: readonly SessionEvent[]) => Promise<SessionEvent[]> {
  const domain = ctx.storageDomain.open(spec);
  let writes = Promise.resolve();
  ctx.effect(() => async () => {await writes; await (await domain).close();});
  ctx.on('tools/pre-execute', async (exec, next) => {
    if (exec.agent?.session.header.agentPreset?.startsWith('nano:')) {
      const call = ctx.tools.get(exec.name, exec.agent)?.presentCall?.(exec.arguments);
      if (call) {
        const key = keyOf(exec.agent.id, exec.callId);
        const snapshot = JSON.parse(JSON.stringify({callId: exec.callId, call}));
        writes = writes.then(async () => {await (await domain).table('calls').put(key, snapshot);});
        await writes;
      }
    }
    return next();
  }, {prepend: true});
  ctx.on('tools/result', (exec, result) => {
    if (!exec.agent?.session.header.agentPreset?.startsWith('nano:')) return;
    const definition = ctx.tools.get(exec.name, exec.agent);
    const value = !result.isError && result.value && typeof result.value === 'object' && !Array.isArray(result.value) ? result.value : {};
    const delegationKind = exec.name === 'subagent' && ['foreground', 'continuable', 'background'].includes(String(value.kind)) ? String(value.kind) : undefined;
    const child = value.kind === 'continuable' ? value.subagentId : value.kind === 'foreground' ? value.runId : undefined;
    const view = {
      callId: exec.callId,
      ...(delegationKind ? {delegationKind} : {}),
      call: definition?.presentCall?.(exec.arguments),
      result: definition?.presentResult?.(exec.arguments, result),
      ...(typeof child === 'string' ? {childSessionId: child} : {}),
    };
    if (view.call || view.result || view.childSessionId || view.delegationKind) {
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
      if (event.type !== 'tool/result' && event.type !== 'tool/call') return event;
      const callId = event.type === 'tool/call' ? event.data.callId : event.data.message.toolCallId;
      const view = table.get(keyOf(sessionId, callId));
      if (!view) return event;
      if (event.type === 'tool/call') return {...event, data:{...event.data, nanoToolView:view}};
      return {...event, data:{...event.data, nanoToolView:view}};
    });
  };
}
