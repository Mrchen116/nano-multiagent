import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

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

function optionDescriptionText(raw: string | undefined) {
  const t = (raw ?? "").trim();
  if (!t) {
    return { hoverFull: "", display: "No description provided." };
  }
  return {
    hoverFull: t,
    display: t.replace(/\r?\n/g, " ").replace(/\s+/g, " ").trim()
  };
}

/** 悬停全文浮层：原生 title 延迟长且长文本常被系统截断，故用 portal + fixed。 */
function OptionCard(props: {
  option: ResolvedAllowlistOption;
  checked: boolean;
  showDescriptions: boolean;
  onToggle: (name: string) => void;
}) {
  const { hoverFull, display } = optionDescriptionText(props.option.description);
  const hasHoverPanel = Boolean(hoverFull) && display !== "No description provided.";
  const [tipOpen, setTipOpen] = useState(false);
  const [tipPos, setTipPos] = useState<{ top: number; left: number; maxW: number }>({ top: 0, left: 0, maxW: 360 });
  const hoverCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const descWrapRef = useRef<HTMLDivElement | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);

  function clearCloseTimer() {
    if (hoverCloseTimer.current !== null) {
      clearTimeout(hoverCloseTimer.current);
      hoverCloseTimer.current = null;
    }
  }

  function openTip(anchor: HTMLElement) {
    clearCloseTimer();
    const r = anchor.getBoundingClientRect();
    const margin = 8;
    const maxW = Math.min(420, Math.max(240, window.innerWidth - margin * 2));
    let left = r.left;
    if (left + maxW > window.innerWidth - margin) {
      left = Math.max(margin, window.innerWidth - margin - maxW);
    }
    // 与描述区重叠一块命中区，且用 relatedTarget 判断，避免移到 portal 浮层时被误关
    const top = r.bottom - 14;
    setTipPos({ top, left, maxW });
    setTipOpen(true);
  }

  function scheduleClose() {
    clearCloseTimer();
    hoverCloseTimer.current = setTimeout(() => setTipOpen(false), 320);
  }

  function isWithinTipOrDesc(node: EventTarget | null) {
    if (!node || !(node instanceof Node)) {
      return false;
    }
    return Boolean(descWrapRef.current?.contains(node) || tipRef.current?.contains(node));
  }

  function handleDescLeave(e: React.MouseEvent) {
    if (isWithinTipOrDesc(e.relatedTarget)) {
      return;
    }
    scheduleClose();
  }

  function handleTipLeave(e: React.MouseEvent) {
    if (isWithinTipOrDesc(e.relatedTarget)) {
      return;
    }
    scheduleClose();
  }

  useEffect(() => () => clearCloseTimer(), []);

  return (
    <label
      className={`grid min-w-0 cursor-pointer gap-2 rounded-2xl border px-3 py-3 transition-colors ${
        props.checked ? "border-teal-300 bg-teal-50/60 shadow-sm" : "border-[var(--im-border)] bg-white/90 hover:border-slate-300"
      }`}
    >
      <div className="flex min-w-0 items-start gap-3">
        <input checked={props.checked} type="checkbox" onChange={() => props.onToggle(props.option.name)} />
        <div className="grid min-w-0 flex-1 gap-1 overflow-hidden">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="min-w-0 truncate text-sm font-semibold text-slate-900">{props.option.name}</span>
            {props.option.unavailable ? (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">Unavailable now</span>
            ) : null}
          </div>
          {props.showDescriptions || props.option.unavailable ? (
            <div
              ref={descWrapRef}
              className="relative min-w-0"
              onMouseEnter={(e) => {
                if (!hasHoverPanel) {
                  return;
                }
                openTip(e.currentTarget.querySelector("[data-desc-line]") ?? e.currentTarget);
              }}
              onMouseLeave={handleDescLeave}
            >
              <p
                data-desc-line
                className="block min-w-0 max-w-full cursor-default overflow-hidden text-ellipsis whitespace-nowrap text-xs leading-5 text-slate-500"
              >
                {display}
              </p>
            </div>
          ) : null}
        </div>
      </div>
      {tipOpen && hasHoverPanel
        ? createPortal(
            <div
              ref={tipRef}
              role="tooltip"
              className="fixed z-[99999] rounded-lg border border-slate-600/80 bg-slate-900 px-3 pb-2 pt-2 text-xs leading-relaxed text-slate-100 shadow-xl"
              style={{
                top: tipPos.top,
                left: tipPos.left,
                maxWidth: tipPos.maxW
              }}
              onMouseEnter={clearCloseTimer}
              onMouseLeave={handleTipLeave}
            >
              <p className="m-0 max-h-[min(70vh,28rem)] overflow-y-auto whitespace-pre-wrap break-words">{hoverFull}</p>
            </div>,
            document.body
          )
        : null}
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
    <fieldset className="im-allowlist-fieldset grid min-w-0 w-full gap-4 rounded-[1.25rem] border border-[var(--im-border)] bg-white/80 p-4">
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
          <div className="grid min-w-0 gap-2 xl:grid-cols-2 xl:[grid-template-columns:minmax(0,1fr)_minmax(0,1fr)]">
            {resolvedOptions.map((option) => (
              <div key={option.name} className="min-w-0">
                <OptionCard
                  option={option}
                  checked={normalizedSelected.includes(option.name)}
                  showDescriptions={showDescriptions}
                  onToggle={toggleOption}
                />
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500">{emptySelectionText}</p>
        )
      ) : null}
    </fieldset>
  );
}
