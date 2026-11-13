import { i18n } from "../../../i18n";

/** Translate work-view labels; model-authored text remains verbatim. */
export const tr = (label: string) => i18n.t(`agents.work.${label}`, { defaultValue: label });

export function formatWorkTokens(tokens: number) {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toLocaleString(i18n.language, {maximumFractionDigits: 2})}M`;
  if (tokens >= 1_000) return `${(tokens / 1_000).toLocaleString(i18n.language, {maximumFractionDigits: 2})}K`;
  return tokens.toLocaleString(i18n.language);
}

export function formatWorkDuration(ms: number) {
  const seconds = ms >= 1000;
  const value = seconds ? ms / 1000 : ms;
  if (i18n.language.startsWith("zh")) return seconds ? `${value.toFixed(2)} 秒` : `${value} 毫秒`;
  return value.toLocaleString(i18n.language, {
    style: "unit", unit: seconds ? "second" : "millisecond", unitDisplay: "long",
    minimumFractionDigits: seconds ? 2 : 0, maximumFractionDigits: seconds ? 2 : 0,
  });
}

export function WorkEventTime({ value }: { value: string }) {
  return <time className="im-work-event-time" dateTime={value}>{new Date(value).toLocaleTimeString(i18n.language, {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  })}</time>;
}
