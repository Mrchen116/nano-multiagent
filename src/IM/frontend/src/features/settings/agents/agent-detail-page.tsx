import { PersonalAgentSettings } from '../../personal-agent/personal-agent-settings';
import { ApprovalModeField, type ApprovalMode } from "./approval-mode-field";
import { tr } from "./agent-work-text";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Label from "@radix-ui/react-label";
import type { FocusEvent, FormEvent, MouseEvent, ReactNode } from "react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useIsMobile } from "../../../hooks/use-is-mobile";
import { useTranslation } from "../../../i18n";
import { createConversation } from "../../chat/chat-api";
import { Avatar, colorForAgent, initialsOf } from "../../chat/components/avatar";
import { AgentsRailDesktop } from "./agents-rail-desktop";
import {
  effectiveReasoningModel,
  isStaleReasoningEffort,
  ModelReasoningField,
  reasoningEffortAfterModelChange,
} from "./model-reasoning-field";
import { fallbacksAfterPrimaryChange, ModelFallbackField } from "./model-fallback-field";
import { AgentPluginsPanel } from "./agent-plugins-panel";
import { PillSelector } from "./pill-selector";
import { SkillSourceSelector } from "./skill-source-selector";
import { AgentWorkPanel } from "./agent-work-panel";
import { AgentChannelsPanel } from "./agent-channels-panel";
import { useAgentSettingsState } from "./use-agent-settings-state";
import { SettingsReadNotice } from "./settings-read-notice";
import {
  AgentAllowlistOption,
  AgentConfig,
  AgentFeature,
  CronJobSummary,
  ModelOption,
  SkillUsageItem,
  SkillsUsageResponse,
  type SettingsRead,
  getAgentConfigRequestDetail,
  getAgentConfigRequestStatus,
  getAgentHeartbeatMd,
  getAgentSettingsSection,
  AgentConfigRequestError,
  deleteAgentCronJob,
  promptPreview,
  isConfigApplyPendingError,
  updateAgentConfig
} from "./im-agent-config-api";

type AgentConfigFormState = AgentConfig;

function normalizeAllowlist(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function normalizeText(value: string) {
  return value.trim();
}

function normalizeAgentConfig(
  config: AgentConfigFormState,
): AgentConfigFormState {
  const defaultModel = normalizeText(config.default_model ?? "") || null;
  return {
    ...config,
    display_name: normalizeText(config.display_name),
    description: normalizeText(config.description),
    custom_prompt: (config.custom_prompt ?? "").trim(),
    features: config.features ?? {},
    skills: normalizeAllowlist(config.skills),
    tool_allowlist: normalizeAllowlist(config.tool_allowlist),
    default_model: defaultModel,
    model_fallbacks: fallbacksAfterPrimaryChange(config.model_fallbacks ?? [], defaultModel),
    reasoning_effort: config.reasoning_effort,
  };
}

// Presence, timestamps and server revisions never turn an untouched form into a draft.
function sameEditableConfig(a: AgentConfig, b: AgentConfig): boolean {
  const fields = (config: AgentConfig) => {
    const {node_id, node_name, node_status, updated_at, profile_version, ...editable} = normalizeAgentConfig(config);
    return editable;
  };
  return JSON.stringify(fields(a)) === JSON.stringify(fields(b));
}

function validateDraft(draft: AgentConfigFormState) {
  const errors: Partial<Record<"display_name", string>> = {};
  if (!draft.display_name) errors.display_name = "Display name is required.";
  return errors;
}

// feat-379-M3: resolve effective feature values from draft + capabilities defaults.
// Draft features take precedence; fall back to capability default_on when key absent.
function resolveEffectiveFeatures(
  draftFeatures: Record<string, boolean> | undefined,
  capabilityFeatures: AgentFeature[]
): Record<string, boolean> {
  const result: Record<string, boolean> = {};
  for (const feat of capabilityFeatures) {
    result[feat.key] = draftFeatures?.[feat.key] ?? feat.default_on;
  }
  return result;
}

function resolveModelOptions(modelOptions: ModelOption[] | undefined, currentModel: string | null, fallbacks: string[] = []): ModelOption[] {
  const resolved: ModelOption[] = [];
  const seen = new Set<string>();
  for (const option of modelOptions ?? []) {
    const name = option.name.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    resolved.push({ ...option, name });
  }
  // bugfix-429 R5: keep the agent's current model selectable even if it is no
  // longer advertised by the node (provider unknown → label degrades to name).
  for (const name of [currentModel, ...fallbacks]) {
    if (name && !seen.has(name)) { resolved.unshift({name, provider: ""}); seen.add(name); }
  }
  return resolved;
}

function formatUpdatedAt(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

// feat-379-M3: Behavior card — features checkbox group + custom_prompt textarea + collapsible preview.
// Uses the same checkbox idiom as allowlist-selector.tsx (appearance:none + :checked → --im-accent)
// and the same collapsible pattern as tool-calls-panel.tsx (aria-expanded + ▸/▾ + class toggle).
interface BehaviorCardProps {
  readOnly: boolean;
  unknownFeatures?: string[];
  capabilitiesKnown: boolean;
  agentId: string;
  draft: AgentConfigFormState;
  capabilityFeatures: AgentFeature[];
  onApprovalModeChange: (value: ApprovalMode) => void;
  onCustomPromptChange: (value: string) => void;
  onFeatureToggle: (key: string, value: boolean) => void;
  onPolicyChange: (value: string) => void;
}

function BehaviorCard({
  readOnly,
  unknownFeatures = [],
  capabilitiesKnown,
  agentId,
  draft,
  capabilityFeatures,
  onApprovalModeChange,
  onCustomPromptChange,
  onFeatureToggle,
  onPolicyChange
}: BehaviorCardProps) {
  const { t } = useTranslation();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewCapturedAt, setPreviewCapturedAt] = useState<string | null>(null);
  const [previewStale, setPreviewStale] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  // Debounce handle for preview re-fetch on change
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewAbort = useRef<AbortController | null>(null);
  useEffect(() => { if (readOnly) { previewAbort.current?.abort(); setPreviewLoading(false); setPreviewStale(true); } return () => previewAbort.current?.abort(); }, [readOnly]);

  const effectiveFeatures = useMemo(
    () => resolveEffectiveFeatures(draft.features, capabilityFeatures),
    [draft.features, capabilityFeatures]
  );

  // Fetch preview when opened or when draft changes while open.
  // feat-379-M9 (決策 14): tool_ids comes directly from draft.tool_allowlist; the old
  // effectiveToolIds hack that injected capability-inferred tools is removed because
  // _build_tool_names() now correctly includes all tools (R1 fix).
  const fetchPreview = useCallback(async () => {
    if (readOnly) return;
    previewAbort.current?.abort();
    const controller = new AbortController();
    previewAbort.current = controller;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const text = await promptPreview(agentId, {
        features: effectiveFeatures,
        custom_prompt: draft.custom_prompt ?? "",
        tool_ids: draft.tool_allowlist ?? [],
        ...(draft.work_mode === "global" ? { work_mode: "global" as const } : {}),
        skill_ids: draft.skills,
        skills_selection_mode: draft.skills_selection_mode
      }, controller.signal);
      if (!controller.signal.aborted) { setPreviewText(text); setPreviewCapturedAt(new Date().toISOString()); setPreviewStale(false); }
    } catch (err) {
      if (!controller.signal.aborted) { setPreviewError(err instanceof Error ? err.message : "Preview failed"); setPreviewStale(true); }
    } finally {
      setPreviewLoading(false);
    }
  }, [readOnly, agentId, effectiveFeatures, draft.custom_prompt, draft.work_mode, draft.tool_allowlist, draft.skills, draft.skills_selection_mode]);

  // Debounce preview re-fetch when draft changes while preview is open.
  useEffect(() => {
    if (!previewOpen || readOnly) return;
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => { void fetchPreview(); }, 600);
    return () => { if (previewTimer.current) clearTimeout(previewTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readOnly, previewOpen, draft.custom_prompt, draft.features, draft.work_mode, draft.tool_allowlist, draft.skills, draft.skills_selection_mode]);

  function handlePreviewToggle() {
    if (!previewOpen) {
      setPreviewOpen(true);
      void fetchPreview();
    } else {
      setPreviewOpen(false);
    }
  }

  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">{t("agents.form.behavior.title")}</h3>
        <p className="im-agent-card-sub">{t("agents.form.behavior.sub")}</p>
      </div>

      {/* Custom Instructions are the only public per-agent prompt input. */}
      <ApprovalModeField disabled={readOnly} value={draft.approval_mode} onChange={onApprovalModeChange} />

      <div className="im-agent-field">
        <Label.Root htmlFor="custom-instructions">{t("agents.form.behavior.customInstructions")}</Label.Root>
        <textarea
          disabled={readOnly}
          id="custom-instructions"
          className="im-agent-textarea"
          value={draft.custom_prompt ?? ""}
          placeholder={t("agents.form.behavior.customInstructionsPlaceholder")}
          aria-describedby="custom-instructions-help"
          rows={4}
          onChange={(e) => onCustomPromptChange(e.target.value)}
        />
        <p id="custom-instructions-help" className="im-agent-field-help">
          {t("agents.form.behavior.customInstructionsHelp")}
        </p>
      </div>

      {!capabilitiesKnown && capabilityFeatures.length === 0 && <div className="im-agent-field" data-testid="features-section">
        <span className="text-[13px] font-semibold text-slate-900">{t("agents.form.behavior.features")}</span>
        <p className="im-agent-field-help">{t("agents.settings.featureUnknown")}</p>
      </div>}
      {/* Features use confirmed defaults only; unknown values stay indeterminate. */}
      {capabilityFeatures.length > 0 && (
        <div data-testid="features-section" className="im-agent-field">
          <span className="text-[13px] font-semibold text-slate-900">{t("agents.form.behavior.features")}</span>
          <p className="im-agent-field-help" style={{ marginTop: 2 }}>{t("agents.form.behavior.featuresHelp")}</p>
          <div className="grid gap-[6px] mt-2">
            {capabilityFeatures.map((feat) => {
              // feat-379-M9 (決策 12): features are always enabled — disabled state removed.
              // tool_allowlist is the linkage authority; features follow tools, not vice versa.
              const checked = effectiveFeatures[feat.key] ?? feat.default_on;
              return (
                <label
                  key={feat.key}
                  className={`flex items-start gap-3 rounded-xl border px-3 py-[10px] transition-colors ${
                    checked
                      ? "border-teal-300 bg-teal-50/60 cursor-pointer"
                      : "border-[var(--im-border)] bg-white/90 cursor-pointer hover:border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    data-feature-key={feat.key}
                    disabled={readOnly}
                    ref={input => { if (input) input.indeterminate = unknownFeatures.includes(feat.key); }}
                    checked={checked}
                    className="im-feature-checkbox mt-[2px] shrink-0"
                    onChange={(e) => onFeatureToggle(feat.key, e.target.checked)}
                  />
                  <div className="min-w-0">
                    {/* label_i18n / help_i18n are i18n keys provided by the backend registry */}
                    <p className="m-0 text-[13px] font-semibold text-slate-900 leading-5">{t(feat.label_i18n, feat.key)}</p>
                    <p className="m-0 text-[11px] text-slate-500 leading-[1.4]">{unknownFeatures.includes(feat.key) ? t("agents.settings.featureUnknown") : t(feat.help_i18n, "")}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* Group reply policy — scene-mandatory, not a toggle */}
      <div className="im-agent-field">
        <Label.Root htmlFor="group-reply-policy">{t("agents.form.behavior.policy")}</Label.Root>
        <select
          disabled={readOnly}
          id="group-reply-policy"
          className="im-input"
          aria-describedby="group-policy-help"
          value={draft.group_reply_policy}
          onChange={(e) => onPolicyChange(e.target.value)}
        >
          <option value="MENTION">{t("agents.form.behavior.policyOptionMention")}</option>
          <option value="ALWAYS">{t("agents.form.behavior.policyOptionAlways")}</option>
          <option value="NO_REPLY">{t("agents.form.behavior.policyOptionNoReply")}</option>
        </select>
        <p id="group-policy-help" className="im-agent-field-help">
          {t("agents.form.behavior.policyHelp")}
        </p>
      </div>

      {/* Collapsible preview — mirrors tool-calls-panel aria-expanded + ▸/▾ pattern */}
      <div>
        <button
          type="button"
          className={`im-behavior-preview-toggle ${previewOpen ? "im-behavior-preview-toggle--open" : ""}`}
          disabled={readOnly && previewText === null}
          onClick={handlePreviewToggle}
          aria-expanded={previewOpen}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "none",
            border: "none",
            padding: "6px 0",
            cursor: "pointer",
            fontSize: "0.8rem",
            fontWeight: 600,
            color: "var(--im-accent, oklch(0.55 0.18 180))"
          }}
        >
          <span aria-hidden="true">{previewOpen ? "▾" : "▸"}</span>
          <span>{t("agents.form.behavior.previewToggle")}</span>
        </button>

        {previewOpen && (
          <div className="im-behavior-preview-panel im-behavior-preview-panel--open" style={{ marginTop: 8 }}>
            {previewLoading && (
              <p className="text-[11px] text-slate-500">{t("agents.form.behavior.previewLoading")}</p>
            )}
            {!previewLoading && <SettingsReadNotice read={{source: previewText === null ? "unavailable" : previewStale ? "last_known" : "current", captured_at: previewCapturedAt, data: previewText, error: previewError ? {code: "read_failed", message: previewError} : null}} />}
            {!previewLoading && previewText !== null && (
              <>
                <pre
                  style={{
                    fontSize: "0.72rem",
                    lineHeight: 1.5,
                    color: "var(--im-muted, oklch(0.50 0.01 240))",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    background: "oklch(0.96 0.004 240)",
                    border: "1px solid var(--im-border)",
                    borderRadius: 8,
                    padding: "10px 12px",
                    maxHeight: 360,
                    overflowY: "auto",
                    margin: 0
                  }}
                >
                  {previewText}
                </pre>
                <p
                  style={{
                    fontSize: "0.70rem",
                    color: "var(--im-muted, oklch(0.55 0.01 240))",
                    marginTop: 4,
                    marginBottom: 0
                  }}
                >
                  {t("agents.form.behavior.previewHelp")}
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// feat-394 decision 5: HeartbeatCard — per-agent heartbeat enable/disable + cadence + activeHours.
// Shows a toggle for heartbeat_enabled, an optional "every" interval input and optional
// active-hours start/end time inputs when enabled.
// feat-394-M7 R5-3 fix: added activeHours start/end UI (spec S2.5 requirement).
// feat-394-M11 decision E: cadence input binds to backend config value (no hardcoded 30m fallback).
// feat-394-M13: adds collapsible HEARTBEAT.md read-only preview panel via RPC (Decision G).
// feat-394 followup: cadence is edited as a number stepper + unit dropdown rather than
// a free-text duration box.  This guarantees the stored value is always in the backend's
// strict `<int><unit>` shape (scheduler parser is `\d+[smhd]`), so an invalid duration that
// only blows up at tick time can never be produced from the UI.
const HEARTBEAT_UNITS = ["m", "h", "d"] as const;
type HeartbeatUnit = "s" | "m" | "h" | "d";

function parseCadence(every: string): { amount: string; unit: HeartbeatUnit } {
  const match = /^\s*(\d+)\s*([smhd])\s*$/i.exec(every);
  if (!match) return { amount: "", unit: "m" };
  return { amount: match[1], unit: match[2].toLowerCase() as HeartbeatUnit };
}

interface HeartbeatCardProps {
  readOnly: boolean;
  agentId: string;
  draft: AgentConfigFormState;
  onToggle: (enabled: boolean) => void;
  onEveryChange: (every: string) => void;
  onActiveHoursChange: (start: string, end: string) => void;
  // feat-394 M9 R6: when heartbeat enable is managed by the Features checkbox list
  // (heartbeat is in capabilityFeatures), hide the redundant inline enable toggle.
  hideEnableToggle?: boolean;
}

function HeartbeatCard({ readOnly, agentId, draft, onToggle, onEveryChange, onActiveHoursChange, hideEnableToggle = false }: HeartbeatCardProps) {
  const { t } = useTranslation();
  // feat-394-M11 decision E: no hardcoded fallback — cadence binds directly to backend value.
  // When heartbeat is not configured, every is undefined → input shows empty (placeholder "30m").
  const heartbeat = draft.heartbeat;
  // feat-394 M9-E: enable is the single-true-source in features["heartbeat"], not heartbeat.enabled.
  const enabled = draft.features?.heartbeat ?? false;
  const every = heartbeat?.every ?? "";
  const { amount: cadenceAmount, unit: cadenceUnit } = parseCadence(every);
  // Show m/h/d; keep a legacy "s" value as an extra option so opening the form never
  // silently rewrites a seconds-based cadence into minutes.
  const cadenceUnitOptions: HeartbeatUnit[] = (HEARTBEAT_UNITS as readonly string[]).includes(cadenceUnit)
    ? [...HEARTBEAT_UNITS]
    : [cadenceUnit, ...HEARTBEAT_UNITS];
  const emitCadence = (amount: string, unit: HeartbeatUnit) => {
    const trimmed = amount.trim();
    // Empty amount → unconfigured (backend falls back to default 30m); never emit a unit-only string.
    onEveryChange(trimmed === "" ? "" : `${trimmed}${unit}`);
  };
  const activeStart = heartbeat?.active_hours?.start ?? "";
  const activeEnd = heartbeat?.active_hours?.end ?? "";

  // feat-394-M13: HEARTBEAT.md collapsible read-only preview — fetched via RPC, not direct file access.
  // Decision G: IM process must never directly read gateway-side workspace files.
  const [hbMdOpen, setHbMdOpen] = useState(false);
  const [hbMdContent, setHbMdContent] = useState<string | null>(null);
  const [hbMdLoading, setHbMdLoading] = useState(false);
  const [hbMdCapturedAt, setHbMdCapturedAt] = useState<string | null>(null);
  const [hbMdStale, setHbMdStale] = useState(false);
  const [hbMdError, setHbMdError] = useState<SettingsRead<string>["error"]>(null);
  const hbAbort = useRef<AbortController | null>(null);
  useEffect(() => { if (readOnly) { hbAbort.current?.abort(); setHbMdLoading(false); setHbMdStale(true); } return () => hbAbort.current?.abort(); }, [readOnly]);

  async function handleHbMdToggle() {
    if (!hbMdOpen) {
      setHbMdOpen(true);
      if (readOnly) return;
      hbAbort.current?.abort();
      const controller = new AbortController();
      hbAbort.current = controller;
      setHbMdLoading(true);
      setHbMdError(null);
      try {
        const resp = await getAgentHeartbeatMd(agentId, controller.signal);
        if (controller.signal.aborted) return;
        if (resp.node_online) { setHbMdContent(resp.content); setHbMdCapturedAt(new Date().toISOString()); setHbMdStale(false); }
        else { setHbMdStale(true); setHbMdError({code: "offline", message: "offline"}); }
      } catch (error) {
        if (!controller.signal.aborted) { setHbMdStale(true); setHbMdError({code: "read_failed", message: String(error)}); }
      } finally {
        setHbMdLoading(false);
      }
    } else {
      setHbMdOpen(false);
    }
  }

  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">{t("agents.form.heartbeat.title")}</h3>
        <p className="im-agent-card-sub">{t("agents.form.heartbeat.sub")}</p>
      </div>
      {/* feat-394 M9 R6: enable toggle shown only when not managed by Features list */}
      {!hideEnableToggle && (
        <div className="im-agent-field">
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              disabled={readOnly}
                data-testid="heartbeat-enabled-toggle"
              checked={enabled}
              className="im-feature-checkbox"
              onChange={(e) => onToggle(e.target.checked)}
            />
            <div>
              <p className="m-0 text-[13px] font-semibold text-slate-900 leading-5">
                {t("agents.form.heartbeat.enabledLabel")}
              </p>
              <p className="m-0 text-[11px] text-slate-500 leading-[1.4]">
                {t("agents.form.heartbeat.enabledHelp")}
              </p>
            </div>
          </label>
        </div>
      )}
      {/* When hideEnableToggle, the card is only rendered when enabled=true (controlled externally),
          so we always show cadence/activeHours config panels. */}
      {(enabled || hideEnableToggle) && (
        <>
          <div className="im-agent-field">
            <Label.Root htmlFor="heartbeat-every">{t("agents.form.heartbeat.everyLabel")}</Label.Root>
            <div className="flex gap-2 items-center">
              <input
                disabled={readOnly}
                id="heartbeat-every"
                className="im-input"
                type="number"
                min={1}
                step={1}
                value={cadenceAmount}
                placeholder="30"
                aria-describedby="heartbeat-every-help"
                onChange={(e) => emitCadence(e.target.value, cadenceUnit)}
                // feat-394-M3 minor Issue 4: select-all on focus so typing replaces the old value
                // rather than appending to it (standard UX for numeric input fields).
                onFocus={(e) => e.target.select()}
              />
              <select
                disabled={readOnly}
                id="heartbeat-every-unit"
                className="im-input"
                data-testid="heartbeat-every-unit"
                value={cadenceUnit}
                aria-label={t("agents.form.heartbeat.everyUnitLabel")}
                onChange={(e) => emitCadence(cadenceAmount, e.target.value as HeartbeatUnit)}
              >
                {cadenceUnitOptions.map((u) => (
                  <option key={u} value={u}>
                    {t(`agents.form.heartbeat.unit.${u}`)}
                  </option>
                ))}
              </select>
            </div>
            <p id="heartbeat-every-help" className="im-agent-field-help">
              {t("agents.form.heartbeat.everyHelp")}
            </p>
          </div>
          {/* feat-394-M7 R5-3 fix: activeHours UI — spec S2.5 "活跃时段外不打扰" */}
          <div className="im-agent-field">
            <Label.Root htmlFor="heartbeat-active-start">
              {t("agents.form.heartbeat.activeHoursLabel", "Active hours (optional)")}
            </Label.Root>
            <div className="flex gap-2 items-center">
              <input
                disabled={readOnly}
                id="heartbeat-active-start"
                className="im-input"
                data-testid="heartbeat-active-hours-start"
                type="time"
                value={activeStart}
                placeholder="09:00"
                aria-label="Active hours start"
                onChange={(e) => onActiveHoursChange(e.target.value, activeEnd)}
              />
              <span className="text-slate-500 text-sm">–</span>
              <input
                disabled={readOnly}
                id="heartbeat-active-end"
                className="im-input"
                data-testid="heartbeat-active-hours-end"
                type="time"
                value={activeEnd}
                placeholder="22:00"
                aria-label="Active hours end"
                onChange={(e) => onActiveHoursChange(activeStart, e.target.value)}
              />
            </div>
            <p className="im-agent-field-help">
              {t("agents.form.heartbeat.activeHoursHelp", "Uses your local time; leave blank for always-on")}
            </p>
          </div>

          {/* feat-394-M13: HEARTBEAT.md read-only preview — content fetched from gateway via RPC
              so IM never directly reads gateway-side workspace files (Decision G). */}
          <div>
            <button
              type="button"
              className={`im-behavior-preview-toggle ${hbMdOpen ? "im-behavior-preview-toggle--open" : ""}`}
              onClick={() => { void handleHbMdToggle(); }}
              aria-expanded={hbMdOpen}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: "none",
                border: "none",
                padding: "6px 0",
                cursor: "pointer",
                fontSize: "0.8rem",
                fontWeight: 600,
                color: "var(--im-accent, oklch(0.55 0.18 180))"
              }}
            >
              <span aria-hidden="true">{hbMdOpen ? "▾" : "▸"}</span>
              <span>{t("agents.form.heartbeat.heartbeatMdToggle", "View HEARTBEAT.md")}</span>
            </button>

            {hbMdOpen && (
              <div className="im-behavior-preview-panel im-behavior-preview-panel--open" style={{ marginTop: 8 }}>
                {hbMdLoading && (
                  <p className="text-[11px] text-slate-500">{t("agents.form.heartbeat.heartbeatMdLoading", "Loading...")}</p>
                )}
                {!hbMdLoading && <SettingsReadNotice read={{source: hbMdContent === null ? "unavailable" : hbMdStale ? "last_known" : "current", captured_at: hbMdCapturedAt, data: hbMdContent, error: hbMdError}} />}
                {!hbMdLoading && hbMdContent !== null && hbMdContent === "" && (
                  <p className="text-[11px] text-slate-400 italic">
                    {t("agents.form.heartbeat.heartbeatMdEmpty", "HEARTBEAT.md not found")}
                  </p>
                )}
                {!hbMdLoading && hbMdContent !== null && hbMdContent !== "" && (
                  <pre
                    style={{
                      fontSize: "0.72rem",
                      lineHeight: 1.5,
                      color: "var(--im-muted, oklch(0.50 0.01 240))",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      background: "oklch(0.96 0.004 240)",
                      border: "1px solid var(--im-border)",
                      borderRadius: 8,
                      padding: "10px 12px",
                      maxHeight: 360,
                      overflowY: "auto",
                      margin: 0
                    }}
                  >
                    {hbMdContent}
                  </pre>
                )}
              </div>
            )}
          </div>

        </>
      )}
    </section>
  );
}

// feat-394-M2 decision 5: CronCard — per-agent cron enable/disable.
// feat-394-M3 WARNING-3: also shows task list + delete (spec Scenario: 配置页查看并手动删除任务).
interface CronCardProps {
  readOnly: boolean;
  operationReadOnly: boolean;
  agentId: string;
  draft: AgentConfigFormState;
  onToggle: (enabled: boolean) => void;
  // feat-394 M9 R6: when cron enable is managed by the Features checkbox list, hide inline toggle.
  hideEnableToggle?: boolean;
}

function CronCard({ readOnly, operationReadOnly, agentId, draft, onToggle, hideEnableToggle = false }: CronCardProps) {
  const { t } = useTranslation();
  // feat-394 M9-E: enable is the single-true-source in features["cron_scheduling"]; no draft.cron object.
  const enabled = draft.features?.cron_scheduling ?? false;
  const queryClient = useQueryClient();

  // feat-394-M3: fetch cron jobs list for this agent
  // When hideEnableToggle the card only renders when cron is on, so enabled||hideEnableToggle.
  const jobsQuery = useQuery({
    queryKey: ["settings", "agents", agentId, "cron"],
    queryFn: ({signal}) => getAgentSettingsSection<CronJobSummary[]>(agentId, "cron", signal),
    enabled: enabled || hideEnableToggle,  // when controlled externally, always fetch
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => {
      if (operationReadOnly || jobsQuery.isFetching || jobsQuery.data?.source !== "current") throw new Error(t("agents.settings.refreshing"));
      return deleteAgentCronJob(agentId, jobId);
    },
    onError: () => { void jobsQuery.refetch(); },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings", "agents", agentId, "cron"] });
    },
  });

  const jobs = jobsQuery.data?.data ?? [];

  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">{t("agents.form.cron.title")}</h3>
        <p className="im-agent-card-sub">{t("agents.form.cron.sub")}</p>
      </div>
      {/* feat-394 M9 R6: enable toggle shown only when not managed by Features list */}
      {!hideEnableToggle && (
        <div className="im-agent-field">
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              disabled={readOnly}
              data-testid="cron-enabled-toggle"
              checked={enabled}
              className="im-feature-checkbox"
              onChange={(e) => onToggle(e.target.checked)}
            />
            <div>
              <p className="m-0 text-[13px] font-semibold text-slate-900 leading-5">
                {t("agents.form.cron.enabledLabel")}
              </p>
              <p className="m-0 text-[11px] text-slate-500 leading-[1.4]">
                {t("agents.form.cron.enabledHelp")}
              </p>
            </div>
          </label>
        </div>
      )}
      {/* feat-394-M3: cron jobs task list (spec Scenario: 配置页查看并手动删除任务) */}
      {(enabled || hideEnableToggle) && (
        <div className="im-agent-field" data-testid="cron-jobs-list">
          <SettingsReadNotice read={jobsQuery.data} />
          {(jobsQuery.isError || jobsQuery.data?.source !== "current" || deleteMutation.isError) && <button type="button" className="im-btn im-btn-muted" disabled={jobsQuery.isFetching} onClick={() => {deleteMutation.reset(); void jobsQuery.refetch();}}>{t("agents.settings.retry")}</button>}
          {deleteMutation.isError && <p role="alert" className="im-agent-field-error">{t("agents.settings.pending")}</p>}
          {jobsQuery.isError && (
            <p className="text-[12px] text-red-500">{t("agents.form.cron.loadError")}</p>
          )}
          {!jobsQuery.isError && jobsQuery.data?.data !== null && jobsQuery.data !== undefined && jobs.length === 0 && (
            <p className="text-[12px] text-slate-400 italic">{t("agents.form.cron.noJobs")}</p>
          )}
          {jobs.length > 0 && (
            <ul className="space-y-2" role="list" aria-label={t("agents.form.cron.jobsListLabel")}>
              {jobs.map((job: CronJobSummary) => (
                <li
                  key={job.id}
                  className="flex items-start justify-between gap-2 p-2 bg-slate-50 rounded border border-slate-200"
                  data-testid={`cron-job-${job.id}`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-slate-800 truncate">{job.name}</p>
                    <p className="text-[11px] text-slate-500 truncate">{job.instruction}</p>
                    <p className="text-[10px] text-slate-400 font-mono truncate">
                      {JSON.stringify(job.schedule)}
                    </p>
                  </div>
                  <button
                    type="button"
                    data-testid={`cron-job-delete-${job.id}`}
                    className="shrink-0 text-[12px] text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 transition-colors"
                    onClick={() => deleteMutation.mutate(job.id)}
                    disabled={operationReadOnly || jobsQuery.isFetching || jobsQuery.data?.source !== "current" || deleteMutation.isPending || deleteMutation.isError}
                    aria-label={`${t("agents.form.cron.deleteJob")} ${job.name}`}
                  >
                    {t("agents.form.cron.deleteJob")}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

type SkillsUsageView = "list" | "agent" | "health";
type AgentDetailSection = "work" | "overview" | "config" | "channels" | "skills" | "plugins" | "sessions";

const CONTRIBUTION_DAYS = 365;
const HEATMAP_DATA_DAYS = 30;
const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

interface ContributionCell {
  key: string;
  date: Date;
  inWindow: boolean;
  value: number;
}

interface FloatingTooltipState {
  left: number;
  top: number;
  text: string;
}

function normalizedUsageSeries(values: number[] | undefined): number[] {
  const series = [...(values ?? [])].slice(-HEATMAP_DATA_DAYS);
  while (series.length < HEATMAP_DATA_DAYS) series.unshift(0);
  return series;
}

function normalizedContributionSeries(values: number[] | undefined): number[] {
  const recent = normalizedUsageSeries(values);
  const series = recent.slice(-CONTRIBUTION_DAYS);
  while (series.length < CONTRIBUTION_DAYS) series.unshift(0);
  return series;
}

function formatSkillTimestamp(value?: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleDateString();
}

function formatTooltipDate(date: Date) {
  const day = date.getDate();
  const suffix = day % 10 === 1 && day !== 11
    ? "st"
    : day % 10 === 2 && day !== 12
      ? "nd"
      : day % 10 === 3 && day !== 13
        ? "rd"
        : "th";
  return `${date.toLocaleDateString("en-US", { month: "long" })} ${day}${suffix}`;
}

function FloatingTooltip({ tooltip }: { tooltip: FloatingTooltipState | null }) {
  if (!tooltip) return null;
  return (
    <div
      className="pointer-events-none fixed z-50 rounded-md bg-slate-900 px-3 py-2 text-[13px] font-semibold text-white shadow-lg"
      style={{
        left: tooltip.left,
        top: tooltip.top,
        transform: "translate(-50%, -100%)"
      }}
      role="tooltip"
    >
      {tooltip.text}
      <span
        className="absolute left-1/2 top-full h-2 w-2 -translate-x-1/2 -translate-y-1 rotate-45 bg-slate-900"
        aria-hidden="true"
      />
    </div>
  );
}

function heatLevel(value: number, max: number) {
  if (max <= 0 || value <= 0) return "#ebedf0";
  const ratio = Math.min(1, value / max);
  if (ratio > 0.75) return "#216e39";
  if (ratio > 0.5) return "#30a14e";
  if (ratio > 0.25) return "#40c463";
  return "#9be9a8";
}

function SkillTrend({ skill }: { skill: SkillUsageItem }) {
  const [hoveredBar, setHoveredBar] = useState<FloatingTooltipState | null>(null);
  const buckets = normalizedUsageSeries(skill.trend_buckets);
  const max = Math.max(1, ...buckets);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const trendStart = new Date(today);
  trendStart.setDate(today.getDate() - (buckets.length - 1));
  const showTrendTooltip = (
    event: MouseEvent<HTMLSpanElement> | FocusEvent<HTMLSpanElement>,
    value: number,
    index: number
  ) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const date = new Date(trendStart);
    date.setDate(trendStart.getDate() + index);
    setHoveredBar({
      left: rect.left + rect.width / 2,
      top: rect.top - 8,
      text: `${value.toLocaleString()} skill uses on ${formatTooltipDate(date)}.`
    });
  };
  return (
    <div
      className="relative flex h-8 items-end gap-[2px]"
      data-testid={`skill-trend-${skill.skill_id}`}
      aria-label={`${skill.name} 30-day trend`}
    >
      {buckets.map((value, index) => (
        <span
          key={`${skill.skill_id}-${index}`}
          tabIndex={0}
          className="block w-[4px] rounded-sm"
          style={{
            height: `${Math.max(3, Math.round((value / max) * 28))}px`,
            background: value > 0 ? "oklch(0.55 0.16 155)" : "oklch(0.88 0.006 240)"
          }}
          aria-label={`${formatTooltipDate(new Date(trendStart.getFullYear(), trendStart.getMonth(), trendStart.getDate() + index))}: ${value} skill uses`}
          onMouseEnter={(event) => showTrendTooltip(event, value, index)}
          onMouseLeave={() => setHoveredBar(null)}
          onFocus={(event) => showTrendTooltip(event, value, index)}
          onBlur={() => setHoveredBar(null)}
        />
      ))}
      <FloatingTooltip tooltip={hoveredBar} />
    </div>
  );
}

function skillSourceLabel(source: string): string {
  switch (source) {
    case "F1":
      return "手动创建";
    case "F2":
      return "历史蒸馏";
    case "F3":
      return "自动沉淀";
    case "F4":
      return "批量复盘";
    default:
      return source || "unknown";
  }
}

function skillBadgeClass(kind: "source" | "state", value: string): string {
  if (kind === "state") {
    if (value === "active") return "bg-emerald-50 text-emerald-700";
    if (value === "stale") return "bg-amber-50 text-amber-700";
    if (value === "archived") return "bg-slate-100 text-slate-600";
    return "bg-slate-100 text-slate-600";
  }
  if (value === "F1") return "bg-fuchsia-50 text-fuchsia-700";
  if (value === "F2") return "bg-indigo-50 text-indigo-700";
  if (value === "F3") return "bg-teal-50 text-teal-700";
  if (value === "F4") return "bg-yellow-50 text-yellow-700";
  return "bg-slate-100 text-slate-600";
}

function SkillBadge({ kind, value, children }: { kind: "source" | "state"; value: string; children: ReactNode }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-[2px] text-[0.65rem] font-semibold ${skillBadgeClass(kind, value)}`}>
      {children}
    </span>
  );
}

function SkillsListView({
  usage,
  showArchived,
  onToggleArchived
}: {
  usage: SkillsUsageResponse;
  showArchived: boolean;
  onToggleArchived: () => void;
}) {
  const visibleSkills = usage.skills.filter(
    (skill) => showArchived || skill.state !== "archived"
  );
  return (
    <section className="im-agent-card" data-testid="skills-usage-list">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="im-agent-card-title">全部 Skill</h3>
          <p className="im-agent-card-sub">按最近使用时间排序</p>
        </div>
        <button
          type="button"
          className="rounded-lg border border-[var(--im-border)] bg-transparent px-[10px] py-[5px] text-[0.72rem] font-semibold text-slate-500 hover:bg-[var(--im-surface-2)]"
          onClick={onToggleArchived}
        >
          {showArchived ? "隐藏 archived" : "显示 archived"}
        </button>
      </div>
      {visibleSkills.length === 0 ? (
        <p className="text-[13px] text-slate-500">当前过滤条件下没有 skill</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[0.78rem]">
            <thead>
              <tr className="border-b border-[var(--im-border)] text-left text-[0.68rem] font-semibold uppercase tracking-[0.04em] text-slate-500">
                <th className="px-2 py-[6px]">名字</th>
                <th className="px-2 py-[6px]">来源</th>
                <th className="px-2 py-[6px]">状态</th>
                <th className="px-2 py-[6px]">使用次数</th>
                <th className="px-2 py-[6px]">最近使用</th>
                <th className="px-2 py-[6px]">趋势</th>
              </tr>
            </thead>
            <tbody>
              {visibleSkills.map((skill) => (
                <tr key={skill.skill_id} className="border-b border-slate-100 last:border-0">
                  <td className="px-2 py-3 font-semibold text-slate-900">{skill.name}</td>
                  <td className="px-2 py-3">
                    <SkillBadge kind="source" value={skill.source}>{skillSourceLabel(skill.source)}</SkillBadge>
                  </td>
                  <td className="px-2 py-3">
                    <SkillBadge kind="state" value={skill.state}>{skill.state}</SkillBadge>
                  </td>
                  <td className="px-2 py-3 font-semibold text-slate-900">{skill.use_count}</td>
                  <td className="px-2 py-3 font-mono text-[12px] text-slate-500">{formatSkillTimestamp(skill.last_used_at)}</td>
                  <td className="px-2 py-3"><SkillTrend skill={skill} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AgentHeatmapCard({ usage }: { usage: SkillsUsageResponse }) {
  const [hoveredCell, setHoveredCell] = useState<FloatingTooltipState | null>(null);
  const series = normalizedContributionSeries(usage.heatmap_data);
  const max = Math.max(0, ...series);
  const total = normalizedUsageSeries(usage.heatmap_data).reduce((sum, value) => sum + value, 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today);
  start.setDate(today.getDate() - (CONTRIBUTION_DAYS - 1));
  const gridStart = new Date(start);
  gridStart.setDate(start.getDate() - start.getDay());
  const cells: ContributionCell[] = [];
  for (let cursor = new Date(gridStart), index = 0; cursor <= today; cursor.setDate(cursor.getDate() + 1), index += 1) {
    const inWindow = cursor >= start;
    const valueIndex = Math.floor((cursor.getTime() - start.getTime()) / 86_400_000);
    cells.push({
      key: `heat-${index}`,
      date: new Date(cursor),
      inWindow,
      value: inWindow ? series[valueIndex] ?? 0 : 0
    });
  }
  const weeks: ContributionCell[][] = [];
  for (let index = 0; index < cells.length; index += 7) {
    weeks.push(cells.slice(index, index + 7));
  }
  const monthLabels = weeks.map((week, index) => {
    const month = week.find((cell) => cell.inWindow)?.date.getMonth();
    const prevMonth = index > 0 ? weeks[index - 1]?.find((cell) => cell.inWindow)?.date.getMonth() : undefined;
    return month !== undefined && month !== prevMonth ? MONTH_LABELS[month] : "";
  });
  const formatCellDate = (date: Date) =>
    date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  const showCellTooltip = (
    event: MouseEvent<HTMLSpanElement> | FocusEvent<HTMLSpanElement>,
    cell: ContributionCell
  ) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setHoveredCell({
      left: rect.left + rect.width / 2,
      top: rect.top - 8,
      text: `${cell.value.toLocaleString()} skill uses on ${formatTooltipDate(cell.date)}.`
    });
  };
  return (
    <section className="im-agent-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="im-agent-card-title">使用热力图</h3>
          <p className="im-agent-card-sub">该 agent 的 skill 使用密度</p>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white px-5 py-4">
        <div className="min-w-max">
          <div
            className="ml-[34px] grid h-5 gap-[4px]"
            style={{ gridTemplateColumns: `repeat(${weeks.length}, 12px)` }}
            aria-hidden="true"
          >
            {monthLabels.map((label, index) => (
              <span key={`month-${index}`} className="text-[11px] leading-4 text-slate-600">
                {label}
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <div className="grid grid-rows-7 gap-[4px] pr-1 text-right text-[12px] leading-3 text-slate-600">
              {["", "Mon", "", "Wed", "", "Fri", ""].map((label, index) => (
                <span key={`weekday-${index}`} className="h-3">{label}</span>
              ))}
            </div>
            <div
              className="flex gap-[4px]"
              data-testid="skills-agent-heatmap"
              aria-label="Agent skill usage contribution calendar"
            >
              {weeks.map((week, weekIndex) => (
                <div key={`week-${weekIndex}`} className="grid grid-rows-7 gap-[4px]">
                  {week.map((cell) => (
                    cell.inWindow ? (
                      <span
                        key={cell.key}
                        tabIndex={0}
                        className="h-3 w-3 rounded-[3px] border border-slate-200"
                        style={{ backgroundColor: heatLevel(cell.value, max) }}
                        aria-label={`${formatCellDate(cell.date)}: ${cell.value} skill uses`}
                        onMouseEnter={(event) => showCellTooltip(event, cell)}
                        onMouseLeave={() => setHoveredCell(null)}
                        onFocus={(event) => showCellTooltip(event, cell)}
                        onBlur={() => setHoveredCell(null)}
                      />
                    ) : (
                      <span
                        key={cell.key}
                        className="invisible h-3 w-3 rounded-[3px] border border-slate-200"
                        aria-hidden="true"
                      />
                    )
                  ))}
                </div>
              ))}
            </div>
          </div>
          <div className="mt-4 flex items-center justify-end gap-2 text-[12px] text-slate-600">
            <span className="mr-auto text-[0.65rem] text-slate-500">{total.toLocaleString()} 次 · 最近 30 天 · 悬停查看</span>
            <span>Less</span>
            {[0, 1, 2, 3, 4].map((level) => (
              <span
                key={`legend-${level}`}
                className="h-3 w-3 rounded-[3px] border border-slate-200"
                style={{ backgroundColor: heatLevel(level, 4) }}
              />
            ))}
            <span>More</span>
          </div>
        </div>
      </div>
      <FloatingTooltip tooltip={hoveredCell} />
    </section>
  );
}

function AgentAutoSkillsCard({ usage }: { usage: SkillsUsageResponse }) {
  const automatedSkills = usage.skills.filter((skill) => ["F3", "F4"].includes(skill.source));
  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">自动创建的 Skill</h3>
        <p className="im-agent-card-sub">自动沉淀与批量复盘输出</p>
      </div>
      {automatedSkills.length === 0 ? (
        <p className="text-[0.8rem] text-slate-500">暂无自动创建的 skill</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[0.78rem]">
            <thead>
              <tr className="border-b border-[var(--im-border)] text-left text-[0.68rem] font-semibold uppercase tracking-[0.04em] text-slate-500">
                <th className="px-2 py-[6px]">名字</th>
                <th className="px-2 py-[6px]">来源</th>
                <th className="px-2 py-[6px]">使用次数</th>
                <th className="px-2 py-[6px]">状态</th>
              </tr>
            </thead>
            <tbody>
              {automatedSkills.map((skill) => (
                <tr key={skill.skill_id} className="border-b border-slate-100 last:border-0">
                  <td className="px-2 py-[7px] font-semibold text-slate-900">{skill.name}</td>
                  <td className="px-2 py-[7px]"><SkillBadge kind="source" value={skill.source}>{skillSourceLabel(skill.source)}</SkillBadge></td>
                  <td className="px-2 py-[7px]">{skill.use_count}</td>
                  <td className="px-2 py-[7px]"><SkillBadge kind="state" value={skill.state}>{skill.state}</SkillBadge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AgentDimensionView({ usage }: { usage: SkillsUsageResponse }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <AgentHeatmapCard usage={usage} />
      <AgentAutoSkillsCard usage={usage} />
    </div>
  );
}

function HealthFunnelView({ usage }: { usage: SkillsUsageResponse }) {
  const rows = [
    { label: "自动创建总数", value: usage.health.created_auto_total },
    { label: "still active", value: usage.health.active_auto_total },
    { label: "use_count > 0", value: usage.health.used_auto_total },
  ];
  const survivalRate = usage.health.created_auto_total > 0
    ? `${usage.health.used_auto_total} / ${usage.health.created_auto_total} = ${Math.round((usage.health.used_auto_total / usage.health.created_auto_total) * 100)}%`
    : "0 / 0 = 0%";
  const automatedSkills = usage.skills.filter((skill) => ["F3", "F4"].includes(skill.source));
  return (
    <div className="grid gap-3">
      <section className="im-agent-card">
        <div>
          <h3 className="im-agent-card-title">自进化存活率</h3>
          <p className="im-agent-card-sub">自动创建的 skill 有多少活了下来</p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-4 py-2">
          {rows.map((row, index) => (
            <Fragment key={row.label}>
              {index > 0 ? <span className="text-[18px] text-slate-300">→</span> : null}
              <div className="min-w-[96px] text-center">
                <p className="m-0 text-[26px] font-extrabold text-slate-900">{row.value}</p>
                <p className="m-0 mt-1 text-[11px] text-slate-500">{row.label}</p>
              </div>
            </Fragment>
          ))}
        </div>
        <p className="m-0 mt-1 text-center text-[12px] text-slate-500">存活率 <strong>{survivalRate}</strong></p>
      </section>
      <section className="im-agent-card">
        <div>
          <h3 className="im-agent-card-title">生命周期时间线</h3>
          <p className="im-agent-card-sub">每个自动 skill 的创建 → 首次使用 → 最后使用</p>
        </div>
        {automatedSkills.length === 0 ? (
          <p className="text-[13px] text-slate-500">暂无自动创建的 skill</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-[var(--im-border)] text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-2 py-2">名字</th>
                  <th className="px-2 py-2">来源</th>
                  <th className="px-2 py-2">创建时间</th>
                  <th className="px-2 py-2">首次使用</th>
                  <th className="px-2 py-2">最后使用</th>
                  <th className="px-2 py-2">状态</th>
                </tr>
              </thead>
              <tbody>
                {automatedSkills.map((skill) => {
                  const firstUsed = skill.session_refs?.[0]?.timestamp ?? skill.last_used_at ?? null;
                  return (
                    <tr key={skill.skill_id} className="border-b border-slate-100 last:border-0">
                      <td className="px-2 py-3 font-semibold text-slate-900">{skill.name}</td>
                      <td className="px-2 py-3"><SkillBadge kind="source" value={skill.source}>{skillSourceLabel(skill.source)}</SkillBadge></td>
                      <td className="px-2 py-3 font-mono text-[12px] text-slate-500">{formatSkillTimestamp(skill.created_at)}</td>
                      <td className="px-2 py-3 font-mono text-[12px] text-slate-500">{formatSkillTimestamp(firstUsed)}</td>
                      <td className="px-2 py-3 font-mono text-[12px] text-slate-500">{formatSkillTimestamp(skill.last_used_at)}</td>
                      <td className="px-2 py-3"><SkillBadge kind="state" value={skill.state}>{skill.state}</SkillBadge></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function PrototypePlaceholder({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="im-agent-card">
      <div>
        <h3 className="im-agent-card-title">{title}</h3>
        <p className="im-agent-card-sub">{children}</p>
      </div>
    </section>
  );
}

function AgentSkillsUsagePanel({ agentId }: { agentId: string }) {
  const {t} = useTranslation();
  const [view, setView] = useState<SkillsUsageView>("list");
  const [showArchived, setShowArchived] = useState(false);
  const usageQuery = useQuery({
    queryKey: ["settings", "agents", agentId, "skills-usage"],
    queryFn: ({signal}) => getAgentSettingsSection<SkillsUsageResponse>(agentId, "usage", signal),
    staleTime: 30_000,
  });

  if (usageQuery.isLoading) {
    return <p className="text-sm text-slate-500">Loading skill usage...</p>;
  }

  const read: SettingsRead<SkillsUsageResponse> | undefined = usageQuery.isError
    ? {source: usageQuery.data?.data ? "last_known" : "unavailable", data: usageQuery.data?.data ?? null, captured_at: usageQuery.data?.captured_at ?? null, error: {code: "read_failed", message: String(usageQuery.error)}}
    : usageQuery.data;
  const usage = read?.data;
  if (!usage) return <section className="im-agent-card"><SettingsReadNotice read={read} /><button type="button" className="im-btn im-btn-muted w-fit" disabled={usageQuery.isFetching} onClick={() => void usageQuery.refetch()}>{t("agents.retry")}</button></section>;
  if (!usage || usage.skills.length === 0) {
    return (
      <section className="im-agent-card">
        <div>
          <SettingsReadNotice read={read} />
          <h3 className="im-agent-card-title">No skill usage yet</h3>
          <p className="im-agent-card-sub">The gateway returned an empty `.usage.json` snapshot for this agent.</p>
          {read?.error && <button type="button" className="im-btn im-btn-muted w-fit" onClick={() => void usageQuery.refetch()}>{t("agents.retry")}</button>}
        </div>
      </section>
    );
  }

  return (
    <div className="grid gap-3" data-testid="agent-skills-usage-panel">
      <SettingsReadNotice read={read} />
      {read?.error && <button type="button" className="im-btn im-btn-muted w-fit" onClick={() => void usageQuery.refetch()}>{t("agents.retry")}</button>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="mb-3 flex flex-wrap gap-0" role="tablist" aria-label="Skill usage views">
          {(["list", "agent", "health"] as SkillsUsageView[]).map((item, index) => (
            <button
              key={item}
              type="button"
              className={`relative border px-[10px] py-[5px] text-[0.72rem] font-semibold transition-colors ${
                index === 0 ? "rounded-l-md" : "-ml-px"
              } ${
                index === 2 ? "rounded-r-md" : ""
              } ${
                view === item
                  ? "z-10 border-slate-900 bg-slate-900 text-white"
                  : "border-[var(--im-border)] bg-transparent text-slate-500 hover:bg-[var(--im-surface-2)]"
              }`}
              onClick={() => setView(item)}
              aria-pressed={view === item}
            >
              {item === "list" ? "Skill 列表" : item === "agent" ? "Agent 维度" : "自进化健康度"}
            </button>
          ))}
        </div>
        <span className="text-[12px] text-slate-500">{usage.skills.length} skills</span>
      </div>
      {view === "list" && (
        <SkillsListView
          usage={usage}
          showArchived={showArchived}
          onToggleArchived={() => setShowArchived((value) => !value)}
        />
      )}
      {view === "agent" && <AgentDimensionView usage={usage} />}
      {view === "health" && <HealthFunnelView usage={usage} />}
    </div>
  );
}

export function AgentDetailPage({ personal = false }: { personal?: boolean } = {}) {
  const { agentId = "" } = useParams();
  return <AgentDetailPageContent key={agentId} agentId={agentId} personal={personal} />;
}

function AgentDetailPageContent({ agentId, personal }: { agentId: string; personal: boolean }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const [draft, setDraft] = useState<AgentConfigFormState | null>(null);
  const [pendingAgent, setPendingAgent] = useState<string | null>(null);
  const baseConfig = useRef<AgentConfigFormState | null>(null);
  const [saved, setSaved] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [applyPending, setApplyPending] = useState(false);
  const [hasAttemptedSave, setHasAttemptedSave] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [searchParams, setSearchParams] = useSearchParams();
  const activeSection = (searchParams.get("view") ?? "config") as AgentDetailSection;
  const setActiveSection = (section: AgentDetailSection) => setSearchParams({ view: section }, { replace: true });
  const savedResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (savedResetTimer.current) clearTimeout(savedResetTimer.current);
    };
  }, []);

  const settings = useAgentSettingsState(agentId);
  const detailQuery = settings.query;
  const confirmationPending = applyPending || !!detailQuery.data?.pendingOperation;
  const readOnly = settings.readOnly || confirmationPending;

  useEffect(() => {
    const config = detailQuery.data?.config;
    if (!config) return;
    setDraft(current => {
      if (current && baseConfig.current && !sameEditableConfig(current, baseConfig.current) && !sameEditableConfig(current, config)) return current;
      baseConfig.current = config;
      return config;
    });
  }, [detailQuery.data?.config]);

  const capabilities = detailQuery.data?.capabilities;
  const owningNode = detailQuery.data?.owningNode ?? null;
  const modelOptions = capabilities?.model_options ?? [];
  const platformDefaultModel = capabilities?.platform_default_model ?? null;
  const normalizedDraft = useMemo(
    () => (draft ? normalizeAgentConfig(draft) : null),
    [draft, modelOptions],
  );
  const availableModels = useMemo(
    () => resolveModelOptions(capabilities?.model_options, draft?.default_model ?? null, draft?.model_fallbacks),
    [capabilities?.model_options, draft?.default_model, draft?.model_fallbacks]
  );
  const validationErrors = useMemo(() => (normalizedDraft ? validateDraft(normalizedDraft) : {}), [normalizedDraft]);
  const hasValidationErrors = Object.keys(validationErrors).length > 0;
  const hasStaleReasoning = detailQuery.data?.liveCapabilities === true && !readOnly && isStaleReasoningEffort(
    modelOptions,
    effectiveReasoningModel(draft?.default_model ?? null, platformDefaultModel),
    draft?.reasoning_effort ?? null,
  );
  const fixedTools = draft?.work_mode === "global" ? ["inbox", "conversations", "send_message", "subagent"] : [];
  const absent = (names: string[], options: {name: string}[]) => names.filter(name => !options.some(option => option.name === name));
  const missingModels = absent([draft?.default_model, ...(draft?.model_fallbacks ?? [])].filter((name): name is string => !!name), modelOptions);
  const missingTools = absent(draft?.tool_allowlist ?? [], [...(capabilities?.tools ?? []), ...fixedTools.map(name => ({name}))]);
  const missingSkills = absent(draft?.skills ?? [], capabilities?.skills ?? []);
  const missingAllowedSkills = (draft?.skills_selection_mode ?? ((draft?.skills.length ?? 0) > 0 ? "explicit_allowlist" : "default_discovery")) === "explicit_allowlist" ? missingSkills : [];
  const catalogCurrent = detailQuery.data?.liveCapabilities === true && !readOnly;
  const catalogInvalid = catalogCurrent && (missingModels.length > 0 || missingTools.length > 0 || missingAllowedSkills.length > 0);
  const isDirty = !!(draft && baseConfig.current && !sameEditableConfig(draft, baseConfig.current));
  const versionConflict = isDirty && baseConfig.current?.profile_version !== detailQuery.data?.config.profile_version;
  const queryErrorDetail =
    detailQuery.error instanceof Error
      ? detailQuery.error.message.split(" failed: ").at(-1) ?? detailQuery.error.message
      : "Unable to load this agent.";

  const mutation = useMutation({
    mutationFn: (next: AgentConfigFormState) => {
      if (readOnly || versionConflict) throw new Error(t("agents.settings.refreshing"));
      const {
        updated_at: _updatedAt,
        owner_id: _ownerId,
        agent_id: _agentId,
        workspace_root: _workspaceRoot,
        workspace_is_default: _workspaceIsDefault,
        node_id: _nodeId,
        node_name: _nodeName,
        node_status: _nodeStatus,
        ...payload
      } = next;
      return updateAgentConfig(agentId, payload);
    },
    onSuccess: async (updated) => {
      setApplyPending(false);
      setErrorMessage(null);
      setSaved(true);
      setHasAttemptedSave(false);
      if (updated && capabilities) {
        const nextConfig = {
          ...updated,
          node_id: updated.node_id ?? owningNode?.node_id ?? capabilities.node_id,
          node_name: owningNode?.node_name ?? updated.node_name ?? null,
          node_status: owningNode?.status ?? updated.node_status ?? capabilities.node_status ?? null
        };
        baseConfig.current = nextConfig;
        setDraft(nextConfig);
        queryClient.setQueryData(["settings", "agents", agentId, "detail-state"], {
          ...detailQuery.data, config: nextConfig, ready: false,
        });
        void detailQuery.refetch();
      }
      void queryClient.invalidateQueries({ queryKey: ["settings", "agents"], exact: true });
      void queryClient.invalidateQueries({ queryKey: ["chat"] });
      void queryClient.invalidateQueries({ queryKey: ["personal-agent"] });
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
      void queryClient.invalidateQueries({ queryKey: ["public-agents"] });
      if (savedResetTimer.current) clearTimeout(savedResetTimer.current);
      savedResetTimer.current = setTimeout(() => {
        setSaved(false);
        savedResetTimer.current = null;
      }, 1800);
    },
    onError: (error) => {
      setSaved(false);
      if (isConfigApplyPendingError(error)) {
        setApplyPending(true);
        setErrorMessage(null);
        return;
      }
      setApplyPending(!(error instanceof AgentConfigRequestError));
      void detailQuery.refetch();
      const detail = getAgentConfigRequestDetail(error);
      const status = getAgentConfigRequestStatus(error);
      setErrorMessage(
        status === 409 && !(error instanceof AgentConfigRequestError && error.code === "agent_node_offline")
          ? t("agents.form.access.reasoning.saveConflict", { detail: `${status}: ${detail}` })
          : detail,
      );
    }
  });

  useEffect(() => {
    if (!applyPending) return;
    const retryInterval = window.setInterval(() => {
      void detailQuery.refetch().then((result) => {
        if (result.isSuccess && !result.data.pendingOperation) {
          setApplyPending(false);
          return;
        }
        if (result.error && !isConfigApplyPendingError(result.error)) {
          setApplyPending(false);
          setErrorMessage(getAgentConfigRequestDetail(result.error));
        }
      });
    }, 1_000);
    return () => window.clearInterval(retryInterval);
  }, [applyPending, detailQuery.refetch]);

  const openDirectChatMutation = useMutation({
    mutationFn: async () => {
      return createConversation({
        title: draft?.display_name || agentId,
        type: "direct",
        participants: [{ type: "agent", id: agentId }]
      });
    },
    onSuccess: async ({ id: conversationId }) => {
      setErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      navigate(`/chat/${conversationId}`);
    },
    onError: (error) => {
      // R9-2: surface the failure prominently instead of swallowing it. Older
      // builds left the user staring at an unresponsive button after a 404 on
      // /im/v1/users; that "broken-feeling" silence is now an explicit banner.
      setErrorMessage(
        error instanceof Error ? error.message.split(" failed: ").at(-1) ?? error.message : "Open direct chat failed"
      );
    }
  });

  function markTouched(field: "display_name") {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function shouldShowError(field: "display_name") {
    return (hasAttemptedSave || touched[field]) && validationErrors[field];
  }

  function selectAgent(nextID: string) {
    if (nextID === agentId) return;
    if (isDirty) setPendingAgent(nextID);
    else navigate(`/settings/agents/${encodeURIComponent(nextID)}`);
  }

  function handleDiscard() {
    if (detailQuery.data?.config) {
      const config = !readOnly ? detailQuery.data.config : baseConfig.current;
      if (!config) return;
      baseConfig.current = config;
      setDraft(config);
      setErrorMessage(null);
      setHasAttemptedSave(false);
      setTouched({});
    }
  }

  function renderDetailState(content: ReactNode) {
    const statePanel = (
      <div
        data-testid="agent-detail-state-panel"
        className="flex min-h-0 flex-1 items-start justify-center overflow-y-auto bg-[oklch(0.93_0.007_240)] px-4 py-10 sm:px-8 sm:py-14"
      >
        {content}
      </div>
    );
    if (isMobile) return statePanel;
    return (
      <div className="flex h-full overflow-hidden">
        <AgentsRailDesktop activeId={agentId} onSelectAgent={selectAgent} />
        {statePanel}
      </div>
    );
  }

  function renderLoadingState() {
    return renderDetailState(
      <section
        data-testid="agent-detail-loading"
        role="status"
        aria-live="polite"
        className="flex w-full max-w-[420px] items-center gap-4 rounded-2xl border border-[var(--im-border)] bg-white/90 px-5 py-5 shadow-sm"
      >
        <span
          className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-[var(--im-accent)]"
          aria-hidden="true"
        />
        <p className="m-0 text-sm font-medium text-slate-600">{t("agents.detail.loading")}</p>
      </section>
    );
  }

  if (detailQuery.isLoading && !draft) {
    return renderLoadingState();
  }

  if (detailQuery.isError && !draft) {
    return renderDetailState(
      <section
        data-testid="agent-detail-error"
        className="grid w-full max-w-[520px] gap-4 rounded-2xl border border-rose-200 bg-white/90 p-5 shadow-sm"
      >
        <div className="space-y-1">
          <p className="text-sm font-semibold text-rose-700">{t("agents.loadError")}</p>
          <p className="break-words text-sm text-slate-600">{queryErrorDetail}</p>
        </div>
        <button className="im-btn im-btn-muted w-fit" type="button" onClick={() => void detailQuery.refetch()}>
          {t("agents.retry")}
        </button>
      </section>
    );
  }

  if (!draft || !normalizedDraft || !capabilities) {
    return renderLoadingState();
  }

  const displayedNodeName =
    draft.node_name ?? capabilities.node_name ?? owningNode?.node_name ?? draft.node_id ?? capabilities.node_id ?? "—";
  const displayedNodeId = draft.node_id ?? capabilities.node_id ?? "—";
  const displayedNodeStatusRaw = settings.nodeState;
  const displayedNodeStatus = displayedNodeStatusRaw.toLowerCase();

  let footerStatusClass = "im-agent-footer-status";
  let footerStatusText = t("agents.detail.noChanges");
  if (versionConflict) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = t("agents.settings.conflict");
  } else if (errorMessage) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = errorMessage;
  } else if (hasAttemptedSave && (hasValidationErrors || hasStaleReasoning)) {
    footerStatusClass = "im-agent-footer-status error";
    footerStatusText = hasStaleReasoning
      ? t("agents.form.access.reasoning.staleError")
      : t("agents.form.errors.required");
  } else if (confirmationPending) {
    footerStatusText = t("agents.form.access.reasoning.applyPending");
  } else if (mutation.isPending) {
    footerStatusClass = "im-agent-footer-status";
    footerStatusText = t("agents.detail.saving");
  } else if (saved) {
    footerStatusClass = "im-agent-footer-status saved";
    footerStatusText = t("agents.detail.saved");
  } else if (isDirty) {
    footerStatusClass = "im-agent-footer-status dirty";
    footerStatusText = t("agents.detail.unsavedChanges");
  }
  const headerSaveText = mutation.isPending || confirmationPending
    ? t("agents.detail.saving")
    : saved
      ? t("agents.detail.saved")
      : isDirty
        ? t("agents.detail.save")
        : t("agents.detail.noChanges");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setHasAttemptedSave(true);
    setErrorMessage(null);
    if (readOnly || versionConflict || catalogInvalid || hasValidationErrors || hasStaleReasoning || applyPending || !isDirty || !normalizedDraft) return;
    mutation.mutate(normalizedDraft);
  }

  const detailPanel = (
    <form
      data-testid="agent-detail"
      className="im-agent-panel"
      onSubmit={handleSubmit}
    >
      <header className="im-agent-panel-header">
        <div className="im-agent-panel-header-row">
          {isMobile && (
            <button
              type="button"
              onClick={() => navigate("/settings/agents")}
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                border: "none",
                background: "oklch(0.91 0.006 240)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
                color: "oklch(0.40 0.01 240)",
                flexShrink: 0
              }}
            >
              ‹
            </button>
          )}
          <Avatar
            initials={initialsOf(draft.display_name)}
            color={colorForAgent(draft)}
            size={isMobile ? 38 : 42}
            status={displayedNodeStatus === "online" ? "online" : "offline"}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="im-agent-panel-title">{draft.display_name || draft.agent_id}</h2>
            <p className="im-agent-panel-subtitle im-agent-panel-node-line">
              <span className="im-agent-panel-agent-id">{draft.agent_id}</span>
              <span
                className={`im-agent-panel-node ${displayedNodeStatus === "online" ? "online" : ""}`}
              >
                <span className="dot" /> {displayedNodeName}
              </span>
            </p>
          </div>
          {!isMobile && (
            <div className="im-agent-header-actions">
              <button
                type="button"
                className="rounded-lg border border-[var(--im-accent)] bg-[var(--im-accent)] px-3 py-[5px] text-[0.75rem] font-semibold text-[var(--im-accent-fg)] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={openDirectChatMutation.isPending}
                onClick={() => openDirectChatMutation.mutate()}
              >
                {openDirectChatMutation.isPending ? t("agents.detail.openChatPending") : t("agents.detail.openChat")}
              </button>
              {activeSection === "config" && <button
                className="rounded-lg border border-[var(--im-border)] bg-[var(--im-surface)] px-3 py-[5px] text-[0.75rem] font-semibold text-[var(--im-text)] hover:bg-[var(--im-surface-2)] disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={readOnly || versionConflict || catalogInvalid || mutation.isPending || applyPending || hasStaleReasoning || !isDirty}
              >
                {headerSaveText}
              </button>}
            </div>
          )}
        </div>
        {errorMessage ? (
          <p
            data-testid={openDirectChatMutation.isError ? "open-chat-error" : "agent-save-error"}
            role="alert"
            className="im-agent-footer-status error"
            aria-live="polite"
          >
            {errorMessage}
          </p>
        ) : null}
        <nav
          className="-mx-5 mt-3 flex flex-wrap gap-0 border-t border-[var(--im-border)] px-5"
          aria-label={t("agents.detail.sections.navLabel")}
        >
          {([
            ...(draft.work_mode === "global" ? [["work", t("agents.detail.sections.work")]] : []),
            ["overview", t("agents.detail.sections.overview")],
            ["config", t("agents.detail.sections.config")],
            ["channels", t("agents.detail.sections.channels")],
            ["skills", t("agents.detail.sections.skills")],
            ["plugins", t("agents.detail.sections.plugins")],
            ["sessions", t("agents.detail.sections.sessions")],
          ] as Array<[AgentDetailSection, string]>).map(([section, label]) => (
            <button
              key={section}
              type="button"
              className={`border-0 border-b-2 bg-transparent px-4 py-3 text-[13px] font-semibold ${
                activeSection === section
                  ? "border-[var(--im-accent)] text-[var(--im-accent)]"
                  : "border-transparent text-slate-500 hover:text-slate-900"
              }`}
              aria-pressed={activeSection === section}
              onClick={() => setActiveSection(section)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      {settings.reason && <div className="px-5 py-3 border-b border-[var(--im-border)]" role="status" data-testid="settings-availability">
        <p className="text-sm text-slate-600">{t(`agents.settings.${settings.reason}`)}</p>
        <SettingsReadNotice read={detailQuery.data?.display} />
        {confirmationPending && settings.reason !== "pending" && <p className="im-agent-field-help">{t("agents.settings.pending")}</p>}
        <button type="button" className="im-btn im-btn-muted mt-2" disabled={detailQuery.isFetching} onClick={() => void queryClient.invalidateQueries({queryKey: ["settings", "agents", agentId]})}>{t("agents.settings.retry")}</button>
      </div>}
      <div className={`im-agent-panel-body im-agent-detail-body ${activeSection === "work" ? "im-agent-work-body" : ""}`}>
        {activeSection === "work" && draft.work_mode === "global" ? (
          <AgentWorkPanel agentId={agentId} />
        ) : activeSection === "skills" ? (
          <AgentSkillsUsagePanel agentId={agentId} />
        ) : activeSection === "plugins" ? (
          <AgentPluginsPanel agentId={agentId} readOnly={settings.connectionReadOnly} />
        ) : activeSection === "overview" ? (
          <PrototypePlaceholder title={t("agents.detail.sections.overview")}>
            {t("agents.detail.sections.overviewPlaceholder")}
          </PrototypePlaceholder>
        ) : activeSection === "channels" ? (
          <AgentChannelsPanel agentId={agentId} nodeStatus={displayedNodeStatusRaw} readOnly={settings.connectionReadOnly} />
        ) : activeSection === "sessions" ? (
          <PrototypePlaceholder title={t("agents.detail.sections.sessions")}>
            {t("agents.detail.sections.sessionsPlaceholder")}
          </PrototypePlaceholder>
        ) : (
          <>
        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.identity.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.identity.subEdit")}</p>
            <p className="text-xs text-slate-500">{tr("工作模式")}：{personal ? t("pa.label") : draft.work_mode === "global" ? tr("全局模式 · 实验") : tr("单 Thread")} · {tr("创建后固定")}</p>
          </div>
          {/* M19/R11-4: Identity row1 = Agent ID + Display Name (Owner UUID 对用户无意义, 移除). */}
          <div className="im-agent-card-grid-2" data-testid="agent-identity-row1">
            <div className="im-agent-field">
              <Label.Root htmlFor="agent-id">{t("agents.form.identity.agentId")}</Label.Root>
              <input id="agent-id" className="im-input im-agent-input-mono" value={draft.agent_id} disabled />
            </div>
            <div className="im-agent-field">
              <Label.Root htmlFor="display-name">{t("agents.form.identity.displayName")}</Label.Root>
              <input
                disabled={readOnly}
                id="display-name"
                className="im-input"
                value={draft.display_name}
                aria-invalid={Boolean(shouldShowError("display_name"))}
                aria-describedby="display-name-help"
                onBlur={() => markTouched("display_name")}
                onChange={(event) => {
                  setSaved(false);
                  setErrorMessage(null);
                  setDraft({ ...draft, display_name: event.target.value });
                }}
              />
              <p id="display-name-help" className="im-agent-field-help">
                {t("agents.form.identity.displayNameHelper")}
              </p>
              {shouldShowError("display_name") ? (
                <p className="im-agent-field-error">{validationErrors.display_name}</p>
              ) : null}
            </div>
          </div>
          <div className="im-agent-field">
            <Label.Root htmlFor="description">{t("agents.form.identity.description")}</Label.Root>
            <input
              disabled={readOnly}
              id="description"
              className="im-input"
              value={draft.description ?? ""}
              aria-describedby="description-help"
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, description: event.target.value });
              }}
            />
            <p id="description-help" className="im-agent-field-help">
              {t("agents.form.identity.descriptionHelp")}
            </p>
          </div>
        </section>

        {personal && <PersonalAgentSettings agentId={agentId} readOnly={settings.connectionReadOnly} />}

        {/* feat-379-M3: Behavior card replaced with BehaviorCard component */}
        <BehaviorCard
          agentId={agentId}
          draft={draft}
          capabilityFeatures={capabilities.features ?? []}
          capabilitiesKnown={detailQuery.data?.liveCapabilities === true}
          readOnly={readOnly}
          unknownFeatures={detailQuery.data?.display.data?.features.filter(feature => feature.enabled === null).map(feature => feature.key)}
          onApprovalModeChange={(value) => {
            setSaved(false);
            setErrorMessage(null);
            setDraft({ ...draft, approval_mode: value });
          }}
          onCustomPromptChange={(value) => {
            setSaved(false);
            setErrorMessage(null);
            setDraft({ ...draft, custom_prompt: value });
          }}
          onFeatureToggle={(key, value) => {
            setSaved(false);
            setErrorMessage(null);
            // feat-379-M9 (決策 12): tick → add requires_tool to allowlist; untick → keep tool.
            // bugfix-468-M1: empty allowlist means "no tools", so enabling a feature only appends
            // its required tool; we no longer materialize the whole default_on set.
            const capFeats = capabilities?.features ?? [];
            const requiresTool = capFeats.find((f) => f.key === key)?.requires_tool ?? null;
            const requiredTools = requiresTool ? [requiresTool] : [];
            const nextAllowlist = value ? [...new Set([...draft.tool_allowlist, ...requiredTools])] : draft.tool_allowlist;
            // feat-394 M9-E: features is the single-true-source for enable state.
            // HeartbeatCard reads features["heartbeat"]; CronCard reads features["cron_scheduling"].
            // No parallel sync into draft.heartbeat.enabled or draft.cron needed.
            const nextDraft = { ...draft, features: { ...(draft.features ?? {}), [key]: value }, tool_allowlist: nextAllowlist };
            setDraft(nextDraft);
          }}
          onPolicyChange={(value) => {
            setSaved(false);
            setErrorMessage(null);
            setDraft({ ...draft, group_reply_policy: value as AgentConfig["group_reply_policy"] });
          }}
        />

        {/* feat-394 M9 R6: HeartbeatCard — show cadence/activeHours config panel.
            When heartbeat is in capabilityFeatures (M9+), enable is controlled by
            the Features checkbox list above; the card renders only when enabled. */}
        {(() => {
          const hbInFeatures = capabilities?.features?.some((f: { key: string }) => f.key === "heartbeat") ?? false;
          // When heartbeat is a registered feature, show card only when the feature is on.
          // Otherwise (old Gateway), always show (backward compat).
          if (hbInFeatures && !draft.features?.heartbeat) return null;
          return (
            <HeartbeatCard
              agentId={agentId}
              readOnly={readOnly}
              draft={draft}
              onToggle={(enabled) => {
                // feat-394 M9-E: enable is in features["heartbeat"]; toggle via features only.
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, features: { ...(draft.features ?? {}), heartbeat: enabled } });
              }}
              onEveryChange={(every) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, heartbeat: { ...(draft.heartbeat ?? {}), every } });
              }}
              onActiveHoursChange={(start, end) => {
                setSaved(false);
                setErrorMessage(null);
                // feat-394-M11: no hardcoded "30m" fallback when spreading prev heartbeat.
                const prevHb = draft.heartbeat ?? {};
                const active_hours = start || end
                  ? { ...(prevHb.active_hours ?? {}), start, end }
                  : undefined;
                setDraft({ ...draft, heartbeat: { ...prevHb, active_hours } });
              }}
              hideEnableToggle={hbInFeatures}
            />
          );
        })()}

        {/* feat-394-M2 decision 5: CronCard — per-agent cron enable/disable.
            feat-394 M9 R6: when cron_scheduling is in capabilityFeatures, the enable
            toggle moves to the Features list; card renders only when cron feature is on. */}
        {(() => {
          const cronInFeatures = capabilities?.features?.some((f: { key: string }) => f.key === "cron_scheduling") ?? false;
          if (cronInFeatures && !draft.features?.cron_scheduling) return null;
          return (
            <CronCard
              operationReadOnly={settings.connectionReadOnly}
              agentId={agentId}
              readOnly={readOnly}
              draft={draft}
              onToggle={(enabled) => {
                // feat-394 M9-E: enable is in features["cron_scheduling"]; no draft.cron object.
                setSaved(false);
                setErrorMessage(null);
                setDraft({ ...draft, features: { ...(draft.features ?? {}), cron_scheduling: enabled } });
              }}
              hideEnableToggle={cronInFeatures}
            />
          );
        })()}

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.access.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.access.sub")}</p>
            <button
              type="button"
              className="im-agent-access-skills-link"
              onClick={() => setActiveSection("skills")}
            >
              View skill statistics
            </button>
          </div>
          <div className="grid gap-4">
            <SkillSourceSelector
              testId="pill-selector-skills"
              readOnly={readOnly}
              label={t("agents.form.access.skills")}
              selected={draft.skills}
              selectionMode={
                draft.skills_selection_mode ??
                (draft.skills.length > 0 ? "explicit_allowlist" : "default_discovery")
              }
              options={[...capabilities.skills, ...missingSkills.map(name => ({name, description: ""}))]}
              workspaceRoot={draft.workspace_root ?? ""}
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
              onChange={(skills, skillsSelectionMode) => {
                setSaved(false);
                setErrorMessage(null);
                setDraft({
                  ...draft,
                  skills,
                  skills_selection_mode: skillsSelectionMode,
                });
              }}
            />
            {catalogCurrent && missingAllowedSkills.length > 0 && <p className="im-agent-field-error">{t("agents.settings.catalogUnavailable", {names: missingAllowedSkills.join(", ")})}</p>}
            {!detailQuery.data?.liveCapabilities && (!detailQuery.data?.display.data || !detailQuery.data.display.data.derived_current) && <p className="im-agent-field-help">{t("agents.settings.skillsUnknown")}</p>}
            <div className="h-px bg-[var(--im-border)]" aria-hidden="true" />
            <PillSelector
              testId="pill-selector-tools"
              readOnly={readOnly}
              label={t("agents.form.access.tools")}
              labelAction={
                <button
                  type="button"
                  className="inline-flex min-h-8 items-center gap-1 rounded px-1 text-sm text-[var(--im-accent)] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--im-accent)]"
                  onClick={() => setActiveSection("plugins")}
                >
                  {t("agents.plugins.manage")}
                  <span aria-hidden="true">→</span>
                </button>
              }
              selected={draft.tool_allowlist}
              fixed={draft.work_mode === "global" ? ["inbox", "conversations", "send_message", "subagent"] : []}
              options={[...capabilities.tools, ...[...missingTools, ...fixedTools.filter(name => !capabilities.tools.some(tool => tool.name === name))].map(name => ({name}))]}
              isLoading={detailQuery.isLoading}
              errorMessage={detailQuery.isError ? queryErrorDetail : null}
              onRetry={() => void detailQuery.refetch()}
              onChange={(toolAllowlist) => {
                setSaved(false);
                setErrorMessage(null);
                // feat-379-M9 (決策 12): removed tool → uncheck any feature that requires it.
                const capFeats = capabilities?.features ?? [];
                const removed = draft.tool_allowlist.filter((t: string) => !toolAllowlist.includes(t));
                const nextFeatures = { ...(draft.features ?? {}) };
                for (const tool of removed) {
                  for (const feat of capFeats) {
                    if (feat.requires_tool === tool) nextFeatures[feat.key] = false;
                  }
                }
                setDraft({ ...draft, tool_allowlist: toolAllowlist, features: nextFeatures });
              }}
            />
          </div>
          {catalogCurrent && missingTools.length > 0 && <p className="im-agent-field-error">{t("agents.settings.catalogUnavailable", {names: missingTools.join(", ")})}</p>}
          <ModelFallbackField
            label={t("agents.form.access.model")}
            labelHtmlFor="default-model"
            models={availableModels}
            primary={effectiveReasoningModel(draft.default_model, platformDefaultModel)}
            value={draft.model_fallbacks ?? []}
            disabled={readOnly}
            onChange={(modelFallbacks) => {
              setSaved(false);
              setErrorMessage(null);
              setDraft({ ...draft, model_fallbacks: modelFallbacks });
            }}
          >
            <select
              id="default-model"
              className="im-input"
              value={draft.default_model ?? ""}
              aria-describedby="default-model-help"
              disabled={readOnly}
              onChange={(event) => {
                setSaved(false);
                setErrorMessage(null);
                const defaultModel = event.target.value || null;
                const effectiveModel = effectiveReasoningModel(defaultModel, platformDefaultModel);
                setDraft({
                  ...draft,
                  default_model: defaultModel,
                  model_fallbacks: fallbacksAfterPrimaryChange(draft.model_fallbacks ?? [], effectiveModel),
                  reasoning_effort: reasoningEffortAfterModelChange(
                    modelOptions,
                    effectiveModel,
                    draft.reasoning_effort,
                  ),
                });
              }}
            >
              <option value="">
                {platformDefaultModel
                  ? t("agents.form.access.modelPlatformDefault", { model: platformDefaultModel })
                  : t("agents.form.access.modelPlatformDefaultPlain")}
              </option>
              {availableModels.map((model) => {
                const providerName = model.provider_display_name || model.provider;
                const providerSuffix = providerName ? ` · ${providerName}` : "";
                const baseLabel = `${model.display_name || model.name}${providerSuffix}`;
                return (
                  <option key={model.name} value={model.name}>
                    {model.name === platformDefaultModel
                      ? `${baseLabel} ${t("agents.form.access.modelDefaultSuffix")}`
                      : baseLabel}
                  </option>
                );
              })}
            </select>
          </ModelFallbackField>
          {catalogCurrent && missingModels.length > 0 && <p className="im-agent-field-error">{t("agents.settings.catalogUnavailable", {names: missingModels.join(", ")})}</p>}
          <ModelReasoningField
            idPrefix="detail-agent"
            disabled={readOnly}
            capabilitiesKnown={detailQuery.data?.liveCapabilities === true && !readOnly}
            lastKnownValue={detailQuery.data?.display.data?.derived_current ? detailQuery.data.display.data.reasoning?.value : null}
            modelOptions={modelOptions}
            selectedModel={effectiveReasoningModel(draft.default_model, platformDefaultModel)}
            value={draft.reasoning_effort}
            applyPending={applyPending}
            onChange={(reasoningEffort) => {
              setSaved(false);
              setErrorMessage(null);
              setDraft({ ...draft, reasoning_effort: reasoningEffort });
            }}
          />
        </section>

        <section className="im-agent-card">
          <div>
            <h3 className="im-agent-card-title">{t("agents.form.workspace.title")}</h3>
            <p className="im-agent-card-sub">{t("agents.form.workspace.sub")}</p>
          </div>
          <div className="im-agent-card-grid-2">
            <div className="im-agent-field">
              <Label.Root htmlFor="workspace-root">{t("agents.form.workspace.workspaceRoot")}</Label.Root>
              <input
                id="workspace-root"
                className="im-input im-agent-input-mono"
                value={draft.workspace_root ?? ""}
                placeholder={t("agents.form.workspace.pending")}
                disabled
              />
            </div>
            <div className="im-agent-field">
              <Label.Root htmlFor="profile-version">{t("agents.form.workspace.profileVersion")}</Label.Root>
              <input
                id="profile-version"
                className="im-input"
                value={t("agents.detail.version", { version: draft.profile_version })}
                disabled
              />
            </div>
          </div>
          <div className="im-agent-card-grid-2">
            <div className="im-agent-field">
              <Label.Root htmlFor="owning-node">{t("agents.form.workspace.owningNode")}</Label.Root>
              <input id="owning-node" className="im-input" value={`${displayedNodeName} (${displayedNodeId})`} disabled />
            </div>
            <div className="im-agent-field">
              <Label.Root htmlFor="last-updated">{t("agents.form.workspace.lastUpdated")}</Label.Root>
              <input id="last-updated" className="im-input" value={formatUpdatedAt(draft.updated_at)} disabled />
            </div>
          </div>
        </section>
          </>
        )}
      </div>

      {activeSection === "config" ? (
        <footer
          className="im-agent-footer im-agent-detail-footer"
          aria-live="polite"
          style={{
            paddingBottom: isMobile ? "calc(14px + env(safe-area-inset-bottom, 0px))" : "14px"
          }}
        >
          <p className={footerStatusClass}>{footerStatusText}</p>
          <div className="im-agent-footer-actions">
            {isMobile && (
              <button
                type="button"
                className="im-btn im-btn-muted"
                disabled={openDirectChatMutation.isPending}
                onClick={() => openDirectChatMutation.mutate()}
              >
                {openDirectChatMutation.isPending ? t("agents.detail.openChatPending") : t("agents.detail.openChat")}
              </button>
            )}
            {isDirty && (
              <button
                className="im-btn im-btn-muted"
                type="button"
                disabled={mutation.isPending || applyPending}
                onClick={handleDiscard}
              >
                {t("agents.detail.discard")}
              </button>
            )}
            <button
              className="im-btn im-btn-primary"
              type="submit"
              disabled={readOnly || versionConflict || catalogInvalid || mutation.isPending || applyPending || hasStaleReasoning || !isDirty}
            >
              {mutation.isPending ? t("agents.detail.saving") : t("agents.detail.saveAgent")}
            </button>
          </div>
        </footer>
      ) : null}
      {pendingAgent && (
        <div className="chat-modal-backdrop" role="presentation">
          <section className="chat-modal" role="dialog" aria-modal="true" aria-labelledby="agent-detail-unsaved-title">
            <header className="chat-modal-header bg-white"><h2 id="agent-detail-unsaved-title">{t("agents.create.unsavedExitTitle")}</h2></header>
            <div className="chat-modal-body"><p className="m-0 text-sm text-slate-600">{t("agents.create.unsavedExitBody")}</p></div>
            <footer className="chat-modal-footer bg-white">
              <button className="chat-modal-btn-ghost" type="button" onClick={() => setPendingAgent(null)}>{t("agents.create.keepEditing")}</button>
              <button className="chat-modal-btn-primary" type="button" onClick={() => navigate(`/settings/agents/${encodeURIComponent(pendingAgent)}`)}>{t("agents.create.leaveWithoutSaving")}</button>
            </footer>
          </section>
        </div>
      )}
    </form>
  );

  if (isMobile) {
    return detailPanel;
  }

  return (
    <div className="flex h-full overflow-hidden">
      <AgentsRailDesktop activeId={agentId} onSelectAgent={selectAgent} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-[oklch(0.93_0.007_240)]">
        {detailPanel}
      </div>
    </div>
  );
}
