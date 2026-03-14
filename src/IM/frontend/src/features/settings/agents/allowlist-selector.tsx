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
        description: "Currently saved on this agent, but not available from the running system.",
        unavailable: true
      });
    }
  }

  return merged;
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
    <fieldset className="grid gap-3 rounded-2xl border border-[var(--im-border)] bg-slate-50/70 p-4">
      <legend className="px-1 text-sm font-semibold text-slate-900">{label}</legend>
      <p id={`${id}-help`} className="text-xs text-slate-500">
        {helpText}
      </p>

      <div aria-live="polite" className="flex flex-wrap gap-2">
        {normalizedSelected.length > 0 ? (
          normalizedSelected.map((name) => (
            <button
              key={name}
              className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-700"
              type="button"
              onClick={() => toggleOption(name)}
            >
              <span>{name}</span>
              <span className="text-[11px] font-medium text-teal-600">Remove</span>
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
          <div className="grid gap-2 md:grid-cols-2">
            {resolvedOptions.map((option) => {
              const checked = normalizedSelected.includes(option.name);
              return (
                <label
                  key={option.name}
                  className={`grid cursor-pointer gap-2 rounded-xl border px-3 py-3 ${checked ? "border-teal-300 bg-white shadow-sm" : "border-[var(--im-border)] bg-white/80"}`}
                >
                  <div className="flex items-start gap-3">
                    <input checked={checked} type="checkbox" onChange={() => toggleOption(option.name)} />
                    <div className="grid gap-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-slate-900">{option.name}</span>
                        {option.unavailable ? (
                          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">Unavailable now</span>
                        ) : null}
                      </div>
                      {showDescriptions || option.unavailable ? (
                        <p className="text-xs text-slate-500">{option.description || "No description provided."}</p>
                      ) : null}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-slate-500">No selectable options are currently available from the running system.</p>
        )
      ) : null}
    </fieldset>
  );
}
