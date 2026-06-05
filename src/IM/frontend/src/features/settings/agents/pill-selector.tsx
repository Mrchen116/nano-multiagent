import * as Label from "@radix-ui/react-label";

// M19/R11-3: prototype `im-components.jsx::MultiSelect` 视觉重写 —
// 全部 options 平铺 pill (不是 picker / 浮层 / checkbox grid),每项 <button>
// + aria-pressed 反映选中态。选中态 oklch teal,未选 oklch 灰底。
// 替换 `allowlist-selector.tsx` 的 fieldset+checkbox grid (R11 reviewer 标
// "60+ 列 checkbox,违反 §95 视觉对齐")。

export type PillOption = {
  name: string;
  description?: string;
  // feat-394 M9 R6: default_on=true → pill renders as selected when tool_allowlist is empty
  // (empty allowlist means "use product defaults", so default tools appear as selected).
  default_on?: boolean;
};

type PillSelectorProps = {
  testId: string;
  label: string;
  selected: string[];
  options: PillOption[];
  isLoading?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  onChange: (next: string[]) => void;
  // When true, empty selected list uses each option's default_on to determine display state.
  useDefaultOn?: boolean;
};

export function PillSelector({
  testId,
  label,
  selected,
  options,
  isLoading = false,
  errorMessage = null,
  onRetry,
  onChange,
  useDefaultOn = false,
}: PillSelectorProps) {
  // feat-394 M9 R6: when useDefaultOn is active and selected is empty, treat each
  // option's default_on as its effective selection state (empty allowlist = defaults).
  const emptyMeansDefault = useDefaultOn && selected.length === 0;

  function isSelected(opt: PillOption): boolean {
    if (emptyMeansDefault) {
      return opt.default_on === true;
    }
    return selected.includes(opt.name);
  }

  function toggle(name: string) {
    if (emptyMeansDefault) {
      // Materialise the defaults into an explicit list, then toggle the clicked item.
      const currentEffective = options
        .filter((o) => o.default_on === true)
        .map((o) => o.name);
      const isOn = currentEffective.includes(name);
      const next = isOn ? currentEffective.filter((n) => n !== name) : [...currentEffective, name];
      onChange(next);
    } else {
      const isOn = selected.includes(name);
      onChange(isOn ? selected.filter((n) => n !== name) : [...selected, name]);
    }
  }

  return (
    <div className="im-agent-field">
      <Label.Root>{label}</Label.Root>
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
