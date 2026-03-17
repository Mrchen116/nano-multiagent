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

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function mergeOptions(selected: string[], options?: AgentAllowlistOption[]) {
  const normalizedSelected = normalizeAllowlist(selected);
  const merged: ResolvedAllowlistOption[] = [...(options ?? [])];
  const knownNames = new Set(merged.map((option) => option.name));

  for (const name of normalizedSelected) {
    if (!knownNames.has(name)) {
      merged.push({
        name,
        description: "Saved on this agent but not currently available from the running system.",
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
        <div className="grid min-w-0 gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">{props.option.name}</span>
            {props.option.unavailable ? (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">Unavailable now</span>
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

      <p id={`${id}-help`} className="max-w-2xl text-xs leading-5 text-slate-500">
        {helpText}
      </p>

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
          <div className="grid gap-2 xl:grid-cols-2">
            {resolvedOptions.map((option) => (
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
          <p className="text-xs text-slate-500">{emptySelectionText}</p>
        )
      ) : null}
    </fieldset>
  );
}
