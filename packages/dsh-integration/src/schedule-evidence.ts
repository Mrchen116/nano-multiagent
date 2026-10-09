import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { inputEvidence } from './input-evidence.js';

interface ScheduledInput { id: string; content: readonly { type: string; text?: string }[]; source?: { kind: string; scheduleId?: string; triggerKind?: string } }
/** Native source plus its public reminder framing preserves admission even before a timer receipt commits. */
export function scheduleEvidence(events: readonly SessionEvent[]) {
  const inputs = new Map<string, ScheduledInput>();
  for (const event of events) {
    const messages = event.type === 'agent/inbox/spliced' ? event.data.inserted : event.type === 'user/message' ? [event.data] : [];
    for (const message of messages) if (message.source?.kind === 'schedule') inputs.set(message.id, message as ScheduledInput);
  }
  return [...inputs.values()].flatMap(message => {
    const text = message.content.filter(part => part.type === 'text').map(part => part.text ?? '').join('');
    let reminders: { schedule_id: string; occurrence_at?: string }[] = [];
    if (message.source?.triggerKind === 'manual' && message.source.scheduleId) reminders = [{ schedule_id: message.source.scheduleId }];
    else if (text.startsWith('[SCHEDULE REMINDER]\n')) {
      const id = /^schedule_id_json: (.+)$/m.exec(text)?.[1];
      if (id) reminders = [{ schedule_id: JSON.parse(id) as string, occurrence_at: /^occurrence_at: (.+)$/m.exec(text)?.[1] }];
    } else if (text.startsWith('[SCHEDULE REMINDER BATCH]\n')) {
      const batch = /^reminders_json: (.+)$/m.exec(text)?.[1];
      if (batch) reminders = JSON.parse(batch) as typeof reminders;
    }
    return reminders.map(reminder => ({ messageId: message.id, scheduleId: reminder.schedule_id,
      scheduledAt: reminder.occurrence_at, trigger: message.source?.triggerKind === 'manual' ? 'manual' : 'timed', ...inputEvidence(events, message.id) }));
  });
}
