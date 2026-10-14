/** Validate a system timezone reported by a foreground client.
 *
 * Args:
 *   value: IANA timezone identifier.
 * Returns:
 *   The accepted identifier.
 * Raises:
 *   RangeError: The value is not a supported timezone.
 */
export function validateTimeZone(value: unknown): string {
  if (typeof value !== 'string' || !value || value.length > 128) throw new RangeError('Invalid timezone');
  new Intl.DateTimeFormat('en', { timeZone: value });
  return value;
}

/** Render an instant in the user's timezone with an explicit UTC offset.
 *
 * Args:
 *   instant: An ISO timestamp or epoch milliseconds.
 *   timeZone: Captured user timezone; absent retains UTC without guessing.
 * Returns:
 *   An ISO timestamp with seconds and an offset, or UTC when the timezone is unknown.
 */
export function formatLocalTime(instant: string | number, timeZone?: string): string {
  const date = new Date(instant);
  if (!timeZone) return typeof instant === 'string' ? instant : date.toISOString();
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(date);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  const { year, month, day, hour, minute, second } = values;
  const offset = Math.round((Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)) - Math.floor(date.getTime() / 1000) * 1000) / 60000);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${offset < 0 ? '-' : '+'}${pad(Math.floor(Math.abs(offset) / 60))}:${pad(Math.abs(offset) % 60)}`;
}
