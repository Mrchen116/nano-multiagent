export interface HeartbeatSettings { every?: string; active_hours?: { start?: string; end?: string; timezone?: string } }
export interface HeartbeatTask { name: string; prompt: string; interval?: number; at?: number; cron?: string }
export function intervalMilliseconds(value: string): number {
  const match = /^\s*(\d+)\s*([smhd])\s*$/i.exec(value);
  if (!match || Number(match[1]) < 1) throw new Error(`Invalid heartbeat interval: ${value}`);
  return Number(match[1]) * ({ s: 1000, m: 60000, h: 3600000, d: 86400000 }[match[2]!.toLowerCase()]!);
}
/** File content supplies tasks; top-level every/interval never overrides configuration. */
export function heartbeatTasks(content: string, settings: HeartbeatSettings): HeartbeatTask[] {
  const tasks: HeartbeatTask[] = [];
  const block = /(?:^|\n)tasks:\s*\n((?:[ \t].*(?:\n|$)|\s*\n)*)/.exec(content)?.[1];
  if (block) for (const task of block.split(/\n?\s*- name:/).slice(1)) {
    const name = task.split('\n')[0]!.trim().replace(/^['"]|['"]$/g, '');
    const interval = /^\s*interval:\s*(.+)$/m.exec(task)?.[1]?.trim().replace(/^['"]|['"]$/g, '');
    const prompt = /^\s*prompt:\s*(.+)$/m.exec(task)?.[1]?.trim().replace(/^['"]|['"]$/g, '');
    if (name && interval && prompt) tasks.push({ name, prompt, interval: intervalMilliseconds(interval) });
  }
  if (tasks.length) return tasks;
  let at: number | undefined; let cron: string | undefined;
  const lines: string[] = [];
  for (const raw of content.split('\n')) {
    const line = raw.trim();
    if (!line || /^#|^<!--.*-->$|^```\w*$|^(---|\*\*\*)$|^[-*+]\s*(\[[ xX]?\]\s*)?$/.test(line)) continue;
    if (/^(every|interval):/i.test(line) || line === 'tasks:') continue;
    if (/^at:/i.test(line)) { if (at !== undefined || cron !== undefined) throw new Error('Conflicting heartbeat schedules'); at = Date.parse(line.slice(3).trim()); if (!Number.isFinite(at)) throw new Error('Invalid heartbeat at time'); continue; }
    if (/^cron:/i.test(line)) { if (at !== undefined || cron !== undefined) throw new Error('Conflicting heartbeat schedules'); cron = line.slice(5).trim(); continue; }
    lines.push(line);
  }
  return lines.length ? [{ name: 'default', prompt: lines.join('\n'), ...(at === undefined && !cron ? { interval: intervalMilliseconds(settings.every ?? '30m') } : { at, cron }) }] : [];
}
export function withinActiveHours(now: number, settings: HeartbeatSettings): boolean {
  const hours = settings.active_hours;
  if (!hours?.start || !hours.end) return true;
  const clock = new Intl.DateTimeFormat('en-GB', { timeZone: hours.timezone ?? 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(now));
  return hours.start <= hours.end ? hours.start <= clock && clock < hours.end : hours.start <= clock || clock < hours.end;
}
/** One due boundary per task; skipped intervals are never backfilled. */
export function heartbeatDue(task: HeartbeatTask, last: number | undefined, now: number): number | undefined {
  if (task.at !== undefined) return task.at <= now && (last === undefined || last < task.at) ? task.at : undefined;
  if (task.cron) {
    const due = Math.floor(now / 60000) * 60000;
    return due !== last && cronMatches(task.cron, new Date(due)) ? due : undefined;
  }
  const interval = task.interval!;
  const due = last === undefined ? Math.floor(now / interval) * interval : last + Math.floor((now - last) / interval) * interval;
  return due <= now && (last === undefined || due > last) ? due : undefined;
}
function cronMatches(expression: string, time: Date): boolean {
  const fields = expression.split(/\s+/);
  if (fields.length !== 5) throw new Error('Heartbeat cron requires five fields');
  const values = [time.getUTCMinutes(), time.getUTCHours(), time.getUTCDate(), time.getUTCMonth() + 1, time.getUTCDay()];
  const bounds = [[0, 59], [0, 23], [1, 31], [1, 12], [0, 6]];
  return fields.every((field, index) => field.split(',').some(part => {
    if (index === 4) part = part.replace(/sun|mon|tue|wed|thu|fri|sat/gi, day => String(['sun','mon','tue','wed','thu','fri','sat'].indexOf(day.toLowerCase())));
    const [range, rawStep] = part.split('/'); const step = rawStep === undefined ? 1 : Number(rawStep);
    const [min, max] = bounds[index]!;
    const [start, end] = range === '*' ? [min!, max!] : range!.includes('-') ? range!.split('-').map(Number) : [Number(range), Number(range)];
    if (!Number.isInteger(step) || step < 1 || !Number.isInteger(start) || !Number.isInteger(end) || start! < min! || end! > max! || start! > end!) throw new Error('Invalid heartbeat cron field');
    return start! <= values[index]! && values[index]! <= end! && (values[index]! - start!) % step === 0;
  }));
}
