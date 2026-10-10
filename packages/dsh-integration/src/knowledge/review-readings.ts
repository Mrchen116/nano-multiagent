import type { Agent } from '@deepseek-ai/dsh-agent';
import type { KnowledgeKind } from './state.js';

/** Count model iterations, with successful foreground maintenance as a reset point. */
export function reviewReadings(events: ReturnType<Agent['session']['snapshotEvents']>, kind: KnowledgeKind) {
  let current = 0; let maintained = 0;
  const calls = new Set<string>();
  for (const event of events) {
    if (event.type === (kind === 'memory' ? 'turn/start' : 'step/start')) current++;
    if (event.type === 'tool/call' && event.data.name === (kind === 'memory' ? 'memory' : 'skill_manage')) calls.add(event.data.callId);
    if (event.type === 'tool/result' && calls.has(event.data.message.toolCallId) && !event.data.message.isError) maintained = current;
  }
  return { current, maintained };
}
