import * as Label from "@radix-ui/react-label";
import type { ReactNode } from "react";

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
};

type PillSelectorProps = {
  testId: string;
  label: string;
  labelAction?: ReactNode;
  selected: string[];
  fixed?: string[];
  options: PillOption[];
  readOnly?: boolean;
  isLoading?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  onChange: (next: string[]) => void;
};

export function PillSelector({
  testId,
  label,
  labelAction,
  selected,
  fixed = [],
  options,
  isLoading = false,
  readOnly = false,
  errorMessage = null,
  onRetry,
  onChange,
}: PillSelectorProps) {
  const selectable = options.filter(opt => opt.source_group !== "workspace");
  function isSelected(opt: PillOption): boolean {
    return selected.includes(opt.name) || fixed.includes(opt.name);
  }

  function toggle(name: string) {
    const isOn = selected.includes(name) || fixed.includes(name);
    onChange(isOn ? selected.filter((n) => n !== name) : [...selected, name]);
  }

  return (
    <div className="im-agent-field">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <Label.Root>{label}</Label.Root>
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
      ) : (
        <div
          data-testid={testId}
          className="flex flex-wrap gap-[6px]"
          role="group"
          aria-label={label}
        >
          {selectable.length === 0 ? (
            <p className="text-sm text-slate-500">—</p>
          ) : (
            selectable.map((opt) => {
              const isOn = isSelected(opt);
              return (
                <button
                  key={opt.name}
                  type="button"
                  data-pill-name={opt.name}
                  aria-pressed={isOn}
                  disabled={readOnly}
                  title={opt.description || opt.name}
                  onClick={() => toggle(opt.name)}
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
      )}

    </div>
  );
}
