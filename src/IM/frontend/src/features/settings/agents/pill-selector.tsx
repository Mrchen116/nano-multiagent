import * as Label from "@radix-ui/react-label";
import { useState, type ReactNode } from "react";

// M19/R11-3: prototype `im-components.jsx::MultiSelect` 视觉重写 —
// 全部 options 平铺 pill (不是 picker / 浮层 / checkbox grid),每项 <button>
// + aria-pressed 反映选中态。选中态 oklch teal,未选 oklch 灰底。
// 替换 `allowlist-selector.tsx` 的 fieldset+checkbox grid (R11 reviewer 标
// "60+ 列 checkbox,违反 §95 视觉对齐")。

export type PillOption = {
  name: string;
  description?: string;
  source_group?: string | null;
  enabled?: boolean | null;
  plugin_bundle?: string | null;
  plugin_title?: string | Record<string, string> | null;
};

type PillSelectorProps = {
  testId: string;
  label: string;
  labelAction?: ReactNode;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  countSummary?: (enabled: number, total: number) => string;
  selected: string[];
  fixed?: string[];
  options: PillOption[];
  readOnly?: boolean;
  isLoading?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  onChange: (next: string[]) => void;
  onToggleOption?: (option: PillOption, nextEnabled: boolean) => void;
};

export function PillSelector({
  testId,
  label,
  labelAction,
  collapsible = false,
  defaultExpanded = false,
  countSummary,
  selected,
  fixed = [],
  options,
  isLoading = false,
  readOnly = false,
  errorMessage = null,
  onRetry,
  onChange,
  onToggleOption,
}: PillSelectorProps) {
  const [expanded, setExpanded] = useState(() => (collapsible ? defaultExpanded : true));

  function isSelected(opt: PillOption): boolean {
    if (opt.source_group === "workspace") {
      return fixed.includes(opt.name) || opt.enabled === true;
    }
    return selected.includes(opt.name) || fixed.includes(opt.name);
  }

  const enabledCount = options.filter(isSelected).length;

  function toggle(opt: PillOption) {
    const isOn = isSelected(opt);
    if (onToggleOption) {
      onToggleOption(opt, !isOn);
      return;
    }
    if (opt.source_group === "workspace") return;
    onChange(isOn ? selected.filter((n) => n !== opt.name) : [...selected, opt.name]);
  }

  return (
    <div className="im-agent-field">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        {collapsible ? (
          <button
            type="button"
            data-testid={`${testId}-toggle`}
            aria-expanded={expanded}
            aria-controls={`${testId}-panel`}
            onClick={() => setExpanded((current) => !current)}
            className="inline-flex min-h-8 items-center gap-2 rounded px-1 py-0.5 text-left text-[13px] font-semibold text-slate-900 hover:text-[var(--im-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--im-accent)]"
          >
            <span aria-hidden="true" className="w-3 text-xs text-slate-500">
              {expanded ? "▾" : "▸"}
            </span>
            <span>{label}</span>
            <span
              data-testid={`${testId}-count`}
              className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-slate-600"
            >
              {countSummary ? countSummary(enabledCount, options.length) : `${enabledCount} / ${options.length}`}
            </span>
          </button>
        ) : (
          <Label.Root>{label}</Label.Root>
        )}
        {labelAction}
      </div>
      {isLoading && options.length === 0 ? (
        <p className="text-sm text-slate-500">…</p>
      ) : errorMessage ? (
        <div className="grid gap-2">
          <p className="text-sm text-rose-600">{errorMessage}</p>
          {onRetry ? (
            <button type="button" className="im-btn im-btn-muted w-fit" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      ) : expanded ? (
        <div
          id={`${testId}-panel`}
          data-testid={testId}
          className="flex flex-wrap gap-[6px]"
          role="group"
          aria-label={label}
        >
          {options.length === 0 ? (
            <p className="text-sm text-slate-500">—</p>
          ) : (
            options.map((opt) => {
              const isOn = isSelected(opt);
              return (
                <button
                  key={opt.name}
                  type="button"
                  data-pill-name={opt.name}
                  aria-pressed={isOn}
                  disabled={readOnly}
                  title={opt.description || opt.name}
                  onClick={() => toggle(opt)}
                  className={
                    "px-[11px] py-[4px] rounded-full text-[12px] font-semibold font-mono border transition-colors " +
                    (isOn
                      ? "bg-[oklch(0.93_0.08_180)] text-[oklch(0.35_0.14_180)] border-[oklch(0.75_0.12_180)]"
                      : "bg-[oklch(0.96_0.005_240)] text-[oklch(0.50_0.01_240)] border-[oklch(0.91_0.005_240)] hover:bg-[oklch(0.94_0.005_240)]")
                  }
                >
                  {opt.name}
                </button>
              );
            })
          )}
        </div>
      ) : null}

    </div>
  );
}
