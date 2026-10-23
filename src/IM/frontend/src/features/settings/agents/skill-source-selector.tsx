import * as Label from "@radix-ui/react-label";

import { useTranslation } from "../../../i18n";
import { AgentAllowlistOption } from "./im-agent-config-api";

type SelectionMode = "default_discovery" | "explicit_allowlist" | "explicit_denylist";
type SourceKey = "workspace" | "global" | "compatibility";

function normalizePath(value: string | null | undefined) {
  return (value ?? "").replace(/\\/g, "/").replace(/\/+$/, "");
}

function skillSourceKey(option: AgentAllowlistOption, workspaceRoot: string): SourceKey {
  if (option.source_group) return option.source_group;
  const location = normalizePath(option.location);
  const root = normalizePath(workspaceRoot);
  if (root && location.startsWith(`${root}/`)) return "workspace";
  if (option.default_on === true || location.includes("/.nanoassistant/skills/")) return "global";
  return "compatibility";
}

interface SkillSourceSelectorProps {
  testId: string;
  label: string;
  selected: string[];
  selectionMode: SelectionMode;
  options: AgentAllowlistOption[];
  workspaceRoot?: string | null;
  readOnly?: boolean;
  isLoading?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  onChange: (next: string[], mode: "explicit_denylist") => void;
}

export function SkillSourceSelector({
  testId,
  label,
  selected,
  selectionMode,
  options,
  workspaceRoot = "",
  isLoading = false,
  readOnly = false,
  errorMessage = null,
  onRetry,
  onChange
}: SkillSourceSelectorProps) {
  const { t } = useTranslation();
  const groups = [
    { key: "workspace" as const, label: t("agents.form.access.skillsLocal") },
    { key: "global" as const, label: t("agents.form.access.skillsGlobal") },
    { key: "compatibility" as const, label: t("agents.form.access.skillsCompatibility") },
  ].map((group) => ({
    ...group,
    options: options.filter((option) => skillSourceKey(option, workspaceRoot ?? "") === group.key),
  })).filter((group) => group.options.length > 0);

  const disabled = selectionMode === "explicit_denylist" ? selected
    : selectionMode === "explicit_allowlist" ? options.map(option => option.name).filter(name => !selected.includes(name)) : [];
  const effectiveSelected = options.map(option => option.name).filter(name => !disabled.includes(name));

  function toggle(name: string) {
    onChange(disabled.includes(name) ? disabled.filter(item => item !== name) : [...disabled, name], "explicit_denylist");
  }

  function toggleGroup(names: string[], allSelected: boolean) {
    const groupNames = new Set(names);
    onChange(allSelected ? Array.from(new Set([...disabled, ...names])) : disabled.filter(name => !groupNames.has(name)), "explicit_denylist");
  }

  return (
    <div className="im-agent-field">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Label.Root>{label}</Label.Root>
        <span className="text-[11px] text-slate-500" data-testid={`${testId}-mode`}>
          {selectionMode === "default_discovery"
            ? t("agents.form.access.skillsDefaultDiscovery")
            : t("agents.form.access.skillsExplicitCount", { count: effectiveSelected.length })}
        </span>
      </div>
      <p className="text-[11px] text-slate-500">{t("agents.form.access.skillsNewDefault")}</p>
      {isLoading && options.length === 0 ? (
        <p className="text-sm text-slate-500">...</p>
      ) : errorMessage ? (
        <div className="grid gap-2">
          <p className="text-sm text-rose-600">{errorMessage}</p>
          {onRetry ? (
            <button type="button" className="im-btn im-btn-muted w-fit" onClick={onRetry}>Retry</button>
          ) : null}
        </div>
      ) : groups.length === 0 ? (
        <p className="text-sm text-slate-500">-</p>
      ) : (
        <div data-testid={testId} className="grid gap-3" role="group" aria-label={label}>
          {groups.map((group) => {
            const selectedCount = group.options.filter((option) => effectiveSelected.includes(option.name)).length;
            const allSelected = selectedCount === group.options.length;
            const partiallySelected = selectedCount > 0 && !allSelected;
            const actionLabel = allSelected
              ? t("agents.form.access.skillsGroupClear")
              : partiallySelected
                ? t("agents.form.access.skillsGroupComplete")
                : t("agents.form.access.skillsGroupSelect");
            return (
              <div key={group.key} className="grid gap-[6px]">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                  <div className="flex items-baseline gap-2 text-[11px] text-slate-500">
                    <span className="font-semibold uppercase tracking-[0.08em]">{group.label}</span>
                    <span className="font-mono">{selectedCount}/{group.options.length}</span>
                  </div>
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={partiallySelected ? "mixed" : allSelected}
                    aria-label={`${group.label}: ${selectedCount}/${group.options.length}, ${actionLabel}`}
                    disabled={readOnly}
                    data-skill-group={group.key}
                    data-state={allSelected ? "all" : partiallySelected ? "partial" : "none"}
                    onClick={() => toggleGroup(group.options.map((option) => option.name), allSelected)}
                    className="inline-flex min-h-[25px] items-center gap-1.5 rounded-md px-1.5 py-0.5 text-[11px] font-semibold text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  >
                    <span
                      aria-hidden="true"
                      className={
                        "grid h-[15px] w-[15px] place-items-center rounded border text-[10px] leading-none " +
                        (selectedCount > 0
                          ? "border-teal-600 bg-teal-600 text-white"
                          : "border-slate-400 bg-white")
                      }
                    >
                      {allSelected ? "✓" : partiallySelected ? "−" : ""}
                    </span>
                    <span aria-hidden="true">{actionLabel}</span>
                  </button>
                </div>
                <div className="flex flex-wrap gap-[6px]">
                  {group.options.map((opt) => {
                    const isOn = effectiveSelected.includes(opt.name);
                    return (
                      <button
                        key={`${group.key}:${opt.location ?? opt.name}`}
                        type="button"
                        disabled={readOnly}
                        data-pill-name={opt.name}
                        aria-pressed={isOn}
                        title={opt.description || opt.location || opt.name}
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
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
