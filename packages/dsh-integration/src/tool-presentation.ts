import { opendir, readFile, realpath } from 'node:fs/promises';
import { join } from 'node:path';
import { JsonStorageBackend } from '@deepseek-ai/dsh-storage-json';
import type { Context } from '@deepseek-ai/cordis';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import type { ToolCallView, ToolResultView } from '@deepseek-ai/dsh-tools';
import {defineDomain, descriptorOf, domainTable, type DomainSpec, type DomainTableSpec} from '@deepseek-ai/dsh-storage-domain';
import {z} from 'zod';
import {RecordWrites} from './record-writes.js';

const keyOf = (session: string, call: string) => Buffer.from(JSON.stringify([session, call])).toString('base64url');

type ToolView = {callId: string; call?: ToolCallView; result?: ToolResultView; childSessionId?: string; delegationKind?: string};
interface ToolViewDomain extends DomainSpec {tables: {calls: DomainTableSpec<string, ToolView>}}
export const toolViewsDomain: ToolViewDomain = defineDomain({name:'nano_tool_views',version:1,layout:'per-record',tables:{calls:domainTable(z.object({callId:z.string(),call:z.any().optional(),result:z.any().optional(),childSessionId:z.string().optional(),delegationKind:z.string().optional()}))}});

/** Freeze public presenter output in a Nano domain; native logs accept no external event vocabulary. */
export function recordToolPresentations(ctx: Context, home: string) {
  const root = join(home, 'storages');
  const calls = join(root, toolViewsDomain.name, 'calls');
  const backend = new JsonStorageBackend(root);
  const unit = backend.kv.open(descriptorOf(toolViewsDomain));
  const writes = new RecordWrites<ToolView>(async (key, snapshot) => {
    await (await unit).putRecord('calls', key, snapshot);
  });
  ctx.effect(() => async () => {
    await writes.settled();
    await backend.close();
  });
  ctx.on('agent/pre-step', async ({agent, step, signal}, next) => {
    const decision = await next();
    // A new turn can recover prior snapshots before its first model or tool call.
    if (decision.kind !== 'reject' && !signal.aborted && step === 1
      && writes.busy && agent.session.header.agentPreset?.startsWith('nano:')) await writes.flush();
    return decision;
  }, {prepend: true});
  ctx.on('tools/pre-execute', async (exec, next) => {
    if (exec.agent?.session.header.agentPreset?.startsWith('nano:')) {
      const call = ctx.tools.get(exec.name, exec.agent)?.presentCall?.(exec.arguments);
      if (call) {
        const key = keyOf(exec.agent.id, exec.callId);
        const snapshot = JSON.parse(JSON.stringify({callId: exec.callId, call}));
        await writes.put(key, snapshot);
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
      void writes.put(key, snapshot);
    }
  });
  const one = async (sessionId: string, event: SessionEvent): Promise<SessionEvent> => {
    if (event.type !== 'tool/result' && event.type !== 'tool/call') return event;
    await writes.wait();
    const callId = event.type === 'tool/call' ? event.data.callId : event.data.message.toolCallId;
    const path = join(calls, keyOf(sessionId, callId) + '.json');
    // The pinned public JSON backend has atomic per-record writes but no point read.
    const file = await readFile(path, 'utf8').catch(error => {
      if (error.code !== 'ENOENT') throw error;
    });
    if (file === undefined) return event;
    const {version, record} = JSON.parse(file) as {version: number; record: ToolView};
    if (version !== toolViewsDomain.version || record?.callId !== callId)
      throw new Error('Tool presentation record does not match its session call');
    if (event.type === 'tool/call') return {...event, data:{...event.data, nanoToolView:record}} as SessionEvent;
    return {...event, data:{...event.data, nanoToolView:record}} as SessionEvent;
  };
  const read = async (sessionId: string, events: readonly SessionEvent[]) => {
    await writes.wait();
    const result: SessionEvent[] = [];
    for (const event of events) result.push(await one(sessionId, event));
    return result;
  };
  const owner = (key: string): unknown => JSON.parse(Buffer.from(key, 'base64url').toString())[0];
  const purge = async (ids: ReadonlySet<string>) => {
    await writes.forget(key => ids.has(owner(key) as string));
    const physical = await realpath(calls).catch(error => {
      if (error.code !== 'ENOENT') throw error;
    });
    if (!physical) return;
    if (physical !== join(await realpath(home), 'storages', toolViewsDomain.name, 'calls'))
      throw new Error('Tool presentations are outside the supported storage layout');
    const directory = await opendir(calls);
    for await (const entry of directory) {
      const key = /^([a-zA-Z0-9_-]+)\.json$/.exec(entry.name)?.[1];
      if (!key || !ids.has(owner(key) as string)) continue;
      if (!entry.isFile()) throw new Error('Unexpected tool presentation file type');
      await (await unit).deleteRecord('calls', key);
    }
  };
  return Object.assign(read, {one, purge});
}
