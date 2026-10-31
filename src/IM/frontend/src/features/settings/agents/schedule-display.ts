import type { TFunction } from "i18next";

/** Describe a saved plan; active overdue entries still need delivery. */
export function formatSchedule(schedule: Record<string, unknown>, language: string, t: TFunction): { rule: string; next: string } {
  const key = "agents.form.cron.";
  let rule = t(`${key}once`);
  if (schedule.kind === "every") {
    const seconds = Number(schedule.everySeconds);
    const [divisor, unit] = seconds % 86400 === 0 ? [86400, "day"] : seconds % 3600 === 0 ? [3600, "hour"] : seconds % 60 === 0 ? [60, "minute"] : [1, "second"];
    rule = t(`${key}every`, { interval: new Intl.NumberFormat(language, { style: "unit", unit: String(unit), unitDisplay: "long" }).format(seconds / Number(divisor)) });
  } else if (schedule.kind === "daily" || schedule.kind === "weekly") {
    const time = String(schedule.time).replace(/:00\.000$/, "").replace(/\.000$/, "");
    const days = schedule.kind === "weekly" ? new Intl.ListFormat(language).format((schedule.weekdays as number[]).map(day =>
      new Intl.DateTimeFormat(language, { weekday: "short", timeZone: "UTC" }).format(new Date(Date.UTC(2024, 0, day))))) : "";
    rule = t(`${key}${schedule.kind}`, { days, time, zone: schedule.timeZone });
  } else if (schedule.kind === "cron") {
    rule = t(`${key}custom`);
  }
  const date = new Date(String(schedule.scheduledAt));
  const next = Number.isNaN(date.getTime()) ? t(`${key}unknownTime`) : new Intl.DateTimeFormat(language, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short",
  }).format(date);
  return { rule, next };
}
