import * as Label from "@radix-ui/react-label";

import { useTranslation } from "../../../i18n";
import { AgentAllowlistOption } from "./im-agent-config-api";

function normalizePath(value: string | null | undefined) {
  return (value ?? "").replace(/\\/g, "/").replace(/\/+$/, "");
}

function skillSourceKey(option: AgentAllowlistOption, workspaceRoot: string): "global" | "local" | "other" {
  const location = normalizePath(option.location);
  const root = normalizePath(workspaceRoot);
  if (location && root && location.startsWith(`${root}/.nanoassistant/skills/`)) {
    return "local";
  }
  if (option.default_on === true || location.includes("/.nanoassistant/skills/")) {
    return "global";
  }
  return "other";
}

interface SkillSourceSelectorProps {
  testId: string;
  label: string;
  selected: string[];
  options: AgentAllowlistOption[];
  workspaceRoot?: string | null;
  isLoading?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  onChange: (next: string[]) => void;
}

export function SkillSourceSelector({
  testId,
  label,
  selected,
  options,
  workspaceRoot = "",
  isLoading = false,
  errorMessage = null,
  onRetry,
  onChange
}: SkillSourceSelectorProps) {
  const { t } = useTranslation();
  const groups = [
    {
      key: "global",
      label: t("agents.form.access.skillsGlobal"),
      options: options.filter((option) => skillSourceKey(option, workspaceRoot ?? "") === "global")
    },
    {
      key: "local",
      label: t("agents.form.access.skillsLocal"),
      options: options.filter((option) => skillSourceKey(option, workspaceRoot ?? "") === "local")
    },
    {
      key: "other",
      label: t("agents.form.access.skillsCompatibility"),
      options: options.filter((option) => skillSourceKey(option, workspaceRoot ?? "") === "other")
    }
  ].filter((group) => group.options.length > 0);

  function toggle(name: string) {
    const isOn = selected.includes(name);
    onChange(isOn ? selected.filter((item) => item !== name) : [...selected, name]);
  }

  return (
    <div className="im-agent-field">
      <Label.Root>{label}</Label.Root>
      {isLoading && options.length === 0 ? (
        <p className="text-sm text-slate-500">...</p>
      ) : errorMessage ? (
        <div className="grid gap-2">
          <p className="text-sm text-rose-600">{errorMessage}</p>
          {onRetry ? (
            <button type="button" className="im-btn im-btn-muted w-fit" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      ) : groups.length === 0 ? (
        <p className="text-sm text-slate-500">-</p>
      ) : (
        <div data-testid={testId} className="grid gap-3" role="group" aria-label={label}>
          {groups.map((group) => (
            <div key={group.key} className="grid gap-[6px]">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                {group.label}
              </div>
              <div className="flex flex-wrap gap-[6px]">
                {group.options.map((opt) => {
                  const isOn = selected.includes(opt.name);
                  return (
                    <button
                      key={`${group.key}:${opt.location ?? opt.name}`}
                      type="button"
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
          ))}
        </div>
      )}
    </div>
  );
}
