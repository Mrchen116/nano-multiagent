import { useMemo } from "react";

import { AgentAllowlistOption } from "./im-agent-config-api";

type ResolvedAllowlistOption = AgentAllowlistOption & {
  unavailable?: boolean;
};

interface AllowlistSelectorProps {
  id: string;
  label: string;
  selected: string[];
  options?: AgentAllowlistOption[];
  helpText: string;
  emptySelectionText: string;
  isLoading?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  showDescriptions?: boolean;
  onChange: (next: string[]) => void;
}

const ADVANCED_OPTION_PATTERNS = [
  /acceptance/i,
  /orchestrator/i,
  /worker/i,
  /playwright/i,
  /project-lead/i,
  /review-pr/i,
  /^bash$/i,
  /^task$/i
];

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function isAdvancedOption(option: AgentAllowlistOption) {
  return ADVANCED_OPTION_PATTERNS.some((pattern) => pattern.test(option.name));
}

function mergeOptions(selected: string[], options?: AgentAllowlistOption[]) {
  const normalizedSelected = normalizeAllowlist(selected);
  const merged: ResolvedAllowlistOption[] = [...(options ?? [])];
  const knownNames = new Set(merged.map((option) => option.name));

  for (const name of normalizedSelected) {
    if (!knownNames.has(name)) {
      merged.push({
        name,
        description: "Currently saved on this agent, but not available from the running system.",
        unavailable: true
      });
    }
  }

  return merged;
}

function OptionCard(props: {
  option: ResolvedAllowlistOption;
  checked: boolean;
  showDescriptions: boolean;
  onToggle: (name: string) => void;
}) {
  return (
    <label
      className={`grid cursor-pointer gap-2 rounded-2xl border px-3 py-3 transition-colors ${
        props.checked ? "border-teal-300 bg-teal-50/60 shadow-sm" : "border-[var(--im-border)] bg-white/90 hover:border-slate-300"
      }`}
    >
      <div className="flex items-start gap-3">
        <input checked={props.checked} type="checkbox" onChange={() => props.onToggle(props.option.name)} />
        <div className="grid gap-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">{props.option.name}</span>
            {props.option.unavailable ? (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">Unavailable now</span>
            ) : null}
            {!props.option.unavailable && isAdvancedOption(props.option) ? (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">Advanced</span>
            ) : null}
          </div>
          {props.showDescriptions || props.option.unavailable ? (
            <p className="text-xs leading-5 text-slate-500">{props.option.description || "No description provided."}</p>
          ) : null}
        </div>
      </div>
    </label>
  );
}

export function AllowlistSelector({
  id,
  label,
  selected,
  options,
  helpText,
  emptySelectionText,
  isLoading = false,
  errorMessage,
  onRetry,
  showDescriptions = true,
  onChange
}: AllowlistSelectorProps) {
  const normalizedSelected = useMemo(() => normalizeAllowlist(selected), [selected]);
  const resolvedOptions = useMemo(() => mergeOptions(normalizedSelected, options), [normalizedSelected, options]);
  const productOptions = useMemo(
    () => resolvedOptions.filter((option) => !isAdvancedOption(option) && !option.unavailable),
    [resolvedOptions]
  );
  const savedAdvancedOptions = useMemo(
    () =>
      resolvedOptions.filter(
        (option) => (isAdvancedOption(option) || option.unavailable) && normalizedSelected.includes(option.name)
      ),
    [normalizedSelected, resolvedOptions]
  );
  const hiddenAdvancedOptions = useMemo(
    () =>
      resolvedOptions.filter(
        (option) => isAdvancedOption(option) && !option.unavailable && !normalizedSelected.includes(option.name)
      ),
    [normalizedSelected, resolvedOptions]
  );

  function toggleOption(name: string) {
    if (normalizedSelected.includes(name)) {
      onChange(normalizedSelected.filter((item) => item !== name));
      return;
    }
    onChange([...normalizedSelected, name]);
  }

  return (
    <fieldset className="grid gap-4 rounded-[1.25rem] border border-[var(--im-border)] bg-white/80 p-4">
      <legend className="px-1 text-sm font-semibold text-slate-900">{label}</legend>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <p id={`${id}-help`} className="max-w-2xl text-xs leading-5 text-slate-500">
          {helpText}
        </p>
        <span className="im-badge">Selected {normalizedSelected.length}</span>
      </div>

      <div aria-live="polite" className="flex flex-wrap gap-2">
        {normalizedSelected.length > 0 ? (
          normalizedSelected.map((name) => (
            <button key={name} className="im-chip" type="button" onClick={() => toggleOption(name)}>
              <span>{name}</span>
              <span aria-hidden="true">×</span>
            </button>
          ))
        ) : (
          <p className="text-xs text-slate-500">{emptySelectionText}</p>
        )}
      </div>

      {isLoading ? <p className="text-xs text-slate-500">Loading available options…</p> : null}

      {!isLoading && errorMessage ? (
        <div className="grid gap-2 rounded-xl border border-rose-200 bg-rose-50/80 p-3 text-sm text-rose-700">
          <p className="font-semibold">Could not load selectable options.</p>
          <p className="text-xs text-rose-600">{errorMessage}</p>
          {onRetry ? (
            <button className="im-btn im-btn-muted w-fit" type="button" onClick={onRetry}>
              Retry options
            </button>
          ) : null}
        </div>
      ) : null}

      {!isLoading && !errorMessage ? (
        resolvedOptions.length > 0 ? (
          <div className="grid gap-4">
            <section className="grid gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">Common choices</p>
                <p className="text-xs text-slate-500">Start with the smallest safe set.</p>
              </div>
              {productOptions.length > 0 ? (
                <div className="grid gap-2 xl:grid-cols-2">
                  {productOptions.map((option) => (
                    <OptionCard
                      key={option.name}
                      option={option}
                      checked={normalizedSelected.includes(option.name)}
                      showDescriptions={showDescriptions}
                      onToggle={toggleOption}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">No product-ready options are currently available from the running system.</p>
              )}
            </section>

            {savedAdvancedOptions.length > 0 ? (
              <section className="grid gap-2 rounded-xl border border-amber-200 bg-amber-50/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-amber-900">Saved advanced selections</p>
                  <p className="text-xs text-amber-700">Visible because this agent already uses them.</p>
                </div>
                <div className="grid gap-2 xl:grid-cols-2">
                  {savedAdvancedOptions.map((option) => (
                    <OptionCard
                      key={option.name}
                      option={option}
                      checked={normalizedSelected.includes(option.name)}
                      showDescriptions={showDescriptions}
                      onToggle={toggleOption}
                    />
                  ))}
                </div>
              </section>
            ) : null}

            {hiddenAdvancedOptions.length > 0 ? (
              <details className="rounded-xl border border-[var(--im-border)] bg-slate-50/80 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                  Show advanced options ({hiddenAdvancedOptions.length} hidden)
                </summary>
                <p className="mt-2 text-xs text-slate-500">Only expand this when you intentionally need developer or orchestration capabilities.</p>
                <div className="mt-3 grid gap-2 xl:grid-cols-2">
                  {hiddenAdvancedOptions.map((option) => (
                    <OptionCard
                      key={option.name}
                      option={option}
                      checked={normalizedSelected.includes(option.name)}
                      showDescriptions={showDescriptions}
                      onToggle={toggleOption}
                    />
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        ) : (
          <p className="text-xs text-slate-500">No selectable options are currently available from the running system.</p>
        )
      ) : null}
    </fieldset>
  );
}
